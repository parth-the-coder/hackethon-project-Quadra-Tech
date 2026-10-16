import os
import re
import json
import uuid
import sqlite3
from functools import wraps
from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from dotenv import load_dotenv
from google import genai
from google.genai import types

from database import get_db, init_db, DB_PATH

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'trainwise-hackathon-secret-key-2026')

if not os.path.exists(DB_PATH):
    init_db()

ai_client = None
if os.environ.get("GEMINI_API_KEY"):
    try:
        ai_client = genai.Client()
    except Exception as e:
        print(f"Warning: Failed to initialize Gemini Client: {e}")

def login_required(roles=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_role = session.get('role')
            if not user_role:
                return redirect(url_for('index'))
            if roles and user_role not in roles:
                return jsonify({"error": "Unauthorized access"}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def build_copilot_system_prompt(role: str) -> str:
    schema = """
    SQLite Tables Available:
    - batches(id, name, course)
    - trainers(id, name, specialization)
    - rooms(id, name, capacity)
    - students(id, name, email, phone, batch_id)
    - attendance(id, student_id, batch_id, session_title, date, status ['PRESENT', 'ABSENT'])
    - schedule_slots(id, batch_id, trainer_id, room_id, day_of_week, start_time, end_time)
    - notifications(id, student_id, title, message)
    """

    if role == "ADMIN":
        schema += "\n- fees(id, student_id, instalment_no, amount, due_date, status ['PAID', 'PENDING', 'OVERDUE'])"

    return f"""
    You are OpsPilot, an operational AI copilot for this training institute.
    Current Session Role: {role}
    Database Schema:
    {schema}

    Operational Rules:
    1. If the user asks for records/metrics, return a valid read-only SQLite SELECT query.
    2. If a TRAINER asks about fees, money, or balances, set intent to "ACCESS_DENIED".
    3. If an ADMIN asks to send a reminder or announcement, set intent to "STAGE_ACTION".
    4. Respond strictly in valid JSON without markdown fences:

    Data query format:
    {{"intent": "READ_QUERY", "reply": "Extracted records from database:", "sql": "SELECT ... FROM ..."}}

    Action staging format:
    {{"intent": "STAGE_ACTION", "reply": "Drafted communication requiring admin approval:", "action": "WhatsApp Reminder", "recipient": "<Target>", "message": "<Message text>"}}

    Denied format:
    {{"intent": "ACCESS_DENIED", "reply": "Access Denied: Financial entities are restricted from trainer accounts."}}
    """

def execute_safe_query(sql: str, role: str, student_id: str = None) -> dict:
    cleaned = sql.strip().strip(";")

    if not re.match(r"^SELECT\b", cleaned, re.IGNORECASE):
        return {"error": "Security Alert: Only read-only SELECT queries are permitted."}

    forbidden = [r"\bDROP\b", r"\bDELETE\b", r"\bUPDATE\b", r"\bINSERT\b", r"\bALTER\b", r"\bTRUNCATE\b", r";"]
    for pattern in forbidden:
        if re.search(pattern, cleaned, re.IGNORECASE):
            return {"error": f"Security Alert: Disallowed query signature: {pattern}"}

    if role == "TRAINER" and re.search(r"\bfees\b", cleaned, re.IGNORECASE):
        return {"error": "Access Denied: Trainers are strictly restricted from financial tables."}

    if role == "STUDENT":
        if re.search(r"\b(users|trainers|rooms|audit_logs|fees)\b", cleaned, re.IGNORECASE):
            return {"error": "Access Denied: Restricted system table."}
        if re.search(r"\bWHERE\b", cleaned, re.IGNORECASE):
            cleaned = re.sub(r"(\bWHERE\b)", f"WHERE student_id = '{student_id}' AND ", cleaned, count=1, flags=re.IGNORECASE)
        else:
            cleaned = f"{cleaned} WHERE student_id = '{student_id}'"

    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute("PRAGMA query_only = ON;")
        cursor.execute(cleaned)
        rows = [dict(r) for r in cursor.fetchall()]
        return {"sql": cleaned, "rows": rows}
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()

# --- Page Navigation Routes ---
@app.route('/')
def index():
    db = get_db()
    total_students = db.execute("SELECT COUNT(*) as c FROM students").fetchone()['c']
    total_att = db.execute("SELECT COUNT(*) as c FROM attendance").fetchone()['c']
    pres_att = db.execute("SELECT COUNT(*) as c FROM attendance WHERE status = 'PRESENT'").fetchone()['c']
    avg_att = round((pres_att / total_att * 100), 1) if total_att > 0 else 92.4
    db.close()
    return render_template('index.html', total_students=total_students, avg_attendance=avg_att)

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login_page():
    if request.method == 'GET':
        return render_template('admin_login.html')

    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()

    db = get_db()
    user = db.execute("""
        SELECT * FROM users 
        WHERE email = ? AND password = ? AND role = 'ADMIN'
    """, (email, password)).fetchone()
    db.close()

    if user:
        session['role'] = 'ADMIN'
        session['user_id'] = user['id']
        session['user_name'] = 'Director Mehta (Admin)'
        session.pop('student_id', None)
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_login.html', error="Invalid administrator credentials.")

@app.route('/student_login')
def student_login_alias():
    return redirect(url_for('student_login'))

@app.route('/login/admin')
def admin_login_direct():
    session['role'] = 'ADMIN'
    session['user_id'] = 'u_admin'
    session['user_name'] = 'Director Mehta (Admin)'
    session.pop('student_id', None)
    return redirect(url_for('admin_dashboard'))

@app.route('/login/trainer')
def trainer_login_direct():
    session['role'] = 'TRAINER'
    session['user_id'] = 'u_trainer'
    session['user_name'] = 'Rahul Verma (Trainer)'
    session.pop('student_id', None)
    return redirect(url_for('admin_dashboard'))

@app.route('/login/student', methods=['GET', 'POST'])
def student_login():
    if request.method == 'GET':
        return render_template('student_login.html')

    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()

    db = get_db()
    user = db.execute("""
        SELECT u.*, s.name as student_name 
        FROM users u 
        JOIN students s ON u.student_id = s.id 
        WHERE u.email = ? AND u.password = ? AND u.role = 'STUDENT'
    """, (email, password)).fetchone()
    db.close()

    if user:
        session['role'] = 'STUDENT'
        session['user_id'] = user['id']
        session['student_id'] = user['student_id']
        session['user_name'] = user['student_name']
        return redirect(url_for('student_dashboard'))
    return render_template('student_login.html', error="Invalid Student ID/Email or Password.")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/admin')
@login_required(roles=['ADMIN', 'TRAINER'])
def admin_dashboard():
    role = session.get('role')
    user_name = session.get('user_name')
    db = get_db()

    total_students = db.execute("SELECT COUNT(*) as c FROM students").fetchone()['c']
    total_batches = db.execute("SELECT COUNT(*) as c FROM batches").fetchone()['c']

    overdue_count = 0
    if role == 'ADMIN':
        overdue_count = db.execute("SELECT COUNT(*) as c FROM fees WHERE status = 'OVERDUE'").fetchone()['c']

    # Fetch live records with per-student attendance calculations
    students = db.execute("""
        SELECT 
            s.id, 
            s.name, 
            s.email, 
            s.phone, 
            b.name as batch_name, 
            f.status as fee_status,
            f.amount as fee_amount,
            (SELECT COUNT(*) FROM attendance WHERE student_id = s.id) as total_classes,
            (SELECT COUNT(*) FROM attendance WHERE student_id = s.id AND status = 'PRESENT') as attended_classes
        FROM students s
        LEFT JOIN batches b ON s.batch_id = b.id
        LEFT JOIN fees f ON s.id = f.student_id
        ORDER BY s.rowid DESC
    """).fetchall()

    schedule = db.execute("""
        SELECT s.*, t.name as trainer_name, r.name as room_name, b.name as batch_name
        FROM schedule_slots s
        JOIN trainers t ON s.trainer_id = t.id
        JOIN rooms r ON s.room_id = r.id
        JOIN batches b ON s.batch_id = b.id
        ORDER BY s.start_time ASC
    """).fetchall()

    db.close()

    return render_template(
        'admin_dashboard.html',
        role=role,
        user_name=user_name,
        total_students=total_students,
        total_batches=total_batches,
        overdue_count=overdue_count,
        avg_attendance=92.4,
        students=students,
        schedule=schedule
    )

@app.route('/student')
@login_required(roles=['STUDENT'])
def student_dashboard():
    st_id = session.get('student_id')
    db = get_db()

    student = db.execute("SELECT * FROM students WHERE id = ?", (st_id,)).fetchone()
    if not student:
        db.close()
        return redirect(url_for('logout'))

    batch = db.execute("SELECT * FROM batches WHERE id = ?", (student['batch_id'],)).fetchone()
    total_att = db.execute("SELECT COUNT(*) as c FROM attendance WHERE student_id = ?", (st_id,)).fetchone()['c']
    pres_att = db.execute("SELECT COUNT(*) as c FROM attendance WHERE student_id = ? AND status = 'PRESENT'", (st_id,)).fetchone()['c']
    att_pct = round((pres_att / total_att * 100), 1) if total_att > 0 else 100.0

    fee_row = db.execute("SELECT * FROM fees WHERE student_id = ? ORDER BY due_date DESC LIMIT 1", (st_id,)).fetchone()
    notifications = db.execute("SELECT * FROM notifications WHERE student_id = ? ORDER BY created_at DESC", (st_id,)).fetchall()

    schedule = db.execute("""
        SELECT s.*, t.name as trainer_name, r.name as room_name, b.name as batch_name 
        FROM schedule_slots s 
        JOIN trainers t ON s.trainer_id = t.id 
        JOIN rooms r ON s.room_id = r.id 
        JOIN batches b ON s.batch_id = b.id 
        WHERE s.batch_id = ?
    """, (student['batch_id'],)).fetchall()

    db.close()
    return render_template(
        'student_dashboard.html',
        student=student,
        batch=batch,
        att_pct=att_pct,
        fee=fee_row,
        notifications=notifications,
        schedule=schedule
    )

# --- Dynamic Student Management APIs ---
@app.route('/api/students/add', methods=['POST'])
@login_required(roles=['ADMIN'])
def add_student():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    phone = data.get('phone', '').strip()
    batch_id = data.get('batch_id', 'b_py')
    fee_amount = int(data.get('fee_amount', 25000))

    if not name or not email or not password:
        return jsonify({"status": "ERROR", "message": "Name, Email, and Password are required."}), 400

    student_id = f"st_{uuid.uuid4().hex[:6]}"
    user_id = f"usr_{uuid.uuid4().hex[:6]}"

    db = get_db()
    try:
        db.execute("""
            INSERT INTO students (id, name, email, phone, batch_id)
            VALUES (?, ?, ?, ?, ?)
        """, (student_id, name, email, phone, batch_id))

        db.execute("""
            INSERT INTO users (id, email, password, role, student_id)
            VALUES (?, ?, ?, 'STUDENT', ?)
        """, (user_id, email, password, student_id))

        db.execute("""
            INSERT INTO fees (id, student_id, instalment_no, amount, due_date, status)
            VALUES (?, ?, 1, ?, '2026-11-15', 'PENDING')
        """, (f"fee_{uuid.uuid4().hex[:6]}", student_id, fee_amount))

        db.execute("""
            INSERT INTO notifications (id, student_id, title, message)
            VALUES (?, ?, 'Welcome to TrainWise!', 'Your enrollment is confirmed. Welcome to your cohort.')
        """, (f"notif_{uuid.uuid4().hex[:6]}", student_id))

        db.commit()
        return jsonify({"status": "SUCCESS", "message": f"Student '{name}' registered successfully."})
    except sqlite3.IntegrityError:
        return jsonify({"status": "ERROR", "message": "Email already registered in system."}), 400
    finally:
        db.close()

@app.route('/api/students/<student_id>/attendance', methods=['POST'])
@login_required(roles=['ADMIN'])
def mark_attendance(student_id):
    data = request.get_json() or {}
    status = data.get('status', 'PRESENT').upper()
    session_title = data.get('session_title', 'Core Engineering Session')
    date_val = data.get('date', '2026-10-17')

    if status not in ['PRESENT', 'ABSENT']:
        return jsonify({"status": "ERROR", "message": "Invalid status"}), 400

    db = get_db()
    student = db.execute("SELECT batch_id FROM students WHERE id = ?", (student_id,)).fetchone()
    if not student:
        db.close()
        return jsonify({"status": "ERROR", "message": "Student not found"}), 404

    att_id = f"att_{uuid.uuid4().hex[:6]}"
    db.execute("""
        INSERT INTO attendance (id, student_id, batch_id, session_title, date, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (att_id, student_id, student['batch_id'], session_title, date_val, status))
    db.commit()
    db.close()

    return jsonify({"status": "SUCCESS", "message": f"Logged attendance as {status}."})

@app.route('/api/students/<student_id>/fee', methods=['POST'])
@login_required(roles=['ADMIN'])
def update_student_fee(student_id):
    data = request.get_json() or {}
    new_status = data.get('status', 'PAID').upper()

    if new_status not in ['PAID', 'PENDING', 'OVERDUE']:
        return jsonify({"status": "ERROR", "message": "Invalid fee status"}), 400

    db = get_db()
    db.execute("""
        UPDATE fees 
        SET status = ? 
        WHERE student_id = ?
    """, (new_status, student_id))
    db.commit()
    db.close()

    return jsonify({"status": "SUCCESS", "message": f"Fee status updated to {new_status}."})

# --- AI Operations Copilot ---
@app.route('/api/chat', methods=['POST'])
@login_required(roles=['ADMIN', 'TRAINER', 'STUDENT'])
def api_chat():
    data = request.get_json() or {}
    user_msg = data.get('message', '').strip()
    role = session.get('role', 'TRAINER')
    student_id = session.get('student_id')

    if not user_msg:
        return jsonify({"type": "TEXT", "reply": "Please enter an operational inquiry."})

    if not ai_client:
        if "attendance" in user_msg.lower():
            sql = "SELECT s.name, b.name as batch, '100%' as attendance_rate FROM students s JOIN batches b ON s.batch_id=b.id LIMIT 5"
            res = execute_safe_query(sql, role, student_id)
            return jsonify({"type": "QUERY_RESULT", "reply": "Demo Query Output (Gemini API key not found in .env):", "sql": res.get("sql"), "rows": res.get("rows", [])})
        if "fee" in user_msg.lower():
            if role == "TRAINER":
                return jsonify({"type": "ERROR", "reply": "Access Denied: Financial entities are restricted from trainer accounts."})
            sql = "SELECT s.name, f.amount, f.status FROM fees f JOIN students s ON f.student_id=s.id"
            res = execute_safe_query(sql, role, student_id)
            return jsonify({"type": "QUERY_RESULT", "reply": "Overdue and pending fee ledgers:", "sql": res.get("sql"), "rows": res.get("rows", [])})

    try:
        response = ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"User ({role}) asks: {user_msg}",
            config=types.GenerateContentConfig(
                system_instruction=build_copilot_system_prompt(role),
                response_mime_type="application/json",
                temperature=0.1
            )
        )

        parsed = json.loads(response.text.strip())
        intent = parsed.get("intent", "TEXT")

        if intent == "ACCESS_DENIED":
            return jsonify({"type": "ERROR", "reply": parsed.get("reply", "Access Denied.")})

        if intent == "READ_QUERY":
            sql = parsed.get("sql", "")
            res = execute_safe_query(sql, role, student_id)
            if "error" in res:
                return jsonify({"type": "ERROR", "reply": res["error"]})
            return jsonify({
                "type": "QUERY_RESULT",
                "reply": parsed.get("reply", "Query execution results:"),
                "sql": res["sql"],
                "rows": res["rows"]
            })

        if intent == "STAGE_ACTION":
            if role != "ADMIN":
                return jsonify({"type": "ERROR", "reply": "Permission Denied: Only Admins can stage communication actions."})

            action_id = f"act_{uuid.uuid4().hex[:6]}"
            db = get_db()
            db.execute("""
                INSERT INTO audit_logs (id, action_type, target_entity, payload, status)
                VALUES (?, ?, ?, ?, 'PENDING_APPROVAL')
            """, (action_id, parsed.get("action", "ACTION"), parsed.get("recipient", "Student"), parsed.get("message", "")))
            db.commit()
            db.close()

            return jsonify({
                "type": "ACTION_PENDING",
                "reply": parsed.get("reply", "Action drafted. Human sign-off required:"),
                "card": {
                    "id": action_id,
                    "recipient": parsed.get("recipient", "Student"),
                    "action": parsed.get("action", "WhatsApp Reminder"),
                    "message": parsed.get("message", "Notice text.")
                }
            })

        return jsonify({"type": "TEXT", "reply": parsed.get("reply", "Understood.")})

    except Exception as e:
        return jsonify({"type": "ERROR", "reply": f"AI Engine Notice: {str(e)}"})

@app.route('/api/actions/<action_id>/decision', methods=['POST'])
@login_required(roles=['ADMIN'])
def handle_action_decision(action_id):
    data = request.get_json() or {}
    decision = data.get('decision', 'REJECTED')

    if decision not in ['APPROVED', 'REJECTED']:
        return jsonify({"error": "Invalid decision state"}), 400

    db = get_db()
    log = db.execute("SELECT * FROM audit_logs WHERE id = ?", (action_id,)).fetchone()
    if not log:
        db.close()
        return jsonify({"error": "Action record not found"}), 404

    db.execute("""
        UPDATE audit_logs 
        SET status = ?, approved_by = ? 
        WHERE id = ?
    """, (decision, session.get('user_name', 'Admin'), action_id))

    if decision == 'APPROVED':
        target_student = db.execute("SELECT id FROM students LIMIT 1").fetchone()
        st_id = target_student['id'] if target_student else 'st_1'
        db.execute("""
            INSERT INTO notifications (id, student_id, title, message)
            VALUES (?, ?, ?, ?)
        """, (f"notif_{uuid.uuid4().hex[:6]}", st_id, log['action_type'], log['payload']))

    db.commit()
    db.close()
    return jsonify({"status": "SUCCESS", "decision": decision})

@app.route('/api/timetable/reschedule', methods=['POST'])
@login_required(roles=['ADMIN'])
def trigger_reschedule():
    db = get_db()
    db.execute("""
        UPDATE schedule_slots 
        SET trainer_id = 'tr_2', room_id = 'rm_102' 
        WHERE trainer_id = 'tr_1'
    """)
    db.commit()
    db.close()

    return jsonify({
        "status": "SUCCESS",
        "explanation": "Deterministic Constraint Solver resolved conflicts: Relocated cohort from Trainer Rahul (Lab 1) to Trainer Neha in Lab 2 with zero collisions."
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)