# Test Results - NL2SQL Clinic Chatbot

| Field | Value |
|-------|-------|
| Database | clinic.db - 200 patients, 15 doctors, 500 appointments, 350 treatments, 300 invoices |
| LLM | GROQ API Key |
| Date | 2026-04-05 13:44 |
| Score | **18/20 (90.0%)** |

---

## Q1 - How many patients do we have?

**Status: PASS**

**Generated SQL:**
```sql
SELECT COUNT(*) AS total_patients FROM patients
```

**Row count:** 1

---

## Q2 - List all doctors and their specializations

**Status: FAIL**

**Generated SQL:**
```sql
SELECT name AS doctor_name, specialization, department FROM doctors ORDER BY name
```

**Row count:** 30

**Issues:**
- Expected exactly 15 rows, got 30

---

## Q3 - Show me appointments for last month

**Status: PASS**

**Generated SQL:**
```sql
SELECT a.id, p.first_name, p.last_name, d.name AS doctor, a.appointment_date, a.status FROM appointments a JOIN patients p ON p.id = a.patient_id JOIN doctors d ON d.id = a.doctor_id WHERE a.appointment_date >= date('now', 'start of month', '-1 month') AND a.appointment_date < date('now', 'start of month') ORDER BY a.appointment_date
```

**Row count:** 75

---

## Q4 - Which doctor has the most appointments?

**Status: PASS**

**Generated SQL:**
```sql
SELECT d.name, COUNT(a.id) AS appointment_count FROM doctors d JOIN appointments a ON d.id = a.doctor_id GROUP BY d.id, d.name ORDER BY appointment_count DESC LIMIT 1
```

**Row count:** 1

---

## Q5 - What is the total revenue?

**Status: PASS**

**Generated SQL:**
```sql
SELECT ROUND(SUM(total_amount), 2) AS total_revenue FROM invoices
```

**Row count:** 1

---

## Q6 - Show revenue by doctor

**Status: PASS**

**Generated SQL:**
```sql
SELECT d.name, ROUND(SUM(i.total_amount), 2) AS total_revenue FROM doctors d JOIN appointments a ON d.id = a.doctor_id JOIN invoices i ON a.patient_id = i.patient_id GROUP BY d.name ORDER BY total_revenue DESC
```

**Row count:** 15

---

## Q7 - How many cancelled appointments last quarter?

**Status: PASS**

**Generated SQL:**
```sql
SELECT COUNT(*) AS cancelled_count FROM appointments WHERE status = 'Cancelled' AND appointment_date >= date('now', '-3 months')
```

**Row count:** 1

---

## Q8 - Top 5 patients by spending

**Status: PASS**

**Generated SQL:**
```sql
SELECT p.first_name, p.last_name, ROUND(SUM(i.total_amount), 2) AS total_spending FROM patients p JOIN invoices i ON p.id = i.patient_id GROUP BY p.id, p.first_name, p.last_name ORDER BY total_spending DESC LIMIT 5
```

**Row count:** 5

---

## Q9 - Average treatment cost by specialization

**Status: PASS**

**Generated SQL:**
```sql
SELECT d.specialization, ROUND(AVG(t.cost), 2) AS avg_cost FROM treatments t JOIN appointments a ON a.id = t.appointment_id JOIN doctors d ON d.id = a.doctor_id GROUP BY d.specialization ORDER BY avg_cost DESC
```

**Row count:** 5

---

## Q10 - Show monthly appointment count for the past 6 months

**Status: FAIL**

**Generated SQL:**
```sql
SELECT strftime('%Y-%m', appointment_date) AS month, COUNT(*) AS total FROM appointments WHERE appointment_date >= date('now', '-6 months') GROUP BY month ORDER BY month
```

**Row count:** 7

**Issues:**
- Expected at most 6 rows, got 7 (LIMIT missing or incorrect)

---

## Q11 - Which city has the most patients?

**Status: PASS**

**Generated SQL:**
```sql
SELECT city, COUNT(*) AS patient_count FROM patients GROUP BY city ORDER BY patient_count DESC LIMIT 1
```

**Row count:** 1

---

## Q12 - List patients who visited more than 3 times

**Status: PASS**

**Generated SQL:**
```sql
SELECT p.first_name, p.last_name, COUNT(a.id) AS visit_count FROM patients p JOIN appointments a ON a.patient_id = p.id GROUP BY p.id, p.first_name, p.last_name HAVING COUNT(a.id) > 3 ORDER BY visit_count DESC
```

**Row count:** 112

---

## Q13 - Show unpaid invoices

**Status: PASS**

**Generated SQL:**
```sql
SELECT i.id, p.first_name, p.last_name, i.total_amount, i.paid_amount, i.status, i.invoice_date FROM invoices i JOIN patients p ON p.id = i.patient_id WHERE i.status IN ('Pending', 'Overdue') ORDER BY i.invoice_date DESC
```

**Row count:** 287

---

## Q14 - What percentage of appointments are no-shows?

**Status: PASS**

**Generated SQL:**
```sql
SELECT ROUND(100.0 * SUM(CASE WHEN status = 'No-Show' THEN 1 ELSE 0 END) / COUNT(*), 2) AS no_show_percentage FROM appointments
```

**Row count:** 1

---

## Q15 - Show the busiest day of the week for appointments

**Status: PASS**

**Generated SQL:**
```sql
SELECT CASE CAST(strftime('%w', appointment_date) AS INTEGER) WHEN 0 THEN 'Sunday' WHEN 1 THEN 'Monday' WHEN 2 THEN 'Tuesday' WHEN 3 THEN 'Wednesday' WHEN 4 THEN 'Thursday' WHEN 5 THEN 'Friday' WHEN 6 THEN 'Saturday' END AS day_name, COUNT(*) AS total FROM appointments GROUP BY strftime('%w', appointment_date) ORDER BY total DESC LIMIT 1
```

**Row count:** 1

---

## Q16 - Revenue trend by month

**Status: PASS**

**Generated SQL:**
```sql
SELECT strftime('%Y-%m', invoice_date) AS month, ROUND(SUM(total_amount), 2) AS revenue FROM invoices GROUP BY month ORDER BY month
```

**Row count:** 13

---

## Q17 - Average appointment duration by doctor

**Status: PASS**

**Generated SQL:**
```sql
SELECT d.name, ROUND(AVG(t.duration_minutes), 1) AS avg_duration FROM doctors d JOIN appointments a ON d.id = a.doctor_id JOIN treatments t ON a.id = t.appointment_id GROUP BY d.id, d.name ORDER BY avg_duration DESC
```

**Row count:** 29

---

## Q18 - List patients with overdue invoices

**Status: PASS**

**Generated SQL:**
```sql
SELECT DISTINCT p.first_name, p.last_name, p.email, i.total_amount, i.paid_amount, i.invoice_date FROM patients p JOIN invoices i ON p.id = i.patient_id WHERE i.status = 'Overdue' ORDER BY i.invoice_date
```

**Row count:** 85

---

## Q19 - Compare revenue between departments

**Status: PASS**

**Generated SQL:**
```sql
SELECT d.department, ROUND(SUM(i.total_amount), 2) AS total_revenue FROM doctors d JOIN appointments a ON d.id = a.doctor_id JOIN invoices i ON a.patient_id = i.patient_id GROUP BY d.department ORDER BY total_revenue DESC
```

**Row count:** 5

---

## Q20 - Show patient registration trend by month

**Status: PASS**

**Generated SQL:**
```sql
SELECT strftime('%Y-%m', registered_date) AS month, COUNT(*) AS new_patients FROM patients GROUP BY month ORDER BY month
```

**Row count:** 25

---

## Summary Table

| # | Question | Status | Rows |
|---|----------|--------|------|
| 1 | How many patients do we have? | PASS | 1 |
| 2 | List all doctors and their specializations | FAIL | 30 |
| 3 | Show me appointments for last month | PASS | 75 |
| 4 | Which doctor has the most appointments? | PASS | 1 |
| 5 | What is the total revenue? | PASS | 1 |
| 6 | Show revenue by doctor | PASS | 15 |
| 7 | How many cancelled appointments last quarter? | PASS | 1 |
| 8 | Top 5 patients by spending | PASS | 5 |
| 9 | Average treatment cost by specialization | PASS | 5 |
| 10 | Show monthly appointment count for the past 6 months | FAIL | 7 |
| 11 | Which city has the most patients? | PASS | 1 |
| 12 | List patients who visited more than 3 times | PASS | 112 |
| 13 | Show unpaid invoices | PASS | 287 |
| 14 | What percentage of appointments are no-shows? | PASS | 1 |
| 15 | Show the busiest day of the week for appointments | PASS | 1 |
| 16 | Revenue trend by month | PASS | 13 |
| 17 | Average appointment duration by doctor | PASS | 29 |
| 18 | List patients with overdue invoices | PASS | 85 |
| 19 | Compare revenue between departments | PASS | 5 |
| 20 | Show patient registration trend by month | PASS | 25 |

**Final Score: 18/20 (90.0%)**

## Failure Analysis

### Q2 - List all doctors and their specializations

- Expected exactly 15 rows, got 30

Generated SQL:
```sql
SELECT name AS doctor_name, specialization, department FROM doctors ORDER BY name
```

### Q10 - Show monthly appointment count for the past 6 months

- Expected at most 6 rows, got 7 (LIMIT missing or incorrect)

Generated SQL:
```sql
SELECT strftime('%Y-%m', appointment_date) AS month, COUNT(*) AS total FROM appointments WHERE appointment_date >= date('now', '-6 months') GROUP BY month ORDER BY month
```
