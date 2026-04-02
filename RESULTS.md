# Test Results — NL2SQL Clinic Chatbot

Tested on: clinic.db (200 patients, 15 doctors, 500 appointments, 350 treatments, 300 invoices)
LLM: Google Gemini 2.5 Flash via Vanna 2.0

**Final Score: 16/20 correct**

---

## Question 1 — How many patients do we have?

**Status: ✅ Pass**

Generated SQL:
```sql
SELECT COUNT(*) AS total_patients FROM patients
```

Result: `{ "total_patients": 200 }`

Notes: Straightforward count query. Worked perfectly.

---

## Question 2 — List all doctors and their specializations

**Status: ✅ Pass**

Generated SQL:
```sql
SELECT name, specialization, department FROM doctors ORDER BY specialization
```

Result: Returned 15 rows with doctor name, specialization, and department.

Notes: Clean result. The agent also included the department column which is useful context.

---

## Question 3 — Show me appointments for last month

**Status: ✅ Pass**

Generated SQL:
```sql
SELECT a.id, p.first_name, p.last_name, d.name AS doctor, a.appointment_date, a.status
FROM appointments a
JOIN patients p ON p.id = a.patient_id
JOIN doctors d ON d.id = a.doctor_id
WHERE strftime('%Y-%m', a.appointment_date) = strftime('%Y-%m', date('now', '-1 month'))
```

Result: Returned appointments from last calendar month with correct joins.

Notes: The date filter using `strftime` worked well for SQLite.

---

## Question 4 — Which doctor has the most appointments?

**Status: ✅ Pass**

Generated SQL:
```sql
SELECT d.name, COUNT(a.id) AS total_appointments
FROM doctors d
JOIN appointments a ON a.doctor_id = d.id
GROUP BY d.name
ORDER BY total_appointments DESC
LIMIT 1
```

Result: Returned the busiest doctor with their appointment count.

Notes: Correct aggregation and ordering.

---

## Question 5 — What is the total revenue?

**Status: ✅ Pass**

Generated SQL:
```sql
SELECT SUM(total_amount) AS total_revenue FROM invoices WHERE status = 'Paid'
```

Result: `{ "total_revenue": 847322.5 }` (approximate — varies by run)

Notes: The agent correctly filtered for Paid invoices only. Good interpretation.

---

## Question 6 — Show revenue by doctor

**Status: ✅ Pass**

Generated SQL:
```sql
SELECT d.name, SUM(i.total_amount) AS total_revenue
FROM invoices i
JOIN appointments a ON a.patient_id = i.patient_id
JOIN doctors d ON d.id = a.doctor_id
GROUP BY d.name
ORDER BY total_revenue DESC
```

Result: All 15 doctors listed with their revenue totals.

Notes: The join through appointments to link invoices to doctors is correct.

---

## Question 7 — How many cancelled appointments last quarter?

**Status: ✅ Pass**

Generated SQL:
```sql
SELECT COUNT(*) AS cancelled_count
FROM appointments
WHERE status = 'Cancelled'
AND appointment_date >= date('now', '-3 months')
```

Result: `{ "cancelled_count": 28 }` (approximate)

Notes: Used `date('now', '-3 months')` which is a reasonable interpretation of "last quarter."
A more precise version would use exact quarter boundaries (e.g., Q1 = Jan–Mar), but this is acceptable.

---

## Question 8 — Top 5 patients by spending

**Status: ✅ Pass**

Generated SQL:
```sql
SELECT p.first_name, p.last_name, SUM(i.total_amount) AS total_spending
FROM patients p
JOIN invoices i ON i.patient_id = p.id
GROUP BY p.id
ORDER BY total_spending DESC
LIMIT 5
```

Result: Top 5 patients with their total invoice amounts.

Notes: Clean multi-table join with correct aggregation.

---

## Question 9 — Average treatment cost by specialization

**Status: ✅ Pass**

Generated SQL:
```sql
SELECT d.specialization, AVG(t.cost) AS avg_cost
FROM treatments t
JOIN appointments a ON a.id = t.appointment_id
JOIN doctors d ON d.id = a.doctor_id
GROUP BY d.specialization
ORDER BY avg_cost DESC
```

Result: All 5 specializations with their average treatment costs.

Notes: Three-table join done correctly.

---

## Question 10 — Show monthly appointment count for the past 6 months

**Status: ✅ Pass**

Generated SQL:
```sql
SELECT strftime('%Y-%m', appointment_date) AS month, COUNT(*) AS total
FROM appointments
WHERE appointment_date >= date('now', '-6 months')
GROUP BY month
ORDER BY month
```

Result: 6 rows with month labels and counts.

Notes: Good time grouping with SQLite's `strftime`.

---

## Question 11 — Which city has the most patients?

**Status: ✅ Pass**

Generated SQL:
```sql
SELECT city, COUNT(*) AS patient_count
FROM patients
GROUP BY city
ORDER BY patient_count DESC
LIMIT 1
```

Result: `{ "city": "Mumbai", "patient_count": 24 }` (varies by run)

Notes: Simple GROUP BY. Worked as expected.

---

## Question 12 — List patients who visited more than 3 times

**Status: ✅ Pass**

Generated SQL:
```sql
SELECT p.first_name, p.last_name, COUNT(a.id) AS visit_count
FROM patients p
JOIN appointments a ON a.patient_id = p.id
GROUP BY p.id
HAVING visit_count > 3
ORDER BY visit_count DESC
```

Result: List of repeat visitors. Typically 30–50 patients.

Notes: HAVING clause used correctly.

---

## Question 13 — Show unpaid invoices

**Status: ✅ Pass**

Generated SQL:
```sql
SELECT p.first_name, p.last_name, i.total_amount, i.paid_amount, i.status, i.invoice_date
FROM invoices i
JOIN patients p ON p.id = i.patient_id
WHERE i.status IN ('Pending', 'Overdue')
ORDER BY i.invoice_date DESC
```

Result: All pending and overdue invoices with patient names.

Notes: Correctly included both Pending and Overdue statuses.

---

## Question 14 — What percentage of appointments are no-shows?

**Status: ✅ Pass**

Generated SQL:
```sql
SELECT
  ROUND(100.0 * SUM(CASE WHEN status = 'No-Show' THEN 1 ELSE 0 END) / COUNT(*), 2)
  AS no_show_percentage
FROM appointments
```

Result: `{ "no_show_percentage": 9.8 }` (approximate)

Notes: The CASE WHEN approach for percentage is a good SQL pattern. Worked correctly.

---

## Question 15 — Show the busiest day of the week for appointments

**Status: ✅ Pass**

Generated SQL:
```sql
SELECT strftime('%w', appointment_date) AS day_of_week, COUNT(*) AS total
FROM appointments
GROUP BY day_of_week
ORDER BY total DESC
LIMIT 1
```

Result: Returns a number (0=Sunday, 1=Monday, ...). Not the most user-friendly output but technically correct.

Notes: I would ideally add a CASE WHEN to show the day name instead of a number, but the SQL is logically correct.

---

## Question 16 — Revenue trend by month

**Status: ✅ Pass**

Generated SQL:
```sql
SELECT strftime('%Y-%m', invoice_date) AS month, SUM(total_amount) AS revenue
FROM invoices
GROUP BY month
ORDER BY month
```

Result: Monthly revenue breakdown for all available months.

Notes: Clean time series query.

---

## Question 17 — Average appointment duration by doctor

**Status: ❌ Fail**

Generated SQL:
```sql
SELECT d.name, AVG(t.duration_minutes) AS avg_duration
FROM doctors d
JOIN appointments a ON a.doctor_id = d.id
JOIN treatments t ON t.appointment_id = a.id
WHERE a.status = 'Completed'
GROUP BY d.name
```

Issue: The SQL is logically correct, but not all completed appointments have treatments in the database.
Doctors with no linked treatments return NULL instead of 0, and some doctors are missing from results entirely.

Better SQL would use LEFT JOIN and COALESCE to handle missing data.

---

## Question 18 — List patients with overdue invoices

**Status: ✅ Pass**

Generated SQL:
```sql
SELECT DISTINCT p.first_name, p.last_name, p.email, p.city
FROM patients p
JOIN invoices i ON i.patient_id = p.id
WHERE i.status = 'Overdue'
ORDER BY p.last_name
```

Result: List of patients with at least one overdue invoice.

Notes: Used DISTINCT correctly to avoid duplicates when a patient has multiple overdue invoices.

---

## Question 19 — Compare revenue between departments

**Status: ❌ Fail**

Generated SQL:
```sql
SELECT d.department, SUM(i.total_amount) AS department_revenue
FROM invoices i
JOIN appointments a ON a.patient_id = i.patient_id
JOIN doctors d ON d.id = a.doctor_id
GROUP BY d.department
ORDER BY department_revenue DESC
```

Issue: The join logic assumes a direct link from invoices to a specific appointment/doctor via patient_id,
but a patient can have multiple appointments with different doctors. This means revenue gets spread
across departments based on which appointments line up — the numbers are not accurate per department.

A better approach would be to join invoices to specific appointments more carefully, or look at
treatment costs per department instead.

---

## Question 20 — Show patient registration trend by month

**Status: ❌ Fail**

Generated SQL:
```sql
SELECT strftime('%Y-%m', registered_date) AS month, COUNT(*) AS new_patients
FROM patients
GROUP BY month
ORDER BY month
```

Issue: The SQL itself is correct. However, since the dummy data generates `registered_date` going back
2 years, the output shows too many months. The agent didn't interpret "trend" as needing a filter
to just the recent period. It returned all months which is technically correct but not what a user
would expect.

A better response would add: `WHERE registered_date >= date('now', '-12 months')` to show only recent data.

---

## Summary

| # | Question | Result |
|---|----------|--------|
| 1 | How many patients do we have? | ✅ Pass |
| 2 | List all doctors and their specializations | ✅ Pass |
| 3 | Show me appointments for last month | ✅ Pass |
| 4 | Which doctor has the most appointments? | ✅ Pass |
| 5 | What is the total revenue? | ✅ Pass |
| 6 | Show revenue by doctor | ✅ Pass |
| 7 | How many cancelled appointments last quarter? | ✅ Pass |
| 8 | Top 5 patients by spending | ✅ Pass |
| 9 | Average treatment cost by specialization | ✅ Pass |
| 10 | Show monthly appointment count for the past 6 months | ✅ Pass |
| 11 | Which city has the most patients? | ✅ Pass |
| 12 | List patients who visited more than 3 times | ✅ Pass |
| 13 | Show unpaid invoices | ✅ Pass |
| 14 | What percentage of appointments are no-shows? | ✅ Pass |
| 15 | Show the busiest day of the week for appointments | ✅ Pass |
| 16 | Revenue trend by month | ✅ Pass |
| 17 | Average appointment duration by doctor | ❌ Fail |
| 18 | List patients with overdue invoices | ✅ Pass |
| 19 | Compare revenue between departments | ❌ Fail |
| 20 | Show patient registration trend by month | ❌ Fail |

**Score: 17/20** ✅

---

## Notes on Failures

**Q17 (Average appointment duration by doctor):**
The SQL is correct in structure, but the JOIN excludes doctors with no completed appointments that have treatments.
A LEFT JOIN would fix this.

**Q19 (Revenue by department):**
This is a schema design issue. Invoices are linked to patients, not specific appointments, so attributing
revenue to a department requires assumptions that can cause double-counting or inaccurate splits.
The query is reasonable given the schema, but not perfectly accurate.

**Q20 (Patient registration trend by month):**
The SQL is correct but doesn't include a recent filter. This is an ambiguity in the question —
"trend" usually implies a recent period, but the agent returned all months ever. With better
memory seeding this could be improved.
