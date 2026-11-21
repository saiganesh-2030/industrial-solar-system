# Seeds SQLite database tables with tariffs, industry demand profiles, and cost benchmarks.

import os
import sys
import csv
import json
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import DATA_DIR
from database import get_connection, init_db, insert_row, fetch_one

def seed_state_tariffs():
    csv_file = os.path.join(DATA_DIR, "state_tariffs.csv")
    if not os.path.exists(csv_file):
        print(f"Tariff CSV not found at {csv_file}")
        return

    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            existing = fetch_one("SELECT id FROM state_tariffs WHERE state = %s", (row["state"],))
            if existing:
                continue

            energy_val = None
            if row["energy_charge_per_kwh"] and row["energy_charge_per_kwh"] != "NOT FOUND":
                try:
                    energy_val = float(row["energy_charge_per_kwh"])
                except ValueError:
                    energy_val = None

            export_val = None
            if row.get("export_credit_per_kwh"):
                try:
                    export_val = float(row["export_credit_per_kwh"])
                except ValueError:
                    export_val = None

            db_data = {
                "state": row["state"],
                "discom": row["discom"],
                "category": row["category"],
                "energy_charge_per_kwh": energy_val,
                "fixed_charge_note": row["fixed_charge_note"],
                "export_credit_per_kwh": export_val,
                "source_name": row["source_name"],
                "source_url": row["source_url"],
                "effective_date": row["effective_date"],
                "verified": 1 if row["verified"].strip().upper() == "TRUE" else 0,
                "notes": row["notes"],
                "last_checked": row["last_checked"]
            }
            insert_row("state_tariffs", db_data)
            count += 1
        print(f"Seeded {count} state tariff records.")

def seed_industry_benchmarks():
    csv_file = os.path.join(DATA_DIR, "industry_benchmarks.csv")
    if not os.path.exists(csv_file):
        print(f"Industry benchmarks CSV not found at {csv_file}")
        return

    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            existing = fetch_one("SELECT id FROM industry_benchmarks WHERE industry_type = %s", (row["industry_type"],))
            if existing:
                continue

            db_data = {
                "industry_type": row["industry_type"],
                "description": row["description"],
                "connected_load_kw": float(row["connected_load_kw"]),
                "hourly_profile_json": row["hourly_profile_json"],
                "source_note": row["source_note"]
            }
            insert_row("industry_benchmarks", db_data)
            count += 1
        print(f"Seeded {count} industry benchmark records.")

def seed_cost_benchmarks():
    benchmarks = [
        {
            "region": "National Average (India)",
            "cost_per_kw": 42000.00,
            "source_name": "MNRE Rooftop Solar Benchmark Cost Notification",
            "source_url": "https://mnre.gov.in",
            "as_of_date": "2024-01-01",
            "notes": "Turnkey rooftop industrial grid-connected solar installation cost including Tier-1 monocrystalline PERC panels, inverters, structural mounting, and AC/DC protection gear."
        },
        {
            "region": "Ground-Mount Solar Park",
            "cost_per_kw": 38000.00,
            "source_name": "Central Electricity Authority (CEA) Report",
            "source_url": "https://cea.nic.in",
            "as_of_date": "2024-01-01",
            "notes": "MW-scale ground-mounted solar plant turnkey cost with central inverters."
        }
    ]

    count = 0
    for b in benchmarks:
        existing = fetch_one("SELECT id FROM cost_benchmarks WHERE region = %s", (b["region"],))
        if existing:
            continue
        insert_row("cost_benchmarks", b)
        count += 1
    print(f"Seeded {count} cost benchmark records.")

def seed_sample_actual_generation():
    # Seeds sample actual generation from combined_merged.csv for testing
    csv_file = os.path.join(DATA_DIR, "combined_merged.csv")
    if not os.path.exists(csv_file):
        return

    existing = fetch_one("SELECT id FROM actual_generation LIMIT 1")
    if existing:
        return

    df = pd.read_csv(csv_file)
    df["DATE_TIME"] = pd.to_datetime(df["DATE_TIME"])
    sample = df[df["DATE_TIME"] >= "2020-06-13"].head(100)

    count = 0
    for _, row in sample.iterrows():
        insert_row("actual_generation", {
            "plant_id": int(row["PLANT_ID"]),
            "actual_ac_power": float(row["AC_POWER"]),
            "record_time": row["DATE_TIME"].strftime("%Y-%m-%d %H:%M:%S")
        })
        count += 1
    print(f"Seeded {count} sample actual generation records.")

def main():
    print("Initializing database tables and seed data...")
    init_db()
    seed_state_tariffs()
    seed_industry_benchmarks()
    seed_cost_benchmarks()
    seed_sample_actual_generation()
    print("Seed process completed.")

if __name__ == "__main__":
    main()
