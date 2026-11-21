# Solar potential service using NASA POWER Climatology API.
# Fetches multi-year monthly average daily solar radiation (ALLSKY_SFC_SW_DWN in kWh/m2/day).
# Peak Sun Hours (PSH) per day directly corresponds to this solar insolation value.

import requests
from config import API_URLS, HTTP_HEADERS, ASSUMPTIONS

# Cache to avoid repetitive NASA POWER queries for the same coordinates
_nasa_cache = {}

# Standard Indian monthly solar radiation fallback (kWh/m2/day) across central India
DEFAULT_MONTHLY_INSOLATION = {
    "JAN": 4.55,
    "FEB": 5.25,
    "MAR": 6.10,
    "APR": 6.45,
    "MAY": 6.30,
    "JUN": 4.80,
    "JUL": 3.90,
    "AUG": 3.85,
    "SEP": 4.60,
    "OCT": 5.10,
    "NOV": 4.70,
    "DEC": 4.35
}

def fetch_solar_potential(latitude, longitude):
    # Returns 12 monthly solar radiation averages, annual average PSH, and source label.
    cache_key = f"{round(latitude, 2)},{round(longitude, 2)}"
    if cache_key in _nasa_cache:
        return _nasa_cache[cache_key]

    params = {
        "parameters": "ALLSKY_SFC_SW_DWN",
        "community": "RE",
        "longitude": longitude,
        "latitude": latitude,
        "format": "JSON"
    }

    try:
        resp = requests.get(API_URLS["nasa_power"], params=params, headers=HTTP_HEADERS, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            param_dict = data.get("properties", {}).get("parameter", {}).get("ALLSKY_SFC_SW_DWN", {})

            month_keys = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
            monthly_values = {}
            valid_nums = []

            for m in month_keys:
                val = param_dict.get(m)
                if val is not None and val > 0:
                    monthly_values[m] = round(float(val), 2)
                    valid_nums.append(float(val))
                else:
                    monthly_values[m] = DEFAULT_MONTHLY_INSOLATION[m]
                    valid_nums.append(DEFAULT_MONTHLY_INSOLATION[m])

            # Annual daily average peak sun hours
            annual_val = param_dict.get("ANN")
            if annual_val is not None and annual_val > 0:
                annual_average_psh = round(float(annual_val), 2)
            else:
                annual_average_psh = round(sum(valid_nums) / len(valid_nums), 2)

            result = {
                "latitude": latitude,
                "longitude": longitude,
                "monthly_radiation_kwh_m2_day": monthly_values,
                "annual_average_peak_sun_hours": annual_average_psh,
                "parameter": "ALLSKY_SFC_SW_DWN (All Sky Surface Shortwave Downward Irradiance)",
                "unit": "kWh/m2/day",
                "source": "NASA POWER Climatology API",
                "source_label": "HISTORICAL API"
            }
            _nasa_cache[cache_key] = result
            return result
    except Exception as e:
        print(f"[NASA POWER Notice] Request failed: {e}. Using regional climatology fallback.")

    # Fallback to standard regional benchmark
    annual_avg = round(sum(DEFAULT_MONTHLY_INSOLATION.values()) / 12.0, 2)
    fallback_result = {
        "latitude": latitude,
        "longitude": longitude,
        "monthly_radiation_kwh_m2_day": DEFAULT_MONTHLY_INSOLATION,
        "annual_average_peak_sun_hours": annual_avg,
        "parameter": "ALLSKY_SFC_SW_DWN",
        "unit": "kWh/m2/day",
        "source": "Central India Benchmark Solar Insolation",
        "source_label": "BENCHMARK ESTIMATE"
    }
    _nasa_cache[cache_key] = fallback_result
    return fallback_result
