# Database helper module using SQLite.
# Runs locally on any computer using Python's built-in sqlite3 library with zero external setup.

import os
import sqlite3
import json
import csv
from config import BASE_DIR, DATA_DIR, DB_PATH

def get_connection():
    # Establishes a connection to the local SQLite database file.
    # Automatically creates the database file in the data directory if not present.
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as err:
        print(f"[Database Notice] SQLite connection failed: {err}")
        return None

def init_db():
    # Creates necessary relational database tables if they do not exist.
    conn = get_connection()
    if conn is None:
        print("[Database Notice] Cannot initialize database tables: connection failed.")
        return False

    try:
        cursor = conn.cursor()

        # 1. Solar Predictions Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS solar_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT NOT NULL,
            plant_id INTEGER NOT NULL,
            input_measurements TEXT NOT NULL,
            predicted_kw REAL NOT NULL,
            predicted_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 2. Weather Records Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS weather_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT NOT NULL,
            state TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            temperature REAL NOT NULL,
            humidity REAL NOT NULL,
            cloud_cover REAL NOT NULL,
            wind_speed REAL NOT NULL,
            precipitation REAL NOT NULL,
            solar_radiation REAL NOT NULL,
            source TEXT NOT NULL,
            fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 3. Actual Generation Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS actual_generation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_id INTEGER NOT NULL,
            actual_ac_power REAL NOT NULL,
            record_time DATETIME NOT NULL
        )
        """)

        # 4. Anomaly Records Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS anomaly_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_id INTEGER NOT NULL,
            record_time DATETIME NOT NULL,
            actual REAL NOT NULL,
            predicted REAL NOT NULL,
            deviation REAL NOT NULL,
            threshold REAL NOT NULL,
            status TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 5. Energy Analysis Feasibility Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS energy_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT NOT NULL,
            state TEXT NOT NULL,
            industry_type TEXT NOT NULL,
            estimated_daily_demand_kwh REAL NOT NULL,
            recommended_capacity_kw REAL NOT NULL,
            annual_solar_generation_kwh REAL NOT NULL,
            grid_cost REAL NOT NULL,
            hybrid_cost REAL NOT NULL,
            solar_cost REAL NOT NULL,
            annual_savings REAL NOT NULL,
            installation_cost REAL NOT NULL,
            roi_percent REAL NOT NULL,
            payback_years REAL NOT NULL,
            recommendation TEXT NOT NULL,
            confidence TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 6. State Tariffs Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS state_tariffs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            state TEXT NOT NULL UNIQUE,
            discom TEXT NOT NULL,
            category TEXT NOT NULL,
            energy_charge_per_kwh REAL NULL,
            fixed_charge_note TEXT,
            export_credit_per_kwh REAL NULL,
            source_name TEXT NOT NULL,
            source_url TEXT NOT NULL,
            effective_date TEXT NOT NULL,
            verified BOOLEAN DEFAULT 0,
            notes TEXT,
            last_checked TEXT NOT NULL
        )
        """)
        cursor.execute("SELECT COUNT(*) AS cnt FROM state_tariffs")
        tar_cnt = cursor.fetchone()
        if tar_cnt and tar_cnt["cnt"] == 0:
            tariffs_csv = os.path.join(DATA_DIR, "state_tariffs.csv")
            if os.path.exists(tariffs_csv):
                with open(tariffs_csv, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        ec = float(r["energy_charge_per_kwh"]) if r.get("energy_charge_per_kwh") else None
                        xc = float(r["export_credit_per_kwh"]) if r.get("export_credit_per_kwh") else None
                        v = 1 if str(r.get("verified", "")).strip().lower() in ["true", "1"] else 0
                        cursor.execute("""
                        INSERT OR IGNORE INTO state_tariffs (state, discom, category, energy_charge_per_kwh, fixed_charge_note, export_credit_per_kwh, source_name, source_url, effective_date, verified, notes, last_checked)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (r["state"], r["discom"], r["category"], ec, r.get("fixed_charge_note", ""), xc, r.get("source_name", ""), r.get("source_url", ""), r.get("effective_date", ""), v, r.get("notes", ""), r.get("last_checked", "")))

        # 7. Cost Benchmarks Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS cost_benchmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            region TEXT NOT NULL,
            cost_per_kw REAL NOT NULL,
            source_name TEXT NOT NULL,
            source_url TEXT NOT NULL,
            as_of_date TEXT NOT NULL,
            notes TEXT
        )
        """)
        cursor.execute("SELECT COUNT(*) AS cnt FROM cost_benchmarks")
        cost_cnt = cursor.fetchone()
        if cost_cnt and cost_cnt["cnt"] == 0:
            cursor.execute("""
            INSERT INTO cost_benchmarks (region, cost_per_kw, source_name, source_url, as_of_date, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """, ("National Average (India)", 45000.0, "MNRE Benchmark Cost", "https://mnre.gov.in", "2024-01-01", "Turnkey industrial rooftop solar benchmark."))

        # 8. Industry Demand Benchmarks Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS industry_benchmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            industry_type TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL,
            connected_load_kw REAL NOT NULL,
            hourly_profile_json TEXT NOT NULL,
            source_note TEXT NOT NULL
        )
        """)
        cursor.execute("SELECT COUNT(*) AS cnt FROM industry_benchmarks")
        ind_cnt = cursor.fetchone()
        if ind_cnt and ind_cnt["cnt"] == 0:
            ind_csv = os.path.join(DATA_DIR, "industry_benchmarks.csv")
            if os.path.exists(ind_csv):
                with open(ind_csv, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        cl = float(r["connected_load_kw"]) if r.get("connected_load_kw") else 100.0
                        cursor.execute("""
                        INSERT OR IGNORE INTO industry_benchmarks (industry_type, description, connected_load_kw, hourly_profile_json, source_note)
                        VALUES (?, ?, ?, ?, ?)
                        """, (r["industry_type"], r["description"], cl, r["hourly_profile_json"], r["source_note"]))

        # Check if solar_predictions has any rows, if not, add realistic sample seed records
        cursor.execute("SELECT COUNT(*) AS cnt FROM solar_predictions")
        count_row = cursor.fetchone()
        if count_row and count_row["cnt"] == 0:
            seed_predictions = [
                ("Hyderabad, Telangana", 4135001, json.dumps({"ambient_temp": 34.0, "irradiation_wm2": 850.0, "time": "12:30", "capacity_kw": 100.0, "module_temp": 52.8}), 89.20, "2026-11-20 12:30:00"),
                ("Bengaluru, Karnataka", 4135001, json.dumps({"ambient_temp": 29.5, "irradiation_wm2": 520.0, "time": "10:00", "capacity_kw": 100.0, "module_temp": 41.2}), 54.80, "2026-11-20 10:00:00"),
                ("Chennai, Tamil Nadu", 4136001, json.dumps({"ambient_temp": 36.0, "irradiation_wm2": 890.0, "time": "13:00", "capacity_kw": 100.0, "module_temp": 55.4}), 72.40, "2026-11-20 13:00:00"),
                ("Ahmedabad, Gujarat", 4136001, json.dumps({"ambient_temp": 27.0, "irradiation_wm2": 310.0, "time": "08:45", "capacity_kw": 100.0, "module_temp": 33.6}), 28.50, "2026-11-20 08:45:00"),
                ("Jaipur, Rajasthan", 4135001, json.dumps({"ambient_temp": 33.0, "irradiation_wm2": 440.0, "time": "15:15", "capacity_kw": 100.0, "module_temp": 43.1}), 46.10, "2026-11-20 15:15:00"),
                ("Mumbai, Maharashtra", 4136001, json.dumps({"ambient_temp": 31.0, "irradiation_wm2": 190.0, "time": "16:30", "capacity_kw": 100.0, "module_temp": 35.2}), 16.80, "2026-11-20 16:30:00")
            ]
            cursor.executemany("""
            INSERT INTO solar_predictions (location, plant_id, input_measurements, predicted_kw, predicted_at)
            VALUES (?, ?, ?, ?, ?)
            """, seed_predictions)

        conn.commit()
        cursor.close()
        conn.close()
        print(f"[Database] SQLite schema verified and ready: {os.path.basename(DB_PATH)}")
        return True
    except Exception as err:
        print(f"[Database Error] Schema initialization error: {err}")
        return False

def insert_row(table_name, data_dict):
    # Inserts a single record dictionary into the specified SQLite table.
    conn = get_connection()
    if conn is None:
        return None

    try:
        cursor = conn.cursor()
        columns = list(data_dict.keys())
        placeholders = ["?"] * len(columns)
        values = [data_dict[col] for col in columns]

        sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
        cursor.execute(sql, values)
        insert_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()
        return insert_id
    except Exception as err:
        print(f"[Database Error] Insert failed on table {table_name}: {err}")
        return None

def fetch_all(query, params=None):
    # Executes a SELECT query and returns rows as a list of dictionaries.
    # Automatically adapts %s placeholders to SQLite ? placeholders.
    conn = get_connection()
    if conn is None:
        return []

    try:
        cursor = conn.cursor()
        safe_query = query.replace("%s", "?")
        cursor.execute(safe_query, params or ())
        rows = cursor.fetchall()
        dict_rows = [dict(r) for r in rows]
        cursor.close()
        conn.close()
        return dict_rows
    except Exception as err:
        print(f"[Database Error] Query fetch_all failed: {err}")
        return []

def fetch_one(query, params=None):
    # Executes a SELECT query and returns a single row dictionary.
    conn = get_connection()
    if conn is None:
        return None

    try:
        cursor = conn.cursor()
        safe_query = query.replace("%s", "?")
        cursor.execute(safe_query, params or ())
        row = cursor.fetchone()
        dict_row = dict(row) if row else None
        cursor.close()
        conn.close()
        return dict_row
    except Exception as err:
        print(f"[Database Error] Query fetch_one failed: {err}")
        return None
