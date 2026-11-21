# Historical replay service for detecting unusual generation deviations.
# Evaluates test records (dates >= 2020-06-13) using the Q3 + 1.5 * IQR threshold method.
# Clearly marked as a historical replay demonstration, never as live operational telemetry.

import os
import pandas as pd
import numpy as np
from datetime import datetime
from config import DATA_DIR, ASSUMPTIONS
from model_service import predict_ac_power
from database import insert_row, fetch_all

def classify_deviation(actual, predicted, threshold, irradiation):
    # Classifies generation discrepancy into approved academic categories.
    # Academic rule: never use the word "failure" or "fault"; use "unusual deviation".
    deviation = actual - predicted
    abs_dev = abs(deviation)

    # 1. Check for possible sensor or zero-generation anomaly:
    # High sunlight (> 0.25 kW/m2) but plant output is zero or near zero.
    if irradiation >= 0.25 and actual <= 50.0 and predicted >= 1000.0:
        return "Possible sensor issue", deviation, abs_dev

    # 2. Check if absolute deviation exceeds statistical threshold (Q3 + 1.5 * IQR)
    if abs_dev > threshold:
        if deviation < 0:
            return "Unusual underperformance", deviation, abs_dev
        else:
            return "Unusual overperformance", deviation, abs_dev

    return "Normal", deviation, abs_dev

def evaluate_manual_deviation(plant_id=4135001, actual_kw=0.0, ambient_temp=30.0, irradiation_kwm2=0.75, hour=12, minute=0, module_temp=None):
    # Evaluates user-entered operational conditions against the trained Random Forest model
    # and statistical IQR outlier bounds.
    plant_id = int(plant_id)
    threshold = ASSUMPTIONS["anomaly_thresholds"].get(plant_id, 752.93)
    dummy_date = datetime(2020, 6, 15, int(hour), int(minute))

    # Model prediction
    pred_kw = predict_ac_power(
        plant_id=plant_id,
        timestamp=dummy_date,
        ambient_temperature=ambient_temp,
        module_temperature=module_temp,
        irradiation=irradiation_kwm2
    )

    status, dev, abs_dev = classify_deviation(actual_kw, pred_kw, threshold, irradiation_kwm2)

    if pred_kw > 20.0:
        dev_pct = round(((actual_kw - pred_kw) / pred_kw) * 100.0, 1)
    else:
        dev_pct = 0.0

    plant_name = "Plant 1" if plant_id == 4135001 else "Plant 2"
    if status == "Normal":
        explanation = f"Generation is within normal limits. The discrepancy of {abs_dev:.1f} kW is below the {threshold:.2f} kW threshold for {plant_name}."
    elif status == "Unusual underperformance":
        explanation = f"The actual generation is {abs_dev:.1f} kW below expected output ({abs(dev_pct):.1f}% lower). This exceeds the {threshold:.2f} kW threshold for {plant_name}, pointing to unexpected losses or partial shading."
    elif status == "Unusual overperformance":
        explanation = f"The actual output is {abs_dev:.1f} kW above expected generation (+{dev_pct:.1f}% higher). This exceeds the {threshold:.2f} kW threshold for {plant_name}."
    else:
        explanation = f"Irradiation is strong at {irradiation_kwm2:.2f} kW/m2 with expected output of {pred_kw:.1f} kW, but recorded power is near zero ({actual_kw:.1f} kW). This indicates a possible sensor disconnection or inverter trip."

    return {
        "plant_id": plant_id,
        "plant_name": plant_name,
        "hour": int(hour),
        "minute": int(minute),
        "time_str": f"{int(hour):02d}:{int(minute):02d}",
        "ambient_temp": float(ambient_temp),
        "irradiation_kwm2": float(irradiation_kwm2),
        "actual_kw": round(float(actual_kw), 2),
        "predicted_kw": round(float(pred_kw), 2),
        "deviation_kw": round(float(dev), 2),
        "abs_deviation_kw": round(float(abs_dev), 2),
        "deviation_percent": dev_pct,
        "threshold_kw": threshold,
        "status": status,
        "is_unusual": status != "Normal",
        "explanation": explanation
    }

def run_deviation_replay(plant_id=4135001, limit=60):
    # Replays test split records on or after 2020-06-13 and detects unusual deviations.
    csv_path = os.path.join(DATA_DIR, "combined_merged.csv")
    if not os.path.exists(csv_path):
        return {"error": "Dataset file combined_merged.csv not found", "records": []}

    df = pd.read_csv(csv_path)
    df["DATE_TIME"] = pd.to_datetime(df["DATE_TIME"])

    plant_id = int(plant_id)
    threshold = ASSUMPTIONS["anomaly_thresholds"].get(plant_id, 752.93)

    # Select test period
    sub = df[(df["PLANT_ID"] == plant_id) & (df["DATE_TIME"] >= "2020-06-13")].copy()
    sub = sub.sort_values("DATE_TIME").reset_index(drop=True)

    # Focus on daytime hours where solar generation is active
    daytime_sub = sub[(sub["DATE_TIME"].dt.hour >= 6) & (sub["DATE_TIME"].dt.hour <= 18)].head(limit)

    records = []
    normal_count = 0
    underperf_count = 0
    overperf_count = 0
    sensor_issue_count = 0

    for _, row in daytime_sub.iterrows():
        ts = row["DATE_TIME"]
        amb_temp = float(row["AMBIENT_TEMPERATURE"])
        mod_temp = float(row["MODULE_TEMPERATURE"])
        irrad = float(row["IRRADIATION"])
        actual = float(row["AC_POWER"])

        pred = predict_ac_power(
            plant_id=plant_id,
            timestamp=ts,
            ambient_temperature=amb_temp,
            module_temperature=mod_temp,
            irradiation=irrad
        )

        status, dev, abs_dev = classify_deviation(actual, pred, threshold, irrad)

        # Percentage deviation
        if pred > 50.0:
            dev_pct = round(((actual - pred) / pred) * 100.0, 1)
        else:
            dev_pct = 0.0

        if status == "Normal":
            normal_count += 1
        elif status == "Unusual underperformance":
            underperf_count += 1
        elif status == "Unusual overperformance":
            overperf_count += 1
        elif status == "Possible sensor issue":
            sensor_issue_count += 1

        rec = {
            "timestamp": ts.strftime("%Y-%m-%d %H:%M"),
            "plant_id": plant_id,
            "irradiation_kwm2": round(irrad, 4),
            "actual_kw": round(actual, 2),
            "predicted_kw": round(pred, 2),
            "deviation_kw": round(dev, 2),
            "deviation_percent": dev_pct,
            "threshold_kw": threshold,
            "status": status,
            "is_unusual": status != "Normal"
        }
        records.append(rec)

        # Save unusual deviations to database table anomaly_records
        if status != "Normal":
            insert_row("anomaly_records", {
                "plant_id": plant_id,
                "record_time": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "actual": actual,
                "predicted": pred,
                "deviation": dev,
                "threshold": threshold,
                "status": status,
                "created_at": datetime.now()
            })

    return {
        "plant_id": plant_id,
        "threshold_kw": threshold,
        "threshold_formula": "Q3 + 1.5 * IQR of Absolute Deviation on validation split",
        "total_records_replayed": len(records),
        "summary": {
            "normal": normal_count,
            "unusual_underperformance": underperf_count,
            "unusual_overperformance": overperf_count,
            "possible_sensor_issues": sensor_issue_count,
            "total_unusual": underperf_count + overperf_count + sensor_issue_count
        },
        "mode": "Historical Replay (Test Data on/after 2020-06-13)",
        "source_label": "HISTORICAL API",
        "records": records
    }
