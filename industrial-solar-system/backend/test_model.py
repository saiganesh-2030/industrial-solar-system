# Verification script for the solar generation model.
# Tests predictions on 10 unseen rows per plant from the test split (dates >= 2020-06-13).

import os
import sys
import sklearn
import pandas as pd
import numpy as np

# Ensure backend directory is in Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import DATA_DIR
from model_service import predict_ac_power, get_model

def run_tests():
    print("==================================================")
    print("Industrial Solar Model Evaluation and Verification")
    print("==================================================")
    print(f"Current scikit-learn runtime version: {sklearn.__version__}")

    # Check model loading
    try:
        model = get_model()
        print("Model loaded successfully from disk.")
    except Exception as e:
        print(f"Error loading model: {e}")
        return

    csv_path = os.path.join(DATA_DIR, "combined_merged.csv")
    if not os.path.exists(csv_path):
        print(f"Dataset not found at {csv_path}")
        return

    df = pd.read_csv(csv_path)
    df["DATE_TIME"] = pd.to_datetime(df["DATE_TIME"])

    # Filter test split records on or after June 13, 2020
    test_df = df[df["DATE_TIME"] >= "2020-06-13"].copy()
    test_df = test_df.sort_values("DATE_TIME").reset_index(drop=True)

    plant_ids = [4135001, 4136001]

    for plant_id in plant_ids:
        print("\n--------------------------------------------------")
        print(f"Testing Plant {plant_id} (10 Sample Daytime Records)")
        print("--------------------------------------------------")

        # Pick daytime hours (between 08:00 and 17:00) on or after 2020-06-13 to demonstrate active solar generation
        daytime_mask = (test_df["PLANT_ID"] == plant_id) & (test_df["DATE_TIME"].dt.hour >= 8) & (test_df["DATE_TIME"].dt.hour <= 17) & (test_df["IRRADIATION"] > 0.05)
        plant_rows = test_df[daytime_mask].head(10)
        if plant_rows.empty:
            plant_rows = test_df[test_df["PLANT_ID"] == plant_id].head(10)

        actuals = []
        preds = []

        print(f"{'Timestamp':<20} {'Irrad (kW/m2)':<15} {'Actual (kW)':<15} {'Pred (kW)':<15} {'Diff (kW)':<12}")
        for _, row in plant_rows.iterrows():
            ts = row["DATE_TIME"]
            amb_temp = row["AMBIENT_TEMPERATURE"]
            mod_temp = row["MODULE_TEMPERATURE"]
            irrad = row["IRRADIATION"]
            actual = row["AC_POWER"]

            pred = predict_ac_power(
                plant_id=plant_id,
                timestamp=ts,
                ambient_temperature=amb_temp,
                module_temperature=mod_temp,
                irradiation=irrad
            )

            actuals.append(actual)
            preds.append(pred)
            diff = actual - pred

            print(f"{str(ts):<20} {irrad:<15.4f} {actual:<15.2f} {pred:<15.2f} {diff:<12.2f}")

        sample_mae = np.mean(np.abs(np.array(actuals) - np.array(preds)))
        print(f"\n10-Sample Daytime Mean Absolute Error (Plant {plant_id}): {sample_mae:.2f} kW")

    print("\nModel verification run complete.")

if __name__ == "__main__":
    run_tests()
