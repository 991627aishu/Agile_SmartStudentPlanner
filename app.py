from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
from functools import wraps
import re
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_change_this_in_production'

# ─── SQLite config ───────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'ssp.db')
os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

# ─── Password validation helper ─────────────────────────────────
def validate_password(password):
    """Validate password: min 6 chars, at least one uppercase, one lowercase, one digit, one special char"""
    if len(password) < 6:
        return False, "Password must be at least 6 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'\d', password):
        return False, "Password must contain at least one digit"
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    return True, ""

# ─── DB helpers ─────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Create all tables if they don't exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at    TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id     INTEGER PRIMARY KEY,
            daily_hours REAL DEFAULT 6,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS subjects (
            subject_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER NOT NULL,
            subject_name     TEXT NOT NULL,
            exam_date        TEXT NOT NULL,
            syllabus_size    INTEGER NOT NULL,
            difficulty_level INTEGER NOT NULL,
            created_at       TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS tasks (
            task_id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER NOT NULL,
            subject_id     INTEGER,
            title          TEXT NOT NULL,
            description    TEXT,
            due_date       TEXT NOT NULL,
            status         TEXT DEFAULT 'PENDING'
                               CHECK(status IN ('PENDING','IN_PROGRESS','COMPLETED','SKIPPED','OVERDUE')),
            priority_score INTEGER DEFAULT 3,
            created_at     TEXT DEFAULT (datetime('now')),
            updated_at     TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id)    REFERENCES users(user_id)    ON DELETE CASCADE,
            FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS daily_timetable (
            timetable_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            subject_id      INTEGER NOT NULL,
            timetable_date  TEXT NOT NULL,
            allocated_hours REAL NOT NULL,
            UNIQUE (user_id, subject_id, timetable_date),
            FOREIGN KEY (user_id)    REFERENCES users(user_id)    ON DELETE CASCADE,
            FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS study_logs (
            log_id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id           INTEGER NOT NULL,
            subject_id        INTEGER NOT NULL,
            study_date        TEXT NOT NULL,
            actual_study_time REAL NOT NULL,
            completion_status TEXT NOT NULL
                                  CHECK(completion_status IN ('COMPLETED','PARTIAL','SKIPPED')),
            stress_level      INTEGER DEFAULT 1,
            sleep_hours       REAL DEFAULT 7,
            created_at        TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id)    REFERENCES users(user_id)    ON DELETE CASCADE,
            FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS performance (
            performance_id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id               INTEGER UNIQUE NOT NULL,
            completion_percentage REAL DEFAULT 0,
            consistency_score     REAL DEFAULT 0,
            stress_score          REAL DEFAULT 0,
            recorded_date         TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS recommendations (
            recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id           INTEGER NOT NULL,
            message           TEXT NOT NULL,
            created_date      TEXT DEFAULT (date('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS notifications (
            notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            title           TEXT NOT NULL,
            message         TEXT NOT NULL,
            is_read         INTEGER DEFAULT 0,
            created_at      TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    conn.close()

# ─── Jinja filter ──────────────────────────────────────────────
@app.template_filter('days_until')
def days_until_filter(date_str):
    try:
        target = datetime.strptime(str(date_str)[:10], '%Y-%m-%d').date()
        return max((target - date.today()).days, 0)
    except:
        return 0

@app.template_filter('format_hours')
def format_hours_filter(hours):
    """Convert decimal hours to hours and minutes format"""
    try:
        hours_float = float(hours)
        hrs = int(hours_float)
        mins = int((hours_float - hrs) * 60)
        if hrs == 0:
            return f"{mins} min"
        elif mins == 0:
            return f"{hrs} hr"
        else:
            return f"{hrs} hr {mins} min"
    except:
        return f"{hours} hrs"
    
@app.context_processor
def inject_globals():
    """Make these variables available in ALL templates"""
    unread_count = 0
    if 'user_id' in session:
        try:
            conn = get_db()
            result = conn.execute(
                "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
                (session['user_id'],)
            )
            unread_count = result.fetchone()[0]
            conn.close()
        except Exception as e:
            print(f"Error getting notifications: {e}")
    
    return {
        'now': datetime.now(),
        'today': date.today(),
        'enumerate': enumerate,
        'min': min,
        'max': max,
        'round': round,
        'unread_notifications': unread_count
    }

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ─── Priority algorithm ────────────────────────────────────────
def calculate_priority(exam_date_str, syllabus_size, difficulty):
    try:
        today_d = date.today()
        exam_d = datetime.strptime(exam_date_str, '%Y-%m-%d').date()
        days_left = max((exam_d - today_d).days, 1)
        urgency = 100 / days_left
        normalized_syllabus = min(syllabus_size / 50, 2)
        return round((urgency * 0.5) + (normalized_syllabus * 0.3) + (difficulty * 0.4), 2)
    except:
        return 10.0

# ─── Multi‑day timetable generation ────────────────────────────
def calculate_daily_allocation(subjects, daily_hours, target_date):
    allocations = []
    for s in subjects:
        exam_date = datetime.strptime(s['exam_date'], '%Y-%m-%d').date()
        days_until_exam = (exam_date - target_date).days
        if days_until_exam > 0:
            urgency = max(0.1, 1.0 - (days_until_exam / max(days_until_exam, 30)))
            base_priority = calculate_priority(s['exam_date'], s['syllabus_size'], s['difficulty_level'])
            final_priority = base_priority * (1 + urgency)
            allocations.append({
                'subject_id': s['subject_id'],
                'subject_name': s['subject_name'],
                'priority': final_priority,
                'exam_date': s['exam_date']
            })
    if not allocations:
        return []
    total_priority = sum(a['priority'] for a in allocations)
    for a in allocations:
        a['allocated_hours'] = round((a['priority'] / total_priority) * daily_hours, 2)
    return allocations

def generate_timetable_internal(user_id, daily_hours):
    conn = get_db()
    subjects = conn.execute("SELECT * FROM subjects WHERE user_id = ?", (user_id,)).fetchall()
    if not subjects:
        conn.close()
        return False
    
    exam_dates = [datetime.strptime(s['exam_date'], '%Y-%m-%d').date() for s in subjects]
    last_exam = max(exam_dates)
    today_date = date.today()
    
    conn.execute("DELETE FROM daily_timetable WHERE user_id = ? AND timetable_date >= date('now')", (user_id,))
    
    current_date = today_date
    while current_date <= last_exam:
        daily_plan = calculate_daily_allocation(subjects, daily_hours, current_date)
        for plan in daily_plan:
            conn.execute(
                "INSERT OR REPLACE INTO daily_timetable (user_id, subject_id, timetable_date, allocated_hours) VALUES (?,?,?,?)",
                (user_id, plan['subject_id'], current_date.isoformat(), plan['allocated_hours'])
            )
        current_date += timedelta(days=1)
    
    conn.commit()
    conn.close()
    return True

# ─── Adaptive rescheduling ──────────────────────────────────────
def adaptive_reschedule(user_id, subject_id, status):
    conn = get_db()
    pref = conn.execute("SELECT daily_hours FROM user_preferences WHERE user_id=?", (user_id,)).fetchone()
    daily_hours = pref['daily_hours'] if pref else 6
    subjects = conn.execute("SELECT * FROM subjects WHERE user_id=?", (user_id,)).fetchall()
    if not subjects:
        conn.close()
        return
    rows = []
    for s in subjects:
        p = calculate_priority(s['exam_date'], s['syllabus_size'], s['difficulty_level'])
        if s['subject_id'] == subject_id:
            p *= 1.5 if status == 'SKIPPED' else 1.2
        rows.append({'subject_id': s['subject_id'], 'priority': p})
    total_p = sum(r['priority'] for r in rows) or 1
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    conn.execute("DELETE FROM daily_timetable WHERE user_id=? AND timetable_date=?", (user_id, tomorrow))
    for r in rows:
        alloc = round((r['priority'] / total_p) * daily_hours, 2)
        conn.execute("INSERT OR REPLACE INTO daily_timetable (user_id, subject_id, timetable_date, allocated_hours) VALUES (?,?,?,?)",
                     (user_id, r['subject_id'], tomorrow, alloc))
    conn.commit()
    conn.close()

# ─── Notification helpers ──────────────────────────────────────
def create_notification(user_id, title, message):
    conn = get_db()
    conn.execute("""
        INSERT INTO notifications (user_id, title, message, is_read, created_at)
        VALUES (?, ?, ?, 0, datetime('now'))
    """, (user_id, title, message))
    conn.commit()
    conn.close()

def check_upcoming_exams_and_tasks(user_id):
    conn = get_db()
    today_str = date.today().isoformat()
    
    exams = conn.execute("""
        SELECT subject_name, exam_date, 
               CAST(julianday(exam_date) - julianday('now') AS INTEGER) AS days_left
        FROM subjects
        WHERE user_id=? AND exam_date BETWEEN date('now') AND date('now', '+3 days')
    """, (user_id,)).fetchall()
    
    for exam in exams:
        create_notification(
            user_id,
            "📚 Exam Coming Soon!",
            f"Your exam for {exam['subject_name']} is in {exam['days_left']} day(s). Keep studying!"
        )
    
    overdue = conn.execute("""
        SELECT title, due_date FROM tasks
        WHERE user_id=? AND due_date < ? AND status != 'COMPLETED'
    """, (user_id, today_str)).fetchall()
    
    for task in overdue:
        create_notification(
            user_id,
            "⚠️ Task Overdue",
            f"Task '{task['title']}' was due on {task['due_date']}. Please update it."
        )
    conn.close()

# ════════════════════════════════════════════════════════════════
#  ROUTES
# ════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        confirm_password = request.form.get('confirm_password', '')
        
        # Check if passwords match
        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return redirect(url_for('register'))
        
        # Validate password strength
        is_valid, msg = validate_password(password)
        if not is_valid:
            flash(msg, 'error')
            return redirect(url_for('register'))
        
        conn = get_db()
        existing = conn.execute("SELECT user_id FROM users WHERE email=?", (email,)).fetchone()
        if existing:
            conn.close()
            flash('Email already registered!', 'error')
            return redirect(url_for('register'))
        
        hashed = generate_password_hash(password)
        conn.execute("INSERT INTO users (name, email, password_hash) VALUES (?,?,?)", (name, email, hashed))
        conn.commit()
        conn.close()
        flash('Account created! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['user_id']
            session['user_name'] = user['name']
            return redirect(url_for('dashboard'))
        flash('Invalid email or password!', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    uid = session['user_id']
    today_str = date.today().isoformat()
    conn = get_db()
    def count(sql, *params):
        return conn.execute(sql, params).fetchone()[0]
    total_tasks = count("SELECT COUNT(*) FROM tasks WHERE user_id=?", uid)
    completed = count("SELECT COUNT(*) FROM tasks WHERE user_id=? AND status='COMPLETED'", uid)
    pending = count("SELECT COUNT(*) FROM tasks WHERE user_id=? AND status='PENDING'", uid)
    in_progress = count("SELECT COUNT(*) FROM tasks WHERE user_id=? AND status='IN_PROGRESS'", uid)
    skipped = count("SELECT COUNT(*) FROM tasks WHERE user_id=? AND status='SKIPPED'", uid)
    total_subjects = count("SELECT COUNT(*) FROM subjects WHERE user_id=?", uid)
    
    upcoming_exams = conn.execute("""
        SELECT subject_name, exam_date,
               CAST(julianday(exam_date) - julianday('now') AS INTEGER) AS days_left
        FROM subjects
        WHERE user_id=? AND exam_date >= date('now')
        ORDER BY exam_date ASC LIMIT 5
    """, (uid,)).fetchall()
    
    todays_plan = conn.execute("""
        SELECT dt.allocated_hours, s.subject_name, s.difficulty_level, s.exam_date
        FROM daily_timetable dt
        JOIN subjects s ON dt.subject_id = s.subject_id
        WHERE dt.user_id=? AND dt.timetable_date=?
        ORDER BY dt.allocated_hours DESC
    """, (uid, today_str)).fetchall()
    
    completion_rate = round(completed / total_tasks * 100, 1) if total_tasks > 0 else 0
    recent_recs = conn.execute("""
        SELECT message, created_date FROM recommendations
        WHERE user_id=? ORDER BY created_date DESC LIMIT 3
    """, (uid,)).fetchall()
    
    # Get study streak
    streak_data = conn.execute("""
        SELECT study_date FROM study_logs 
        WHERE user_id=? 
        ORDER BY study_date DESC LIMIT 30
    """, (uid,)).fetchall()
    
    streak = 0
    if streak_data:
        check_date = date.today()
        for log in streak_data:
            log_date = datetime.strptime(log['study_date'], '%Y-%m-%d').date()
            if log_date == check_date:
                streak += 1
                check_date -= timedelta(days=1)
            elif log_date == check_date - timedelta(days=1):
                streak += 1
                check_date -= timedelta(days=1)
            else:
                break
    
    conn.close()
    
    check_upcoming_exams_and_tasks(uid)
    
    return render_template('dashboard.html',
        total_tasks=total_tasks, completed=completed,
        pending=pending, in_progress=in_progress, skipped=skipped,
        total_subjects=total_subjects,
        upcoming_exams=upcoming_exams,
        todays_plan=todays_plan,
        completion_rate=completion_rate,
        recent_recs=recent_recs,
        streak=streak)

@app.route('/subjects', methods=['GET', 'POST'])
@login_required
def subjects():
    uid = session['user_id']
    conn = get_db()
    if request.method == 'POST':
        conn.execute(
            "INSERT INTO subjects (user_id, subject_name, exam_date, syllabus_size, difficulty_level) VALUES (?,?,?,?,?)",
            (uid, request.form['subject_name'], request.form['exam_date'],
             int(request.form['syllabus_size']), int(request.form['difficulty_level']))
        )
        conn.commit()
        flash('Subject added successfully!', 'success')
    subj_list = conn.execute("SELECT * FROM subjects WHERE user_id=? ORDER BY exam_date ASC", (uid,)).fetchall()
    pref = conn.execute("SELECT daily_hours FROM user_preferences WHERE user_id=?", (uid,)).fetchone()
    conn.close()
    return render_template('subjects.html', subjects=subj_list, daily_hours=pref['daily_hours'] if pref else 6)

@app.route('/subjects/delete/<int:sid>')
@login_required
def delete_subject(sid):
    conn = get_db()
    conn.execute("DELETE FROM subjects WHERE subject_id=? AND user_id=?", (sid, session['user_id']))
    conn.commit()
    conn.close()
    flash('Subject deleted.', 'success')
    return redirect(url_for('subjects'))

@app.route('/generate_timetable', methods=['POST'])
@login_required
def gen_timetable():
    uid = session['user_id']
    daily_hours = float(request.form.get('daily_hours', 6))
    if daily_hours < 1: daily_hours = 4
    if daily_hours > 16: daily_hours = 12
    conn = get_db()
    conn.execute("""
        INSERT INTO user_preferences (user_id, daily_hours) VALUES (?,?)
        ON CONFLICT(user_id) DO UPDATE SET daily_hours = excluded.daily_hours
    """, (uid, daily_hours))
    subject_count = conn.execute("SELECT COUNT(*) FROM subjects WHERE user_id = ?", (uid,)).fetchone()[0]
    conn.close()
    if subject_count == 0:
        flash('❌ Please add at least one subject first!', 'error')
        return redirect(url_for('subjects'))
    success = generate_timetable_internal(uid, daily_hours)
    if success:
        flash('✅ Multi-day timetable generated! Planned from today until your last exam.', 'success')
        create_notification(uid, "🎉 Timetable Generated", "Your smart multi-day study plan is ready. Check the Planner!")
    else:
        flash('⚠️ Failed to generate timetable.', 'error')
    return redirect(url_for('planner'))

@app.route('/tasks', methods=['GET', 'POST'])
@login_required
def tasks():
    uid = session['user_id']
    conn = get_db()
    if request.method == 'POST':
        conn.execute(
            "INSERT INTO tasks (user_id, subject_id, title, description, due_date, priority_score) VALUES (?,?,?,?,?,?)",
            (uid, request.form.get('subject_id') or None, request.form['title'],
             request.form.get('description', ''), request.form['due_date'],
             int(request.form.get('priority_score', 3)))
        )
        conn.commit()
        flash('Task created!', 'success')
    task_list = conn.execute("""
        SELECT t.*, s.subject_name
        FROM tasks t LEFT JOIN subjects s ON t.subject_id = s.subject_id
        WHERE t.user_id=? ORDER BY 
            CASE t.status 
                WHEN 'PENDING' THEN 1
                WHEN 'IN_PROGRESS' THEN 2
                WHEN 'OVERDUE' THEN 3
                WHEN 'COMPLETED' THEN 4
                ELSE 5
            END,
            t.due_date ASC
    """, (uid,)).fetchall()
    subj_list = conn.execute("SELECT * FROM subjects WHERE user_id=?", (uid,)).fetchall()
    conn.close()
    return render_template('tasks.html', tasks=task_list, subjects=subj_list)

@app.route('/tasks/update_status/<int:tid>', methods=['POST'])
@login_required
def update_task_status(tid):
    conn = get_db()
    conn.execute("UPDATE tasks SET status=?, updated_at=datetime('now') WHERE task_id=? AND user_id=?",
                 (request.form['status'], tid, session['user_id']))
    conn.commit()
    conn.close()
    return redirect(url_for('tasks'))

@app.route('/tasks/delete/<int:tid>')
@login_required
def delete_task(tid):
    conn = get_db()
    conn.execute("DELETE FROM tasks WHERE task_id=? AND user_id=?", (tid, session['user_id']))
    conn.commit()
    conn.close()
    return redirect(url_for('tasks'))

@app.route('/planner')
@app.route('/planner/<date_str>')
@login_required
def planner(date_str=None):
    uid = session['user_id']
    if date_str:
        try:
            view_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except:
            view_date = date.today()
    else:
        view_date = date.today()
    conn = get_db()
    todays_plan = conn.execute("""
        SELECT dt.allocated_hours, s.subject_name, s.exam_date, s.difficulty_level
        FROM daily_timetable dt JOIN subjects s ON dt.subject_id = s.subject_id
        WHERE dt.user_id=? AND dt.timetable_date=?
        ORDER BY dt.allocated_hours DESC
    """, (uid, view_date.isoformat())).fetchall()
    upcoming_tasks = conn.execute("""
        SELECT t.*, s.subject_name
        FROM tasks t LEFT JOIN subjects s ON t.subject_id = s.subject_id
        WHERE t.user_id=? AND t.due_date >= date('now') AND t.status != 'COMPLETED'
        ORDER BY t.due_date ASC LIMIT 10
    """, (uid,)).fetchall()
    pref = conn.execute("SELECT daily_hours FROM user_preferences WHERE user_id=?", (uid,)).fetchone()
    subjects = conn.execute("SELECT subject_name, exam_date FROM subjects WHERE user_id=?", (uid,)).fetchall()
    conn.close()
    prev_day = view_date - timedelta(days=1)
    next_day = view_date + timedelta(days=1)
    return render_template('planner.html',
                           todays_plan=todays_plan,
                           upcoming_tasks=upcoming_tasks,
                           daily_hours=pref['daily_hours'] if pref else 6,
                           view_date=view_date,
                           prev_day=prev_day.isoformat(),
                           next_day=next_day.isoformat(),
                           subjects=subjects)

@app.route('/progress', methods=['GET', 'POST'])
@login_required
def progress():
    uid = session['user_id']
    conn = get_db()
    if request.method == 'POST':
        subject_id = int(request.form['subject_id'])
        actual_hours = float(request.form['actual_hours'])
        completion_status = request.form['completion_status']
        stress_level = int(request.form.get('stress_level', 1))
        sleep_hours = float(request.form.get('sleep_hours', 7))
        today_str = date.today().isoformat()
        conn.execute("""
            INSERT INTO study_logs (user_id, subject_id, study_date, actual_study_time, completion_status, stress_level, sleep_hours)
            VALUES (?,?,?,?,?,?,?)
        """, (uid, subject_id, today_str, actual_hours, completion_status, stress_level, sleep_hours))
        total = conn.execute("SELECT COUNT(*) FROM tasks WHERE user_id=?", (uid,)).fetchone()[0] or 1
        done = conn.execute("SELECT COUNT(*) FROM tasks WHERE user_id=? AND status='COMPLETED'", (uid,)).fetchone()[0]
        cp = round(done / total * 100, 1)
        avg_stress = conn.execute("SELECT AVG(stress_level) FROM study_logs WHERE user_id=?", (uid,)).fetchone()[0] or 1
        conn.execute("""
            INSERT INTO performance (user_id, completion_percentage, consistency_score, stress_score, recorded_date)
            VALUES (?,?,?,?,date('now'))
            ON CONFLICT(user_id) DO UPDATE SET
              completion_percentage=excluded.completion_percentage,
              consistency_score=excluded.consistency_score,
              stress_score=excluded.stress_score,
              recorded_date=excluded.recorded_date
        """, (uid, cp, round(cp * 0.8, 1), round(avg_stress, 2)))
        if stress_level >= 4:
            msg = "High stress detected! Take a 15-min break, then tackle one small topic at a time."
            conn.execute("INSERT INTO recommendations (user_id, message) VALUES (?,?)", (uid, msg))
            create_notification(uid, "😰 High Stress Alert", msg)
        elif completion_status == 'SKIPPED':
            msg = "You skipped a session. Your timetable will be adjusted. Try to cover it tomorrow!"
            conn.execute("INSERT INTO recommendations (user_id, message) VALUES (?,?)", (uid, msg))
            create_notification(uid, "⚠️ Session Skipped", msg)
        conn.commit()
        if completion_status in ('SKIPPED', 'PARTIAL'):
            adaptive_reschedule(uid, subject_id, completion_status)
        flash('Progress logged successfully!', 'success')
    logs = conn.execute("""
        SELECT sl.*, s.subject_name
        FROM study_logs sl JOIN subjects s ON sl.subject_id = s.subject_id
        WHERE sl.user_id=? ORDER BY sl.study_date DESC LIMIT 10
    """, (uid,)).fetchall()
    subj_list = conn.execute("SELECT * FROM subjects WHERE user_id=?", (uid,)).fetchall()
    perf = conn.execute("SELECT * FROM performance WHERE user_id=? ORDER BY recorded_date DESC LIMIT 1", (uid,)).fetchone()
    completed = conn.execute("SELECT COUNT(*) FROM tasks WHERE user_id=? AND status='COMPLETED'", (uid,)).fetchone()[0]
    total_t = conn.execute("SELECT COUNT(*) FROM tasks WHERE user_id=?", (uid,)).fetchone()[0]
    subject_stats = conn.execute("""
        SELECT s.subject_name, SUM(sl.actual_study_time) AS total_hours, COUNT(*) AS sessions
        FROM study_logs sl JOIN subjects s ON sl.subject_id = s.subject_id
        WHERE sl.user_id=? GROUP BY sl.subject_id
    """, (uid,)).fetchall()
    conn.close()
    return render_template('progress.html', logs=logs, subjects=subj_list, perf=perf,
                           completed=completed, total_tasks=total_t, subject_stats=subject_stats)

@app.route('/recommendations')
@login_required
def recommendations():
    uid = session['user_id']
    conn = get_db()
    recs = conn.execute("SELECT * FROM recommendations WHERE user_id=? ORDER BY created_date DESC LIMIT 20", (uid,)).fetchall()
    perf = conn.execute("SELECT * FROM performance WHERE user_id=? ORDER BY recorded_date DESC LIMIT 1", (uid,)).fetchone()
    conn.close()
    return render_template('recommendations.html', recommendations=recs, perf=perf)

@app.route('/notifications')
@login_required
def notifications():
    uid = session['user_id']
    conn = get_db()
    notifications = conn.execute("""
        SELECT * FROM notifications 
        WHERE user_id = ? 
        ORDER BY created_at DESC 
        LIMIT 50
    """, (uid,)).fetchall()
    
    conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (uid,))
    conn.commit()
    conn.close()
    
    return render_template('notifications.html', notifications=notifications)

@app.route('/api/progress_chart')
@login_required
def progress_chart():
    uid = session['user_id']
    conn = get_db()
    rows = conn.execute("""
        SELECT study_date, SUM(actual_study_time) AS hours
        FROM study_logs WHERE user_id=?
        GROUP BY study_date ORDER BY study_date DESC LIMIT 7
    """, (uid,)).fetchall()
    conn.close()
    labels = [r['study_date'] for r in reversed(rows)]
    data = [round(r['hours'], 2) for r in reversed(rows)]
    return jsonify({'labels': labels, 'data': data})

if __name__ == '__main__':
    init_db()
    app.run(debug=True)