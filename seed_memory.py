
import sys
from vanna_setup import get_agent, SQLValidator


QA_PAIRS = [

    # ── Patients — alternate phrasings ────────────────────────────────────
    {
        "question": "How many patients are there?",
        "sql": "SELECT COUNT(*) AS total_patients FROM patients"
    },
    {
        "question": "Total number of patients",
        "sql": "SELECT COUNT(*) AS total_patients FROM patients"
    },
    {
        "question": "What is the total patient count?",
        "sql": "SELECT COUNT(*) AS total_patients FROM patients"
    },
    {
        "question": "How many patients are registered?",
        "sql": "SELECT COUNT(*) AS total_patients FROM patients"
    },
    {
        "question": "List all patients",
        "sql": (
            "SELECT first_name, last_name, email, phone, city, gender "
            "FROM patients ORDER BY last_name"
        )
    },
    {
        "question": "Show all patients",
        "sql": (
            "SELECT first_name, last_name, email, phone, city, gender "
            "FROM patients ORDER BY last_name"
        )
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
        "sql": (
            "SELECT gender, COUNT(*) AS count "
            "FROM patients GROUP BY gender ORDER BY count DESC"
        )
    },
    {
        "question": "Show patients by gender",
        "sql": (
            "SELECT gender, COUNT(*) AS count "
            "FROM patients GROUP BY gender ORDER BY count DESC"
        )
    },
    {
        "question": "Show patients by city",
        "sql": (
            "SELECT city, COUNT(*) AS patient_count "
            "FROM patients GROUP BY city ORDER BY patient_count DESC"
        )
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
        "question": "How many patients registered this year?",
        "sql": (
            "SELECT COUNT(*) AS patients_this_year FROM patients "
            "WHERE strftime('%Y', registered_date) = strftime('%Y', 'now')"
        )
    },
    {
        "question": "How many patients registered last month?",
        "sql": (
            "SELECT COUNT(*) AS new_patients FROM patients "
            "WHERE registered_date >= date('now', 'start of month', '-1 month') "
            "AND registered_date < date('now', 'start of month')"
        )
    },

    # ── Doctors — alternate phrasings ─────────────────────────────────────
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
        "question": "What is the total doctor count?",
        "sql": "SELECT COUNT(*) AS total_doctors FROM doctors"
    },
    {
        "question": "List all doctors",
        "sql": (
            "SELECT name, specialization, department, phone "
            "FROM doctors ORDER BY name"
        )
    },
    {
        "question": "Show all doctors",
        "sql": (
            "SELECT name, specialization, department, phone "
            "FROM doctors ORDER BY name"
        )
    },
    {
        "question": "List all doctors and their specializations",
        "sql": (
            "SELECT name, specialization, department "
            "FROM doctors ORDER BY name"
        )
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
    {
        "question": "List doctors in cardiology",
        "sql": (
            "SELECT name, department, phone FROM doctors "
            "WHERE specialization = 'Cardiology' ORDER BY name"
        )
    },

    # ── Appointments ──────────────────────────────────────────────────────
    {
        "question": "How many appointments do we have?",
        "sql": "SELECT COUNT(*) AS total_appointments FROM appointments"
    },
    {
        "question": "Total number of appointments",
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
        "question": "How many cancelled appointments do we have?",
        "sql": (
            "SELECT COUNT(*) AS cancelled_count FROM appointments "
            "WHERE status = 'Cancelled'"
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
        "question": "How many no-show appointments?",
        "sql": (
            "SELECT COUNT(*) AS no_show_count FROM appointments "
            "WHERE status = 'No-Show'"
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
        "question": "Show appointment status breakdown",
        "sql": (
            "SELECT status, COUNT(*) AS count FROM appointments "
            "GROUP BY status ORDER BY count DESC"
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
            "/ COUNT(*), 2) AS no_show_percentage "
            "FROM appointments"
        )
    },
    {
        "question": "Show the busiest day of the week for appointments",
        "sql": (
            "SELECT CASE CAST(strftime('%w', appointment_date) AS INTEGER) "
            "WHEN 0 THEN 'Sunday' WHEN 1 THEN 'Monday' "
            "WHEN 2 THEN 'Tuesday' WHEN 3 THEN 'Wednesday' "
            "WHEN 4 THEN 'Thursday' WHEN 5 THEN 'Friday' "
            "WHEN 6 THEN 'Saturday' END AS day_name, "
            "COUNT(*) AS total FROM appointments "
            "GROUP BY strftime('%w', appointment_date) "
            "ORDER BY total DESC"
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
        "question": "List patients who visited more than 5 times",
        "sql": (
            "SELECT p.first_name, p.last_name, COUNT(a.id) AS visit_count "
            "FROM patients p "
            "JOIN appointments a ON a.patient_id = p.id "
            "GROUP BY p.id, p.first_name, p.last_name "
            "HAVING visit_count > 5 ORDER BY visit_count DESC"
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
        "sql": (
            "SELECT ROUND(SUM(cost), 2) AS total_treatment_cost "
            "FROM treatments"
        )
    },
    {
        "question": "How many treatments have been done?",
        "sql": "SELECT COUNT(*) AS total_treatments FROM treatments"
    },

    # ── Financial ─────────────────────────────────────────────────────────
    {
        "question": "What is the total revenue?",
        "sql": (
            "SELECT ROUND(SUM(total_amount), 2) AS total_revenue "
            "FROM invoices"
        )
    },
    {
        "question": "What is the total revenue collected?",
        "sql": (
            "SELECT ROUND(SUM(paid_amount), 2) AS total_collected "
            "FROM invoices"
        )
    },
    {
        "question": "What is the total amount billed?",
        "sql": (
            "SELECT ROUND(SUM(total_amount), 2) AS total_billed "
            "FROM invoices"
        )
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
        "question": "Top 10 patients by spending",
        "sql": (
            "SELECT p.first_name, p.last_name, "
            "ROUND(SUM(i.total_amount), 2) AS total_spending "
            "FROM patients p "
            "JOIN invoices i ON p.id = i.patient_id "
            "GROUP BY p.id, p.first_name, p.last_name "
            "ORDER BY total_spending DESC LIMIT 10"
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
            "SELECT ROUND(SUM(total_amount - paid_amount), 2) "
            "AS outstanding_amount "
            "FROM invoices WHERE status IN ('Pending', 'Overdue')"
        )
    },
    {
        "question": "How many invoices are overdue?",
        "sql": (
            "SELECT COUNT(*) AS overdue_count FROM invoices "
            "WHERE status = 'Overdue'"
        )
    },
    {
        "question": "How many invoices are pending?",
        "sql": (
            "SELECT COUNT(*) AS pending_count FROM invoices "
            "WHERE status = 'Pending'"
        )
    },
    {
        "question": "How many invoices are paid?",
        "sql": (
            "SELECT COUNT(*) AS paid_count FROM invoices "
            "WHERE status = 'Paid'"
        )
    },
]


# Seed function

def seed_memory() -> None:
    print("Seeding agent memory with Q&A pairs...")
    print("-" * 55)

    agent  = get_agent()
    seeded = 0
    failed = 0
    skipped = 0

    for i, pair in enumerate(QA_PAIRS, start=1):
        question = pair["question"]
        sql      = pair["sql"]

        # Validate SQL before adding to memory
        is_valid, err = SQLValidator.validate(sql)
        if not is_valid:
            print(f"  [{i:>2}] INVALID SQL — skipped: {question[:45]}")
            print(f"         Reason: {err}")
            failed += 1
            continue

        try:
            agent.add_training_data(question, sql)
            print(f"  [{i:>2}] Added : {question[:55]}")
            seeded += 1
        except Exception as exc:
            print(f"  [{i:>2}] ERROR : {question[:45]} — {exc}")
            failed += 1

    print("-" * 55)
    print(f"  Seeded  : {seeded} pairs")
    print(f"  Failed  : {failed} pairs")
    print(f"  Total memory items: {agent.get_memory_count()}")
    print("\nMemory seeding complete!")

    if failed > 0:
        print(f"WARNING: {failed} pairs failed — check SQL above")
        sys.exit(1)


# Entry point

if __name__ == "__main__":
    seed_memory()