
import json
import requests
from datetime import datetime
from typing import Optional

BASE_URL = "http://127.0.0.1:8000"


TEST_CASES = [
  
    # Q1 — Total patient count                                            

    {
        "id": 1,
        "question": "How many patients do we have?",
        "must_contain": ["patients", "count"],
        "must_not_contain": ["invoices", "appointments"],
        "expect_single": True,
        "min_rows": 1,
    },

    # Q2 — List all doctors (exact row check: 15 doctors in DB)          
    {
        "id": 2,
        "question": "List all doctors and their specializations",
        "must_contain": ["doctors", "specialization"],
        "must_not_contain": ["patients", "invoices"],
        "min_rows": 15,
        "exact_rows": 15,
    },


    # Q3 — Last month appointments (strict date syntax check)             
    {
        "id": 3,
        "question": "Show me appointments for last month",
        "must_contain": ["appointments", "appointment_date", "start of month"],
        "min_rows": 0,
    },

    # Q4 — Doctor with most appointments                                  
    {
        "id": 4,
        "question": "Which doctor has the most appointments?",
        "must_contain": ["doctors", "appointments", "count"],
        "must_not_contain": ["invoices", "treatments"],
        "expect_single": True,
        "min_rows": 1,
    },

    # Q5 — Total revenue (single SUM)                                     

    {
        "id": 5,
        "question": "What is the total revenue?",
        "must_contain": ["invoices", "sum"],
        "must_not_contain": ["patients", "appointments"],
        "expect_single": True,
        "min_rows": 1,
    },

    # Q6 — Revenue grouped by doctor                                      
    {
        "id": 6,
        "question": "Show revenue by doctor",
        "must_contain": ["doctors", "invoices", "sum", "group by"],
        "min_rows": 1,
    },

    # Q7 — Cancelled appointments last quarter                            
    {
        "id": 7,
        "question": "How many cancelled appointments last quarter?",
        "must_contain": ["appointments", "cancelled", "count"],
        "must_not_contain": ["invoices", "patients"],
        "expect_single": True,
        "min_rows": 1,
    },

    # Q8 — Top 5 patients by spending                                     

    {
        "id": 8,
        "question": "Top 5 patients by spending",
        "must_contain": ["patients", "invoices", "limit"],
        "min_rows": 1,
        "max_rows": 5,
        "exact_rows": 5,
    },

    # Q9 — Average treatment cost by specialization                       
    {
        "id": 9,
        "question": "Average treatment cost by specialization",
        "must_contain": ["treatments", "specialization", "avg"],
        "must_not_contain": ["invoices"],
        "min_rows": 1,
    },

    # Q10 — Monthly appointment count past 6 months                       
    {
        "id": 10,
        "question": "Show monthly appointment count for the past 6 months",
        "must_contain": ["appointments", "strftime", "month"],
        "min_rows": 1,
        "max_rows": 6,
    },

    # Q11 — City with most patients                                       
    {
        "id": 11,
        "question": "Which city has the most patients?",
        "must_contain": ["patients", "city", "count"],
        "must_not_contain": ["doctors", "invoices"],
        "expect_single": True,
        "min_rows": 1,
    },

    # Q12 — Patients visiting more than 3 times                           
    {
        "id": 12,
        "question": "List patients who visited more than 3 times",
        "must_contain": ["patients", "appointments", "having"],
        "min_rows": 1,
    },

    # Q13 — Unpaid invoices                                               
    {
        "id": 13,
        "question": "Show unpaid invoices",
        "must_contain": ["invoices", "pending"],
        "min_rows": 1,
    },

    # Q14 — No-show percentage                                            
    {
        "id": 14,
        "question": "What percentage of appointments are no-shows?",
        "must_contain": ["appointments", "no-show"],
        "must_not_contain": ["invoices", "patients"],
        "expect_single": True,
        "min_rows": 1,
    },

    # Q15 — Busiest day of week for appointments                          #
    {
        "id": 15,
        "question": "Show the busiest day of the week for appointments",
        "must_contain": ["appointments", "strftime"],
        "min_rows": 1,
    },

    # Q16 — Revenue trend by month                                        
    {
        "id": 16,
        "question": "Revenue trend by month",
        "must_contain": ["invoices", "strftime", "sum"],
        "must_not_contain": ["appointments", "patients"],
        "min_rows": 1,
    },

    # Q17 — Average appointment duration by doctor                        #
    {
        "id": 17,
        "question": "Average appointment duration by doctor",
        "must_contain": ["doctors", "duration_minutes", "avg"],
        "must_not_contain": ["invoices"],
        "min_rows": 0,
    },

    # Q18 — Patients with overdue invoices                                #
    {
        "id": 18,
        "question": "List patients with overdue invoices",
        "must_contain": ["patients", "invoices", "overdue"],
        "min_rows": 1,
    },

    # Q19 — Revenue compared between departments                          #
    {
        "id": 19,
        "question": "Compare revenue between departments",
        "must_contain": ["doctors", "invoices", "department"],
        "min_rows": 1,
    },

    # Q20 — Patient registration trend by month                           #
    {
        "id": 20,
        "question": "Show patient registration trend by month",
        "must_contain": ["patients", "registered_date", "strftime"],
        "must_not_contain": ["appointments", "invoices"],
        "min_rows": 1,
    },
]

# SQL validation

def check_sql(sql: str, test: dict) -> tuple[bool, list[str]]:
    """
    Validate generated SQL against test rules.
    Returns (passed: bool, issues: list[str])
    """
    issues    = []
    sql_lower = sql.lower()

    # Must start with SELECT or WITH
    if not (sql_lower.strip().startswith("select") or
            sql_lower.strip().startswith("with")):
        issues.append(f"SQL does not start with SELECT/WITH: {sql[:60]}")
        return False, issues  # No point checking further

    # Required keywords must be present
    for keyword in test.get("must_contain", []):
        if keyword.lower() not in sql_lower:
            issues.append(f"Missing keyword: '{keyword}'")

    # Forbidden keywords must NOT be present
    for keyword in test.get("must_not_contain", []):
        if keyword.lower() in sql_lower:
            issues.append(
                f"Unexpected keyword '{keyword}' found "
                f"(suggests wrong/recycled query)"
            )

    return len(issues) == 0, issues

# Single test runner

def run_test(test: dict) -> dict:
    """Send question to /chat and validate the response."""
    result = {
        "id":        test["id"],
        "question":  test["question"],
        "status":    "FAIL",
        "sql":       None,
        "row_count": None,
        "issues":    [],
        "api_error": None,
    }

    try:
        resp = requests.post(
            f"{BASE_URL}/chat",
            json={"question": test["question"]},
            timeout=30,
        )

        # Parse response safely
        try:
            data = resp.json()
        except Exception:
            result["api_error"] = (
                f"Invalid JSON response (HTTP {resp.status_code})"
            )
            return result

        if resp.status_code != 200:
            result["api_error"] = f"HTTP {resp.status_code}: {data}"
            return result

        # Check for API-level errors
        api_error = data.get("error")
        if api_error:
            result["issues"].append(
                f"API returned error '{api_error}': {data.get('message', '')}"
            )
            return result

        sql       = data.get("sql_query") or ""
        rows      = data.get("rows") or []
        row_count = data.get("row_count", len(rows))

        result["sql"]       = sql
        result["row_count"] = row_count

        # SQL content checks
        _, sql_issues = check_sql(sql, test)
        result["issues"].extend(sql_issues)

        # Minimum row count
        min_rows = test.get("min_rows", -1)
        if min_rows > 0 and row_count < min_rows:
            result["issues"].append(
                f"Expected at least {min_rows} rows, got {row_count}"
            )

        # Maximum row count
        max_rows = test.get("max_rows")
        if max_rows is not None and row_count > max_rows:
            result["issues"].append(
                f"Expected at most {max_rows} rows, got {row_count} "
                f"(LIMIT missing or incorrect)"
            )

        # Exact row count
        exact_rows = test.get("exact_rows")
        if exact_rows is not None and row_count != exact_rows:
            result["issues"].append(
                f"Expected exactly {exact_rows} rows, got {row_count}"
            )

        # Single-row aggregation
        if test.get("expect_single") and row_count != 1:
            result["issues"].append(
                f"Expected 1 row for aggregation, got {row_count}"
            )

        if not result["issues"]:
            result["status"] = "PASS"

    except requests.exceptions.ConnectionError:
        result["api_error"] = (
            "Cannot connect to API — "
            "start server: uvicorn main:app --port 8000"
        )
    except requests.exceptions.Timeout:
        result["api_error"] = "Request timed out after 30s"
    except Exception as exc:
        result["api_error"] = f"Unexpected error: {exc}"

    return result


# Markdown report

def generate_results_md(results: list[dict], score: int, total: int) -> str:
    failed = [r for r in results if r["status"] == "FAIL"]
    rate   = score / total * 100

    lines = [
        "# Test Results - NL2SQL Clinic Chatbot",
        "",
        "| Field | Value |",
        "|-------|-------|",
        "| Database | clinic.db - 200 patients, 15 doctors, "
        "500 appointments, 350 treatments, 300 invoices |",
        "| LLM | Google Gemini 2.0 Flash |",
        f"| Date | {datetime.now().strftime('%Y-%m-%d %H:%M')} |",
        f"| Score | **{score}/{total} ({rate:.1f}%)** |",
        "",
        "---",
        "",
    ]

    # Per-question sections
    for r in results:
        status_label = "PASS" if r["status"] == "PASS" else "FAIL"
        lines += [
            f"## Q{r['id']} - {r['question']}",
            "",
            f"**Status: {status_label}**",
            "",
        ]

        if r.get("api_error"):
            lines.append(f"**API Error:** `{r['api_error']}`")
        else:
            sql = r.get("sql") or "No SQL generated"
            lines += [
                "**Generated SQL:**",
                "```sql",
                sql,
                "```",
                "",
                f"**Row count:** {r.get('row_count', 'N/A')}",
            ]
            if r["issues"]:
                lines += ["", "**Issues:**"]
                for issue in r["issues"]:
                    lines.append(f"- {issue}")

        lines += ["", "---", ""]

    # Summary table
    lines += [
        "## Summary Table",
        "",
        "| # | Question | Status | Rows |",
        "|---|----------|--------|------|",
    ]
    for r in results:
        status_label = "PASS" if r["status"] == "PASS" else "FAIL"
        lines.append(
            f"| {r['id']} | {r['question']} "
            f"| {status_label} | {r.get('row_count', 'N/A')} |"
        )

    lines += [
        "",
        f"**Final Score: {score}/{total} ({rate:.1f}%)**",
        "",
    ]

    # Failure analysis
    if failed:
        lines += ["## Failure Analysis", ""]
        for r in failed:
            lines += [f"### Q{r['id']} - {r['question']}", ""]
            if r.get("api_error"):
                lines.append(f"- API Error: {r['api_error']}")
            for issue in r["issues"]:
                lines.append(f"- {issue}")
            if r.get("sql"):
                lines += ["", "Generated SQL:", "```sql", r["sql"], "```"]
            lines.append("")

    return "\n".join(lines)

# Main

def main():
    print("Testing 20 Questions - NL2SQL Clinic Chatbot")
    print("=" * 72)

    # Health check
    try:
        resp   = requests.get(f"{BASE_URL}/health", timeout=5)
        health = resp.json()
        print(f"API status  : {health.get('status', 'unknown')}")
        print(f"Database    : {health.get('database', 'unknown')}")
        print(f"Memory items: {health.get('agent_memory_items', '?')}")
    except Exception:
        print("Cannot reach the API at http://127.0.0.1:8000")
        print("Start the server: uvicorn main:app --port 8000")
        return

    print("=" * 72)

    results = []
    passed  = 0

    for test in TEST_CASES:
        print(f"\nQuestion {test['id']:>2}/20: {test['question']}")
        result = run_test(test)
        results.append(result)

        if result["status"] == "PASS":
            passed += 1
            sql_preview = (result["sql"] or "")[:75].replace("\n", " ")
            print(f"  PASS")
            print(f"     SQL : {sql_preview}...")
            print(f"     Rows: {result['row_count']}")
        else:
            print(f"  FAIL")
            if result.get("api_error"):
                print(f"     Error : {result['api_error']}")
            for issue in result["issues"]:
                print(f"     Issue : {issue}")
            sql_preview = (result["sql"] or "No SQL")[:75].replace("\n", " ")
            print(f"     SQL : {sql_preview}")

    total = len(TEST_CASES)
    rate  = passed / total * 100

    print("\n" + "=" * 72)
    print(f"Summary: {passed} PASSED, {total - passed} FAILED out of {total}")
    print(f"Success Rate: {rate:.1f}%")
    print("=" * 72)

    # Save JSON 
    clean_results = [
        {
            "id":        r["id"],
            "question":  r["question"],
            "status":    r["status"],
            "sql":       r["sql"],
            "row_count": r["row_count"],
            "issues":    r["issues"],
            "api_error": r["api_error"],
        }
        for r in results
    ]

    json_output = {
        "score":        passed,
        "total":        total,
        "success_rate": f"{rate:.1f}%",
        "tested_at":    datetime.now().isoformat(),
        "passed_ids":   [r["id"] for r in results if r["status"] == "PASS"],
        "failed_ids":   [r["id"] for r in results if r["status"] == "FAIL"],
        "results":      clean_results,
    }
    with open("test_results.json", "w", encoding="utf-8") as f:
        json.dump(json_output, f, indent=2, ensure_ascii=False)
    print("\nResults saved to test_results.json")

    # Save Markdown
    md = generate_results_md(results, passed, total)
    with open("RESULTS.md", "w", encoding="utf-8") as f:
        f.write(md)
    print("Results saved to RESULTS.md")


if __name__ == "__main__":
    main()