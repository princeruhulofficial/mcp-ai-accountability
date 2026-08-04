"""
Basic smoke tests for mcp-ai-accountability.
Run with: pytest tests/
"""

import os
import tempfile
from pathlib import Path

# Point the server at a temporary DB for tests
tmpdir = tempfile.mkdtemp()
os.environ["RELIABILITY_DB"] = str(Path(tmpdir) / "test.db")

from src.server import (
    start_session,
    record_interaction,
    get_reliability_score,
    analyze_failures,
    recommend_improvements,
    end_session,
)


def test_full_flow():
    # Start
    session = start_session(agent_id="test-agent")
    assert "session_id" in session
    sid = session["session_id"]

    # Record success
    r1 = record_interaction(
        agent_id="test-agent",
        tool_name="search",
        success=True,
        latency_ms=120,
        session_id=sid,
    )
    assert r1["recorded"] is True

    # Record failure
    r2 = record_interaction(
        agent_id="test-agent",
        tool_name="search",
        success=False,
        latency_ms=50,
        error_message="timeout",
        session_id=sid,
    )
    assert r2["recorded"] is True

    # Score
    score = get_reliability_score(agent_id="test-agent", hours=1)
    assert score["total_interactions"] == 2
    assert score["reliability_score"] == 50.0

    # Failures
    fails = analyze_failures(agent_id="test-agent", hours=1)
    assert len(fails["top_failing_tools"]) >= 1

    # Recommendations
    recs = recommend_improvements(agent_id="test-agent", hours=1)
    assert len(recs["recommendations"]) > 0

    # End
    end = end_session(session_id=sid)
    assert end["reliability_score"] == 50.0


if __name__ == "__main__":
    test_full_flow()
    print("All basic tests passed.")
