# Machine learning service for solar power generation prediction.
# Loads the trained scikit-learn Random Forest pipeline and provides prediction helpers.

import os
import math
import joblib
import pandas as pd
import numpy as np
from config import MODELS_DIR, ASSUMPTIONS

# Path to the serialized Random Forest pipeline model
MODEL_PATH = os.path.join(MODELS_DIR, "random_forest.pkl")

# Load model once at module initialization
_model = None

def get_model():
    # Returns the loaded scikit-learn pipeline instance.
    global _model
    if _model is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"Model file not found at {MODEL_PATH}")
        _model = joblib.load(MODEL_PATH)
    return _model

def estimate_module_temperature(ambient_temperature, irradiation):
    # Estimates solar panel surface temperature using our fitted regression:
    # MODULE_TEMPERATURE = -2.1415 + 1.0303 * AMBIENT + 27.9989 * IRRADIATION
    # R2 = 0.9709 on dataset measurements.
    if irradiation <= 0.0001:
        return float(ambient_temperature)
    reg = ASSUMPTIONS["module_temp_regression"]
    est = reg["intercept"] + (reg["coef_ambient"] * ambient_temperature) + (reg["coef_irradiation"] * irradiation)
    # Physical bounds check: module temp cannot drop below ambient under sunlight
    return max(float(ambient_temperature), float(est))

def predict_ac_power(plant_id, timestamp, ambient_temperature, module_temperature=None, irradiation=0.0):
    # Predicts AC power generation in kW for a given plant and environmental conditions.
    # The pipeline expects exact column order:
    # ['PLANT_ID', 'TIME_SIN', 'TIME_COS', 'AMBIENT_TEMPERATURE', 'MODULE_TEMPERATURE', 'IRRADIATION']
    model = get_model()

    # Solar daylight check: panels only produce power during daylight hours (approx 06:00 to 18:30)
    hour = timestamp.hour
    minute = timestamp.minute
    is_night = (hour < 6) or (hour == 18 and minute >= 45) or (hour >= 19)
    if is_night or irradiation <= 0.0001:
        return 0.0

    # Time encoding: minutes elapsed since midnight
    minutes = hour * 60 + minute
    time_sin = math.sin(2.0 * math.pi * minutes / 1440.0)
    time_cos = math.cos(2.0 * math.pi * minutes / 1440.0)

    # Estimate module temperature if not measured directly by a sensor
    if module_temperature is None:
        module_temperature = estimate_module_temperature(ambient_temperature, irradiation)

    input_df = pd.DataFrame([{
        "PLANT_ID": int(plant_id),
        "TIME_SIN": float(time_sin),
        "TIME_COS": float(time_cos),
        "AMBIENT_TEMPERATURE": float(ambient_temperature),
        "MODULE_TEMPERATURE": float(module_temperature),
        "IRRADIATION": float(irradiation)
    }])

    raw_prediction = model.predict(input_df)[0]
    return float(max(0.0, raw_prediction))

def calculate_yield_fraction(predicted_ac, plant_id=4135001):
    # Normalizes utility-scale plant output into a unitless yield fraction (0.0 to 1.0).
    # Reference peak is the maximum observed generation in the training CSV.
    # Label: "relative to the dataset plant's observed peak, not a real installed capacity"
    reference_peak = ASSUMPTIONS["plant_peak_ac"].get(int(plant_id), 29150.21)
    if reference_peak <= 0:
        return 0.0
    fraction = predicted_ac / reference_peak
    return min(1.0, max(0.0, fraction))

def scale_generation_to_capacity(predicted_ac, target_capacity_kw, plant_id=4135001):
    # Scales predicted generation from the utility-scale reference plant down to a factory's solar capacity.
    # Returns generation in kW for the industrial installation.
    fraction = calculate_yield_fraction(predicted_ac, plant_id)
    return fraction * target_capacity_kw
