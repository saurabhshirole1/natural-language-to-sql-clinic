"""
main.py

FastAPI application for the NL2SQL clinic chatbot.
Users send a plain English question and get back SQL results + a summary.

Run with: uvicorn main:app --port 8000
"""

import re
import sqlite3
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator

from vanna.core.user import RequestContext
from vanna_setup import agent, agent_memory, DB_PATH


# --- SQL Validation ---

BLOCKED_KEYWORDS = [
    r"\bINSERT\b", r"\bUPDATE\b", r"\bDELETE\b", r"\bDROP\b",
    r"\bALTER\b", r"\bEXEC\b", r"\bxp_", r"\bsp_",
    r"\bGRANT\b", r"\bREVOKE\b", r"\bSHUTDOWN\b",
    r"\bsqlite_master\b", r"\bsqlite_sequence\b"
]


def validate_sql(sql: str) -> None:
    """Only SELECT queries allowed. Rejects dangerous keywords."""
    if not sql:
        raise ValueError("Empty SQL query")
    sql_upper = sql.upper().strip()
    if not sql_upper.startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed.")
    for pattern in BLOCKED_KEYWORDS:
        if re.search(pattern, sql, re.IGNORECASE):
            raise ValueError(f"Blocked keyword found in SQL: {pattern}")


# --- Request / Response models ---

class ChatRequest(BaseModel):
    question: str

    @validator("question")
    def question_must_be_valid(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Question cannot be empty")
        if len(v) > 500:
            raise ValueError("Question is too long. Max 500 characters.")
        return v


class ChatResponse(BaseModel):
    message: str
    sql_query: Optional[str] = None
    columns: Optional[list] = None
    rows: Optional[list] = None
    row_count: Optional[int] = None
    chart: Optional[dict] = None
    chart_type: Optional[str] = None
    error: Optional[str] = None


# --- Parse components returned by Vanna agent ---

def parse_agent_response(components: list) -> dict:
    """
    Vanna 2.0 returns UiComponent objects.
    We look for:
    - DataFrameComponent (has rows + columns + the SQL in metadata)
    - RichTextComponent (has the final answer text in 'content')
    - StatusCardComponent with title 'Executing run_sql' (has SQL in metadata)
    """
    result = {
        "message": "",
        "sql_query": None,
        "columns": None,
        "rows": None,
        "row_count": None,
    }

    for component in components:
        rc = getattr(component, "rich_component", None)
        if rc is None:
            continue

        rc_type = type(rc).__name__

        # DataFrameComponent — this has the actual query results
        if rc_type == "DataFrameComponent":
            if hasattr(rc, "columns") and rc.columns:
                result["columns"] = list(rc.columns)
            if hasattr(rc, "rows") and rc.rows:
                # rows is a list of dicts in Vanna 2.0
                if isinstance(rc.rows[0], dict):
                    result["rows"] = [list(r.values()) for r in rc.rows]
                else:
                    result["rows"] = [list(r) for r in rc.rows]
                result["row_count"] = len(result["rows"])

        # RichTextComponent — this has the final human-readable answer
        if rc_type == "RichTextComponent":
            if hasattr(rc, "content") and rc.content:
                result["message"] = rc.content

        # StatusCardComponent with run_sql — this has the SQL query
        if rc_type == "StatusCardComponent":
            title = getattr(rc, "title", "")
            if "run_sql" in title:
                metadata = getattr(rc, "metadata", {}) or {}
                sql = metadata.get("sql")
                if sql:
                    result["sql_query"] = sql

    # Fallback message if agent didn't return a RichTextComponent
    if not result["message"]:
        if result["row_count"] is not None:
            result["message"] = f"Found {result['row_count']} result(s) for your question."
        else:
            result["message"] = "Query completed."

    return result


# --- FastAPI setup ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting NL2SQL Clinic API...")
    yield
    print("Shutting down...")


app = FastAPI(
    title="NL2SQL Clinic Chatbot",
    description="Ask questions about clinic data in plain English",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Endpoints ---

@app.get("/health")
async def health_check():
    """Check if the API and database are working."""
    db_status = "connected"
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("SELECT 1")
        conn.close()
    except Exception as e:
        db_status = f"error: {str(e)}"

    memory_count = 0
    try:
        if hasattr(agent_memory, "memories"):
            memory_count = len(agent_memory.memories)
        elif hasattr(agent_memory, "_memories"):
            memory_count = len(agent_memory._memories)
    except Exception:
        pass

    return {
        "status": "ok",
        "database": db_status,
        "agent_memory_items": memory_count
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, raw_request: Request):
    """
    Takes a plain English question and returns SQL results.
    """
    question = request.question

    try:
        headers = dict(raw_request.headers)
        request_context = RequestContext(headers=headers)

        components = []
        async for component in agent.send_message(
            request_context=request_context,
            message=question
        ):
            components.append(component)

        if not components:
            return ChatResponse(
                message="The agent returned no response. Please try rephrasing.",
                error="empty_response"
            )

        parsed = parse_agent_response(components)

        # Validate SQL if we found one
        if parsed["sql_query"]:
            try:
                validate_sql(parsed["sql_query"])
            except ValueError as ve:
                return ChatResponse(
                    message="The generated query was blocked for safety reasons.",
                    sql_query=parsed["sql_query"],
                    error=str(ve)
                )

        if parsed["rows"] is not None and len(parsed["rows"]) == 0:
            parsed["message"] = "No data found for your question."

        return ChatResponse(
            message=parsed["message"],
            sql_query=parsed["sql_query"],
            columns=parsed["columns"],
            rows=parsed["rows"],
            row_count=parsed["row_count"]
        )

    except Exception as e:
        print(f"[ERROR] {e}")
        return ChatResponse(
            message="Something went wrong. Please try rephrasing your question.",
            error=str(e)
        )


@app.get("/")
async def root():
    return {"message": "NL2SQL Clinic API is running. Use POST /chat to ask questions."}