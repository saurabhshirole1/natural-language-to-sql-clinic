"""
main.py

FastAPI application for the NL2SQL Clinic chatbot.
Send a plain-English question -> get SQL results + summary back.

Run with:
    uvicorn main:app --reload --port 8000
"""

import os
import sqlite3
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, List, Any, Tuple

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from vanna_setup import get_agent, DATABASE_PATH, SQLValidator

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("nl2sql")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Question cannot be empty")
        if len(v) > 500:
            raise ValueError("Question is too long (max 500 characters)")
        return v


class TrainRequest(BaseModel):
    question: str
    sql: str

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Question cannot be empty")
        if len(v) > 500:
            raise ValueError("Question too long (max 500 characters)")
        return v

    @field_validator("sql")
    @classmethod
    def validate_sql(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("SQL cannot be empty")
        upper = v.upper().lstrip()
        if not (upper.startswith("SELECT") or upper.startswith("WITH")):
            raise ValueError("Only SELECT/WITH queries are allowed")
        if len(v) > 5000:
            raise ValueError("SQL too long (max 5000 characters)")
        return v


class ChatResponse(BaseModel):
    message:    str
    sql_query:  Optional[str]             = None
    columns:    Optional[List[str]]       = None
    rows:       Optional[List[List[Any]]] = None
    row_count:  Optional[int]             = None
    chart:      Optional[dict]            = None
    chart_type: Optional[str]             = None
    error:      Optional[str]             = None


class TrainResponse(BaseModel):
    message:      str
    memory_count: int


class SchemaResponse(BaseModel):
    tables:       dict
    total_tables: int


class HealthResponse(BaseModel):
    status:             str
    database:           str
    database_path:      str
    agent_memory_items: int
    timestamp:          str


class StatsResponse(BaseModel):
    patients:         int
    doctors:          int
    appointments:     int
    treatments:       int
    invoices:         int
    total_revenue:    float
    pending_invoices: int
    overdue_invoices: int


# ---------------------------------------------------------------------------
# Chart suggestion
# ---------------------------------------------------------------------------

def _safe_numeric(val: Any) -> bool:
    """Return True if val is a non-None number."""
    return val is not None and isinstance(val, (int, float))


def suggest_chart(
    question:  str,
    columns:   List[str],
    rows:      List[List[Any]],
    row_count: int,
) -> Tuple[Optional[str], Optional[dict]]:
    """
    Suggest a chart type and data structure based on the query results.
    Returns (chart_type, chart_data) or (None, None).
    """
    if not columns or not rows or row_count == 0:
        return None, None
    if row_count == 1 and len(columns) == 1:
        return None, None

    q_lower = question.lower()

    # Find a representative non-null row
    sample_row = rows[0]
    for candidate in rows:
        if any(v is not None for v in candidate):
            sample_row = candidate
            break

    # Classify columns as numeric or label
    numeric_indices: List[int] = []
    label_indices:   List[int] = []
    for i, val in enumerate(sample_row):
        if _safe_numeric(val):
            numeric_indices.append(i)
        else:
            label_indices.append(i)

    if not numeric_indices:
        return None, None

    label_col = label_indices[0] if label_indices else 0
    value_col = numeric_indices[0]

    def build_chart(
        chart_type: str,
        multi_dataset: bool = False,
    ) -> Tuple[str, dict]:
        labels = [
            str(row[label_col]) if row[label_col] is not None else "N/A"
            for row in rows
        ]
        if multi_dataset and len(numeric_indices) > 1:
            datasets = [
                {
                    "label": columns[idx],
                    "data":  [row[idx] if row[idx] is not None else 0
                              for row in rows],
                }
                for idx in numeric_indices
            ]
        else:
            datasets = [{
                "label": columns[value_col],
                "data":  [row[value_col] if row[value_col] is not None else 0
                          for row in rows],
            }]

        chart_data: dict = {"labels": labels, "datasets": datasets}
        if chart_type != "pie":
            chart_data["x_axis"] = columns[label_col]
            chart_data["y_axis"] = columns[value_col]

        return chart_type, chart_data

    # Rule 1: Trend / time-series → LINE
    trend_kw = [
        "trend", "monthly", "over time", "past", "timeline",
        "history", "by month", "per month", "registration",
    ]
    if any(kw in q_lower for kw in trend_kw) and row_count > 1:
        return build_chart("line")

    # Rule 2: Percentage / distribution → PIE
    pie_kw = ["percentage", "distribution", "breakdown",
              "proportion", "share", "ratio"]
    if any(kw in q_lower for kw in pie_kw) and 2 <= row_count <= 12:
        return build_chart("pie")

    # Rule 3: Ranking / comparison → BAR
    bar_kw = [
        "top", "most", "busiest", "compare", "comparison",
        "by doctor", "by doctors", "by department", "by city",
        "by specialization", "by specialist", "revenue by",
        "spending", "highest", "lowest", "ranking",
    ]
    if any(kw in q_lower for kw in bar_kw) and row_count > 1:
        return build_chart("bar")

    # Rule 4: Day of week → BAR
    if "day" in q_lower and "week" in q_lower and row_count > 1:
        return build_chart("bar")

    # Rule 5: Generic 2-column → BAR
    if len(columns) == 2 and len(numeric_indices) >= 1 and row_count > 1:
        return build_chart("bar")

    # Rule 6: Multiple numeric columns → multi-dataset BAR
    if len(numeric_indices) > 1 and row_count > 1:
        return build_chart("bar", multi_dataset=True)

    return None, None


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _get_table_names(conn: sqlite3.Connection) -> List[str]:
    """Return all user table names, excluding SQLite internal tables."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# App lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup checks and agent warm-up."""
    log.info("=" * 50)
    log.info("Starting NL2SQL Clinic API...")

    if not os.path.exists(DATABASE_PATH):
        log.warning(f"Database NOT found at: {DATABASE_PATH}")
        log.warning("Run: python setup_database.py")
    else:
        try:
            conn        = sqlite3.connect(DATABASE_PATH)
            table_names = _get_table_names(conn)
            counts      = {
                tbl: conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                for tbl in table_names
            }
            conn.close()

            log.info(f"Database  : {DATABASE_PATH}")
            log.info(f"Tables    : {', '.join(table_names)}")
            for tbl, cnt in counts.items():
                log.info(f"  {tbl:<15}: {cnt} rows")

        except Exception as exc:
            log.error(f"Database error: {exc}")

    agent = get_agent()
    log.info(f"Agent memory: {agent.get_memory_count()} Q&A pairs")
    log.info("API ready at http://127.0.0.1:8000")
    log.info("=" * 50)

    yield

    log.info("Shutting down NL2SQL API.")


# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="NL2SQL Clinic Chatbot",
    description=(
        "Ask plain-English questions about clinic data and get SQL results back. "
        "Supports patient, doctor, appointment, treatment, and invoice queries."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    """API landing page."""
    return {
        "message": "NL2SQL Clinic API is running",
        "version": "2.0.0",
        "endpoints": {
            "POST /chat":     "Ask a natural language question",
            "POST /train":    "Add a question-SQL training pair",
            "GET  /health":   "API and database status",
            "GET  /stats":    "Quick summary statistics",
            "GET  /schema":   "Database schema with column details",
            "GET  /examples": "Example questions by category",
        },
        "quick_start": {
            "method": "POST",
            "url":    "/chat",
            "body":   {"question": "How many patients do we have?"},
        },
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Verify the API, database, and agent are operational."""
    db_status = "disconnected"
    try:
        if os.path.exists(DATABASE_PATH):
            conn = sqlite3.connect(DATABASE_PATH)
            conn.execute("SELECT 1")
            conn.close()
            db_status = "connected"
        else:
            db_status = f"not found: {DATABASE_PATH}"
    except Exception as exc:
        db_status = f"error: {exc}"

    agent = get_agent()
    return HealthResponse(
        status             = "ok" if db_status == "connected" else "degraded",
        database           = db_status,
        database_path      = DATABASE_PATH,
        agent_memory_items = agent.get_memory_count(),
        timestamp          = datetime.now().isoformat(),
    )


@app.get("/stats", response_model=StatsResponse)
async def get_stats():
    """Return quick summary statistics from the database."""
    if not os.path.exists(DATABASE_PATH):
        raise HTTPException(status_code=503, detail="Database not found")

    try:
        conn = sqlite3.connect(DATABASE_PATH)

        def count(table: str, where: str = "") -> int:
            q = f"SELECT COUNT(*) FROM {table}"
            if where:
                q += f" WHERE {where}"
            return conn.execute(q).fetchone()[0]

        def scalar(query: str) -> float:
            result = conn.execute(query).fetchone()[0]
            return round(float(result), 2) if result is not None else 0.0

        stats = StatsResponse(
            patients         = count("patients"),
            doctors          = count("doctors"),
            appointments     = count("appointments"),
            treatments       = count("treatments"),
            invoices         = count("invoices"),
            total_revenue    = scalar("SELECT SUM(total_amount) FROM invoices"),
            pending_invoices = count("invoices", "status = 'Pending'"),
            overdue_invoices = count("invoices", "status = 'Overdue'"),
        )
        conn.close()
        return stats

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Stats error: {exc}")


@app.get("/schema", response_model=SchemaResponse)
async def get_schema():
    """Return the full database schema with column types and row counts."""
    if not os.path.exists(DATABASE_PATH):
        raise HTTPException(status_code=503, detail="Database not found")

    try:
        conn        = sqlite3.connect(DATABASE_PATH)
        table_names = _get_table_names(conn)
        tables      = {}

        for table_name in table_names:
            col_info = conn.execute(
                f"PRAGMA table_info({table_name})"
            ).fetchall()
            columns = [
                {
                    "name":        col[1],
                    "type":        col[2],
                    "nullable":    not bool(col[3]),
                    "primary_key": bool(col[5]),
                }
                for col in col_info
            ]
            row_count = conn.execute(
                f"SELECT COUNT(*) FROM {table_name}"
            ).fetchone()[0]

            tables[table_name] = {
                "columns":   columns,
                "row_count": row_count,
            }

        conn.close()
        return SchemaResponse(tables=tables, total_tables=len(tables))

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Schema error: {exc}")


@app.get("/examples")
async def get_examples():
    """Return categorized example questions."""
    return {
        "examples": [
            {
                "category": "Patients",
                "questions": [
                    "How many patients do we have?",
                    "How many patients are there?",
                    "Which city has the most patients?",
                    "Show patients by city",
                    "Show patient registration trend by month",
                    "List all patients from New York",
                ],
            },
            {
                "category": "Doctors",
                "questions": [
                    "How many doctors are there?",
                    "List all doctors and their specializations",
                    "Which doctor has the most appointments?",
                    "How many doctors are in each specialization?",
                ],
            },
            {
                "category": "Appointments",
                "questions": [
                    "Show me appointments for last month",
                    "How many cancelled appointments last quarter?",
                    "What percentage of appointments are no-shows?",
                    "Show the busiest day of the week for appointments",
                    "Show monthly appointment count for the past 6 months",
                    "List patients who visited more than 3 times",
                ],
            },
            {
                "category": "Treatments",
                "questions": [
                    "Average treatment cost by specialization",
                    "Average appointment duration by doctor",
                    "What treatments are available?",
                    "Most expensive treatments",
                ],
            },
            {
                "category": "Financial",
                "questions": [
                    "What is the total revenue?",
                    "Show revenue by doctor",
                    "Top 5 patients by spending",
                    "Show unpaid invoices",
                    "List patients with overdue invoices",
                    "Revenue trend by month",
                    "Compare revenue between departments",
                    "Total outstanding amount",
                ],
            },
        ]
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Convert a natural-language question to SQL, execute it, return results.

    Request body:
        { "question": "Show me the top 5 patients by total spending" }
    """
    log.info(f"CHAT  Q: {request.question}")

    try:
        agent  = get_agent()
        result = agent.ask(request.question)

        # Sanitise error — don't leak internal details to client
        error_msg = result.get("error")
        if error_msg and error_msg not in (
            "out_of_scope", "irrelevant_sql", "no_sql_generated"
        ):
            log.error(f"Internal error: {error_msg}")
            error_msg = "An internal error occurred. Please try again."

        response = ChatResponse(
            message   = result["message"],
            sql_query = result.get("sql_query"),
            columns   = result.get("columns") or [],
            rows      = result.get("rows") or [],
            row_count = result.get("row_count", 0),
            error     = error_msg,
        )

        # Suggest chart only on successful queries with data
        if (
            not result.get("error")
            and result.get("columns")
            and result.get("rows")
        ):
            chart_type, chart_data = suggest_chart(
                question  = request.question,
                columns   = result["columns"],
                rows      = result["rows"],
                row_count = result.get("row_count", 0),
            )
            if chart_type:
                response.chart_type = chart_type
                response.chart      = chart_data

        log.info(
            f"CHAT  A: rows={result.get('row_count', 0)} "
            f"error={result.get('error', 'none')}"
        )
        return response

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    except Exception as exc:
        log.exception(f"Unhandled error in /chat: {exc}")
        return ChatResponse(
            message = "Something went wrong. Please try again.",
            error   = "server_error",
        )


@app.post("/train", response_model=TrainResponse)
async def train(request: TrainRequest):
    """
    Add a known-good question-SQL pair to the agent's memory.

    Request body:
        {
            "question": "How many patients are from Chicago?",
            "sql": "SELECT COUNT(*) AS count FROM patients WHERE city = 'Chicago'"
        }
    """
    log.info(f"TRAIN Q: {request.question[:60]}")

    try:
        # Validate SQL safety before adding to memory
        is_valid, err = SQLValidator.validate(request.sql)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"Invalid SQL: {err}")

        agent  = get_agent()
        before = agent.get_memory_count()
        agent.add_training_data(request.question, request.sql)
        after  = agent.get_memory_count()

        msg = (
            "Training pair added successfully"
            if after > before
            else "Training pair updated (question already existed)"
        )
        log.info(f"TRAIN result: {msg} — memory={after}")
        return TrainResponse(message=msg, memory_count=after)

    except HTTPException:
        raise
    except Exception as exc:
        log.exception(f"Training error: {exc}")
        raise HTTPException(status_code=500, detail=f"Training error: {exc}")


# ---------------------------------------------------------------------------
# Run directly: python main.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)