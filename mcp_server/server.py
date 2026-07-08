"""
MCP server exposing the fine-tuned infra-ops text-to-SQL model as tools
any MCP-compatible client (Claude Desktop, etc.) can call.
"""
import os
import sys
import sqlite3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from common import SYSTEM_PROMPT, MODEL_NAME, ADAPTER_PATH, DB_PATH

from mlx_lm import load, generate
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("infra-ops-text-to-sql")

print("Loading fine-tuned QLoRA model (happens once at startup)...", file=sys.stderr)
_model, _tokenizer = load(MODEL_NAME, adapter_path=ADAPTER_PATH)
print("Model loaded. MCP server ready.", file=sys.stderr)


def _extract_sql(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.lower().startswith("sql"):
            text = text[3:]
    if ";" in text:
        text = text.split(";")[0] + ";"
    return text.strip()


def _run_sql(sql):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(sql)
    columns = [d[0] for d in cur.description] if cur.description else []
    rows = cur.fetchall()
    conn.close()
    return columns, rows


@mcp.tool()
def text_to_sql(question: str) -> dict:
    """Convert a natural-language question about the engineering-operations
    database (teams, services, servers, incidents, deployments, alerts,
    on-call shifts, config changes) into a SQL query, execute it, and
    return both the generated SQL and the actual query results."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    prompt = _tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    raw_output = generate(_model, _tokenizer, prompt=prompt, max_tokens=150, verbose=False)
    sql = _extract_sql(raw_output)
    try:
        columns, rows = _run_sql(sql)
        return {"question": question, "sql": sql, "columns": columns, "rows": rows, "error": None}
    except Exception as e:
        return {"question": question, "sql": sql, "columns": [], "rows": [], "error": str(e)}


@mcp.tool()
def get_schema() -> str:
    """Return the engineering-operations database schema so the agent knows
    what tables and columns exist."""
    return SYSTEM_PROMPT


if __name__ == "__main__":
    mcp.run()
