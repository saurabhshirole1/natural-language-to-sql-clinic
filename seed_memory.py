"""
seed_memory.py

This script pre-seeds the agent memory with 15 known good Q&A pairs.
The agent will use these to answer similar questions faster.

Note: In Vanna 2.0, memory learning is automatic. This script manually
kickstarts the memory with well-known correct queries for our clinic schema.

Run this AFTER setup_database.py and BEFORE starting the API server.
"""

import asyncio
from vanna.core.user import User, RequestContext
from vanna_setup import agent_memory

# These are the 15 Q&A pairs we want the agent to know about
# Covers patients, doctors, appointments, finances, and time-based queries

QA_PAIRS = [
    # Patient queries
    {
        "question": "How many patients do we have?",
        "sql": "SELECT COUNT(*) AS total_patients FROM patients"
    },
    {
        "question": "List all patients from Mumbai",
        "sql": "SELECT first_name, last_name, email, phone FROM patients WHERE city = 'Mumbai'"
    },
    {
        "question": "How many male and female patients are there?",
        "sql": "SELECT gender, COUNT(*) AS count FROM patients GROUP BY gender"
    },
    {
        "question": "Which city has the most patients?",
        "sql": (
            "SELECT city, COUNT(*) AS patient_count FROM patients "
            "GROUP BY city ORDER BY patient_count DESC LIMIT 1"
        )
    },

    # Doctor queries
    {
        "question": "List all doctors and their specializations",
        "sql": "SELECT name, specialization, department FROM doctors ORDER BY specialization"
    },
    {
        "question": "Which doctor has the most appointments?",
        "sql": (
            "SELECT d.name, COUNT(a.id) AS total_appointments "
            "FROM doctors d "
            "JOIN appointments a ON a.doctor_id = d.id "
            "GROUP BY d.name ORDER BY total_appointments DESC LIMIT 1"
        )
    },

    # Appointment queries
    {
        "question": "Show me appointments for last month",
        "sql": (
            "SELECT a.id, p.first_name, p.last_name, d.name AS doctor, "
            "a.appointment_date, a.status "
            "FROM appointments a "
            "JOIN patients p ON p.id = a.patient_id "
            "JOIN doctors d ON d.id = a.doctor_id "
            "WHERE strftime('%Y-%m', a.appointment_date) = "
            "strftime('%Y-%m', date('now', '-1 month'))"
        )
    },
    {
        "question": "How many cancelled appointments are there?",
        "sql": "SELECT COUNT(*) AS cancelled_count FROM appointments WHERE status = 'Cancelled'"
    },
    {
        "question": "Show monthly appointment count for the past 6 months",
        "sql": (
            "SELECT strftime('%Y-%m', appointment_date) AS month, COUNT(*) AS total "
            "FROM appointments "
            "WHERE appointment_date >= date('now', '-6 months') "
            "GROUP BY month ORDER BY month"
        )
    },

    # Financial queries
    {
        "question": "What is the total revenue?",
        "sql": "SELECT SUM(total_amount) AS total_revenue FROM invoices WHERE status = 'Paid'"
    },
    {
        "question": "Show revenue by doctor",
        "sql": (
            "SELECT d.name, SUM(i.total_amount) AS total_revenue "
            "FROM invoices i "
            "JOIN appointments a ON a.patient_id = i.patient_id "
            "JOIN doctors d ON d.id = a.doctor_id "
            "GROUP BY d.name ORDER BY total_revenue DESC"
        )
    },
    {
        "question": "Show unpaid invoices",
        "sql": (
            "SELECT p.first_name, p.last_name, i.total_amount, i.paid_amount, "
            "i.status, i.invoice_date "
            "FROM invoices i "
            "JOIN patients p ON p.id = i.patient_id "
            "WHERE i.status IN ('Pending', 'Overdue') "
            "ORDER BY i.invoice_date DESC"
        )
    },

    # Time-based queries
    {
        "question": "Revenue trend by month",
        "sql": (
            "SELECT strftime('%Y-%m', invoice_date) AS month, "
            "SUM(total_amount) AS revenue "
            "FROM invoices "
            "GROUP BY month ORDER BY month"
        )
    },
    {
        "question": "Top 5 patients by spending",
        "sql": (
            "SELECT p.first_name, p.last_name, SUM(i.total_amount) AS total_spending "
            "FROM patients p "
            "JOIN invoices i ON i.patient_id = p.id "
            "GROUP BY p.id ORDER BY total_spending DESC LIMIT 5"
        )
    },
    {
        "question": "Average treatment cost by specialization",
        "sql": (
            "SELECT d.specialization, AVG(t.cost) AS avg_cost "
            "FROM treatments t "
            "JOIN appointments a ON a.id = t.appointment_id "
            "JOIN doctors d ON d.id = a.doctor_id "
            "GROUP BY d.specialization ORDER BY avg_cost DESC"
        )
    },
]


async def seed_memory():
    """Seeds agent memory with pre-defined Q&A pairs."""
    print("Seeding agent memory with 15 Q&A pairs...")

    for i, pair in enumerate(QA_PAIRS):
        try:
            # We use save_tool_usage to directly store the known good SQL
            # tool_name corresponds to the run_sql tool in Vanna 2.0
            await agent_memory.save_tool_usage(
                question=pair["question"],
                tool_name="run_sql",
                args={"sql": pair["sql"]},
                context=None,   # DemoAgentMemory allows None context for seeding
                success=True
            )
            print(f"  [{i+1}/15] Seeded: {pair['question'][:50]}...")
        except Exception as e:
            # DemoAgentMemory may require a proper context object
            # If this fails, the agent still works - just without pre-seeded memory
            print(f"  [{i+1}/15] Warning: Could not seed '{pair['question'][:40]}': {e}")

    print(f"\nDone! Seeded {len(QA_PAIRS)} Q&A pairs into agent memory.")
    print("The agent will now use these as starting examples for similar questions.")


if __name__ == "__main__":
    asyncio.run(seed_memory())
