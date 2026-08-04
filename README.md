# mcp-ai-accountability

**Make your AI agents trustworthy and accountable.**

This is a production-ready Model Context Protocol (MCP) server that helps AI agents (and the entrepreneurs who build them) measure, track, score, and improve reliability.

## Why this exists

AI agents fail silently every day.  
Tool calls time out. Schemas drift. Hallucinations happen.  
Entrepreneurs lose money and trust because they cannot see *why* their agent is unreliable.

This MCP server turns reliability into a first-class tool that any agent can call.

## What it does (simple language)

Imagine your AI agent is a delivery boy.  
Sometimes he delivers the package late or to the wrong house.  
This server is like a scorecard + GPS tracker + coach that:

- Records every delivery (tool call)
- Gives a reliability score (0-100)
- Tells you *why* things went wrong
- Suggests how to make the agent better next time

Perfect for founders who want accountable AI products.

## Main Tools

| Tool | What it does |
|------|--------------|
| `record_interaction` | Log a tool call result (success/fail + details) |
| `get_reliability_score` | Get current score for an agent or session |
| `analyze_failures` | Find patterns in failures |
| `recommend_improvements` | Get concrete suggestions to improve reliability |
| `generate_audit_report` | Full report for compliance / investors |
| `check_mcp_health` | Ping another MCP server and check if it is healthy |
| `start_session` / `end_session` | Track full agent runs |

## Quick Start

```bash
# Install
pip install mcp-ai-accountability

# Or run from source
uv sync
uv run python -m src.server
```

Add to your Claude / Cursor / any MCP client:

```json
{
  "mcpServers": {
    "ai-accountability": {
      "command": "uv",
      "args": ["run", "python", "-m", "src.server"],
      "env": {
        "RELIABILITY_DB": "./reliability.db"
      }
    }
  }
}
```

## For Entrepreneurs (non-developers)

You do **not** need to write code.  
Just connect this MCP to your existing AI agent (Claude Desktop, Cursor, etc.).  
Then ask your agent:

> "Check my reliability score for the last 24 hours and tell me the top 3 problems."

The agent will use the tools automatically and give you a clear report.

## Pricing Suggestion

- Free tier: 1,000 interactions / month
- Pro: $29/month – unlimited + audit reports + Slack alerts
- Enterprise: custom (SSO + private hosting)

## License

MIT

Built daily by the Prevalid team for the AI agent ecosystem.
