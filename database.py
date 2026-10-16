import sqlite3
import os

DB_DIR = os.path.join(os.path.dirname(__file__), 'instance')
DB_PATH = os.path.join(DB_DIR, 'trainwise.db')

def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
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
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('ADMIN', 'TRAINER', 'STUDENT')),
        student_id TEXT REFERENCES students(id),
        trainer_id TEXT REFERENCES trainers(id)
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
        email TEXT NOT NULL UNIQUE,
        phone TEXT NOT NULL,
        batch_id TEXT REFERENCES batches(id)
    );

    CREATE TABLE attendance (
        id TEXT PRIMARY KEY,
        student_id TEXT REFERENCES students(id),
        batch_id TEXT REFERENCES batches(id),
        session_title TEXT NOT NULL,
        date DATE NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('PRESENT', 'ABSENT'))
    );

    CREATE TABLE fees (
        id TEXT PRIMARY KEY,
        student_id TEXT REFERENCES students(id),
        instalment_no INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        due_date DATE NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('PAID', 'PENDING', 'OVERDUE'))
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
        status TEXT NOT NULL,
        approved_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Base Batches, Rooms, and Trainers
    INSERT INTO batches (id, name, course) VALUES
    ('b_py', 'Python Full Stack', 'Software Engineering'),
    ('b_react', 'React Masters', 'Frontend Engineering');

    INSERT INTO trainers (id, name, specialization) VALUES
    ('tr_1', 'Rahul Verma', 'Python & Machine Learning'),
    ('tr_2', 'Neha Kulkarni', 'React & FullStack Architecture');

    INSERT INTO rooms (id, name, capacity) VALUES
    ('rm_101', 'Lab 1 - AI', 30),
    ('rm_102', 'Lab 2 - Web', 25);

    INSERT INTO schedule_slots (id, batch_id, trainer_id, room_id, day_of_week, start_time, end_time) VALUES
    ('slot_1', 'b_py', 'tr_1', 'rm_101', 'Monday', '10:00 AM', '12:00 PM'),
    ('slot_2', 'b_react', 'tr_2', 'rm_102', 'Monday', '02:00 PM', '04:00 PM');

    -- Base Staff Credentials (Admin & Trainer)
    INSERT INTO users (id, email, password, role, student_id, trainer_id) VALUES
    ('u_admin', 'admin@trainwise.com', 'admin123', 'ADMIN', NULL, NULL),
    ('u_trainer', 'rahul@trainwise.com', 'trainer123', 'TRAINER', NULL, 'tr_1');
    ''')

    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

if __name__ == '__main__':
    init_db()
    print("Database re-initialized without hardcoded students.")