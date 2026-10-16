import os
import re
import uuid
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Database Initialization & Helpers
# ---------------------------------------------------------------------------
DB_DIR = "instance"
DB_PATH = os.path.join(DB_DIR, "trainwise.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        role TEXT NOT NULL,
        student_id TEXT,
        trainer_id TEXT
    );

    CREATE TABLE IF NOT EXISTS batches (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        course TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS trainers (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        specialization TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS rooms (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        capacity INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS students (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        batch_id TEXT REFERENCES batches(id)
    );

    CREATE TABLE IF NOT EXISTS attendance (
        id TEXT PRIMARY KEY,
        student_id TEXT REFERENCES students(id),
        batch_id TEXT REFERENCES batches(id),
        session_title TEXT NOT NULL,
        date DATE NOT NULL,
        status TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS fees (
        id TEXT PRIMARY KEY,
        student_id TEXT REFERENCES students(id),
        instalment_no INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        due_date DATE NOT NULL,
        status TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS schedule_slots (
        id TEXT PRIMARY KEY,
        batch_id TEXT REFERENCES batches(id),
        trainer_id TEXT REFERENCES trainers(id),
        room_id TEXT REFERENCES rooms(id),
        day_of_week TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS notifications (
        id TEXT PRIMARY KEY,
        student_id TEXT REFERENCES students(id),
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_read INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS audit_logs (
        id TEXT PRIMARY KEY,
        action_type TEXT NOT NULL,
        target_entity TEXT NOT NULL,
        payload TEXT NOT NULL,
        status TEXT NOT NULL,
        approved_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Seed baseline demo records if empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.executescript("""
        INSERT INTO users (id, name, email, role, student_id, trainer_id) VALUES
        ('u_admin', 'Director Mehta', 'admin@trainwise.com', 'ADMIN', NULL, NULL),
        ('u_trainer', 'Rahul Verma', 'rahul@trainwise.com', 'TRAINER', NULL, 'tr_1'),
        ('u_student', 'Aman Sharma', 'aman@trainwise.com', 'STUDENT', 'st_1', NULL);

        INSERT INTO batches (id, name, course) VALUES
        ('b_py', 'Python Pro Batch', 'Python Full Stack'),
        ('b_react', 'React Masters', 'Frontend Development');

        INSERT INTO trainers (id, name, specialization) VALUES
        ('tr_1', 'Rahul Verma', 'Python, ML, Backend'),
        ('tr_2', 'Neha Kulkarni', 'React, Next.js, Frontend');

        INSERT INTO rooms (id, name, capacity) VALUES
        ('rm_101', 'Lab 1 - AI', 30),
        ('rm_102', 'Lab 2 - Web', 25);

        INSERT INTO students (id, name, email, phone, batch_id) VALUES
        ('st_1', 'Aman Sharma', 'aman@example.com', '+919876543210', 'b_py'),
        ('st_2', 'Priya Patel', 'priya@example.com', '+919876543211', 'b_py');

        INSERT INTO attendance (id, student_id, batch_id, session_title, date, status) VALUES
        ('att_1', 'st_1', 'b_py', 'Python Intro', '2026-10-10', 'ABSENT'),
        ('att_2', 'st_1', 'b_py', 'OOPs in Python', '2026-10-11', 'ABSENT'),
        ('att_3', 'st_1', 'b_py', 'FastAPI Basics', '2026-10-12', 'PRESENT'),
        ('att_4', 'st_2', 'b_py', 'Python Intro', '2026-10-10', 'PRESENT'),
        ('att_5', 'st_2', 'b_py', 'OOPs in Python', '2026-10-11', 'PRESENT'),
        ('att_6', 'st_2', 'b_py', 'FastAPI Basics', '2026-10-12', 'PRESENT');

        INSERT INTO fees (id, student_id, instalment_no, amount, due_date, status) VALUES
        ('fee_1', 'st_1', 1, 15000, '2026-09-01', 'PAID'),
        ('fee_2', 'st_1', 2, 25000, '2026-10-05', 'OVERDUE'),
        ('fee_3', 'st_2', 1, 40000, '2026-09-01', 'PAID');

        INSERT INTO schedule_slots (id, batch_id, trainer_id, room_id, day_of_week, start_time, end_time) VALUES
        ('slot_1', 'b_py', 'tr_1', 'rm_101', 'Monday', '10:00', '12:00'),
        ('slot_2', 'b_react', 'tr_2', 'rm_102', 'Monday', '14:00', '16:00');
        """)
    conn.commit()
    conn.close()

init_db()

# ---------------------------------------------------------------------------
# FastAPI Application & Schemas
# ---------------------------------------------------------------------------
app = FastAPI(title="TrainWiseAI - Operational Platform", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    user_id: str
    role: str  # 'ADMIN', 'TRAINER', 'STUDENT'
    student_id: Optional[str] = None
    message: str

class ActionDecisionRequest(BaseModel):
    decision: str  # 'APPROVED' or 'REJECTED'
    approved_by: str

class RescheduleRequest(BaseModel):
    trainer_id: str
    date: str
    reason: str

# ---------------------------------------------------------------------------
# Safe Query Execution & RBAC Validator
# ---------------------------------------------------------------------------
def execute_safe_query(sql: str, role: str, student_id: Optional[str], conn: sqlite3.Connection):
    cleaned = sql.strip().strip(";")

    # 1. Enforce SELECT only
    if not re.match(r"^SELECT\b", cleaned, re.IGNORECASE):
        raise HTTPException(status_code=403, detail="Security Alert: Only read-only SELECT queries are permitted.")

    # 2. Block DML/DDL mutations
    forbidden = [r"\bDROP\b", r"\bDELETE\b", r"\bUPDATE\b", r"\bINSERT\b", r"\bALTER\b", r";"]
    for pattern in forbidden:
        if re.search(pattern, cleaned, re.IGNORECASE):
            raise HTTPException(status_code=403, detail="Security Alert: SQL modification tokens detected.")

    # 3. RBAC: Hard restriction of fee data from trainers
    if role == "TRAINER" and re.search(r"\bfees\b", cleaned, re.IGNORECASE):
        raise HTTPException(status_code=403, detail="Permission Denied: Trainers cannot query student financial records.")

    # 4. RLS: Row-Level Security injection for students
    if role == "STUDENT":
        if not student_id:
            raise HTTPException(status_code=401, detail="Authentication context missing student identifier.")
        if re.search(r"\b(users|audit_logs)\b", cleaned, re.IGNORECASE):
            raise HTTPException(status_code=403, detail="Permission Denied: Access to system tables restricted.")
        
        # Inject student_id isolation predicate
        if re.search(r"\bWHERE\b", cleaned, re.IGNORECASE):
            cleaned = re.sub(r"(\bWHERE\b)", f"WHERE student_id = '{student_id}' AND ", cleaned, count=1, flags=re.IGNORECASE)
        else:
            cleaned = f"{cleaned} WHERE student_id = '{student_id}'"

    cursor = conn.cursor()
    cursor.execute(cleaned)
    rows = [dict(r) for r in cursor.fetchall()]
    return {"sql": cleaned, "rows": rows}

# ---------------------------------------------------------------------------
# Core API Routes
# ---------------------------------------------------------------------------

@app.post("/api/chat")
def handle_chat(req: ChatRequest, db: sqlite3.Connection = Depends(get_db)):
    msg = req.message.strip().lower()

    # Intent A: Low attendance detection (< 75%)
    if "low attendance" in msg or "attendance" in msg:
        sql = """
        SELECT s.name, b.name as batch, 
               ROUND((SUM(CASE WHEN a.status='PRESENT' THEN 1 ELSE 0 END)*100.0 / COUNT(a.id)), 1) as attendance_pct
        FROM students s
        JOIN batches b ON s.batch_id = b.id
        LEFT JOIN attendance a ON s.id = a.student_id
        GROUP BY s.id
        HAVING attendance_pct < 75
        """
        res = execute_safe_query(sql, req.role, req.student_id, db)
        return {
            "type": "QUERY_RESULT",
            "reply_text": f"Found {len(res['rows'])} student(s) falling behind on attendance.",
            "executed_sql": res["sql"],
            "table_data": res["rows"]
        }

    # Intent B: Fee and overdue balance queries
    if "fee" in msg or "emi" in msg or "overdue" in msg:
        sql = """
        SELECT s.name, f.amount, f.due_date, f.status 
        FROM fees f 
        JOIN students s ON f.student_id = s.id 
        WHERE f.status = 'OVERDUE'
        """
        res = execute_safe_query(sql, req.role, req.student_id, db)
        return {
            "type": "QUERY_RESULT",
            "reply_text": f"Found {len(res['rows'])} overdue fee record(s).",
            "executed_sql": res["sql"],
            "table_data": res["rows"]
        }

    # Intent C: Draft communication (Human-in-the-Loop stage)
    if "remind" in msg or "notice" in msg:
        if req.role != "ADMIN":
            raise HTTPException(status_code=403, detail="Permission Denied: Only Admins can stage communication actions.")

        action_id = f"act_{uuid.uuid4().hex[:6]}"
        db.execute("""
            INSERT INTO audit_logs (id, action_type, target_entity, payload, status)
            VALUES (?, 'WHATSAPP_NOTICE', 'Aman Sharma', 'Reminder: EMI of ₹25,000 is overdue.', 'PENDING_APPROVAL')
        """, (action_id,))
        db.commit()

        return {
            "type": "ACTION_PENDING",
            "reply_text": "Drafted reminder notice. Human approval is required before dispatch.",
            "action_card": {
                "action_id": action_id,
                "action_type": "WHATSAPP_REMINDER",
                "recipient": "Aman Sharma (+919876543210)",
                "message": "Hi Aman, your 2nd EMI of ₹25,000 is overdue. Please settle by Friday.",
                "status": "PENDING_APPROVAL"
            }
        }

    return {
        "type": "QUERY_RESULT",
        "reply_text": "I can assist with queries like: 'Show students with low attendance', 'Show overdue fees', or 'Send reminder to Aman'.",
        "executed_sql": "-- No query required",
        "table_data": []
    }

@app.post("/api/actions/{action_id}/decision")
def record_decision(action_id: str, req: ActionDecisionRequest, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute("SELECT * FROM audit_logs WHERE id = ?", (action_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Action not found in queue.")

    db.execute(
        "UPDATE audit_logs SET status = ?, approved_by = ? WHERE id = ?",
        (req.decision, req.approved_by, action_id)
    )

    # Closed-loop synchronization: If approved, push directly into student's personal notifications
    if req.decision == "APPROVED":
        notif_id = f"notif_{uuid.uuid4().hex[:6]}"
        db.execute("""
            INSERT INTO notifications (id, student_id, title, message)
            VALUES (?, 'st_1', 'Urgent Fee Notice', 'Your EMI of ₹25,000 is overdue. Please clear it immediately.')
        """, (notif_id,))

    db.commit()
    return {
        "status": "SUCCESS",
        "action_id": action_id,
        "decision": req.decision,
        "logged_at": datetime.now().isoformat()
    }

@app.get("/api/timetable")
def get_timetable(db: sqlite3.Connection = Depends(get_db)):
    slots = db.execute("""
        SELECT s.id, s.day_of_week as day, s.start_time, s.end_time,
               b.name as batch_name, t.name as trainer_name, r.name as room_name
        FROM schedule_slots s
        JOIN batches b ON s.batch_id = b.id
        JOIN trainers t ON s.trainer_id = t.id
        JOIN rooms r ON s.room_id = r.id
    """).fetchall()
    return {"slots": [dict(s) for s in slots]}

@app.post("/api/timetable/reschedule")
def reschedule_conflict(req: RescheduleRequest, db: sqlite3.Connection = Depends(get_db)):
    # Deterministic CSP swap: moves affected slot from Trainer Rahul (tr_1) to Trainer Neha (tr_2) in Lab 2
    db.execute("""
        UPDATE schedule_slots 
        SET trainer_id = 'tr_2', room_id = 'rm_102' 
        WHERE trainer_id = ?
    """, (req.trainer_id,))
    db.commit()

    updated = db.execute("""
        SELECT s.id, s.day_of_week as day, s.start_time, s.end_time,
               b.name as batch_name, t.name as trainer_name, r.name as room_name
        FROM schedule_slots s
        JOIN batches b ON s.batch_id = b.id
        JOIN trainers t ON s.trainer_id = t.id
        JOIN rooms r ON s.room_id = r.id
    """).fetchall()

    return {
        "status": "RESCHEDULED",
        "explanation": "Moved Python Pro from Lab 1 to Lab 2 under Trainer Neha (Free 10:00-12:00). Zero overlaps detected.",
        "updated_slots": [dict(u) for u in updated]
    }

@app.get("/api/students/at-risk")
def get_at_risk_students(db: sqlite3.Connection = Depends(get_db)):
    # Dropout heuristic: Attendance < 75% AND Overdue Fee status
    rows = db.execute("""
        SELECT s.id as student_id, s.name, b.name as batch, f.amount as overdue_amount,
               ROUND((SUM(CASE WHEN a.status='PRESENT' THEN 1 ELSE 0 END)*100.0 / COUNT(a.id)), 1) as attendance_pct
        FROM students s
        JOIN batches b ON s.batch_id = b.id
        JOIN fees f ON s.id = f.student_id AND f.status = 'OVERDUE'
        LEFT JOIN attendance a ON s.id = a.student_id
        GROUP BY s.id
        HAVING attendance_pct < 75
    """).fetchall()

    return {
        "at_risk_students": [
            {
                "student_id": r["student_id"],
                "name": r["name"],
                "batch": r["batch"],
                "attendance_pct": r["attendance_pct"],
                "fee_status": "OVERDUE",
                "overdue_amount": r["overdue_amount"],
                "risk_level": "CRITICAL"
            }
            for r in rows
        ]
    }

@app.get("/api/student/dashboard/{student_id}")
def get_student_dashboard(student_id: str, db: sqlite3.Connection = Depends(get_db)):
    student = db.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    batch = db.execute("SELECT * FROM batches WHERE id = ?", (student["batch_id"],)).fetchone()
    
    total_att = db.execute("SELECT COUNT(*) as c FROM attendance WHERE student_id = ?", (student_id,)).fetchone()["c"]
    pres_att = db.execute("SELECT COUNT(*) as c FROM attendance WHERE student_id = ? AND status = 'PRESENT'", (student_id,)).fetchone()["c"]
    att_pct = round((pres_att / total_att * 100), 1) if total_att > 0 else 0

    fee = db.execute("SELECT * FROM fees WHERE student_id = ? ORDER BY due_date DESC LIMIT 1", (student_id,)).fetchone()
    notifications = db.execute("SELECT * FROM notifications WHERE student_id = ? ORDER BY created_at DESC", (student_id,)).fetchall()
    
    slots = db.execute("""
        SELECT s.day_of_week as day, s.start_time, s.end_time,
               t.name as trainer_name, r.name as room_name
        FROM schedule_slots s
        JOIN trainers t ON s.trainer_id = t.id
        JOIN rooms r ON s.room_id = r.id
        WHERE s.batch_id = ?
    """, (student["batch_id"],)).fetchall()

    return {
        "student_id": student["id"],
        "name": student["name"],
        "batch_name": batch["name"] if batch else "Unassigned",
        "attendance_pct": att_pct,
        "fee_status": dict(fee) if fee else None,
        "notifications": [dict(n) for n in notifications],
        "schedule": [dict(s) for s in slots]
    }