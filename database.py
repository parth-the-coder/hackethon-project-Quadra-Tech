import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'trainwise.db')

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.executescript('''
    DROP TABLE IF EXISTS audit_logs;
    DROP TABLE IF EXISTS notifications;
    DROP TABLE IF EXISTS recordings;
    DROP TABLE IF EXISTS schedule_slots;
    DROP TABLE IF EXISTS fees;
    DROP TABLE IF EXISTS attendance;
    DROP TABLE IF EXISTS students;
    DROP TABLE IF EXISTS rooms;
    DROP TABLE IF EXISTS trainers;
    DROP TABLE IF EXISTS batches;
    DROP TABLE IF EXISTS users;

    CREATE TABLE users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        role TEXT NOT NULL, -- 'ADMIN', 'COUNSELOR', 'TRAINER', 'ACCOUNTS', 'STUDENT'
        student_id TEXT,
        trainer_id TEXT
    );

    CREATE TABLE batches (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        course TEXT NOT NULL
    );

    CREATE TABLE trainers (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        specialization TEXT NOT NULL
    );

    CREATE TABLE rooms (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        capacity INTEGER NOT NULL
    );

    CREATE TABLE students (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        batch_id TEXT REFERENCES batches(id)
    );

    CREATE TABLE attendance (
        id TEXT PRIMARY KEY,
        student_id TEXT REFERENCES students(id),
        batch_id TEXT REFERENCES batches(id),
        session_title TEXT NOT NULL,
        date DATE NOT NULL,
        status TEXT NOT NULL -- 'PRESENT', 'ABSENT'
    );

    CREATE TABLE fees (
        id TEXT PRIMARY KEY,
        student_id TEXT REFERENCES students(id),
        instalment_no INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        due_date DATE NOT NULL,
        status TEXT NOT NULL -- 'PAID', 'PENDING', 'OVERDUE'
    );

    CREATE TABLE schedule_slots (
        id TEXT PRIMARY KEY,
        batch_id TEXT REFERENCES batches(id),
        trainer_id TEXT REFERENCES trainers(id),
        room_id TEXT REFERENCES rooms(id),
        day_of_week TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL
    );

    CREATE TABLE recordings (
        id TEXT PRIMARY KEY,
        batch_id TEXT REFERENCES batches(id),
        title TEXT NOT NULL,
        video_url TEXT NOT NULL,
        recorded_date DATE NOT NULL
    );

    CREATE TABLE notifications (
        id TEXT PRIMARY KEY,
        student_id TEXT REFERENCES students(id),
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_read INTEGER DEFAULT 0
    );

    CREATE TABLE audit_logs (
        id TEXT PRIMARY KEY,
        action_type TEXT NOT NULL,
        target_entity TEXT NOT NULL,
        payload TEXT NOT NULL,
        status TEXT NOT NULL, -- 'PENDING_APPROVAL', 'APPROVED', 'REJECTED'
        approved_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Seed Users
    INSERT INTO users (id, name, email, role, student_id, trainer_id) VALUES
    ('u_admin', 'Director Mehta', 'admin@trainwise.com', 'ADMIN', NULL, NULL),
    ('u_trainer', 'Rahul Verma (Trainer)', 'rahul@trainwise.com', 'TRAINER', NULL, 'tr_1'),
    ('u_student', 'Aman Sharma', 'aman@trainwise.com', 'STUDENT', 'st_1', NULL);

    -- Seed Master Entities
    INSERT INTO batches (id, name, course) VALUES
    ('b_py', 'Python Full Stack', 'Software Engineering'),
    ('b_react', 'React Masters', 'Frontend Engineering');

    INSERT INTO trainers (id, name, specialization) VALUES
    ('tr_1', 'Rahul Verma', 'Python & Machine Learning'),
    ('tr_2', 'Neha Kulkarni', 'React, Node.js & FullStack');

    INSERT INTO rooms (id, name, capacity) VALUES
    ('rm_101', 'Lab 1 - AI', 30),
    ('rm_102', 'Lab 2 - Web', 25);

    -- Seed Students
    INSERT INTO students (id, name, email, phone, batch_id) VALUES
    ('st_1', 'Aman Sharma', 'aman@trainwise.com', '+919876543210', 'b_py'),
    ('st_2', 'Priya Patel', 'priya@trainwise.com', '+919876543211', 'b_py');

    -- Seed Attendance (Aman = 33% critical; Priya = 100%)
    INSERT INTO attendance (id, student_id, batch_id, session_title, date, status) VALUES
    ('att_1', 'st_1', 'b_py', 'Python Basics', '2026-10-10', 'ABSENT'),
    ('att_2', 'st_1', 'b_py', 'Data Structures', '2026-10-11', 'ABSENT'),
    ('att_3', 'st_1', 'b_py', 'OOPs in Python', '2026-10-12', 'PRESENT'),
    ('att_4', 'st_2', 'b_py', 'Python Basics', '2026-10-10', 'PRESENT'),
    ('att_5', 'st_2', 'b_py', 'Data Structures', '2026-10-11', 'PRESENT'),
    ('att_6', 'st_2', 'b_py', 'OOPs in Python', '2026-10-12', 'PRESENT');

    -- Seed Fees (Aman overdue)
    INSERT INTO fees (id, student_id, instalment_no, amount, due_date, status) VALUES
    ('fee_1', 'st_1', 1, 15000, '2026-09-01', 'PAID'),
    ('fee_2', 'st_1', 2, 25000, '2026-10-05', 'OVERDUE'),
    ('fee_3', 'st_2', 1, 40000, '2026-09-01', 'PAID');

    -- Seed Timetable Slots
    INSERT INTO schedule_slots (id, batch_id, trainer_id, room_id, day_of_week, start_time, end_time) VALUES
    ('slot_1', 'b_py', 'tr_1', 'rm_101', 'Monday', '10:00 AM', '12:00 PM'),
    ('slot_2', 'b_react', 'tr_2', 'rm_102', 'Monday', '02:00 PM', '04:00 PM');

    -- Seed Recordings
    INSERT INTO recordings (id, batch_id, title, video_url, recorded_date) VALUES
    ('rec_1', 'b_py', 'OOP Concepts & Decorators', 'https://example.com/rec/1', '2026-10-12');
    ''')

    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

if __name__ == '__main__':
    init_db()
    print("Database initialized at instance/trainwise.db")