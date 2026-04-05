#!/usr/bin/env python3
"""
setup_database.py

Creates the clinic.db SQLite database with schema and realistic dummy data.

Usage:
    python setup_database.py

Database contents (default):
    - 15 doctors  (3 per specialization)
    - 200 patients
    - 500 appointments
    - ~350 treatments (for completed appointments only)
    - 300 invoices
"""

import os
import random
import sqlite3
from datetime import datetime, timedelta
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DATABASE_PATH   = "clinic.db"
RANDOM_SEED     = 42          # Fixed seed for reproducible data

NUM_DOCTORS      = 15
NUM_PATIENTS     = 200
NUM_APPOINTMENTS = 500
NUM_TREATMENTS   = 350
NUM_INVOICES     = 300

# ---------------------------------------------------------------------------
# Data pools
# ---------------------------------------------------------------------------
FIRST_NAMES_MALE = [
    "James", "John", "Robert", "Michael", "William", "David", "Richard",
    "Joseph", "Thomas", "Charles", "Christopher", "Daniel", "Matthew",
    "Anthony", "Mark", "Donald", "Steven", "Paul", "Andrew", "Joshua",
    "Kenneth", "Kevin", "Brian",
]

FIRST_NAMES_FEMALE = [
    "Mary", "Patricia", "Jennifer", "Linda", "Barbara", "Elizabeth",
    "Susan", "Jessica", "Sarah", "Karen", "Lisa", "Nancy", "Betty",
    "Margaret", "Sandra", "Ashley", "Kimberly", "Emily", "Donna",
    "Michelle", "Dorothy", "Carol", "Amanda",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
    "Ramirez", "Lewis", "Robinson",
]

CITIES = [
    "New York", "Los Angeles", "Chicago", "Houston", "Phoenix",
    "Philadelphia", "San Antonio", "San Diego", "Dallas", "San Jose",
]

SPECIALIZATIONS = [
    "Dermatology", "Cardiology", "Orthopedics", "General", "Pediatrics"
]

DEPARTMENTS = {
    "Dermatology": "Skin Care Department",
    "Cardiology":  "Heart & Vascular Department",
    "Orthopedics": "Bone & Joint Department",
    "General":     "General Medicine",
    "Pediatrics":  "Children's Health Department",
}

APPOINTMENT_STATUSES = ["Scheduled", "Completed", "Cancelled", "No-Show"]
APPOINTMENT_WEIGHTS  = [0.15, 0.60, 0.15, 0.10]

TREATMENT_NAMES = [
    "General Consultation", "Blood Test", "X-Ray", "MRI Scan", "CT Scan",
    "Physical Therapy", "Skin Treatment", "Cardiac Checkup", "Vaccination",
    "Minor Surgery", "Wound Dressing", "Allergy Test", "ECG", "Ultrasound",
    "Dental Cleaning", "Eye Examination", "Hearing Test",
    "Physiotherapy Session",
]

INVOICE_STATUSES = ["Paid", "Pending", "Overdue"]
INVOICE_WEIGHTS  = [0.60, 0.25, 0.15]

APPOINTMENT_NOTES = [
    "Regular checkup",
    "Follow-up visit",
    "Initial consultation",
    "Referred by GP",
    "Emergency visit",
    "Routine screening",
    None, None, None,   # ~33% NULL notes
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def generate_phone() -> str:
    """Return a realistic US phone number string."""
    return (
        f"({random.randint(200, 999)}) "
        f"{random.randint(100, 999)}-"
        f"{random.randint(1000, 9999)}"
    )


def generate_email(first_name: str, last_name: str) -> str:
    """Return a realistic email address."""
    domains    = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "email.com"]
    separators = [".", "_", ""]
    sep        = random.choice(separators)
    suffix     = str(random.randint(1, 999)) if random.random() > 0.5 else ""
    return (
        f"{first_name.lower()}{sep}{last_name.lower()}{suffix}"
        f"@{random.choice(domains)}"
    )


def random_date(start: datetime, end: datetime) -> datetime:
    """
    Return a random datetime between start and end.
    Guards against start > end (returns start in that case).
    """
    if end <= start:
        return start
    delta = end - start
    return start + timedelta(days=random.randint(0, delta.days))


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------

def create_schema(cursor: sqlite3.Cursor) -> None:
    """Drop and recreate all tables."""
    cursor.executescript("""
        PRAGMA foreign_keys = OFF;

        DROP TABLE IF EXISTS invoices;
        DROP TABLE IF EXISTS treatments;
        DROP TABLE IF EXISTS appointments;
        DROP TABLE IF EXISTS doctors;
        DROP TABLE IF EXISTS patients;

        PRAGMA foreign_keys = ON;
    """)

    cursor.execute("""
        CREATE TABLE patients (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name      TEXT    NOT NULL,
            last_name       TEXT    NOT NULL,
            email           TEXT,
            phone           TEXT,
            date_of_birth   DATE,
            gender          TEXT    CHECK(gender IN ('M', 'F')),
            city            TEXT,
            registered_date DATE
        )
    """)

    cursor.execute("""
        CREATE TABLE doctors (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            name           TEXT NOT NULL,
            specialization TEXT,
            department     TEXT,
            phone          TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE appointments (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id       INTEGER,
            doctor_id        INTEGER,
            appointment_date DATETIME,
            status           TEXT CHECK(status IN (
                                 'Scheduled', 'Completed', 'Cancelled', 'No-Show'
                             )),
            notes            TEXT,
            FOREIGN KEY (patient_id) REFERENCES patients(id),
            FOREIGN KEY (doctor_id)  REFERENCES doctors(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE treatments (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id   INTEGER,
            treatment_name   TEXT,
            cost             REAL,
            duration_minutes INTEGER,
            FOREIGN KEY (appointment_id) REFERENCES appointments(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE invoices (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id   INTEGER,
            invoice_date DATE,
            total_amount REAL,
            paid_amount  REAL,
            status       TEXT CHECK(status IN ('Paid', 'Pending', 'Overdue')),
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        )
    """)

    print("  Schema created successfully")


# ---------------------------------------------------------------------------
# Data insertion
# ---------------------------------------------------------------------------

def insert_doctors(cursor: sqlite3.Cursor) -> List[int]:
    """
    Insert doctors evenly spread across all specializations.
    Always inserts exactly NUM_DOCTORS records.
    Returns list of inserted IDs.
    """
    doctor_ids      = []
    doctors_per_spec = NUM_DOCTORS // len(SPECIALIZATIONS)
    remainder        = NUM_DOCTORS  % len(SPECIALIZATIONS)

    for spec_idx, spec in enumerate(SPECIALIZATIONS):
        # Distribute remainder doctors across first N specializations
        count = doctors_per_spec + (1 if spec_idx < remainder else 0)
        dept  = DEPARTMENTS[spec]

        for _ in range(count):
            first = random.choice(FIRST_NAMES_MALE + FIRST_NAMES_FEMALE)
            last  = random.choice(LAST_NAMES)
            cursor.execute(
                "INSERT INTO doctors (name, specialization, department, phone) "
                "VALUES (?, ?, ?, ?)",
                (f"Dr. {first} {last}", spec, dept, generate_phone()),
            )
            doctor_ids.append(cursor.lastrowid)

    print(f"  Inserted {len(doctor_ids)} doctors "
          f"({NUM_DOCTORS // len(SPECIALIZATIONS)} per specialization)")
    return doctor_ids


def insert_patients(cursor: sqlite3.Cursor) -> List[int]:
    """Insert NUM_PATIENTS patients. Returns list of IDs."""
    patient_ids = []
    today       = datetime.now()
    three_years_ago = today - timedelta(days=365 * 3)

    for _ in range(NUM_PATIENTS):
        gender     = random.choice(["M", "F"])
        first_name = random.choice(
            FIRST_NAMES_MALE if gender == "M" else FIRST_NAMES_FEMALE
        )
        last_name = random.choice(LAST_NAMES)

        email = (
            generate_email(first_name, last_name)
            if random.random() > 0.1 else None
        )
        phone = generate_phone() if random.random() > 0.15 else None

        # Age 1–90 years
        age_days      = random.randint(365, 365 * 90)
        date_of_birth = (today - timedelta(days=age_days)).strftime("%Y-%m-%d")

        registered_date = random_date(three_years_ago, today).strftime("%Y-%m-%d")

        cursor.execute(
            "INSERT INTO patients "
            "(first_name, last_name, email, phone, "
            " date_of_birth, gender, city, registered_date) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                first_name, last_name, email, phone,
                date_of_birth, gender,
                random.choice(CITIES), registered_date,
            ),
        )
        patient_ids.append(cursor.lastrowid)

    print(f"  Inserted {len(patient_ids)} patients")
    return patient_ids


def insert_appointments(
    cursor: sqlite3.Cursor,
    patient_ids: List[int],
    doctor_ids: List[int],
) -> List[Tuple[int, str]]:
    """
    Insert NUM_APPOINTMENTS appointments.
    20% of patients are 'frequent' (get ~50% of appointments).
    30% of doctors are 'busy'    (get ~60% of appointments).
    Returns list of (appointment_id, status).
    """
    today           = datetime.now()
    one_year_ago    = today - timedelta(days=365)
    thirty_days_out = today + timedelta(days=30)

    frequent_patients = random.sample(
        patient_ids, k=max(1, int(len(patient_ids) * 0.2))
    )
    busy_doctors = random.sample(
        doctor_ids, k=max(1, int(len(doctor_ids) * 0.3))
    )

    appointments: List[Tuple[int, str]] = []

    for _ in range(NUM_APPOINTMENTS):
        patient_id = (
            random.choice(frequent_patients)
            if random.random() < 0.5
            else random.choice(patient_ids)
        )
        doctor_id = (
            random.choice(busy_doctors)
            if random.random() < 0.6
            else random.choice(doctor_ids)
        )

        appt_date = random_date(one_year_ago, thirty_days_out)

        # Future → always Scheduled; past → weighted random
        if appt_date > today:
            status = "Scheduled"
        else:
            status = random.choices(
                APPOINTMENT_STATUSES,
                weights=APPOINTMENT_WEIGHTS,
            )[0]

        cursor.execute(
            "INSERT INTO appointments "
            "(patient_id, doctor_id, appointment_date, status, notes) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                patient_id,
                doctor_id,
                appt_date.strftime("%Y-%m-%d %H:%M:%S"),
                status,
                random.choice(APPOINTMENT_NOTES),
            ),
        )
        appointments.append((cursor.lastrowid, status))

    # Status breakdown for info
    from collections import Counter
    status_counts = Counter(s for _, s in appointments)
    print(f"  Inserted {len(appointments)} appointments "
          f"({dict(status_counts)})")
    return appointments


def insert_treatments(
    cursor: sqlite3.Cursor,
    appointments: List[Tuple[int, str]],
) -> int:
    """
    Insert treatments for completed appointments only.
    If fewer completed appointments exist than NUM_TREATMENTS,
    inserts as many as possible and prints a warning.
    """
    completed_ids = [aid for aid, status in appointments if status == "Completed"]

    if not completed_ids:
        print("  WARNING: No completed appointments — 0 treatments inserted")
        return 0

    target = min(NUM_TREATMENTS, len(completed_ids))
    if target < NUM_TREATMENTS:
        print(
            f"  WARNING: Only {len(completed_ids)} completed appointments "
            f"available — inserting {target} treatments (requested {NUM_TREATMENTS})"
        )

    selected = random.sample(completed_ids, k=target)

    for appt_id in selected:
        cursor.execute(
            "INSERT INTO treatments "
            "(appointment_id, treatment_name, cost, duration_minutes) "
            "VALUES (?, ?, ?, ?)",
            (
                appt_id,
                random.choice(TREATMENT_NAMES),
                round(random.uniform(50, 5_000), 2),
                random.choice([15, 30, 45, 60, 90, 120]),
            ),
        )

    print(f"  Inserted {target} treatments")
    return target


def insert_invoices(cursor: sqlite3.Cursor, patient_ids: List[int]) -> int:
    """
    Insert NUM_INVOICES invoices spread across patients.
    Each patient may receive multiple invoices.
    """
    today        = datetime.now()
    one_year_ago = today - timedelta(days=365)

    # Select a subset of patients to receive invoices
    invoice_patient_pool = random.sample(
        patient_ids,
        k=min(NUM_INVOICES, len(patient_ids)),
    )

    invoice_count = 0
    for _ in range(NUM_INVOICES):
        patient_id   = random.choice(invoice_patient_pool)
        invoice_date = random_date(one_year_ago, today).strftime("%Y-%m-%d")
        total_amount = round(random.uniform(100, 10_000), 2)

        status = random.choices(INVOICE_STATUSES, weights=INVOICE_WEIGHTS)[0]

        if status == "Paid":
            paid_amount = total_amount
        elif status == "Pending":
            paid_amount = round(random.uniform(0, total_amount * 0.5), 2)
        else:   # Overdue
            paid_amount = round(random.uniform(0, total_amount * 0.3), 2)

        cursor.execute(
            "INSERT INTO invoices "
            "(patient_id, invoice_date, total_amount, paid_amount, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (patient_id, invoice_date, total_amount, paid_amount, status),
        )
        invoice_count += 1

    print(f"  Inserted {invoice_count} invoices")
    return invoice_count


# ---------------------------------------------------------------------------
# Summary report
# ---------------------------------------------------------------------------

def print_summary(cursor: sqlite3.Cursor) -> None:
    """Print a human-readable summary of every table."""
    print("\n" + "=" * 55)
    print("DATABASE SUMMARY")
    print("=" * 55)

    # Row counts
    for table in ["patients", "doctors", "appointments", "treatments", "invoices"]:
        try:
            count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table.capitalize():<15}: {count:>5} records")
        except Exception as exc:
            print(f"  {table.capitalize():<15}: ERROR — {exc}")

    # Appointment status breakdown
    print("\n  APPOINTMENT STATUS:")
    try:
        rows = cursor.execute(
            "SELECT status, COUNT(*) AS n FROM appointments "
            "GROUP BY status ORDER BY n DESC"
        ).fetchall()
        for status, n in rows:
            print(f"    {status:<12}: {n}")
    except Exception as exc:
        print(f"    ERROR — {exc}")

    # Invoice status breakdown
    print("\n  INVOICE STATUS:")
    try:
        rows = cursor.execute(
            "SELECT status, COUNT(*) AS n, "
            "ROUND(SUM(total_amount), 2) AS total "
            "FROM invoices GROUP BY status ORDER BY total DESC"
        ).fetchall()
        for status, n, total in rows:
            print(f"    {status:<10}: {n:>3} invoices  ${total:>12,.2f}")
    except Exception as exc:
        print(f"    ERROR — {exc}")

    # Top 5 cities by patient count
    print("\n  TOP 5 CITIES BY PATIENT COUNT:")
    try:
        rows = cursor.execute(
            "SELECT city, COUNT(*) AS n FROM patients "
            "GROUP BY city ORDER BY n DESC LIMIT 5"
        ).fetchall()
        for city, n in rows:
            print(f"    {city:<20}: {n} patients")
    except Exception as exc:
        print(f"    ERROR — {exc}")

    # Revenue summary
    print("\n  REVENUE SUMMARY:")
    try:
        row = cursor.execute(
            "SELECT "
            "  ROUND(SUM(total_amount), 2) AS total_billed, "
            "  ROUND(SUM(paid_amount),  2) AS total_collected, "
            "  ROUND(SUM(total_amount - paid_amount), 2) AS outstanding "
            "FROM invoices"
        ).fetchone()
        if row:
            print(f"    Total billed   : ${row[0]:>12,.2f}")
            print(f"    Total collected: ${row[1]:>12,.2f}")
            print(f"    Outstanding    : ${row[2]:>12,.2f}")
    except Exception as exc:
        print(f"    ERROR — {exc}")

    print("=" * 55)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Create the database from scratch."""
    # Set reproducible seed
    random.seed(RANDOM_SEED)
    print(f"Random seed: {RANDOM_SEED} (reproducible data)")

    # Remove existing DB
    if os.path.exists(DATABASE_PATH):
        os.remove(DATABASE_PATH)
        print(f"Removed existing {DATABASE_PATH}")

    conn   = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    print(f"\nCreating database: {DATABASE_PATH}")
    print("-" * 55)

    try:
        create_schema(cursor)
        doctor_ids   = insert_doctors(cursor)
        patient_ids  = insert_patients(cursor)
        appointments = insert_appointments(cursor, patient_ids, doctor_ids)
        insert_treatments(cursor, appointments)
        insert_invoices(cursor, patient_ids)
        conn.commit()
        print_summary(cursor)
        print(f"\nDatabase '{DATABASE_PATH}' created successfully!")

    except Exception as exc:
        conn.rollback()
        print(f"\nERROR creating database: {exc}")
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()