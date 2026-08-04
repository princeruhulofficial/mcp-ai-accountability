"""
mcp-ai-accountability
A production-ready MCP server that makes AI agents accountable.

Entrepreneurs can connect this to any MCP client and ask their agent:
"What is my reliability score and how can I improve it?"
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_PATH = Path(os.getenv("RELIABILITY_DB", "./reliability.db"))
mcp = FastMCP(
    name="mcp-ai-accountability",
    instructions=(
        "You are connected to the AI Accountability MCP. "
        "Use these tools to log interactions, measure reliability scores, "
        "analyze failures and get concrete recommendations so the agent "
        "(and its owner) can become more trustworthy."
    ),
)

# ---------------------------------------------------------------------------
# Simple local SQLite store (zero external cost)
# ---------------------------------------------------------------------------

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS interactions (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            agent_id TEXT,
            tool_name TEXT,
            success INTEGER,
            latency_ms REAL,
            error_message TEXT,
            metadata TEXT,
            created_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            agent_id TEXT,
            started_at TEXT,
            ended_at TEXT,
            total_calls INTEGER DEFAULT 0,
            successful_calls INTEGER DEFAULT 0
        )
        """
    )
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def start_session(agent_id: str) -> dict:
    """
    Start a new tracking session for an agent.
    Call this at the beginning of a multi-step agent run.
    Returns a session_id that you should pass to later tools.
    """
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO sessions (id, agent_id, started_at) VALUES (?, ?, ?)",
            (session_id, agent_id, now),
        )
        conn.commit()
    return {
        "session_id": session_id,
        "agent_id": agent_id,
        "started_at": now,
        "message": "Session started. Pass this session_id to record_interaction.",
    }


@mcp.tool()
def end_session(session_id: str) -> dict:
    """
    End a tracking session and get a quick summary.
    """
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not row:
            return {"error": "Session not found"}
        conn.execute(
            "UPDATE sessions SET ended_at = ? WHERE id = ?", (now, session_id)
        )
        stats = conn.execute(
            """
            SELECT COUNT(*) as total,
                   SUM(success) as successful
            FROM interactions WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
        conn.execute(
            "UPDATE sessions SET total_calls = ?, successful_calls = ? WHERE id = ?",
            (stats["total"] or 0, stats["successful"] or 0, session_id),
        )
        conn.commit()
        total = stats["total"] or 0
        successful = stats["successful"] or 0
        score = round((successful / total) * 100, 1) if total else 0.0
    return {
        "session_id": session_id,
        "ended_at": now,
        "total_calls": total,
        "successful_calls": successful,
        "reliability_score": score,
        "message": f"Session closed. Reliability score: {score}/100",
    }


@mcp.tool()
def record_interaction(
    agent_id: str,
    tool_name: str,
    success: bool,
    latency_ms: float = 0.0,
    error_message: Optional[str] = None,
    session_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> dict:
    """
    Log one tool-call result.
    Call this after every important tool use so reliability can be measured.
    """
    interaction_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO interactions
            (id, session_id, agent_id, tool_name, success, latency_ms, error_message, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                interaction_id,
                session_id,
                agent_id,
                tool_name,
                1 if success else 0,
                latency_ms,
                error_message,
                json.dumps(metadata or {}),
                now,
            ),
        )
        conn.commit()
    return {
        "interaction_id": interaction_id,
        "recorded": True,
        "success": success,
        "message": "Interaction recorded successfully.",
    }


@mcp.tool()
def get_reliability_score(
    agent_id: str,
    hours: int = 24,
) -> dict:
    """
    Get the current reliability score (0-100) for an agent.
    Score = percentage of successful tool calls in the last N hours.
    """
    cutoff = datetime.now(timezone.utc).timestamp() - (hours * 3600)
    cutoff_iso = datetime.fromtimestamp(cutoff, tz=timezone.utc).isoformat()
    with get_db() as conn:
        stats = conn.execute(
            """
            SELECT COUNT(*) as total,
                   SUM(success) as successful,
                   AVG(latency_ms) as avg_latency
            FROM interactions
            WHERE agent_id = ? AND created_at >= ?
            """,
            (agent_id, cutoff_iso),
        ).fetchone()
    total = stats["total"] or 0
    successful = stats["successful"] or 0
    score = round((successful / total) * 100, 1) if total else None
    return {
        "agent_id": agent_id,
        "window_hours": hours,
        "total_interactions": total,
        "successful": successful,
        "failed": total - successful if total else 0,
        "reliability_score": score,
        "avg_latency_ms": round(stats["avg_latency"] or 0, 1),
        "message": (
            f"Score: {score}/100 over last {hours}h"
            if score is not None
            else "No data yet. Start recording interactions."
        ),
    }


@mcp.tool()
def analyze_failures(
    agent_id: str,
    hours: int = 72,
    limit: int = 20,
) -> dict:
    """
    Find the most common failure patterns for an agent.
    Returns the tools that fail most often and sample error messages.
    """
    cutoff = datetime.now(timezone.utc).timestamp() - (hours * 3600)
    cutoff_iso = datetime.fromtimestamp(cutoff, tz=timezone.utc).isoformat()
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT tool_name,
                   COUNT(*) as fail_count,
                   GROUP_CONCAT(error_message, ' | ') as sample_errors
            FROM interactions
            WHERE agent_id = ? AND success = 0 AND created_at >= ?
            GROUP BY tool_name
            ORDER BY fail_count DESC
            LIMIT ?
            """,
            (agent_id, cutoff_iso, limit),
        ).fetchall()
    failures = [
        {
            "tool_name": r["tool_name"],
            "fail_count": r["fail_count"],
            "sample_errors": (r["sample_errors"] or "")[:300],
        }
        for r in rows
    ]
    return {
        "agent_id": agent_id,
        "window_hours": hours,
        "top_failing_tools": failures,
        "message": f"Found {len(failures)} tools with failures." if failures else "No failures recorded. Great job!",
    }


@mcp.tool()
def recommend_improvements(agent_id: str, hours: int = 72) -> dict:
    """
    Give concrete, actionable recommendations to improve reliability.
    Based on real failure data.
    """
    score_data = get_reliability_score(agent_id, hours)
    fail_data = analyze_failures(agent_id, hours)

    recommendations = []
    score = score_data.get("reliability_score")

    if score is None:
        recommendations.append(
            "Start calling record_interaction after every important tool use so we have data."
        )
    elif score < 70:
        recommendations.append(
            "Reliability is below 70. Review the top failing tools and add retries or fallbacks."
        )
    elif score < 90:
        recommendations.append(
            "Good baseline. Focus on the tools that still fail occasionally."
        )
    else:
        recommendations.append(
            "Excellent reliability! Keep monitoring for schema drift and latency spikes."
        )

    for f in fail_data.get("top_failing_tools", [])[:3]:
        recommendations.append(
            f"Tool '{f['tool_name']}' failed {f['fail_count']} times. "
            f"Check error patterns and consider adding validation or a backup tool."
        )

    if score_data.get("avg_latency_ms", 0) > 3000:
        recommendations.append(
            "Average latency is high (>3s). Consider caching or switching to faster endpoints."
        )

    return {
        "agent_id": agent_id,
        "current_score": score,
        "recommendations": recommendations,
        "message": "Here are the top actions you can take right now.",
    }


@mcp.tool()
def generate_audit_report(agent_id: str, hours: int = 168) -> dict:
    """
    Generate a full audit-style report useful for investors, compliance or internal reviews.
    """
    score = get_reliability_score(agent_id, hours)
    failures = analyze_failures(agent_id, hours)
    recs = recommend_improvements(agent_id, hours)

    report = {
        "report_id": str(uuid.uuid4()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "agent_id": agent_id,
        "period_hours": hours,
        "summary": score,
        "failure_analysis": failures,
        "recommendations": recs["recommendations"],
        "status": (
            "HEALTHY" if (score.get("reliability_score") or 0) >= 90
            else "NEEDS_ATTENTION" if (score.get("reliability_score") or 0) >= 70
            else "CRITICAL"
        ),
    }
    return report


@mcp.tool()
def check_mcp_health(server_url: str = "http://localhost:8000") -> dict:
    """
    Simple health check against another MCP server (HTTP transport).
    Useful for multi-agent systems that depend on other MCP servers.
    """
    import urllib.request

    payload = json.dumps(
        {"jsonrpc": "2.0", "id": "health", "method": "ping"}
    ).encode()
    req = urllib.request.Request(
        server_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode()
            latency = round((time.time() - start) * 1000, 1)
            return {
                "url": server_url,
                "healthy": True,
                "latency_ms": latency,
                "response_preview": body[:200],
                "message": "Server responded successfully.",
            }
    except Exception as e:
        return {
            "url": server_url,
            "healthy": False,
            "error": str(e),
            "message": "Server did not respond correctly.",
        }


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
