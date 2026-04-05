"""
vanna_setup.py

Vanna 2.0 Agent — NL2SQL for Clinic Management System
Uses Groq API (not Google Gemini).
"""

import os
import re
import math
import sqlite3
from collections import Counter
from typing import Optional, Dict, Any, List, Tuple

from dotenv import load_dotenv

load_dotenv()

DATABASE_PATH = os.getenv("DB_PATH", "clinic.db")

# ---------------------------------------------------------------------------
# Database schema
# ---------------------------------------------------------------------------
SCHEMA_CONTEXT = """
Tables in the clinic SQLite database:

patients(id, first_name, last_name, email, phone, date_of_birth, gender, city, registered_date)
  gender: 'M' or 'F'

doctors(id, name, specialization, department, phone)
  specialization examples: Dermatology, Cardiology, Orthopedics, General, Pediatrics

appointments(id, patient_id, doctor_id, appointment_date, status, notes)
  patient_id -> patients.id
  doctor_id  -> doctors.id
  status: 'Scheduled' | 'Completed' | 'Cancelled' | 'No-Show'

treatments(id, appointment_id, treatment_name, cost, duration_minutes)
  appointment_id -> appointments.id

invoices(id, patient_id, invoice_date, total_amount, paid_amount, status)
  patient_id -> patients.id
  status: 'Paid' | 'Pending' | 'Overdue'

Key relationships:
  - patients.id = appointments.patient_id
  - doctors.id = appointments.doctor_id
  - appointments.id = treatments.appointment_id
  - patients.id = invoices.patient_id
  - To link doctors to invoices: doctors -> appointments -> patients -> invoices
  - To link doctors to treatments: doctors -> appointments -> treatments

Fields NOT in the database (answer "not available" for these):
  - patient blood type, weight, height, BMI
  - patient insurance, insurance number
  - patient diagnosis, medical history, prescription
  - doctor salary, doctor rating, doctor experience
  - appointment room number, hospital bed
  - cause of death, mortality, deceased status
"""

# ---------------------------------------------------------------------------
# Out-of-scope detection
# ---------------------------------------------------------------------------

OUT_OF_SCOPE_PATTERNS = [
    r"\b(dead|died|death|deceased|mortality|killed|fatality|fatalities)\b",
    r"\b(weather|temperature|forecast|climate)\b",
    r"\b(stock|bitcoin|crypto|cryptocurrency|forex|share price)\b",
    r"\b(news|politics|election|government|president|minister)\b",
    r"\b(sports|cricket|football|soccer|tennis|ipl|match|score)\b",
    r"\b(movie|film|actor|actress|celebrity|entertainment)\b",
    r"\b(salary|payroll|tax|hr department|human resource)\b",
    r"\b(inventory|warehouse|supply chain|logistics|shipping)\b",
    r"\b(password|login|hack|breach|vulnerability|exploit)\b",
    r"\b(covid|pandemic|epidemic|outbreak|virus|infection)\b",
]

NOT_IN_DATABASE_PATTERNS = [
    (r"\b(blood type|blood group)\b",
     "Blood type/group is not stored in this clinic database."),
    (r"\b(weight|height|bmi|body mass)\b",
     "Patient weight/height/BMI is not stored in this clinic database."),
    (r"\b(insurance|insurance number|policy)\b",
     "Insurance information is not stored in this clinic database."),
    (r"\b(diagnosis|diagnos[ie]s|medical history|prescription|medicine|drug|medication)\b",
     "Diagnosis and prescription data is not stored in this clinic database."),
    (r"\b(salary|earning|wage)\b",
     "Doctor/staff salary data is not stored in this clinic database."),
    (r"\b(rating|review|feedback|score)\b",
     "Doctor ratings/reviews are not stored in this clinic database."),
    (r"\b(room|bed|ward|floor|building)\b",
     "Room/ward/bed information is not stored in this clinic database."),
    (r"\b(dead|died|death|deceased|mortality|killed)\b",
     "Mortality/death records are not stored in this clinic database. "
     "The database only tracks active patient appointments and invoices."),
    (r"\b(alive|survival|survive)\b",
     "Survival/mortality data is not tracked in this clinic database."),
    (r"\b(age of death|cause of death)\b",
     "Cause of death is not tracked in this clinic database."),
]

IN_SCOPE_KEYWORDS = [
    "patient", "patients", "doctor", "doctors", "appointment", "appointments",
    "treatment", "treatments", "invoice", "invoices",
    "revenue", "cost", "spending", "amount", "paid", "unpaid", "payment",
    "billing", "bill", "fees", "fee", "overdue", "pending",
    "specialization", "specialisation", "department", "specialist",
    "dermatology", "cardiology", "orthopedics", "pediatrics", "general",
    "city", "gender", "male", "female", "registered", "registration",
    "phone", "email", "name", "date of birth", "dob",
    "scheduled", "completed", "cancelled", "canceled", "no-show", "noshow",
    "duration", "visit", "visits", "checkup", "check-up",
    "monthly", "month", "weekly", "week", "daily", "day", "trend",
    "last month", "last quarter", "past", "history", "recent",
    "how many", "count", "total", "average", "avg", "top", "most",
    "least", "busiest", "highest", "lowest", "maximum", "minimum",
    "percentage", "percent", "ratio", "breakdown", "distribution",
    "list", "show", "compare", "find", "which", "what",
]


# ---------------------------------------------------------------------------
# Comprehensive seed examples
# ---------------------------------------------------------------------------
SEED_EXAMPLES = [
    # ── Patients ──────────────────────────────────────────────────────────
    {
        "question": "How many patients do we have?",
        "sql": "SELECT COUNT(*) AS total_patients FROM patients"
    },
    {
        "question": "How many patients are there?",
        "sql": "SELECT COUNT(*) AS total_patients FROM patients"
    },
    {
        "question": "Total number of patients",
        "sql": "SELECT COUNT(*) AS total_patients FROM patients"
    },
    {
        "question": "List all patients from New York",
        "sql": (
            "SELECT first_name, last_name, email, phone "
            "FROM patients WHERE city = 'New York' ORDER BY last_name"
        )
    },
    {
        "question": "How many male and female patients do we have?",
        "sql": "SELECT gender, COUNT(*) AS count FROM patients GROUP BY gender"
    },
    {
        "question": "Which city has the most patients?",
        "sql": (
            "SELECT city, COUNT(*) AS patient_count FROM patients "
            "GROUP BY city ORDER BY patient_count DESC LIMIT 1"
        )
    },
    {
        "question": "Show patient registration trend by month",
        "sql": (
            "SELECT strftime('%Y-%m', registered_date) AS month, "
            "COUNT(*) AS new_patients "
            "FROM patients GROUP BY month ORDER BY month"
        )
    },
    {
        "question": "List all patients",
        "sql": (
            "SELECT first_name, last_name, email, phone, city, gender "
            "FROM patients ORDER BY last_name"
        )
    },
    {
        "question": "Show patients by city",
        "sql": (
            "SELECT city, COUNT(*) AS patient_count FROM patients "
            "GROUP BY city ORDER BY patient_count DESC"
        )
    },
    {
        "question": "How many patients registered this year?",
        "sql": (
            "SELECT COUNT(*) AS patients_this_year FROM patients "
            "WHERE strftime('%Y', registered_date) = strftime('%Y', 'now')"
        )
    },

    # ── Doctors ───────────────────────────────────────────────────────────
    {
        "question": "How many doctors do we have?",
        "sql": "SELECT COUNT(*) AS total_doctors FROM doctors"
    },
    {
        "question": "How many doctors are there?",
        "sql": "SELECT COUNT(*) AS total_doctors FROM doctors"
    },
    {
        "question": "Total number of doctors",
        "sql": "SELECT COUNT(*) AS total_doctors FROM doctors"
    },
    {
        "question": "List all doctors and their specializations",
        "sql": "SELECT name, specialization, department FROM doctors ORDER BY name"
    },
    {
        "question": "List all doctors",
        "sql": "SELECT name, specialization, department, phone FROM doctors ORDER BY name"
    },
    {
        "question": "Which doctor has the most appointments?",
        "sql": (
            "SELECT d.name, COUNT(a.id) AS appointment_count "
            "FROM doctors d "
            "JOIN appointments a ON d.id = a.doctor_id "
            "GROUP BY d.id, d.name "
            "ORDER BY appointment_count DESC LIMIT 1"
        )
    },
    {
        "question": "How many doctors are in each specialization?",
        "sql": (
            "SELECT specialization, COUNT(*) AS doctor_count "
            "FROM doctors GROUP BY specialization ORDER BY doctor_count DESC"
        )
    },
    {
        "question": "Show doctors by department",
        "sql": (
            "SELECT department, COUNT(*) AS doctor_count "
            "FROM doctors GROUP BY department ORDER BY doctor_count DESC"
        )
    },

    # ── Appointments ──────────────────────────────────────────────────────
    {
        "question": "How many appointments do we have?",
        "sql": "SELECT COUNT(*) AS total_appointments FROM appointments"
    },
    {
        "question": "Show me appointments for last month",
        "sql": (
            "SELECT a.id, p.first_name, p.last_name, d.name AS doctor, "
            "a.appointment_date, a.status "
            "FROM appointments a "
            "JOIN patients p ON p.id = a.patient_id "
            "JOIN doctors d ON d.id = a.doctor_id "
            "WHERE a.appointment_date >= date('now', 'start of month', '-1 month') "
            "AND a.appointment_date < date('now', 'start of month') "
            "ORDER BY a.appointment_date"
        )
    },
    {
        "question": "How many cancelled appointments last quarter?",
        "sql": (
            "SELECT COUNT(*) AS cancelled_count FROM appointments "
            "WHERE status = 'Cancelled' "
            "AND appointment_date >= date('now', '-3 months')"
        )
    },
    {
        "question": "How many cancelled appointments are there?",
        "sql": (
            "SELECT COUNT(*) AS cancelled_count FROM appointments "
            "WHERE status = 'Cancelled'"
        )
    },
    {
        "question": "Show monthly appointment count for the past 6 months",
        "sql": (
            "SELECT strftime('%Y-%m', appointment_date) AS month, "
            "COUNT(*) AS total "
            "FROM appointments "
            "WHERE appointment_date >= date('now', '-6 months') "
            "GROUP BY month ORDER BY month"
        )
    },
    {
        "question": "What percentage of appointments are no-shows?",
        "sql": (
            "SELECT ROUND(100.0 * "
            "SUM(CASE WHEN status = 'No-Show' THEN 1 ELSE 0 END) "
            "/ COUNT(*), 2) AS no_show_percentage FROM appointments"
        )
    },
    {
        "question": "Show the busiest day of the week for appointments",
        "sql": (
            "SELECT CASE CAST(strftime('%w', appointment_date) AS INTEGER) "
            "WHEN 0 THEN 'Sunday' WHEN 1 THEN 'Monday' WHEN 2 THEN 'Tuesday' "
            "WHEN 3 THEN 'Wednesday' WHEN 4 THEN 'Thursday' "
            "WHEN 5 THEN 'Friday' WHEN 6 THEN 'Saturday' END AS day_name, "
            "COUNT(*) AS total FROM appointments "
            "GROUP BY strftime('%w', appointment_date) ORDER BY total DESC"
        )
    },
    {
        "question": "List patients who visited more than 3 times",
        "sql": (
            "SELECT p.first_name, p.last_name, COUNT(a.id) AS visit_count "
            "FROM patients p "
            "JOIN appointments a ON a.patient_id = p.id "
            "GROUP BY p.id, p.first_name, p.last_name "
            "HAVING visit_count > 3 ORDER BY visit_count DESC"
        )
    },
    {
        "question": "Show appointment status breakdown",
        "sql": (
            "SELECT status, COUNT(*) AS count FROM appointments "
            "GROUP BY status ORDER BY count DESC"
        )
    },
    {
        "question": "How many completed appointments?",
        "sql": (
            "SELECT COUNT(*) AS completed_count FROM appointments "
            "WHERE status = 'Completed'"
        )
    },
    {
        "question": "How many scheduled appointments?",
        "sql": (
            "SELECT COUNT(*) AS scheduled_count FROM appointments "
            "WHERE status = 'Scheduled'"
        )
    },
    {
        "question": "How many no-show appointments?",
        "sql": (
            "SELECT COUNT(*) AS no_show_count FROM appointments "
            "WHERE status = 'No-Show'"
        )
    },

    # ── Treatments ────────────────────────────────────────────────────────
    {
        "question": "Average treatment cost by specialization",
        "sql": (
            "SELECT d.specialization, ROUND(AVG(t.cost), 2) AS avg_cost "
            "FROM treatments t "
            "JOIN appointments a ON a.id = t.appointment_id "
            "JOIN doctors d ON d.id = a.doctor_id "
            "GROUP BY d.specialization ORDER BY avg_cost DESC"
        )
    },
    {
        "question": "Average appointment duration by doctor",
        "sql": (
            "SELECT d.name, ROUND(AVG(t.duration_minutes), 1) AS avg_duration "
            "FROM doctors d "
            "JOIN appointments a ON d.id = a.doctor_id "
            "JOIN treatments t ON a.id = t.appointment_id "
            "GROUP BY d.id, d.name ORDER BY avg_duration DESC"
        )
    },
    {
        "question": "What treatments are available?",
        "sql": (
            "SELECT DISTINCT treatment_name, "
            "ROUND(AVG(cost), 2) AS avg_cost, "
            "ROUND(AVG(duration_minutes), 0) AS avg_duration_mins "
            "FROM treatments GROUP BY treatment_name ORDER BY treatment_name"
        )
    },
    {
        "question": "Most expensive treatments",
        "sql": (
            "SELECT treatment_name, ROUND(AVG(cost), 2) AS avg_cost "
            "FROM treatments GROUP BY treatment_name "
            "ORDER BY avg_cost DESC LIMIT 10"
        )
    },
    {
        "question": "Total treatment cost",
        "sql": "SELECT ROUND(SUM(cost), 2) AS total_treatment_cost FROM treatments"
    },

    # ── Financial ─────────────────────────────────────────────────────────
    {
        "question": "What is the total revenue?",
        "sql": "SELECT ROUND(SUM(total_amount), 2) AS total_revenue FROM invoices"
    },
    {
        "question": "What is the total revenue collected?",
        "sql": "SELECT ROUND(SUM(paid_amount), 2) AS total_collected FROM invoices"
    },
    {
        "question": "Show revenue by doctor",
        "sql": (
            "SELECT d.name, ROUND(SUM(i.total_amount), 2) AS total_revenue "
            "FROM doctors d "
            "JOIN appointments a ON d.id = a.doctor_id "
            "JOIN invoices i ON a.patient_id = i.patient_id "
            "GROUP BY d.name ORDER BY total_revenue DESC"
        )
    },
    {
        "question": "Top 5 patients by spending",
        "sql": (
            "SELECT p.first_name, p.last_name, "
            "ROUND(SUM(i.total_amount), 2) AS total_spending "
            "FROM patients p "
            "JOIN invoices i ON p.id = i.patient_id "
            "GROUP BY p.id, p.first_name, p.last_name "
            "ORDER BY total_spending DESC LIMIT 5"
        )
    },
    {
        "question": "Show unpaid invoices",
        "sql": (
            "SELECT p.first_name, p.last_name, i.total_amount, "
            "i.paid_amount, i.status, i.invoice_date "
            "FROM invoices i "
            "JOIN patients p ON p.id = i.patient_id "
            "WHERE i.status IN ('Pending', 'Overdue') "
            "ORDER BY i.invoice_date DESC"
        )
    },
    {
        "question": "List patients with overdue invoices",
        "sql": (
            "SELECT DISTINCT p.first_name, p.last_name, p.email, "
            "i.total_amount, i.paid_amount, i.invoice_date "
            "FROM patients p "
            "JOIN invoices i ON p.id = i.patient_id "
            "WHERE i.status = 'Overdue' "
            "ORDER BY i.invoice_date"
        )
    },
    {
        "question": "Revenue trend by month",
        "sql": (
            "SELECT strftime('%Y-%m', invoice_date) AS month, "
            "ROUND(SUM(total_amount), 2) AS revenue "
            "FROM invoices GROUP BY month ORDER BY month"
        )
    },
    {
        "question": "Compare revenue between departments",
        "sql": (
            "SELECT d.department, ROUND(SUM(i.total_amount), 2) AS total_revenue "
            "FROM doctors d "
            "JOIN appointments a ON d.id = a.doctor_id "
            "JOIN invoices i ON a.patient_id = i.patient_id "
            "GROUP BY d.department ORDER BY total_revenue DESC"
        )
    },
    {
        "question": "Invoice status breakdown",
        "sql": (
            "SELECT status, COUNT(*) AS count, "
            "ROUND(SUM(total_amount), 2) AS total_amount "
            "FROM invoices GROUP BY status ORDER BY total_amount DESC"
        )
    },
    {
        "question": "Total outstanding amount",
        "sql": (
            "SELECT ROUND(SUM(total_amount - paid_amount), 2) AS outstanding_amount "
            "FROM invoices WHERE status IN ('Pending', 'Overdue')"
        )
    },
]


# ---------------------------------------------------------------------------
# SQL Validator
# ---------------------------------------------------------------------------
class SQLValidator:
    """Ensures only safe, read-only SELECT queries reach the database."""

    _BLOCKED = [
        r"\bINSERT\b", r"\bUPDATE\b", r"\bDELETE\b", r"\bDROP\b",
        r"\bALTER\b", r"\bCREATE\b", r"\bTRUNCATE\b", r"\bEXEC\b",
        r"\bEXECUTE\b", r"\bGRANT\b", r"\bREVOKE\b", r"\bSHUTDOWN\b",
        r"\bxp_", r"\bsp_", r"sqlite_master", r"sqlite_schema",
    ]

    @classmethod
    def validate(cls, sql: str) -> Tuple[bool, str]:
        if not sql or not sql.strip():
            return False, "Empty SQL query"
        cleaned = sql.upper().strip()
        if not (cleaned.startswith("SELECT") or cleaned.startswith("WITH")):
            return False, "Only SELECT queries are permitted"
        for pattern in cls._BLOCKED:
            if re.search(pattern, sql, re.IGNORECASE):
                return False, f"Blocked keyword detected: {pattern}"
        return True, ""


# ---------------------------------------------------------------------------
# Improved Memory Store
# ---------------------------------------------------------------------------
class SimpleMemoryStore:
    """In-memory store with cosine similarity scoring."""

    STOP_WORDS = {
        "the", "a", "an", "is", "are", "was", "were", "do", "does", "did",
        "have", "has", "had", "be", "been", "being", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "dare", "ought",
        "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "as", "into", "through", "during", "before", "after", "above",
        "below", "between", "out", "off", "over", "under", "again",
        "further", "then", "once", "here", "there", "when", "where", "why",
        "all", "each", "every", "both", "few", "more", "most", "other",
        "some", "such", "no", "nor", "not", "only", "own", "same", "so",
        "than", "too", "very", "just", "because", "but", "and", "or", "if",
        "while", "about", "up", "down", "it", "its", "this", "that",
        "these", "those", "i", "me", "my", "we", "us", "our", "you", "your",
        "he", "him", "his", "she", "her", "they", "them", "their", "what",
        "whom", "give", "tell", "display", "find", "see",
    }

    def __init__(self):
        self.qa_pairs: List[Dict[str, str]] = []

    def add(self, question: str, sql: str) -> None:
        for pair in self.qa_pairs:
            if pair["question"].lower().strip() == question.lower().strip():
                pair["sql"] = sql
                return
        self.qa_pairs.append({"question": question, "sql": sql})

    def _tokenize(self, text: str) -> List[str]:
        words = re.findall(r'[a-z0-9]+', text.lower())
        return [w for w in words if w not in self.STOP_WORDS and len(w) > 1]

    def _cosine_similarity(self, q1: str, q2: str) -> float:
        c1 = Counter(self._tokenize(q1))
        c2 = Counter(self._tokenize(q2))
        common = set(c1.keys()) & set(c2.keys())
        if not common:
            return 0.0
        numerator = sum(c1[w] * c2[w] for w in common)
        denom = (math.sqrt(sum(v ** 2 for v in c1.values())) *
                 math.sqrt(sum(v ** 2 for v in c2.values())))
        return numerator / denom if denom else 0.0

    def search(self, question: str, limit: int = 5) -> List[Dict[str, str]]:
        scored = [
            (self._cosine_similarity(question, p["question"]), p)
            for p in self.qa_pairs
        ]
        scored = [(s, p) for s, p in scored if s > 0]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored[:limit]]

    def search_best(self, question: str, threshold: float = 0.75) -> Optional[Dict[str, str]]:
        scored = [
            (self._cosine_similarity(question, p["question"]), p)
            for p in self.qa_pairs
        ]
        if not scored:
            return None
        best_score, best_pair = max(scored, key=lambda x: x[0])
        return best_pair if best_score >= threshold else None

    def count(self) -> int:
        return len(self.qa_pairs)


# ---------------------------------------------------------------------------
# VannaAgent - FIXED FOR GROQ
# ---------------------------------------------------------------------------
class VannaAgent:
    """NL2SQL agent backed by Groq and improved memory."""

    _SYSTEM = f"""You are an expert SQL assistant for a clinic management system using SQLite.

{SCHEMA_CONTEXT}

STRICT RULES:
1. Output ONLY a raw SQLite SELECT query. No markdown, no explanation, no code fences.
2. Never use INSERT, UPDATE, DELETE, DROP, ALTER, EXEC, GRANT, REVOKE, SHUTDOWN.
3. Use proper JOINs when data spans multiple tables.
4. Always give columns meaningful aliases (AS ...).
5. Use COUNT/SUM/AVG for aggregation questions.
6. Add ORDER BY + LIMIT for "top", "most", "busiest" questions.
7. Use GROUP BY whenever you aggregate across groups.
8. For date filtering: use SQLite date functions.
9. "last month": WHERE col >= date('now','start of month','-1 month') AND col < date('now','start of month')
10. "last quarter": WHERE col >= date('now','-3 months')
11. "cancelled": WHERE status = 'Cancelled'
12. "no-show": WHERE status = 'No-Show'
13. "unpaid": WHERE status IN ('Pending','Overdue')
14. "overdue": WHERE status = 'Overdue'
15. "busiest day": use strftime('%w', appointment_date)
16. "monthly trend": use strftime('%Y-%m', date_col) GROUP BY month
17. "average duration": AVG(duration_minutes) from treatments JOIN appointments
18. "revenue by department": doctors->appointments->invoices GROUP BY department
19. Never access sqlite_master or system tables.
20. "how many X" with no breakdown = SELECT COUNT(*) AS total_X FROM X (no GROUP BY).
21. Only GROUP BY when question asks for breakdown BY something.
22. Generate SQL that EXACTLY answers the question asked."""

    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self.memory = SimpleMemoryStore()
        self._client = None
        self._init_llm()
        for ex in SEED_EXAMPLES:
            self.memory.add(ex["question"], ex["sql"])

    # ------------------------------------------------------------------ #
    # LLM setup - FIXED FOR GROQ                                          #
    # ------------------------------------------------------------------ #
    def _init_llm(self) -> None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            print("Warning: No GROQ_API_KEY. LLM disabled — memory-only mode.")
            return
        try:
            from groq import Groq
            self._client = Groq(api_key=api_key)
            print("Groq LLM initialized successfully")
        except ImportError:
            print("Warning: groq package not installed. Run: pip install groq")
        except Exception as exc:
            print(f"Warning: Groq init failed: {exc}")

    # ------------------------------------------------------------------ #
    # Prompt builder                                                        #
    # ------------------------------------------------------------------ #
    def _build_prompt(self, question: str) -> str:
        similar = self.memory.search(question, limit=4)
        parts = [
            f"Question: {question}",
            "",
            "Generate a single SQLite SELECT query that answers this question exactly.",
            "",
        ]
        if similar:
            parts.append("Similar example queries for reference (adapt, don't copy blindly):")
            parts.append("")
            for i, pair in enumerate(similar, 1):
                parts.append(f"Example {i}:")
                parts.append(f"  Q: {pair['question']}")
                parts.append(f"  SQL: {pair['sql']}")
                parts.append("")
        parts.append("Output ONLY the SQL query, nothing else.")
        return "\n".join(parts)

    # ------------------------------------------------------------------ #
    # LLM call - FIXED FOR GROQ                                           #
    # ------------------------------------------------------------------ #
    def _call_llm(self, question: str) -> Optional[str]:
        if not self._client:
            return None
        try:
            # Use current Groq model (llama-3.3-70b-versatile)
            response = self._client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": self._SYSTEM},
                    {"role": "user", "content": self._build_prompt(question)}
                ],
                temperature=0.0,
                max_tokens=1024,
            )
            
            raw = response.choices[0].message.content.strip()
            
            # Strip markdown fences
            raw = re.sub(r"^```(?:sql)?\s*", "", raw, flags=re.IGNORECASE)
            raw = re.sub(r"\s*```$", "", raw)
            raw = raw.strip()
            
            # Extract only the SQL part
            lines = raw.split('\n')
            sql_lines = []
            found_sql = False
            for line in lines:
                stripped = line.strip().upper()
                if not found_sql and (
                    stripped.startswith('SELECT') or
                    stripped.startswith('WITH')
                ):
                    found_sql = True
                if found_sql:
                    sql_lines.append(line)
            raw = '\n'.join(sql_lines).strip() if sql_lines else raw
            return raw if raw else None
            
        except Exception as exc:
            print(f"LLM error: {exc}")
            return None

    # ------------------------------------------------------------------ #
    # SQL generation with fallback                                         #
    # ------------------------------------------------------------------ #
    def generate_sql(self, question: str) -> Optional[str]:
        """Generate SQL: LLM first, then memory fallback."""
        # 1. Try LLM
        sql = self._call_llm(question)
        if sql:
            valid, _ = SQLValidator.validate(sql)
            if valid:
                return sql

        # 2. High-confidence memory match
        best = self.memory.search_best(question, threshold=0.75)
        if best:
            print(f"  [memory] High-confidence match: {best['question'][:55]}")
            return best["sql"]

        # 3. Lower threshold fallback
        best_low = self.memory.search_best(question, threshold=0.5)
        if best_low:
            print(f"  [memory] Low-confidence match: {best_low['question'][:55]}")
            return best_low["sql"]

        return None

    # ------------------------------------------------------------------ #
    # SQL execution                                                         #
    # ------------------------------------------------------------------ #
    def execute_sql(self, sql: str) -> Dict[str, Any]:
        is_valid, error = SQLValidator.validate(sql)
        if not is_valid:
            return {"error": error, "columns": [], "rows": [], "row_count": 0}
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute(sql)
            columns = [d[0] for d in cursor.description] if cursor.description else []
            rows = [list(row) for row in cursor.fetchall()]
            conn.close()
            return {
                "columns": columns, "rows": rows,
                "row_count": len(rows), "error": None
            }
        except Exception as exc:
            return {"error": str(exc), "columns": [], "rows": [], "row_count": 0}

    def _check_out_of_scope(self, question: str) -> Tuple[bool, str]:
        """
        Returns (is_blocked, message).
        Checks completely out-of-scope topics first,
        then fields not in the database.
        """
        q_lower = question.lower().strip()

        # 1. Completely out-of-scope topics
        for pattern in OUT_OF_SCOPE_PATTERNS:
            if re.search(pattern, q_lower):
                return True, (
                    "This question is outside the scope of the clinic database. "
                    "I can only answer questions about patients, doctors, "
                    "appointments, treatments, and invoices."
                )

        # 2. Clinic-related but data not in this database
        for pattern, reason in NOT_IN_DATABASE_PATTERNS:
            if re.search(pattern, q_lower):
                return True, (
                    f"{reason} "
                    f"You can ask about: patient demographics, doctor specializations, "
                    f"appointments, treatment costs/durations, and invoice/revenue data."
                )

        # 3. Check if it has ANY clinic-related keyword
        has_clinic_kw = any(kw in q_lower for kw in IN_SCOPE_KEYWORDS)
        if not has_clinic_kw:
            return True, (
                "This question doesn't appear to be related to clinic data. "
                "I can answer questions about patients, doctors, appointments, "
                "treatments, and invoices."
            )

        return False, ""

    def _validate_sql_relevance(self, question: str, sql: str) -> Tuple[bool, str]:
        """
        Verify the generated SQL actually addresses the question.
        Only checks for clear mismatches to avoid false positives.
        """
        q_lower = question.lower()
        sql_lower = sql.lower()

        strict_rules = [
            ("appointment",    "appointments",     "appointments table"),
            ("treatment",      "treatments",       "treatments table"),
            ("invoice",        "invoices",         "invoices table"),
            ("revenue",        "invoices",         "invoices table for revenue"),
            ("billing",        "invoices",         "invoices table for billing"),
            ("specialization", "specialization",   "specialization column"),
            ("duration",       "duration_minutes", "duration_minutes column"),
            ("registered",     "registered_date",  "registered_date column"),
            ("cancelled",      "cancelled",        "Cancelled status filter"),
            ("overdue",        "overdue",          "Overdue status filter"),
            ("no-show",        "no-show",          "No-Show status filter"),
        ]

        for q_kw, sql_kw, desc in strict_rules:
            if q_kw in q_lower and sql_kw not in sql_lower:
                return False, f"Generated SQL is missing {desc}"

        return True, ""

    def ask(self, question: str) -> Dict[str, Any]:
        """Full pipeline: validate → generate → check → execute → respond."""
        result: Dict[str, Any] = {
            "question": question,
            "sql_query": None,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "message": "",
            "error": None,
        }

        # Step 1: Scope + data availability check
        blocked, reason = self._check_out_of_scope(question)
        if blocked:
            result["error"] = "out_of_scope"
            result["message"] = f"I cannot answer this question. {reason}"
            return result

        # Step 2: Generate SQL
        sql = self.generate_sql(question)
        if not sql:
            result["error"] = "no_sql_generated"
            result["message"] = (
                "I couldn't generate a query for this question. "
                "Please try rephrasing or ask about patients, doctors, "
                "appointments, treatments, or invoices."
            )
            return result

        result["sql_query"] = sql

        # Step 3: Safety validation
        is_valid, err = SQLValidator.validate(sql)
        if not is_valid:
            result["error"] = err
            result["message"] = f"The generated query was blocked for safety: {err}"
            return result

        # Step 4: Relevance check
        is_relevant, relevance_err = self._validate_sql_relevance(question, sql)
        if not is_relevant:
            result["error"] = "irrelevant_sql"
            result["message"] = (
                f"I couldn't generate an accurate query for this question. "
                f"Detail: {relevance_err}. Please try rephrasing."
            )
            return result

        # Step 5: Execute
        exec_result = self.execute_sql(sql)
        if exec_result.get("error"):
            result["error"] = exec_result["error"]
            result["message"] = f"Database error: {exec_result['error']}"
            return result

        result["columns"] = exec_result["columns"]
        result["rows"] = exec_result["rows"]
        result["row_count"] = exec_result["row_count"]

        # Step 6: Human-readable message
        rc = result["row_count"]
        if rc == 0:
            result["message"] = "No data found for your query."
        elif rc == 1 and len(result["columns"]) == 1:
            result["message"] = f"Result: {result['rows'][0][0]}"
        else:
            result["message"] = f"Found {rc} result(s)."

        # Step 7: Cache successful query
        self.memory.add(question, sql)

        return result

    # ------------------------------------------------------------------ #
    # Public helpers                                                        #
    # ------------------------------------------------------------------ #
    def add_training_data(self, question: str, sql: str) -> None:
        self.memory.add(question, sql)

    def get_memory_count(self) -> int:
        return self.memory.count()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_agent_instance: Optional[VannaAgent] = None


def get_agent() -> VannaAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = VannaAgent(db_path=DATABASE_PATH)
    return _agent_instance


agent = get_agent()


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("\n-- VannaAgent smoke test --")
    a = get_agent()

    tests = [
        # Should PASS (in database)
        ("How many patients do we have?",            True),
        ("How many doctors are there?",              True),
        ("How many appointments do we have?",        True),
        ("List all doctors",                         True),
        ("What is the total revenue?",               True),
        ("Which doctor has the most appointments?",  True),
        ("Show me appointments for last month",      True),
        ("Average treatment cost by specialization", True),
        ("Show unpaid invoices",                     True),
        # Should BLOCK (out of scope)
        ("how many patients are dead?",              False),
        ("what is the weather today?",               False),
        ("show me stock prices",                     False),
        # Should BLOCK (not in database)
        ("what is the blood type of patients?",      False),
        ("show patient insurance details",           False),
        ("what medications are prescribed?",         False),
    ]

    passed = 0
    for question, should_pass in tests:
        r = a.ask(question)
        is_error = bool(r.get("error"))
        ok = (should_pass and not is_error) or (not should_pass and is_error)
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        print(f"  [{status}] {question[:55]}")
        if not ok:
            print(f"         Expected {'answer' if should_pass else 'block'}, "
                  f"got: {r.get('message', '')[:80]}")

    print(f"\nSmoke test: {passed}/{len(tests)} passed")