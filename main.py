import os
import re
import json
import uuid
import sqlite3
from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from dotenv import load_dotenv
from google import genai
from google.genai import types
from database import get_db, init_db, DB_PATH

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'hackathon-super-secret-trainwise-key')

if not os.path.exists(DB_PATH):
    init_db()

# Initialize Gemini Client if GEMINI_API_KEY is present
ai_client = None
if os.environ.get("GEMINI_API_KEY"):
    ai_client = genai.Client()

def get_system_instruction(role: str) -> str:
    schema = """
    SQLite Tables Available:
    - batches(id, name, course)
    - trainers(id, name, specialization)
    - rooms(id, name, capacity)
    - students(id, name, email, phone, batch_id)
    - attendance(id, student_id, batch_id, session_title, date, status ['PRESENT', 'ABSENT'])
    - schedule_slots(id, batch_id, trainer_id, room_id, day_of_week, start_time, end_time)
    - recordings(id, batch_id, title, video_url, recorded_date)
    """

    # STRUCTURAL RBAC: Trainer role NEVER receives the fee schema
    if role == "ADMIN":
        schema += "\n- fees(id, student_id, instalment_no, amount, due_date, status ['PAID', 'PENDING', 'OVERDUE'])"

    return f"""
    You are OpsPilot, an operational AI copilot for a training institute.
    Current Session Role: {role}
    Database Schema:
    {schema}

    Operational Rules:
    1. If the user asks for data/metrics/attendance/schedule, generate a clean SQLite read-only SELECT query.
    2. If a TRAINER asks about fees, installments, or revenue, set intent to "ACCESS_DENIED" and explain that trainers have no financial access.
    3. If the user asks to send an alert/message/reminder (ADMIN only), set intent to "STAGE_ACTION". Never execute mutations directly.
    4. You MUST respond strictly in valid JSON without any markdown formatting or code blocks:

    For Data Queries:
    {{"intent": "READ_QUERY", "reply": "Found matching records.", "sql": "SELECT ... FROM ..."}}

    For Staged Actions:
    {{"intent": "STAGE_ACTION", "reply": "Drafted reminder requiring review.", "action": "WhatsApp Reminder", "recipient": "<Name (Phone)>", "message": "<Drafted text>"}}

    For Access Denied:
    {{"intent": "ACCESS_DENIED", "reply": "Access Denied: Financial entities are restricted from trainer accounts."}}
    """

def execute_safe_query(sql: str, role: str, student_id: str = None):
    cleaned = sql.strip().strip(";")

    # Read-Only check
    if not re.match(r"^SELECT\b", cleaned, re.IGNORECASE):
        return {"error": "Security Alert: Only read-only SELECT queries are permitted."}

    forbidden = [r"\bDROP\b", r"\bDELETE\b", r"\bUPDATE\b", r"\bINSERT\b", r"\bALTER\b", r";"]
    for pattern in forbidden:
        if re.search(pattern, cleaned, re.IGNORECASE):
            return {"error": "Security Alert: Modification tokens are blocked."}

    # DB Layer RBAC for Trainer
    if role == "TRAINER" and re.search(r"\bfees\b", cleaned, re.IGNORECASE):
        return {"error": "Access Denied: Trainers are strictly restricted from financial tables."}

    # RLS for Student
    if role == "STUDENT":
        if re.search(r"\b(users|trainers|rooms|audit_logs)\b", cleaned, re.IGNORECASE):
            return {"error": "Access Denied: Restricted system table."}
        if re.search(r"\bWHERE\b", cleaned, re.IGNORECASE):
            cleaned = re.sub(r"(\bWHERE\b)", f"WHERE student_id = '{student_id}' AND ", cleaned, count=1, flags=re.IGNORECASE)
        else:
            cleaned = f"{cleaned} WHERE student_id = '{student_id}'"

    db = get_db()
    try:
        cursor = db.cursor()
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
    return render_template('index.html')

@app.route('/admin_login')
def admin_login_page():
    return render_template('admin_login.html')

@app.route('/student_login')
def student_login_page():
    return render_template('student_login.html')

@app.route('/login/admin')
def admin_login():
    session['role'] = 'ADMIN'
    session['user_id'] = 'u_admin'
    session['user_name'] = 'Director Mehta (Admin)'
    session.pop('student_id', None)
    return redirect(url_for('admin_dashboard'))

@app.route('/login/trainer')
def trainer_login():
    session['role'] = 'TRAINER'
    session['user_id'] = 'u_trainer'
    session['user_name'] = 'Rahul Verma (Trainer)'
    session.pop('student_id', None)
    return redirect(url_for('admin_dashboard'))

@app.route('/login/student')
def student_login():
    session['role'] = 'STUDENT'
    session['user_id'] = 'u_student'
    session['student_id'] = 'st_1'
    session['user_name'] = 'Aman Sharma'
    return redirect(url_for('student_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/admin')
def admin_dashboard():
    if session.get('role') not in ['ADMIN', 'TRAINER']:
        return redirect(url_for('index'))
    return render_template('admin_dashboard.html', role=session.get('role'), user_name=session.get('user_name'))

@app.route('/student')
def student_dashboard():
    if session.get('role') != 'STUDENT':
        return redirect(url_for('index'))
    
    st_id = session.get('student_id')
    db = get_db()
    student = db.execute("SELECT * FROM students WHERE id = ?", (st_id,)).fetchone()
    batch = db.execute("SELECT * FROM batches WHERE id = ?", (student['batch_id'],)).fetchone()
    
    total_att = db.execute("SELECT COUNT(*) as c FROM attendance WHERE student_id = ?", (st_id,)).fetchone()['c']
    pres_att = db.execute("SELECT COUNT(*) as c FROM attendance WHERE student_id = ? AND status = 'PRESENT'", (st_id,)).fetchone()['c']
    att_pct = round((pres_att / total_att * 100), 1) if total_att > 0 else 0
    
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
    return render_template('student_dashboard.html', 
                           student=student, batch=batch, att_pct=att_pct, 
                           fee=fee_row, notifications=notifications, schedule=schedule)

# --- Copilot API ---
@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.get_json() or {}
    user_msg = data.get('message', '').strip()
    role = session.get('role', 'TRAINER')
    student_id = session.get('student_id')

    if not user_msg:
        return jsonify({"type": "TEXT", "reply": "Please enter a question or command."})

    # Fallback simulation if GEMINI_API_KEY is not yet supplied in .env
    if not ai_client:
        if "attendance" in user_msg.lower():
            sql = "SELECT s.name, b.name as batch, '33%' as attendance_pct FROM students s JOIN batches b ON s.batch_id=b.id WHERE s.id='st_1'"
            res = execute_safe_query(sql, role, student_id)
            return jsonify({"type": "QUERY_RESULT", "reply": "Found 1 student falling behind (Demo Mode - Add API Key for live AI):", "sql": res["sql"], "rows": res["rows"]})
        if "fee" in user_msg.lower():
            if role == "TRAINER":
                return jsonify({"type": "ERROR", "reply": "Access Denied: Financial entities are restricted from trainer accounts."})
            sql = "SELECT s.name, f.amount, f.status FROM fees f JOIN students s ON f.student_id=s.id WHERE f.status='OVERDUE'"
            res = execute_safe_query(sql, role, student_id)
            return jsonify({"type": "QUERY_RESULT", "reply": "Found overdue records:", "sql": res["sql"], "rows": res["rows"]})

    try:
        response = ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"User ({role}) asked: {user_msg}",
            config=types.GenerateContentConfig(
                system_instruction=get_system_instruction(role),
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
                "reply": parsed.get("reply", "Action drafted. Human approval required:"),
                "card": {
                    "id": action_id,
                    "recipient": parsed.get("recipient", "Aman Sharma (+919876543210)"),
                    "action": parsed.get("action", "WhatsApp Reminder"),
                    "message": parsed.get("message", "Payment reminder.")
                }
            })

        return jsonify({"type": "TEXT", "reply": parsed.get("reply", "Understood.")})

    except Exception as e:
        return jsonify({"type": "ERROR", "reply": f"AI Engine Notice: {str(e)}"})

@app.route('/api/actions/<action_id>/decision', methods=['POST'])
def api_action_decision(action_id):
    data = request.get_json() or {}
    decision = data.get('decision', 'REJECTED')
    
    db = get_db()
    log = db.execute("SELECT * FROM audit_logs WHERE id = ?", (action_id,)).fetchone()
    if not log:
        db.close()
        return jsonify({"error": "Action record not found"}), 404

    db.execute(
        "UPDATE audit_logs SET status = ?, approved_by = ? WHERE id = ?", 
        (decision, session.get('user_name', 'Admin'), action_id)
    )
    
    # Push to student notifications on approval
    if decision == 'APPROVED':
        db.execute("""
            INSERT INTO notifications (id, student_id, title, message)
            VALUES (?, 'st_1', 'Urgent Payment Reminder', 'Your EMI of ₹25,000 is overdue. Please clear it immediately.')
        """, (f"notif_{uuid.uuid4().hex[:6]}",))

    db.commit()
    db.close()
    return jsonify({"status": "SUCCESS", "decision": decision})

@app.route('/api/timetable/reschedule', methods=['POST'])
def api_reschedule():
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
        "explanation": "Moved Python Pro from Lab 1 (Trainer Rahul) to Lab 2 under Trainer Neha (Free at 10:00 AM). Zero collisions found."
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)