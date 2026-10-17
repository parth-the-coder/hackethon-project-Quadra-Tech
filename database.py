import os
import sqlite3

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'opspilot.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS batches (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            course TEXT NOT NULL
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trainers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            specialization TEXT NOT NULL
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            capacity INTEGER NOT NULL
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT NOT NULL,
            batch_id TEXT,
            FOREIGN KEY (batch_id) REFERENCES batches (id)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT CHECK(role IN ('ADMIN', 'TRAINER', 'STUDENT')) NOT NULL,
            student_id TEXT,
            FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fees (
            id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL,
            instalment_no INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            due_date TEXT NOT NULL,
            status TEXT CHECK(status IN ('PAID', 'PENDING', 'OVERDUE')) NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL,
            batch_id TEXT NOT NULL,
            session_title TEXT NOT NULL,
            date TEXT NOT NULL,
            status TEXT CHECK(status IN ('PRESENT', 'ABSENT')) NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
            FOREIGN KEY (batch_id) REFERENCES batches (id)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schedule_slots (
            id TEXT PRIMARY KEY,
            batch_id TEXT NOT NULL,
            trainer_id TEXT NOT NULL,
            room_id TEXT NOT NULL,
            day_of_week TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            FOREIGN KEY (batch_id) REFERENCES batches (id),
            FOREIGN KEY (trainer_id) REFERENCES trainers (id),
            FOREIGN KEY (room_id) REFERENCES rooms (id)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
        );
    """)

    cursor.execute("SELECT COUNT(*) FROM batches")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO batches VALUES (?, ?, ?)", [
            ('b_py', 'Python Full Stack', 'Python & Flask Development'),
            ('b_react', 'React Masters', 'Modern React & TypeScript')
        ])

        cursor.executemany("INSERT INTO trainers VALUES (?, ?, ?)", [
            ('tr_1', 'Rahul Verma', 'Full Stack Architecture & Python'),
            ('tr_2', 'Neha Sharma', 'Frontend Ecosystems & React')
        ])

        cursor.executemany("INSERT INTO rooms VALUES (?, ?, ?)", [
            ('rm_101', 'Lab 1 — Turing Hall', 35),
            ('rm_102', 'Lab 2 — Lovelace Suite', 30)
        ])

        cursor.executemany("INSERT INTO users VALUES (?, ?, ?, ?, ?)", [
            ('u_admin', 'admin@trainwise.com', 'admin123', 'ADMIN', None),
            ('u_trainer', 'rahul@trainwise.com', 'trainer123', 'TRAINER', None)
        ])

        initial_students = [
            ('st_1', 'Parth Tellawar', 'parth@trainwise.com', '+91 9823011223', 'b_py'),
            ('st_2', 'Jignesh Musale', 'jignesh@trainwise.com', '+91 9823044556', 'b_react'),
            ('st_3', 'Siddhika Maddalwar', 'siddhika@trainwise.com', '+91 9823077889', 'b_py')
        ]
        cursor.executemany("INSERT INTO students VALUES (?, ?, ?, ?, ?)", initial_students)

        cursor.executemany("INSERT INTO users VALUES (?, ?, ?, ?, ?)", [
            ('usr_st_1', 'parth@trainwise.com', 'pass123', 'STUDENT', 'st_1'),
            ('usr_st_2', 'jignesh@trainwise.com', 'pass123', 'STUDENT', 'st_2'),
            ('usr_st_3', 'siddhika@trainwise.com', 'pass123', 'STUDENT', 'st_3')
        ])

        cursor.executemany("INSERT INTO fees VALUES (?, ?, ?, ?, ?, ?)", [
            ('fee_1', 'st_1', 1, 25000, '2026-10-05', 'OVERDUE'),
            ('fee_2', 'st_2', 1, 30000, '2026-10-15', 'PENDING'),
            ('fee_3', 'st_3', 1, 25000, '2026-09-20', 'PAID')
        ])

        cursor.executemany("INSERT INTO attendance VALUES (?, ?, ?, ?, ?, ?)", [
            ('att_1', 'st_1', 'b_py', 'Python Syntax & Data Structures', '2026-10-10', 'PRESENT'),
            ('att_2', 'st_1', 'b_py', 'Flask Routing & RESTful Design', '2026-10-12', 'PRESENT'),
            ('att_3', 'st_1', 'b_py', 'SQLite Engine & Schema Relationality', '2026-10-14', 'ABSENT'),
            ('att_4', 'st_2', 'b_react', 'Component Lifecycle & Virtual DOM', '2026-10-11', 'PRESENT'),
            ('att_5', 'st_2', 'b_react', 'React Hooks & State Architecture', '2026-10-13', 'PRESENT'),
            ('att_6', 'st_3', 'b_py', 'Python Syntax & Data Structures', '2026-10-10', 'PRESENT'),
            ('att_7', 'st_3', 'b_py', 'Flask Routing & RESTful Design', '2026-10-12', 'PRESENT'),
            ('att_8', 'st_3', 'b_py', 'SQLite Engine & Schema Relationality', '2026-10-14', 'PRESENT')
        ])

        cursor.executemany("INSERT INTO schedule_slots VALUES (?, ?, ?, ?, ?, ?, ?)", [
            ('sch_1', 'b_py', 'tr_1', 'rm_101', 'Monday', '09:00 AM', '11:00 AM'),
            ('sch_2', 'b_react', 'tr_2', 'rm_102', 'Monday', '11:30 AM', '01:30 PM'),
            ('sch_3', 'b_py', 'tr_1', 'rm_101', 'Wednesday', '09:00 AM', '11:00 AM'),
            ('sch_4', 'b_react', 'tr_2', 'rm_102', 'Wednesday', '11:30 AM', '01:30 PM'),
            ('sch_5', 'b_py', 'tr_1', 'rm_101', 'Friday', '09:00 AM', '11:00 AM'),
            ('sch_6', 'b_react', 'tr_2', 'rm_102', 'Friday', '11:30 AM', '01:30 PM')
        ])

        cursor.executemany("INSERT INTO notifications VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)", [
            ('notif_1', 'st_1', 'Tuition Overdue Warning', 'Your first installment of ₹25,000 was due on October 5th. Please clear it immediately.'),
            ('notif_2', 'st_2', 'Upcoming Lab Relocation', 'Wednesday React session will be conducted in Lab 2 Lovelace Suite.'),
            ('notif_3', 'st_3', 'Welcome to Python Full Stack', 'Your registration is complete. Check your schedule tab for lecture timings.')
        ])

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print(f"OpsPilot database verified at: {DB_PATH}")