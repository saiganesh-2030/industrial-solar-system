# Live weather and 48-hour forecast service using Open-Meteo API.
# Fetches temperature, humidity, cloud cover, wind, rain, and shortwave solar radiation.

import requests
from datetime import datetime
from config import API_URLS, HTTP_HEADERS
from database import insert_row, fetch_one

# In-memory backup cache in case database or external network is temporarily down
_latest_weather_cache = None

def compute_suitability_score(avg_temp, avg_cloud, total_rain, avg_radiation):
    # Calculates a solar weather suitability score from 0 to 100.
    # Formula breakdown:
    # 1. Radiation points (0 to 40 pts): sunlight is the primary energy driver.
    #    Peak midday radiation around 800-1000 W/m2 yields full 40 points.
    rad_pts = min(40.0, (avg_radiation / 800.0) * 40.0)

    # 2. Cloud cover points (0 to 30 pts): clearer skies let more direct beam through.
    cloud_pts = max(0.0, 30.0 - (avg_cloud / 100.0 * 30.0))

    # 3. Precipitation penalty (0 to 15 pts): rain blocks sunlight and causes diffuse reflection.
    rain_pts = max(0.0, 15.0 - (min(total_rain, 15.0)))

    # 4. Temperature points (0 to 15 pts): PV cell efficiency drops ~0.4% per deg C above 25 deg C.
    # Ideal range is 20-30 deg C; extreme heat above 40 deg C penalizes points.
    if 20.0 <= avg_temp <= 30.0:
        temp_pts = 15.0
    elif avg_temp < 20.0:
        temp_pts = max(5.0, 15.0 - (20.0 - avg_temp) * 0.5)
    else:
        temp_pts = max(3.0, 15.0 - (avg_temp - 30.0) * 0.8)

    total_score = round(rad_pts + cloud_pts + rain_pts + temp_pts, 1)

    if total_score >= 80:
        category = "Excellent"
        summary = "Clear skies with strong solar irradiance and favorable operating temperatures."
    elif total_score >= 60:
        category = "Good"
        summary = "Moderate sunshine with minor cloud interference; solid generation expected."
    elif total_score >= 40:
        category = "Moderate"
        summary = "High cloud cover or elevated heat derating; reduced output expected."
    else:
        category = "Poor"
        summary = "Heavy cloudiness or rainfall substantially limiting panel generation."

    return {
        "score": total_score,
        "category": category,
        "summary": summary,
        "breakdown": {
            "radiation_points": round(rad_pts, 1),
            "cloud_points": round(cloud_pts, 1),
            "precipitation_points": round(rain_pts, 1),
            "temperature_points": round(temp_pts, 1)
        },
        "formula": "Score = Radiation (max 40) + Sky Clarity (max 30) + Rain Factor (max 15) + Thermal Factor (max 15)"
    }

def fetch_weather(latitude, longitude, location_name="Detected Location", state_name="Telangana"):
    # Retrieves live weather and next 48-hour hourly forecast from Open-Meteo.
    global _latest_weather_cache

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": [
            "temperature_2m",
            "relative_humidity_2m",
            "cloud_cover",
            "wind_speed_10m",
            "precipitation",
            "shortwave_radiation"
        ],
        "hourly": [
            "temperature_2m",
            "relative_humidity_2m",
            "cloud_cover",
            "wind_speed_10m",
            "precipitation",
            "shortwave_radiation"
        ],
        "timezone": "auto",
        "forecast_days": 2
    }

    try:
        resp = requests.get(API_URLS["weather_forecast"], params=params, headers=HTTP_HEADERS, timeout=6)
        if resp.status_code == 200:
            raw = resp.json()
            curr = raw.get("current", {})
            hourly = raw.get("hourly", {})

            # Prepare structured hourly forecast
            times = hourly.get("time", [])[:48]
            hourly_list = []
            for i in range(len(times)):
                rad_wm2 = float(hourly.get("shortwave_radiation", [0])[i] or 0.0)
                hourly_list.append({
                    "time": times[i],
                    "temperature": float(hourly.get("temperature_2m", [0])[i] or 0.0),
                    "humidity": float(hourly.get("relative_humidity_2m", [0])[i] or 0.0),
                    "cloud_cover": float(hourly.get("cloud_cover", [0])[i] or 0.0),
                    "wind_speed": float(hourly.get("wind_speed_10m", [0])[i] or 0.0),
                    "precipitation": float(hourly.get("precipitation", [0])[i] or 0.0),
                    # W/m2 from Open-Meteo
                    "radiation_wm2": rad_wm2,
                    # Convert W/m2 to kW/m2 to feed the ML model
                    "model_irradiation_kwm2": round(rad_wm2 / 1000.0, 4)
                })

            current_rad_wm2 = float(curr.get("shortwave_radiation", 0.0) or 0.0)
            current_weather = {
                "temperature": float(curr.get("temperature_2m", 28.0)),
                "humidity": float(curr.get("relative_humidity_2m", 50.0)),
                "cloud_cover": float(curr.get("cloud_cover", 20.0)),
                "wind_speed": float(curr.get("wind_speed_10m", 3.5)),
                "precipitation": float(curr.get("precipitation", 0.0)),
                "solar_radiation_wm2": current_rad_wm2,
                "model_irradiation_kwm2": round(current_rad_wm2 / 1000.0, 4),
                "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "Open-Meteo API",
                "source_label": "LIVE API"
            }

            # Calculate suitability score based on forecast average
            daytime_hours = [h for h in hourly_list[:24] if h["radiation_wm2"] > 10.0]
            if daytime_hours:
                avg_temp = sum(h["temperature"] for h in daytime_hours) / len(daytime_hours)
                avg_cloud = sum(h["cloud_cover"] for h in daytime_hours) / len(daytime_hours)
                avg_rad = sum(h["radiation_wm2"] for h in daytime_hours) / len(daytime_hours)
                tot_rain = sum(h["precipitation"] for h in hourly_list[:24])
            else:
                avg_temp = current_weather["temperature"]
                avg_cloud = current_weather["cloud_cover"]
                avg_rad = max(350.0, current_weather["solar_radiation_wm2"])
                tot_rain = current_weather["precipitation"]

            suitability = compute_suitability_score(avg_temp, avg_cloud, tot_rain, avg_rad)

            result = {
                "location": location_name,
                "state": state_name,
                "latitude": latitude,
                "longitude": longitude,
                "current": current_weather,
                "hourly": hourly_list,
                "suitability": suitability,
                "source_label": "LIVE API"
            }

            # Cache in memory
            _latest_weather_cache = result

            # Save in database table weather_records
            db_row = {
                "location": location_name[:150],
                "state": state_name[:100],
                "latitude": latitude,
                "longitude": longitude,
                "temperature": current_weather["temperature"],
                "humidity": current_weather["humidity"],
                "cloud_cover": current_weather["cloud_cover"],
                "wind_speed": current_weather["wind_speed"],
                "precipitation": current_weather["precipitation"],
                "solar_radiation": current_weather["solar_radiation_wm2"],
                "source": "Open-Meteo API",
                "fetched_at": datetime.now()
            }
            insert_row("weather_records", db_row)

            return result
    except Exception as e:
        print(f"[Weather Warning] Live weather API request failed: {e}")

    # Fallback to database cached records or memory cache
    cached_db = fetch_one(
        "SELECT * FROM weather_records WHERE state = %s ORDER BY fetched_at DESC LIMIT 1",
        (state_name,)
    )
    if cached_db:
        fetch_time = str(cached_db.get("fetched_at", "recent"))
        return {
            "location": cached_db.get("location", location_name),
            "state": cached_db.get("state", state_name),
            "latitude": float(cached_db.get("latitude", latitude)),
            "longitude": float(cached_db.get("longitude", longitude)),
            "current": {
                "temperature": float(cached_db.get("temperature", 28.0)),
                "humidity": float(cached_db.get("humidity", 50.0)),
                "cloud_cover": float(cached_db.get("cloud_cover", 20.0)),
                "wind_speed": float(cached_db.get("wind_speed", 3.0)),
                "precipitation": float(cached_db.get("precipitation", 0.0)),
                "solar_radiation_wm2": float(cached_db.get("solar_radiation", 500.0)),
                "model_irradiation_kwm2": round(float(cached_db.get("solar_radiation", 500.0)) / 1000.0, 4),
                "fetched_at": fetch_time,
                "source": "Cached Database Record",
                "source_label": f"cached at {fetch_time}"
            },
            "hourly": _build_synthetic_hourly(float(cached_db.get("temperature", 28.0))),
            "suitability": compute_suitability_score(28.0, 20.0, 0.0, 500.0),
            "source_label": f"cached at {fetch_time}"
        }

    if _latest_weather_cache:
        cached_result = dict(_latest_weather_cache)
        cached_result["source_label"] = "cached from memory"
        return cached_result

    # Default offline synthetic fallback
    return {
        "location": location_name,
        "state": state_name,
        "latitude": latitude,
        "longitude": longitude,
        "current": {
            "temperature": 30.0,
            "humidity": 45.0,
            "cloud_cover": 15.0,
            "wind_speed": 3.2,
            "precipitation": 0.0,
            "solar_radiation_wm2": 650.0,
            "model_irradiation_kwm2": 0.650,
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "Offline Baseline",
            "source_label": "ASSUMPTION"
        },
        "hourly": _build_synthetic_hourly(30.0),
        "suitability": compute_suitability_score(30.0, 15.0, 0.0, 650.0),
        "source_label": "ASSUMPTION"
    }

def _build_synthetic_hourly(base_temp):
    # Generates a standard solar day profile for fallback when APIs are offline
    today = datetime.now().strftime("%Y-%m-%d")
    hourly = []
    for h in range(24):
        # Solar radiation bell curve peaked at 13:00
        if 6 <= h <= 18:
            sun_factor = max(0.0, 1.0 - abs(h - 12.5) / 6.0)
            rad_wm2 = round(850.0 * sun_factor, 1)
        else:
            rad_wm2 = 0.0

        hourly.append({
            "time": f"{today}T{h:02d}:00",
            "temperature": round(base_temp - 4.0 + (rad_wm2 / 850.0 * 6.0), 1),
            "humidity": 50.0,
            "cloud_cover": 15.0,
            "wind_speed": 3.0,
            "precipitation": 0.0,
            "radiation_wm2": rad_wm2,
            "model_irradiation_kwm2": round(rad_wm2 / 1000.0, 4)
        })
    return hourly
