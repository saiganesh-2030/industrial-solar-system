import os
import sys
import math
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any

import joblib
import pandas as pd
import sklearn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Ensure industrial-solar-system/backend is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "industrial-solar-system" / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

# Import domain services
from config import BASE_DIR, ASSUMPTIONS
from location_service import get_location_from_ip, reverse_geocode_nominatim, search_locations_open_meteo
from weather_service import fetch_weather
from solar_potential_service import fetch_solar_potential
from model_service import predict_ac_power, calculate_yield_fraction, estimate_module_temperature
from tariff_service import get_tariff_for_state, get_all_tariffs
from cost_service import get_installation_cost_per_kw, calculate_installation_cost
from feasibility_engine import run_feasibility_analysis, get_all_industry_types, get_industry_benchmark
from deviation_service import run_deviation_replay, evaluate_manual_deviation
from database import fetch_all, init_db
from prediction_storage import get_stored_predictions, save_prediction_record

# Model file path
LOCAL_MODEL = Path(__file__).resolve().parent / "random_forest.pkl"
ROOT_MODEL = Path(__file__).resolve().parent.parent / "models" / "random_forest.pkl"

if LOCAL_MODEL.exists():
    MODEL_PATH = LOCAL_MODEL
elif ROOT_MODEL.exists():
    MODEL_PATH = ROOT_MODEL
else:
    MODEL_PATH = LOCAL_MODEL

model = None

def load_model():
    global model
    if model is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"Model file not found at {MODEL_PATH}")
        model = joblib.load(MODEL_PATH)
    return model

try:
    load_model()
    init_db()
except Exception as e:
    pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_model()
    try:
        init_db()
    except Exception:
        pass
    yield

app = FastAPI(
    title="Industrial Solar Power & Energy Feasibility API",
    description="Comprehensive FastAPI backend serving scikit-learn Random Forest model, Open-Meteo live weather, NASA POWER climatology, 25-year financial feasibility engine, and SQLite database.",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- PYDANTIC SCHEMAS -----------------
class DirectPredictInput(BaseModel):
    irradiance: float = Field(..., description="Solar irradiance (kW/m2 or W/m2)")
    module_temp: float = Field(..., description="Back-of-panel module temperature (deg C)")
    ambient_temp: float = Field(..., description="Ambient air temperature (deg C)")
    time: str = Field(..., description="Time of day in HH:MM 24-hr format (e.g. '14:30')")
    plant_id: int = Field(..., description="Plant ID: 4135001 or 4136001")

class ManualDeviationInput(BaseModel):
    plant_id: int = 4135001
    actual_kw: float = 21500.0
    ambient_temp: float = 34.0
    irradiation: float = 780.0
    time_str: str = "12:30"
    module_temp: Optional[float] = None

class SinglePredictInput(BaseModel):
    plant_id: int = 4135001
    ambient_temp: float = 32.0
    irradiation: float = 750.0
    time_str: str = "12:00"
    capacity_kw: float = 100.0
    module_temp: Optional[float] = None
    save_to_db: bool = False

class SavePredictionInput(BaseModel):
    location: str = "Industrial Facility Site"
    plant_id: int = 4135001
    input_measurements: Dict[str, Any]
    predicted_kw: float

# ----------------- 1. GENERAL / HEALTH -----------------
@app.get("/", tags=["General"])
def read_root():
    return {
        "message": "Industrial Solar Power Prediction & Feasibility API",
        "status": "active",
        "docs_url": "/docs",
        "openapi_url": "/openapi.json"
    }

@app.get("/health", tags=["General"])
def health_check():
    return {
        "status": "ok",
        "model_loaded": model is not None,
        "sklearn_version": sklearn.__version__,
        "supported_plant_ids": [4135001, 4136001],
        "database": "SQLite (industrial_solar.db)"
    }

# ----------------- 2. MODEL PREDICTION -----------------
@app.post("/predict", tags=["Model Prediction"])
def predict(data: DirectPredictInput):
    """Direct model inference endpoint accepting irradiance, temperatures, time, and plant_id."""
    mdl = load_model()
    if mdl is None:
        raise HTTPException(status_code=503, detail="Model is not loaded")

    if data.plant_id not in [4135001, 4136001]:
        raise HTTPException(status_code=400, detail=f"Invalid plant_id {data.plant_id}. Must be 4135001 or 4136001")

    try:
        parts = data.time.strip().split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError()
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid time format '{data.time}'. Expected 'HH:MM'")

    # Nighttime physical check
    is_night = (hour < 6) or (hour == 18 and minute >= 45) or (hour >= 19)
    irrad_val = data.irradiance / 1000.0 if data.irradiance > 5.0 else data.irradiance

    if is_night or irrad_val <= 0.0001:
        return {
            "plant_id": data.plant_id,
            "time": data.time,
            "predicted_power": 0.0
        }

    minutes = hour * 60 + minute
    time_sin = math.sin(2.0 * math.pi * minutes / 1440.0)
    time_cos = math.cos(2.0 * math.pi * minutes / 1440.0)

    input_df = pd.DataFrame([{
        "PLANT_ID": int(data.plant_id),
        "TIME_SIN": float(time_sin),
        "TIME_COS": float(time_cos),
        "AMBIENT_TEMPERATURE": float(data.ambient_temp),
        "MODULE_TEMPERATURE": float(data.module_temp),
        "IRRADIATION": float(irrad_val)
    }])

    raw_pred = mdl.predict(input_df)[0]
    predicted_val = float(max(0.0, raw_pred))

    return {
        "plant_id": data.plant_id,
        "time": data.time,
        "predicted_power": round(predicted_val, 4)
    }

@app.get("/api/single-predict", tags=["Model Prediction"])
@app.post("/api/single-predict", tags=["Model Prediction"])
def api_single_predict(
    plant_id: int = 4135001,
    ambient_temp: float = 32.0,
    irradiation: float = 750.0,
    time_str: str = "12:00",
    capacity_kw: float = 100.0,
    module_temp: Optional[float] = None,
    save_to_db: bool = False
):
    """Interactive single-point evaluation endpoint for dashboard testing."""
    try:
        irrad_kwm2 = irradiation / 1000.0 if irradiation > 5.0 else irradiation

        parts = time_str.strip().split(":") if ":" in str(time_str) else ["12", "00"]
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0

        is_night = (hour < 6) or (hour == 18 and minute >= 45) or (hour >= 19)

        is_custom_mod_temp = False
        if module_temp is not None:
            mod_temp = float(module_temp)
            is_custom_mod_temp = True
        else:
            if is_night or irrad_kwm2 <= 0.0001:
                mod_temp = ambient_temp
            else:
                mod_temp = estimate_module_temperature(ambient_temp, irrad_kwm2)

        if is_night or irrad_kwm2 <= 0.0001:
            irrad_kwm2 = 0.0
            predicted_utility_ac = 0.0
            yield_frac = 0.0
            predicted_system_ac = 0.0
        else:
            dummy_date = datetime(2020, 6, 15, hour, minute)
            predicted_utility_ac = predict_ac_power(plant_id, dummy_date, ambient_temp, mod_temp, irrad_kwm2)
            yield_frac = calculate_yield_fraction(predicted_utility_ac, plant_id)
            predicted_system_ac = round(yield_frac * capacity_kw, 2)

        db_log_result = None
        if save_to_db:
            try:
                db_log_result = save_prediction_record(
                    location="Demo Field Site",
                    plant_id=plant_id,
                    input_data={
                        "ambient_temp": round(ambient_temp, 1),
                        "irradiation_wm2": round(irrad_kwm2 * 1000.0, 1),
                        "time": f"{hour:02d}:{minute:02d}",
                        "capacity_kw": capacity_kw,
                        "module_temp": round(mod_temp, 1)
                    },
                    predicted_kw=predicted_system_ac
                )
            except Exception:
                pass

        resp = {
            "status": "success",
            "plant_id": plant_id,
            "plant_name": "Plant 1" if plant_id == 4135001 else "Plant 2",
            "hour": hour,
            "minute": minute,
            "time_str": f"{hour:02d}:{minute:02d}",
            "is_night": is_night,
            "ambient_temp": round(ambient_temp, 1),
            "module_temp": round(mod_temp, 1),
            "is_custom_module_temp": is_custom_mod_temp,
            "irradiation_kwm2": round(irrad_kwm2, 4),
            "irradiation_wm2": round(irrad_kwm2 * 1000.0, 1),
            "capacity_kw": capacity_kw,
            "predicted_system_ac_kw": predicted_system_ac,
            "predicted_utility_ac_kw": round(predicted_utility_ac, 2),
            "yield_fraction_per_kw": round(yield_frac, 4),
            "source_label": "MODEL PREDICTION"
        }
        if db_log_result:
            resp["db_saved"] = db_log_result.get("db_saved", False)
            resp["db_record_id"] = db_log_result.get("id")
        return resp
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/prediction", tags=["Model Prediction"])
def api_prediction(
    lat: float = 17.3850,
    lon: float = 78.4867,
    capacity: float = 100.0,
    plant_id: int = 4135001
):
    """48-Hour forward solar generation projection with temperature and normalized yield fraction."""
    try:
        weather_res = fetch_weather(lat, lon)
        hourly_weather = weather_res.get("hourly", [])

        predictions = []
        for item in hourly_weather:
            amb_temp = float(item["temperature"])
            irrad = float(item["model_irradiation_kwm2"])
            time_str = item["time"]
            ts = time_str.split("T")

            h, m = map(int, ts[1].split(":")[:2])
            dummy_date = datetime(2020, 6, 15, h, m)
            mod_temp = estimate_module_temperature(amb_temp, irrad)
            pred_raw = predict_ac_power(plant_id, dummy_date, amb_temp, mod_temp, irrad)
            yield_frac = calculate_yield_fraction(pred_raw, plant_id)
            scaled_gen = round(yield_frac * capacity, 2)

            predictions.append({
                "time": time_str,
                "hour": h,
                "ambient_temp": amb_temp,
                "module_temp_estimated": round(mod_temp, 1),
                "irradiation_kwm2": irrad,
                "radiation_wm2": item["radiation_wm2"],
                "yield_fraction_per_kw": round(yield_frac, 4),
                "predicted_kw": scaled_gen
            })

        return {
            "status": "success",
            "capacity_kw": capacity,
            "plant_id_referenced": plant_id,
            "total_predicted_24h_kwh": round(sum(p["predicted_kw"] for p in predictions[:24]), 2),
            "total_predicted_48h_kwh": round(sum(p["predicted_kw"] for p in predictions), 2),
            "estimated_module_temperature_note": "MODULE_TEMP = -2.1415 + (1.0303 * AMBIENT) + (27.9989 * IRRADIATION)",
            "yield_fraction_note": "Relative to observed peak in dataset.",
            "source_label": "MODEL PREDICTION",
            "hourly_predictions": predictions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/model-metrics", tags=["Model Prediction"])
def api_model_metrics(plant_id: int = 4135001):
    """Evaluation metrics comparison from solar_model.ipynb (Linear, Ridge, Lasso, SVR, Random Forest)."""
    if plant_id == 4136001:
        comparison_table = [
            {"model": "Linear Regression", "mae": 2261.30, "rmse": 2972.80, "r2": 0.8430},
            {"model": "Tuned Ridge", "mae": 2259.40, "rmse": 2970.70, "r2": 0.8432},
            {"model": "Tuned Lasso", "mae": 2258.90, "rmse": 2968.80, "r2": 0.8434},
            {"model": "Tuned Support Vector Regressor (SVR)", "mae": 1510.10, "rmse": 2490.20, "r2": 0.8946},
            {"model": "Tuned Random Forest (Selected)", "mae": 778.93, "rmse": 1891.31, "r2": 0.8881}
        ]
        final_test_metrics = {
            "model": "Random Forest Regressor Pipeline",
            "plant_id": 4136001,
            "plant_name": "Plant 2 (4136001) - Plateau Limited Array",
            "test_dataset": "Unseen test split records for Plant 2 (dates >= 2020-06-13, 480 records)",
            "mae": 778.93,
            "rmse": 1891.31,
            "r2_score": 0.8881,
            "explanation": "Plant 2 exhibits midday inverter clipping at ~13,000 kW and higher cell temperatures."
        }
    else:
        comparison_table = [
            {"model": "Linear Regression", "mae": 1120.40, "rmse": 1710.20, "r2": 0.9412},
            {"model": "Tuned Ridge", "mae": 1119.50, "rmse": 1708.90, "r2": 0.9413},
            {"model": "Tuned Lasso", "mae": 1118.90, "rmse": 1707.50, "r2": 0.9414},
            {"model": "Tuned Support Vector Regressor (SVR)", "mae": 730.80, "rmse": 1290.40, "r2": 0.9650},
            {"model": "Tuned Random Forest (Selected)", "mae": 255.03, "rmse": 558.29, "r2": 0.9954}
        ]
        final_test_metrics = {
            "model": "Random Forest Regressor Pipeline",
            "plant_id": 4135001,
            "plant_name": "Plant 1 (4135001) - Standard Field Array",
            "test_dataset": "Unseen test split records for Plant 1 (dates >= 2020-06-13, 478 records)",
            "mae": 255.03,
            "rmse": 558.29,
            "r2_score": 0.9954,
            "explanation": "Plant 1 has an unconstrained continuous generation curve, enabling 99.54% variance explanation."
        }

    return {
        "status": "success",
        "plant_id": plant_id,
        "academic_note": "MAE, RMSE, and R2 are evaluation metrics, not models.",
        "models_comparison": comparison_table,
        "final_test_evaluation": final_test_metrics,
        "source_label": "MODEL PREDICTION"
    }

# ----------------- 3. WEATHER & CLIMATOLOGY -----------------
@app.get("/api/weather", tags=["Weather & Climatology"])
def api_weather(
    lat: float = 17.3850,
    lon: float = 78.4867,
    city: str = "Hyderabad",
    state: str = "Telangana"
):
    """Fetches live 48-hour forecast from Open-Meteo including cloud cover, wind, temperature, and radiation."""
    try:
        data = fetch_weather(lat, lon, city, state)
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/solar-potential", tags=["Weather & Climatology"])
def api_solar_potential(lat: float = 17.3850, lon: float = 78.4867):
    """Fetches NASA POWER multi-year monthly solar insolation climatology (Peak Sun Hours)."""
    try:
        data = fetch_solar_potential(lat, lon)
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----------------- 4. LOCATION & GEOCODING -----------------
@app.get("/api/location", tags=["Location & Geocoding"])
def api_location(
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    search: Optional[str] = None
):
    """Detects location via IP fallback, reverse geocodes coordinates via Nominatim, or searches cities."""
    try:
        if search:
            results = search_locations_open_meteo(search)
            return {"status": "success", "results": results, "source_label": "LIVE API"}

        if lat is not None and lon is not None:
            rev = reverse_geocode_nominatim(lat, lon)
            return {
                "status": "success",
                "latitude": lat,
                "longitude": lon,
                "city": rev.get("city", "Detected Location"),
                "state": rev.get("state", "Telangana"),
                "country": rev.get("country", "India"),
                "detection_method": "Browser GPS / Geolocation",
                "source_label": rev.get("source_label", "LIVE API")
            }

        loc = get_location_from_ip()
        return {"status": "success", **loc}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----------------- 5. FEASIBILITY & ECONOMICS -----------------
@app.get("/api/feasibility", tags=["Feasibility & Economics"])
def api_feasibility(
    lat: float = 17.3850,
    lon: float = 78.4867,
    city: str = "Hyderabad",
    state: str = "Telangana",
    industry: str = "Light Manufacturing",
    plant_id: int = 4135001
):
    """25-Year financial simulation comparing Grid-Only, Hybrid (25%, 50%, 75%), and Full Solar configurations."""
    try:
        location_info = {"latitude": lat, "longitude": lon, "city": city, "state": state}
        weather_res = fetch_weather(lat, lon, city, state)
        analysis = run_feasibility_analysis(location_info, weather_res, industry, plant_id=plant_id)
        return {"status": "success", "data": analysis}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/states-comparison", tags=["Feasibility & Economics"])
def api_states_comparison(
    industry: str = "Light Manufacturing",
    plant_id: int = 4135001
):
    """Ranks 12 major Indian states by solar financial feasibility (payback period and annual savings)."""
    try:
        state_locations = {
            "Telangana": {"lat": 17.3850, "lon": 78.4867, "city": "Hyderabad"},
            "Andhra Pradesh": {"lat": 16.5062, "lon": 80.6480, "city": "Vijayawada"},
            "Karnataka": {"lat": 12.9716, "lon": 77.5946, "city": "Bengaluru"},
            "Tamil Nadu": {"lat": 13.0827, "lon": 80.2707, "city": "Chennai"},
            "Maharashtra": {"lat": 19.0760, "lon": 72.8777, "city": "Mumbai"},
            "Gujarat": {"lat": 23.0225, "lon": 72.5714, "city": "Ahmedabad"},
            "Rajasthan": {"lat": 26.9124, "lon": 75.7873, "city": "Jaipur"},
            "Delhi": {"lat": 28.6139, "lon": 77.2090, "city": "New Delhi"},
            "Uttar Pradesh": {"lat": 26.8467, "lon": 80.9462, "city": "Lucknow"},
            "Madhya Pradesh": {"lat": 23.2599, "lon": 77.4126, "city": "Bhopal"},
            "West Bengal": {"lat": 22.5726, "lon": 88.3639, "city": "Kolkata"},
            "Kerala": {"lat": 8.5241, "lon": 76.9366, "city": "Thiruvananthapuram"}
        }

        comparison_results = []
        for state_name, coords in state_locations.items():
            try:
                tariff = get_tariff_for_state(state_name)
                sol = fetch_solar_potential(coords["lat"], coords["lon"])
                psh = sol.get("annual_average_psh", 4.8)

                industry_data = get_industry_benchmark(industry)
                conn_load = industry_data["connected_load_kw"]
                pr = ASSUMPTIONS["performance_ratio"]

                ref_peak = ASSUMPTIONS["plant_peak_ac"].get(int(plant_id), 29150.21)
                yield_scaling = 0.814 if plant_id == 4136001 else 1.0

                daily_gen_per_kw = psh * pr * yield_scaling
                annual_yield_per_kw = daily_gen_per_kw * 365

                annual_gen_kwh = annual_yield_per_kw * conn_load
                rate = tariff.get("energy_charge_per_kwh", 7.50)
                gross_savings = annual_gen_kwh * rate
                capex = get_installation_cost_per_kw(state_name) * conn_load
                om_cost = capex * ASSUMPTIONS["annual_om_rate_of_capex"]
                net_savings = max(1.0, gross_savings - om_cost)
                payback = round(capex / net_savings, 2)
                roi = round((net_savings / capex) * 100, 1)

                comparison_results.append({
                    "state": state_name,
                    "city": coords["city"],
                    "peak_sun_hours": psh,
                    "tariff_rate": rate,
                    "annual_yield_kwh_per_kw": round(annual_yield_per_kw, 1),
                    "annual_savings_inr": round(net_savings, 0),
                    "payback_years": payback,
                    "roi_percent": roi,
                    "plant_id_used": plant_id
                })
            except Exception:
                continue

        comparison_results.sort(key=lambda x: x["payback_years"])
        return {
            "status": "success",
            "industry": industry,
            "plant_id": plant_id,
            "total_states": len(comparison_results),
            "rankings": comparison_results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/industries", tags=["Feasibility & Economics"])
def api_industries():
    """Returns benchmark connected load and demand profiles for industrial factory types."""
    return {"status": "success", "industries": get_all_industry_types()}

@app.get("/api/history", tags=["Feasibility & Economics"])
def api_history():
    """Recent saved feasibility analysis runs from SQLite energy_analysis table."""
    records = fetch_all("SELECT * FROM energy_analysis ORDER BY created_at DESC LIMIT 20")
    return {"status": "success", "records": records}

# ----------------- 6. STATE TARIFFS -----------------
@app.get("/api/tariff", tags=["State Tariffs"])
def api_tariff(state: str = "Telangana"):
    """Lookup published SERC industrial HT electricity tariff for a given state."""
    try:
        data = get_tariff_for_state(state)
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tariffs", tags=["State Tariffs"])
def api_all_tariffs():
    """Returns all 12 audited state electricity tariff schedules."""
    try:
        return {"status": "success", "data": get_all_tariffs()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----------------- 7. DEVIATION DETECTION -----------------
@app.get("/api/deviation", tags=["Deviation Detection"])
def api_deviation(plant_id: int = 4135001):
    """Historical sensor replay timeline evaluating generation gaps against statistical IQR threshold."""
    try:
        data = run_deviation_replay(plant_id)
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/check-deviation", tags=["Deviation Detection"])
@app.post("/api/check-deviation", tags=["Deviation Detection"])
def api_check_deviation(
    plant_id: int = 4135001,
    actual_kw: float = 21500.0,
    ambient_temp: float = 34.0,
    irradiation: float = 780.0,
    time_str: str = "12:30",
    module_temp: Optional[float] = None
):
    """Single-point evaluator for live inverter deviation diagnosis."""
    try:
        parts = time_str.strip().split(":") if ":" in str(time_str) else ["12", "30"]
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0

        irrad_kwm2 = irradiation / 1000.0 if irradiation > 5.0 else irradiation

        result = evaluate_manual_deviation(
            plant_id=plant_id,
            actual_kw=actual_kw,
            ambient_temp=ambient_temp,
            irradiation_kwm2=irrad_kwm2,
            hour=hour,
            minute=minute,
            module_temp=module_temp
        )
        return {"status": "success", "data": result, "source_label": "MODEL EVALUATION"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----------------- 8. DATABASE STORAGE -----------------
@app.get("/api/stored-predictions", tags=["Database Storage"])
def api_stored_predictions(
    plant_id: Optional[int] = None,
    limit: int = 25
):
    """Retrieves logged prediction records from SQLite solar_predictions table."""
    try:
        result = get_stored_predictions(plant_id=plant_id, limit=limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/save-prediction", tags=["Database Storage"])
def api_save_prediction(payload: SavePredictionInput):
    """Logs a single prediction record into SQLite solar_predictions table."""
    try:
        result = save_prediction_record(
            location=payload.location,
            plant_id=payload.plant_id,
            input_data=payload.input_measurements,
            predicted_kw=payload.predicted_kw
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
