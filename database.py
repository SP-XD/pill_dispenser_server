import sqlite3
from config import DATABASE_FILE
from datetime import datetime

def init_db():
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    
    # Doctor
    c.execute('''
        CREATE TABLE IF NOT EXISTS doctor (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL
        )
    ''')
    
    # Patient
    c.execute('''
        CREATE TABLE IF NOT EXISTS patient (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER,
            doctor_id INTEGER,
            notes TEXT,
            FOREIGN KEY (doctor_id) REFERENCES doctor(id)
        )
    ''')
    
    # Pill Dispenser Device (one per patient)
    c.execute('''
        CREATE TABLE IF NOT EXISTS pill_dispenser (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER UNIQUE,
            serial_number TEXT UNIQUE,
            FOREIGN KEY (patient_id) REFERENCES patient(id)
        )
    ''')
    
    # Dispenser Module
    # Two modules per dispenser
    c.execute('''
        CREATE TABLE IF NOT EXISTS dispenser_module (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pill_dispenser_id INTEGER,
            module_name TEXT,  -- e.g., "motor1", "motor2"
            pills_left INTEGER,
            threshold INTEGER,
            pending INTEGER DEFAULT 0,
            FOREIGN KEY (pill_dispenser_id) REFERENCES pill_dispenser(id)
        )
    ''')

    # Schedule per medicine 
    c.execute('''
        CREATE TABLE IF NOT EXISTS schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            dispenser_module_id INTEGER,
            medicine_name TEXT NOT NULL,  -- Added medicine name
            time TEXT, -- HH:MM
            repeat_type TEXT CHECK(repeat_type IN ('daily', 'custom')) DEFAULT 'daily',
            days_of_week TEXT,  -- e.g., "mon,wed,fri"
            until_date TEXT,    -- optional, format: "YYYY-MM-DD"
            FOREIGN KEY (patient_id) REFERENCES patient(id),
            FOREIGN KEY (dispenser_module_id) REFERENCES dispenser_module(id)
        )
    ''')

    # Event Log
    c.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            dispenser_module_id INTEGER,
            message TEXT,
            FOREIGN KEY (dispenser_module_id) REFERENCES dispenser_module(id)
        )
    ''')

    conn.commit()
    conn.close()


def log_event(dispenser_module_name, message):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    
    # Look up the dispenser_module_id
    c.execute("SELECT id FROM dispenser_module WHERE module_name = ?", (dispenser_module_name,))
    row = c.fetchone()
    module_id = row[0] if row else None

    c.execute("INSERT INTO logs (timestamp, dispenser_module_id, message) VALUES (?, ?, ?)",
              (datetime.now().isoformat(), module_id, message))
    conn.commit()
    conn.close()


def get_logs(limit=50):
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT logs.id, timestamp, module_name, message
        FROM logs
        LEFT JOIN dispenser_module ON logs.dispenser_module_id = dispenser_module.id
        ORDER BY logs.id DESC LIMIT ?
    """, (limit,))
    logs = c.fetchall()
    conn.close()
    return logs
