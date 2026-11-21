# Helper module for saving and retrieving solar model predictions from SQLite.
# Provides automatic fallback to local JSON storage if needed.

import os
import json
from datetime import datetime
from decimal import Decimal
from config import BASE_DIR
from database import get_connection, insert_row, fetch_all

CACHE_FILE = os.path.join(BASE_DIR, "data", "stored_predictions_cache.json")

def get_initial_seed_records():
    # Sample realistic prediction records for initial display and offline fallback
    return [
        {
            "id": 101,
            "location": "Hyderabad, Telangana",
            "plant_id": 4135001,
            "input_measurements": json.dumps({
                "ambient_temp": 34.0,
                "irradiation_wm2": 850.0,
                "time": "12:30",
                "capacity_kw": 100.0,
                "module_temp": 52.8
            }),
            "predicted_kw": 89.20,
            "predicted_at": "2026-11-20 12:30:00",
            "status": "Stored in Database"
        },
        {
            "id": 102,
            "location": "Bengaluru, Karnataka",
            "plant_id": 4135001,
            "input_measurements": json.dumps({
                "ambient_temp": 29.5,
                "irradiation_wm2": 520.0,
                "time": "10:00",
                "capacity_kw": 100.0,
                "module_temp": 41.2
            }),
            "predicted_kw": 54.80,
            "predicted_at": "2026-11-20 10:00:00",
            "status": "Stored in Database"
        },
        {
            "id": 103,
            "location": "Chennai, Tamil Nadu",
            "plant_id": 4136001,
            "input_measurements": json.dumps({
                "ambient_temp": 36.0,
                "irradiation_wm2": 890.0,
                "time": "13:00",
                "capacity_kw": 100.0,
                "module_temp": 55.4
            }),
            "predicted_kw": 72.40,
            "predicted_at": "2026-11-20 13:00:00",
            "status": "Stored in Database"
        },
        {
            "id": 104,
            "location": "Ahmedabad, Gujarat",
            "plant_id": 4136001,
            "input_measurements": json.dumps({
                "ambient_temp": 27.0,
                "irradiation_wm2": 310.0,
                "time": "08:45",
                "capacity_kw": 100.0,
                "module_temp": 33.6
            }),
            "predicted_kw": 28.50,
            "predicted_at": "2026-11-20 08:45:00",
            "status": "Stored in Database"
        },
        {
            "id": 105,
            "location": "Jaipur, Rajasthan",
            "plant_id": 4135001,
            "input_measurements": json.dumps({
                "ambient_temp": 33.0,
                "irradiation_wm2": 440.0,
                "time": "15:15",
                "capacity_kw": 100.0,
                "module_temp": 43.1
            }),
            "predicted_kw": 46.10,
            "predicted_at": "2026-11-20 15:15:00",
            "status": "Stored in Database"
        },
        {
            "id": 106,
            "location": "Mumbai, Maharashtra",
            "plant_id": 4136001,
            "input_measurements": json.dumps({
                "ambient_temp": 31.0,
                "irradiation_wm2": 190.0,
                "time": "16:30",
                "capacity_kw": 100.0,
                "module_temp": 35.2
            }),
            "predicted_kw": 16.80,
            "predicted_at": "2026-11-20 16:30:00",
            "status": "Stored in Database"
        }
    ]

def load_local_cache():
    # Reads the fallback local JSON cache file
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception as e:
            print(f"[Cache Notice] Error reading cache file: {e}")

    # Initialize with default seeds if missing or invalid
    seeds = get_initial_seed_records()
    save_local_cache(seeds)
    return seeds

def save_local_cache(records):
    # Writes the records to the fallback local JSON cache file
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, default=str)
        return True
    except Exception as e:
        print(f"[Cache Notice] Error writing cache file: {e}")
        return False

def format_row_for_json(row):
    # Safely converts Decimal and Datetime types to strings and floats
    out = dict(row)
    if "predicted_kw" in out and out["predicted_kw"] is not None:
        out["predicted_kw"] = float(out["predicted_kw"])
    if "predicted_at" in out and out["predicted_at"] is not None:
        out["predicted_at"] = str(out["predicted_at"])
    if "id" in out and out["id"] is not None:
        out["id"] = int(out["id"])
    if "plant_id" in out and out["plant_id"] is not None:
        out["plant_id"] = int(out["plant_id"])
    return out

def get_stored_predictions(plant_id=None, limit=25):
    # Retrieves predictions from SQLite solar_predictions table.
    # If database is not reachable, returns records from the local fallback cache.
    conn = get_connection()
    is_connected = conn is not None

    if is_connected:
        try:
            conn.close()
            if plant_id:
                query = ("SELECT id, location, plant_id, input_measurements, predicted_kw, predicted_at "
                         "FROM solar_predictions WHERE plant_id = %s "
                         "ORDER BY predicted_at DESC, id DESC LIMIT %s")
                raw_rows = fetch_all(query, (plant_id, limit))
            else:
                query = ("SELECT id, location, plant_id, input_measurements, predicted_kw, predicted_at "
                         "FROM solar_predictions "
                         "ORDER BY predicted_at DESC, id DESC LIMIT %s")
                raw_rows = fetch_all(query, (limit,))

            if raw_rows and len(raw_rows) > 0:
                clean_rows = [format_row_for_json(r) for r in raw_rows]
                return {
                    "status": "success",
                    "db_connected": True,
                    "db_source": "SQLite Database (industrial_solar.db)",
                    "table_name": "solar_predictions",
                    "total_records": len(clean_rows),
                    "records": clean_rows
                }
            else:
                # If table is empty, seed it with sample records
                seeds = get_initial_seed_records()
                for s in seeds:
                    insert_row("solar_predictions", {
                        "location": s["location"],
                        "plant_id": s["plant_id"],
                        "input_measurements": s["input_measurements"],
                        "predicted_kw": s["predicted_kw"]
                    })
                # Re-query
                return get_stored_predictions(plant_id=plant_id, limit=limit)
        except Exception as e:
            print(f"[Database Error] Querying solar_predictions failed: {e}")

    # Offline / Fallback mode
    cached_records = load_local_cache()
    if plant_id:
        filtered = [r for r in cached_records if int(r.get("plant_id", 0)) == int(plant_id)]
    else:
        filtered = cached_records

    # Sort descending by id
    filtered = sorted(filtered, key=lambda x: x.get("id", 0), reverse=True)[:limit]

    return {
        "status": "success",
        "db_connected": False,
        "db_source": "Local Fallback Cache (Database offline)",
        "table_name": "solar_predictions",
        "total_records": len(filtered),
        "records": filtered
    }

def save_prediction_record(location, plant_id, input_data, predicted_kw):
    # Saves a prediction record into SQLite table solar_predictions,
    # and keeps the local JSON fallback cache synchronized.
    if isinstance(input_data, dict):
        input_str = json.dumps(input_data)
    else:
        input_str = str(input_data)

    new_id = None
    db_saved = False

    # 1. Attempt insert into SQLite
    try:
        conn = get_connection()
        if conn is not None:
            conn.close()
            inserted = insert_row("solar_predictions", {
                "location": location,
                "plant_id": int(plant_id),
                "input_measurements": input_str,
                "predicted_kw": float(predicted_kw)
            })
            if inserted:
                new_id = inserted
                db_saved = True
    except Exception as e:
        print(f"[Database Error] Failed to insert prediction to SQLite: {e}")

    # 2. Synchronize local fallback cache
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    records = load_local_cache()
    if not new_id:
        max_id = max([r.get("id", 100) for r in records], default=100)
        new_id = max_id + 1

    new_record = {
        "id": new_id,
        "location": location,
        "plant_id": int(plant_id),
        "input_measurements": input_str,
        "predicted_kw": float(predicted_kw),
        "predicted_at": now_str,
        "status": "Saved to SQLite" if db_saved else "Saved to Local Cache"
    }

    records.insert(0, new_record)
    save_local_cache(records[:100])

    return {
        "status": "success",
        "id": new_id,
        "db_saved": db_saved,
        "record": new_record
    }
