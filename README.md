# NL2SQL Clinic Chatbot

A Natural Language to SQL system built with **Vanna AI 2.0** and **FastAPI**.
Ask questions in plain English and get results from a clinic database — no SQL needed.

## LLM Provider

<!-- This project uses **Google Gemini** (`gemini-2.5-flash`) via `GeminiLlmService`. -->  
This Project uses **Grok API**(`llama-3.3-70b-versatile`)
<!--Get a free API key at: https://aistudio.google.com/apikey-->

---

## Project Structure

```
project/
├── setup_database.py   # Creates clinic.db with schema + dummy data
├── vanna_setup.py      # Vanna 2.0 Agent initialization
├── seed_memory.py      # Seeds agent memory with 15 known Q&A pairs
├── main.py             # FastAPI application
├── requirements.txt    # All dependencies
├── README.md           # This file
├── RESULTS.md          # Test results for 20 questions
└── clinic.db           # Generated SQLite database
```

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd nl2sql-clinic
```

### 2. Create a virtual environment (optional but recommended)

```bash
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up your API key

Create a `.env` file in the project root:

```
GROQ_API_KEY=your-grok-api-key-here
```

You can get a free key at https://console.groq.com/keys.

### 5. Create the database

```bash
python setup_database.py
```

This creates `clinic.db` and prints a summary:
```
Created 200 patients, 15 doctors, 500 appointments...
```

### 6. Seed agent memory

```bash
python seed_memory.py
```

This pre-loads 15 known correct Q&A pairs so the agent has a head start.

### 7. Start the API server

```bash
uvicorn main:app --port 8000
```

Or to run everything in one shot (as required):

```bash
pip install -r requirements.txt && python setup_database.py && python seed_memory.py && uvicorn main:app --port 8000
```

---

## API Documentation

### POST /chat

Ask a question in plain English.

**Request:**
```json
{
  "question": "Show me the top 5 patients by total spending"
}
```

**Response:**
```json
{
  "message": "Here are the top 5 patients by total spending.",
  "sql_query": "SELECT p.first_name, p.last_name, SUM(i.total_amount) AS total_spending FROM patients p JOIN invoices i ON i.patient_id = p.id GROUP BY p.id ORDER BY total_spending DESC LIMIT 5",
  "columns": ["first_name", "last_name", "total_spending"],
  "rows": [["Priya", "Sharma", 7240.5], ["Rahul", "Verma", 6890.0]],
  "row_count": 5,
  "chart": null,
  "chart_type": null,
  "error": null
}
```

**Example using curl:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "How many patients do we have?"}'
```

---

### GET /health

Check if the API and database are working.

**Response:**
```json
{
  "status": "ok",
  "database": "connected",
  "agent_memory_items": 15
}
```

---

### GET /

Basic check that the server is running.

**Response:**
```json
{
  "message": "NL2SQL Clinic API is running. Use POST /chat to ask questions."
}
```

---

## Architecture Overview

```
User Question (plain English)
        |
        v
FastAPI /chat endpoint (main.py)
        |
        v
Input Validation (length, not empty)
        |
        v
Vanna 2.0 Agent (vanna_setup.py)
  - Grok API(`llama-3.3-70b-versatile`)
  - RunSqlTool → SqliteRunner → clinic.db
        |
        v
SQL Validation (SELECT only, no dangerous keywords)
        |
        v
Parse response → JSON returned to user
```

---

## Database Schema

The clinic database has 5 tables:
- **patients** — 200 patients across 10 cities
- **doctors** — 15 doctors across 5 specializations
- **appointments** — 500 appointments over the past 12 months
- **treatments** — 350 treatments linked to completed appointments
- **invoices** — 300 invoices with mixed payment statuses

---

## What I Would Improve With More Time

- Switch from `DemoAgentMemory` (in-memory) to `ChromaAgentMemory` (persistent) so memory survives restarts
- Add proper JWT authentication in `DefaultUserResolver` instead of a single shared user
- Add rate limiting to the `/chat` endpoint to prevent abuse
- Add a caching layer so repeated questions don't hit the LLM again
- Better chart generation — currently Plotly charts are returned when the agent decides to use `VisualizeDataTool`, but I'd add logic to always generate a chart when the result has numeric data
- Add structured logging so it's easier to debug issues in production
