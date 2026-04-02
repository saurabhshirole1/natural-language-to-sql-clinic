import sqlite3
import random
from datetime import datetime, timedelta

# This script creates the clinic database and fills it with dummy data
# Run this first before anything else

DB_PATH = "clinic.db"

FIRST_NAMES = [
    "Aarav", "Priya", "Rohan", "Sneha", "Arjun", "Kavya", "Vikram", "Ananya",
    "Rahul", "Pooja", "Amit", "Deepa", "Sanjay", "Meera", "Karan", "Nisha",
    "Dev", "Swati", "Raj", "Neha", "Aditya", "Isha", "Suresh", "Divya",
    "Ravi", "Preeti", "Ashok", "Sunita", "Mohan", "Geeta", "Varun", "Shreya",
    "Nikhil", "Pallavi", "Tarun", "Ankita", "Vishal", "Rekha", "Gaurav", "Smita"
]

LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Gupta", "Singh", "Kumar", "Mehta", "Joshi",
    "Rao", "Nair", "Iyer", "Shah", "Reddy", "Chopra", "Bose", "Das",
    "Malhotra", "Chauhan", "Pandey", "Mishra"
]

CITIES = [
    "Mumbai", "Pune", "Delhi", "Bangalore", "Chennai",
    "Hyderabad", "Kolkata", "Ahmedabad", "Jaipur", "Surat"
]

SPECIALIZATIONS = ["Dermatology", "Cardiology", "Orthopedics", "General", "Pediatrics"]

DEPARTMENTS = {
    "Dermatology": "Skin Care",
    "Cardiology": "Heart & Vascular",
    "Orthopedics": "Bone & Joint",
    "General": "General Medicine",
    "Pediatrics": "Child Health"
}

DOCTOR_NAMES = [
    "Dr. Rajan Mehta", "Dr. Priya Nair", "Dr. Suresh Gupta", "Dr. Anita Sharma", "Dr. Vivek Patel",
    "Dr. Sunita Rao", "Dr. Anil Kumar", "Dr. Deepa Joshi", "Dr. Manoj Singh", "Dr. Kavita Verma",
    "Dr. Rajesh Iyer", "Dr. Smita Das", "Dr. Prakash Shah", "Dr. Leela Reddy", "Dr. Harsh Chopra"
]

TREATMENT_NAMES = {
    "Dermatology": ["Acne Treatment", "Skin Biopsy", "Laser Therapy", "Chemical Peel", "Botox"],
    "Cardiology": ["ECG", "Echocardiogram", "Stress Test", "Angioplasty", "Holter Monitor"],
    "Orthopedics": ["X-Ray", "Joint Injection", "Physiotherapy", "Bone Density Test", "Arthroscopy"],
    "General": ["Blood Test", "Urine Analysis", "Vaccination", "BP Check", "General Checkup"],
    "Pediatrics": ["Vaccination", "Growth Check", "Nebulization", "Hearing Test", "Eye Checkup"]
}

STATUSES = ["Scheduled", "Completed", "Cancelled", "No-Show"]
INVOICE_STATUSES = ["Paid", "Pending", "Overdue"]


def random_date(days_back=365):
    """Returns a random date within the past N days"""
    return datetime.now() - timedelta(days=random.randint(0, days_back))


def random_phone():
    """Generates a random Indian-style phone number"""
    return f"+91 {random.randint(70000, 99999)}{random.randint(10000, 99999)}"


def random_email(first, last):
    """Generates a realistic-looking email"""
    domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com"]
    return f"{first.lower()}.{last.lower()}{random.randint(1, 99)}@{random.choice(domains)}"


def create_tables(conn):
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            date_of_birth DATE,
            gender TEXT,
            city TEXT,
            registered_date DATE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            specialization TEXT,
            department TEXT,
            phone TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            doctor_id INTEGER,
            appointment_date DATETIME,
            status TEXT,
            notes TEXT,
            FOREIGN KEY (patient_id) REFERENCES patients(id),
            FOREIGN KEY (doctor_id) REFERENCES doctors(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS treatments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id INTEGER,
            treatment_name TEXT,
            cost REAL,
            duration_minutes INTEGER,
            FOREIGN KEY (appointment_id) REFERENCES appointments(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            invoice_date DATE,
            total_amount REAL,
            paid_amount REAL,
            status TEXT,
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        )
    """)

    conn.commit()
    print("Tables created successfully.")


def insert_doctors(conn):
    c = conn.cursor()
    # 15 doctors, 3 per specialization
    doctors = []
    spec_cycle = SPECIALIZATIONS * 3  # gives 15 total

    for i, name in enumerate(DOCTOR_NAMES):
        spec = spec_cycle[i]
        dept = DEPARTMENTS[spec]
        phone = random_phone() if random.random() > 0.1 else None
        doctors.append((name, spec, dept, phone))

    c.executemany(
        "INSERT INTO doctors (name, specialization, department, phone) VALUES (?,?,?,?)",
        doctors
    )
    conn.commit()
    return len(doctors)


def insert_patients(conn):
    c = conn.cursor()
    patients = []

    for _ in range(200):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        # some patients won't have email or phone - makes it more realistic
        email = random_email(first, last) if random.random() > 0.15 else None
        phone = random_phone() if random.random() > 0.1 else None
        dob = random_date(365 * 60)  # up to 60 years back
        gender = random.choice(["M", "F"])
        city = random.choice(CITIES)
        reg_date = random_date(730)  # registered in last 2 years

        patients.append((first, last, email, phone,
                         dob.strftime("%Y-%m-%d"), gender, city,
                         reg_date.strftime("%Y-%m-%d")))

    c.executemany(
        """INSERT INTO patients
           (first_name, last_name, email, phone, date_of_birth, gender, city, registered_date)
           VALUES (?,?,?,?,?,?,?,?)""",
        patients
    )
    conn.commit()
    return len(patients)


def insert_appointments(conn):
    c = conn.cursor()

    # get all patient and doctor ids
    patient_ids = [row[0] for row in c.execute("SELECT id FROM patients").fetchall()]
    doctor_rows = c.execute("SELECT id, specialization FROM doctors").fetchall()

    # some patients should have many appointments (repeat visitors)
    # weights: some patients are "frequent visitors"
    weights = [random.choices([1, 3, 5], weights=[60, 30, 10])[0] for _ in patient_ids]

    appointments = []
    for _ in range(500):
        # pick patient with weighted frequency
        patient_id = random.choices(patient_ids, weights=weights)[0]
        doctor_id, spec = random.choice(doctor_rows)
        appt_date = random_date(365)  # past 12 months
        status = random.choices(STATUSES, weights=[15, 55, 20, 10])[0]
        notes = None
        if random.random() > 0.4:
            notes = random.choice([
                "Follow-up needed", "Patient doing well", "Medication adjusted",
                "Lab reports required", "Referred to specialist", None
            ])

        appointments.append((patient_id, doctor_id,
                              appt_date.strftime("%Y-%m-%d %H:%M:%S"),
                              status, notes))

    c.executemany(
        """INSERT INTO appointments
           (patient_id, doctor_id, appointment_date, status, notes)
           VALUES (?,?,?,?,?)""",
        appointments
    )
    conn.commit()
    return len(appointments)


def insert_treatments(conn):
    c = conn.cursor()

    # only completed appointments get treatments
    completed = c.execute(
        "SELECT a.id, d.specialization FROM appointments a "
        "JOIN doctors d ON d.id = a.doctor_id WHERE a.status = 'Completed'"
    ).fetchall()

    treatments = []
    count = 0
    for appt_id, spec in completed:
        if count >= 350:
            break
        t_name = random.choice(TREATMENT_NAMES.get(spec, ["General Checkup"]))
        cost = round(random.uniform(50, 5000), 2)
        duration = random.randint(15, 120)
        treatments.append((appt_id, t_name, cost, duration))
        count += 1

    c.executemany(
        "INSERT INTO treatments (appointment_id, treatment_name, cost, duration_minutes) VALUES (?,?,?,?)",
        treatments
    )
    conn.commit()
    return len(treatments)


def insert_invoices(conn):
    c = conn.cursor()

    patient_ids = [row[0] for row in c.execute("SELECT id FROM patients").fetchall()]
    invoices = []

    for _ in range(300):
        patient_id = random.choice(patient_ids)
        inv_date = random_date(365)
        total = round(random.uniform(200, 8000), 2)
        status = random.choices(INVOICE_STATUSES, weights=[55, 30, 15])[0]

        if status == "Paid":
            paid = total
        elif status == "Pending":
            paid = round(random.uniform(0, total * 0.5), 2)
        else:  # Overdue
            paid = round(random.uniform(0, total * 0.3), 2)

        invoices.append((patient_id, inv_date.strftime("%Y-%m-%d"), total, paid, status))

    c.executemany(
        "INSERT INTO invoices (patient_id, invoice_date, total_amount, paid_amount, status) VALUES (?,?,?,?,?)",
        invoices
    )
    conn.commit()
    return len(invoices)


def main():
    conn = sqlite3.connect(DB_PATH)

    create_tables(conn)

    num_doctors = insert_doctors(conn)
    num_patients = insert_patients(conn)
    num_appointments = insert_appointments(conn)
    num_treatments = insert_treatments(conn)
    num_invoices = insert_invoices(conn)

    conn.close()

    print(f"\nDatabase setup complete! Summary:")
    print(f"  Created {num_doctors} doctors")
    print(f"  Created {num_patients} patients")
    print(f"  Created {num_appointments} appointments")
    print(f"  Created {num_treatments} treatments")
    print(f"  Created {num_invoices} invoices")
    print(f"\nDatabase saved to: {DB_PATH}")


if __name__ == "__main__":
    main()
