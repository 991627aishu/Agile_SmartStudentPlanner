-- ============================================================
--  Smart Student Planner — SQLite Database Schema
--  This file is optional! The app creates tables automatically.
--  Use this only if you want to inspect or backup the structure.
-- ============================================================

-- ── Users ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT DEFAULT (datetime('now'))
);

-- ── User Preferences ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id     INTEGER PRIMARY KEY,
    daily_hours REAL DEFAULT 6,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- ── Subjects ──────────────────────────────────────────────────
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

-- ── Tasks ─────────────────────────────────────────────────────
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

-- ── Daily Timetable ───────────────────────────────────────────
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

-- ── Study Logs ────────────────────────────────────────────────
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

-- ── Performance ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS performance (
    performance_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id               INTEGER UNIQUE NOT NULL,
    completion_percentage REAL DEFAULT 0,
    consistency_score     REAL DEFAULT 0,
    stress_score          REAL DEFAULT 0,
    recorded_date         TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- ── Recommendations ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS recommendations (
    recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL,
    message           TEXT NOT NULL,
    created_date      TEXT DEFAULT (date('now')),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- ── Notifications ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notifications (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    title           TEXT NOT NULL,
    message         TEXT NOT NULL,
    is_read         INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- ── Indexes for performance ───────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_tasks_user     ON tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_due      ON tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_subjects_user  ON subjects(user_id);
CREATE INDEX IF NOT EXISTS idx_logs_user_date ON study_logs(user_id, study_date);
CREATE INDEX IF NOT EXISTS idx_timetable_date ON daily_timetable(user_id, timetable_date);