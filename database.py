"""
Database initialisation and synthetic data seeding for
the Nurse Staffing & Roster Optimisation System.
"""

import sqlite3
import random
from datetime import date, timedelta

DB_PATH = "nurse_roster.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    # ── Staff table ──────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS staff (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            role        TEXT NOT NULL,
            grade       TEXT NOT NULL,
            skills      TEXT NOT NULL,
            contract_hours INTEGER NOT NULL,
            phone       TEXT,
            email       TEXT
        )
    """)

    # ── Availability table ───────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS availability (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id    INTEGER NOT NULL,
            date        TEXT NOT NULL,
            available   INTEGER NOT NULL DEFAULT 1,
            preferred_shift TEXT,
            FOREIGN KEY (staff_id) REFERENCES staff(id)
        )
    """)

    # ── Shifts table ─────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS shifts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            start_time  TEXT NOT NULL,
            end_time    TEXT NOT NULL,
            duration_hours REAL NOT NULL
        )
    """)

    # ── Roster table ─────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS roster (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id    INTEGER NOT NULL,
            shift_id    INTEGER NOT NULL,
            roster_date TEXT NOT NULL,
            status      TEXT DEFAULT 'draft',
            notes       TEXT,
            FOREIGN KEY (staff_id) REFERENCES staff(id),
            FOREIGN KEY (shift_id) REFERENCES shifts(id)
        )
    """)

    # ── Violations table ─────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS violations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            roster_id   INTEGER,
            staff_id    INTEGER,
            violation_type TEXT NOT NULL,
            description TEXT NOT NULL,
            severity    TEXT DEFAULT 'warning',
            resolved    INTEGER DEFAULT 0
        )
    """)

    # ── Approval table ───────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS approvals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            roster_date_start TEXT NOT NULL,
            roster_date_end   TEXT NOT NULL,
            status      TEXT DEFAULT 'pending',
            manager_name TEXT,
            comments    TEXT,
            approved_at TEXT
        )
    """)

    conn.commit()
    _seed_data(conn)
    conn.close()


def _seed_data(conn):
    c = conn.cursor()

    # Skip if already seeded
    c.execute("SELECT COUNT(*) FROM staff")
    if c.fetchone()[0] > 0:
        return

    # ── Shifts ───────────────────────────────────────────────────────────────
    shifts = [
        ("Morning",   "07:00", "15:00", 8.0),
        ("Afternoon", "15:00", "23:00", 8.0),
        ("Night",     "23:00", "07:00", 8.0),
        ("Long Day",  "07:00", "19:00", 12.0),
    ]
    c.executemany(
        "INSERT INTO shifts (name, start_time, end_time, duration_hours) VALUES (?,?,?,?)",
        shifts
    )

    # ── Staff pool (synthetic) ────────────────────────────────────────────────
    roles_grades = [
        ("RN",  "Senior",   ["IV therapy","Wound care","ICU","Triage"],        40),
        ("RN",  "Junior",   ["Basic care","Wound care","Medication admin"],    40),
        ("RN",  "Senior",   ["Paediatrics","IV therapy","Triage"],             40),
        ("RN",  "Senior",   ["Oncology","IV therapy","Palliative care"],       40),
        ("RN",  "Junior",   ["Basic care","Medication admin"],                 37),
        ("EN",  "Grade 2",  ["Personal care","Vital signs","Medication admin"],37),
        ("EN",  "Grade 2",  ["Personal care","Vital signs"],                   37),
        ("EN",  "Grade 1",  ["Personal care","Vital signs"],                   30),
        ("EN",  "Grade 1",  ["Personal care"],                                 30),
        ("RN",  "Senior",   ["ICU","IV therapy","Wound care","Triage"],        40),
        ("RN",  "Junior",   ["Paediatrics","Basic care","Medication admin"],   40),
        ("RN",  "Senior",   ["Emergency","Triage","IV therapy"],               40),
        ("RN",  "Junior",   ["Basic care","Wound care"],                       37),
        ("EN",  "Grade 2",  ["Vital signs","Medication admin","Personal care"],37),
        ("EN",  "Grade 1",  ["Personal care","Vital signs"],                   30),
        ("RN",  "Senior",   ["Oncology","Palliative care","IV therapy"],       40),
        ("RN",  "Junior",   ["Basic care","Medication admin","Wound care"],    37),
        ("EN",  "Grade 2",  ["Personal care","Vital signs","Medication admin"],37),
        ("RN",  "Senior",   ["ICU","Emergency","Triage","IV therapy"],         40),
        ("RN",  "Junior",   ["Basic care","Paediatrics"],                      40),
    ]

    first_names = ["Alice","Brian","Catherine","Daniel","Emma","Frank","Grace",
                   "Henry","Iris","James","Karen","Liam","Maya","Nathan","Olivia",
                   "Patrick","Quinn","Rachel","Steven","Tina"]
    last_names  = ["Smith","Johnson","Williams","Brown","Jones","Miller","Davis",
                   "Wilson","Moore","Taylor","Anderson","Thomas","Jackson","White",
                   "Harris","Martin","Thompson","Garcia","Martinez","Robinson"]

    random.seed(42)
    staff_ids = []
    for i, (role, grade, skills, hours) in enumerate(roles_grades):
        name  = f"{first_names[i]} {last_names[i]}"
        phone = f"04{random.randint(10,99)} {random.randint(100,999)} {random.randint(100,999)}"
        email = f"{first_names[i].lower()}.{last_names[i].lower()}@hospital.org"
        c.execute(
            "INSERT INTO staff (name, role, grade, skills, contract_hours, phone, email) VALUES (?,?,?,?,?,?,?)",
            (name, role, grade, ",".join(skills), hours, phone, email)
        )
        staff_ids.append(c.lastrowid)

    # ── Availability (2-week window starting next Monday) ─────────────────────
    today   = date.today()
    monday  = today + timedelta(days=(7 - today.weekday()) % 7 or 7)
    roster_start = monday
    roster_end   = monday + timedelta(days=13)

    shift_prefs = ["Morning","Afternoon","Night","Long Day", None]
    unavailable_days = {sid: set() for sid in staff_ids}

    for sid in staff_ids:
        # Randomly mark 1-2 days unavailable
        unavail = random.sample(range(14), random.randint(1, 2))
        for d in unavail:
            unavailable_days[sid].add(d)

    for day_offset in range(14):
        current_date = roster_start + timedelta(days=day_offset)
        for sid in staff_ids:
            available = 0 if day_offset in unavailable_days[sid] else 1
            pref = random.choice(shift_prefs) if available else None
            c.execute(
                "INSERT INTO availability (staff_id, date, available, preferred_shift) VALUES (?,?,?,?)",
                (sid, current_date.isoformat(), available, pref)
            )

    conn.commit()
    print(f"[DB] Seeded {len(staff_ids)} staff members. Roster window: {roster_start} – {roster_end}")
