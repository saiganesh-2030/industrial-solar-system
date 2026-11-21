# Configuration settings and engineering assumptions for the solar system.
import os

# Base paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODELS_DIR = os.path.join(BASE_DIR, "models")

# Database configuration: uses SQLite by default so it runs on any computer with zero setup.
DB_PATH = os.path.join(DATA_DIR, "industrial_solar.db")

# Optional MySQL database settings (if connecting to an external MySQL server)
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", 3306)),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", "root"),
    "database": os.environ.get("DB_NAME", "industrial_solar"),
    "charset": "utf8mb4",
    "autocommit": True
}

# External API endpoints
API_URLS = {
    # Open-Meteo weather forecast (no API key required)
    "weather_forecast": "https://api.open-meteo.com/v1/forecast",
    # Open-Meteo city and coordinates lookup
    "geocoding": "https://geocoding-api.open-meteo.com/v1/search",
    # OpenStreetMap Nominatim reverse geocoder
    "nominatim_reverse": "https://nominatim.openstreetmap.org/reverse",
    # NASA POWER climatology API for long-term daily solar radiation
    "nasa_power": "https://power.larc.nasa.gov/api/temporal/climatology/point",
    # IP Geolocation primary endpoint
    "ip_geolocation": "https://ipapi.co/json/",
    # IP Geolocation fallback endpoint
    "ip_geolocation_fallback": "http://ip-api.com/json/"
}

# HTTP request headers
HTTP_HEADERS = {
    "User-Agent": "IndustrialSolarFeasibility/1.0 (academic college project; contact: student@college.edu)"
}

# Solar and economic assumptions
ASSUMPTIONS = {
    # System performance ratio (PR): accounts for inverter conversion loss,
    # wiring drop, dust deposition, and thermal loss.
    "performance_ratio": 0.75,

    # Annual PV module degradation: silicon panels lose roughly 0.5% output per year.
    "annual_degradation_rate": 0.005,

    # Operations and maintenance (O&M): budgeted at 1% of initial capital cost annually.
    "annual_om_rate_of_capex": 0.01,

    # Economic evaluation lifespan for industrial tier-1 solar panels.
    "system_life_years": 25,

    # Fallback solar peak sun hours (kWh/m2/day) across central and southern India.
    "default_peak_sun_hours": 4.8,

    # Fallback capital cost in INR per kW for turnkey industrial solar installations.
    "default_cost_per_kw": 42000.0,

    # Fallback industrial electricity tariff in INR per kWh if state tariff is missing.
    "default_tariff_per_kwh": 7.50,

    # Central Electricity Authority (CEA) standard baseline grid emission factor for India (kg CO2 / kWh).
    "co2_emission_factor_kg_per_kwh": 0.82,

    # Reference plant IDs from the training dataset
    "default_plant_id": 4135001,
    "plant_ids": [4135001, 4136001],

    # Plant observed peak generation in kW from training data (used for yield normalization)
    "plant_peak_ac": {
        4135001: 29150.21,
        4136001: 25979.76
    },

    # Linear regression coefficients for module temperature estimation
    # Equation: MODULE_TEMPERATURE = intercept + (coef_ambient * AMBIENT) + (coef_irrad * IRRADIATION)
    "module_temp_regression": {
        "intercept": -2.1415,
        "coef_ambient": 1.0303,
        "coef_irradiation": 27.9989,
        "r2_score": 0.9709
    },

    # Anomaly deviation threshold in kW per plant (calculated using Q3 + 1.5 * IQR)
    "anomaly_thresholds": {
        4135001: 752.93,
        4136001: 1565.40
    }
}
