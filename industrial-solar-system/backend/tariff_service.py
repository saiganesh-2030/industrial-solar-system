# Electricity tariff lookup service for Indian states.
# Retrieves industrial HT/LT electricity rates, fixed charges, and export credits.

import os
import csv
from config import DATA_DIR, ASSUMPTIONS
from database import fetch_one, fetch_all

def _load_tariffs_from_csv():
    csv_file = os.path.join(DATA_DIR, "state_tariffs.csv")
    if not os.path.exists(csv_file):
        return {}
    tariffs = {}
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tariffs[row["state"].strip().lower()] = row
    return tariffs

def get_tariff_for_state(state_name):
    # Returns tariff information for a given state name.
    # Uses database lookup first; falls back to CSV file if database is offline.
    if not state_name:
        state_name = "Telangana"

    # 1. Try SQLite database
    db_row = fetch_one("SELECT * FROM state_tariffs WHERE LOWER(state) = %s", (state_name.strip().lower(),))
    if db_row:
        rate = db_row.get("energy_charge_per_kwh")
        if rate is not None:
            return {
                "state": db_row["state"],
                "discom": db_row["discom"],
                "category": db_row["category"],
                "energy_charge_per_kwh": float(rate),
                "fixed_charge_note": db_row.get("fixed_charge_note", ""),
                "export_credit_per_kwh": float(db_row["export_credit_per_kwh"]) if db_row.get("export_credit_per_kwh") else 0.0,
                "source_name": db_row.get("source_name", "SERC Tariff Schedule"),
                "source_url": db_row.get("source_url", ""),
                "effective_date": str(db_row.get("effective_date", "2023-04-01")),
                "verified": bool(db_row.get("verified", False)),
                "verified_badge": "Verified" if db_row.get("verified") else "Not yet verified",
                "notes": db_row.get("notes", ""),
                "is_fallback": False,
                "source_label": "HISTORICAL API"
            }

    # 2. Try CSV file
    csv_tariffs = _load_tariffs_from_csv()
    state_key = state_name.strip().lower()

    # Try partial or exact match
    matched_row = None
    for k, v in csv_tariffs.items():
        if k in state_key or state_key in k:
            matched_row = v
            break

    if matched_row and matched_row.get("energy_charge_per_kwh") and matched_row["energy_charge_per_kwh"] != "NOT FOUND":
        try:
            rate = float(matched_row["energy_charge_per_kwh"])
            export_val = float(matched_row["export_credit_per_kwh"]) if matched_row.get("export_credit_per_kwh") else 0.0
            is_verified = matched_row["verified"].strip().upper() == "TRUE"
            return {
                "state": matched_row["state"],
                "discom": matched_row["discom"],
                "category": matched_row["category"],
                "energy_charge_per_kwh": rate,
                "fixed_charge_note": matched_row.get("fixed_charge_note", ""),
                "export_credit_per_kwh": export_val,
                "source_name": matched_row.get("source_name", "SERC Tariff Order"),
                "source_url": matched_row.get("source_url", ""),
                "effective_date": matched_row.get("effective_date", "2023-04-01"),
                "verified": is_verified,
                "verified_badge": "Verified" if is_verified else "Not yet verified",
                "notes": matched_row.get("notes", ""),
                "is_fallback": False,
                "source_label": "HISTORICAL API"
            }
        except ValueError:
            pass

    # 3. State tariff not found: use clearly marked assumption fallback
    fallback_rate = ASSUMPTIONS["default_tariff_per_kwh"]
    return {
        "state": state_name,
        "discom": "DISCOM Not Listed",
        "category": "HT Industrial (Assumption)",
        "energy_charge_per_kwh": fallback_rate,
        "fixed_charge_note": "Demand charges not applied under fallback assumption.",
        "export_credit_per_kwh": 0.0,
        "source_name": "National Industrial Tariff Average Benchmark",
        "source_url": "",
        "effective_date": "2024-01-01",
        "verified": False,
        "verified_badge": "Not yet verified",
        "notes": f"Tariff unavailable for {state_name}. Using standard fallback benchmark of Rs {fallback_rate}/kWh.",
        "is_fallback": True,
        "source_label": "ASSUMPTION"
    }

def get_all_tariffs():
    # Returns all state tariffs as a list for states comparison page.
    db_rows = fetch_all("SELECT * FROM state_tariffs ORDER BY energy_charge_per_kwh DESC")
    if db_rows:
        results = []
        for r in db_rows:
            rate = float(r["energy_charge_per_kwh"]) if r.get("energy_charge_per_kwh") else None
            results.append({
                "state": r["state"],
                "discom": r["discom"],
                "category": r["category"],
                "energy_charge_per_kwh": rate,
                "fixed_charge_note": r.get("fixed_charge_note", ""),
                "export_credit_per_kwh": float(r["export_credit_per_kwh"]) if r.get("export_credit_per_kwh") else None,
                "source_name": r.get("source_name", ""),
                "source_url": r.get("source_url", ""),
                "effective_date": str(r.get("effective_date", "")),
                "verified": bool(r.get("verified", False)),
                "verified_badge": "Verified" if r.get("verified") else "Not yet verified",
                "notes": r.get("notes", "")
            })
        return results

    # CSV fallback
    csv_tariffs = _load_tariffs_from_csv()
    results = []
    for row in csv_tariffs.values():
        try:
            rate = float(row["energy_charge_per_kwh"]) if row.get("energy_charge_per_kwh") and row["energy_charge_per_kwh"] != "NOT FOUND" else None
            export_val = float(row["export_credit_per_kwh"]) if row.get("export_credit_per_kwh") else None
            is_v = row["verified"].strip().upper() == "TRUE"
            results.append({
                "state": row["state"],
                "discom": row["discom"],
                "category": row["category"],
                "energy_charge_per_kwh": rate,
                "fixed_charge_note": row.get("fixed_charge_note", ""),
                "export_credit_per_kwh": export_val,
                "source_name": row.get("source_name", ""),
                "source_url": row.get("source_url", ""),
                "effective_date": row.get("effective_date", ""),
                "verified": is_v,
                "verified_badge": "Verified" if is_v else "Not yet verified",
                "notes": row.get("notes", "")
            })
        except Exception:
            continue
    return results
