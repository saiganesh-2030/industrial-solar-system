# Industrial Solar Power Prediction and Energy Feasibility Analysis System

An academic project providing automated solar power prediction, live meteorological monitoring, state-level industrial electricity tariff analysis, and 25-year financial feasibility sizing for manufacturing plants in India.

---

## 1. Project Directory Structure

```
industrial-solar-system/
  backend/
    app.py                     # Flask REST API server and static file handler
    config.py                  # Database settings, API endpoints, and engineering assumptions
    database.py                # MySQL connection helpers (mysql-connector-python)
    model_service.py           # ML prediction, temperature regression, and yield scaling
    location_service.py        # Geolocation and reverse geocoding via Nominatim & Open-Meteo
    weather_service.py         # Open-Meteo live weather, 48-hour forecasts, and suitability score
    solar_potential_service.py # NASA POWER climatology integration for Peak Sun Hours
    tariff_service.py          # State-wise industrial electricity tariff lookups
    cost_service.py            # Capital expenditure and annual O&M budgeting
    feasibility_engine.py      # Hourly time-aligned energy balance simulation engine
    deviation_service.py       # Historical replay of actual vs predicted inverter deviations
    test_model.py              # Verification script testing predictions on unseen test split
    seed_data.py               # Seeds MySQL tables from CSV files
    schema.sql                 # MySQL schema definitions
    requirements.txt           # Python dependency specifications
  models/
    random_forest.pkl          # Serialized Random Forest Regressor Pipeline
  data/
    combined_merged.csv        # 15-minute generation and weather dataset
    state_tariffs.csv          # Industrial HT tariffs across 15 Indian states
    industry_benchmarks.csv    # Connected load and 24-hour demand profiles for 6 industries
  notebooks/
    solar_model.ipynb          # Exploratory analysis, feature engineering, and model training
  frontend/
    index.html                 # Dashboard (Location, live weather, suitability, 24h forecast)
    prediction.html            # 48-Hour forward generation forecast and interactive capacity slider
    weather.html               # Live site weather telemetry and NASA POWER monthly charts
    feasibility.html           # Step-by-step automatic sizing and financial feasibility
    comparison.html            # Grid vs Hybrid vs Solar-Max lifecycle cost comparisons
    states.html                # Cross-state industrial tariff and payback period ranking
    deviation.html             # Historical replay of inverter deviations with IQR bounds
    model.html                 # ML algorithm comparison table and evaluation metrics
    css/
      style.css                # Academic theme stylesheet
    js/
      common.js                # Shared navigation, location detection, and modal logic
      index.js                 # Dashboard controllers
      prediction.js            # Prediction slider and 48-hour chart controllers
      weather.js               # Weather trends and NASA POWER chart controllers
      feasibility.js           # Feasibility workflow controllers
      comparison.js            # Options comparison and cashflow chart controllers
      states.js                # State tariff ranking controllers
      deviation.js             # Deviation replay controllers
      model.js                 # Model benchmark controllers
  docs/
    faculty_notes.md           # Comprehensive faculty viva preparation and formulas reference
  README.md                    # Setup and execution guide
```

---

## 2. Installation and Setup

### Prerequisites
- Python 3.10 or higher
- MySQL Server 8.0 or higher (optional for offline testing; SQLite is not used)

### Step 1: Create and Activate Virtual Environment
Open PowerShell or your command prompt in the project root:

```powershell
cd industrial-solar-system
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Step 2: Install Python Dependencies
```powershell
pip install -r backend/requirements.txt
```

---

## 3. Setting Up MySQL on Windows

The system stores weather logs, tariff schedules, demand benchmarks, and simulation records in MySQL.

### Option A: Using MySQL Community Server
1. Download the MySQL Installer from dev.mysql.com/downloads/installer.
2. Select "Server only" or "Developer Default" and follow the installation wizard.
3. When prompted, set the root password (for example: `root`).
4. Ensure the MySQL Windows service is started:
   ```powershell
   Start-Service MySQL80
   ```
5. Log into the MySQL shell and create the database:
   ```sql
   mysql -u root -p
   CREATE DATABASE industrial_solar;
   EXIT;
   ```

### Option B: Using XAMPP
1. Download and start XAMPP.
2. Start the MySQL module from the XAMPP Control Panel.
3. Open phpMyAdmin at `http://localhost/phpmyadmin` and create a database named `industrial_solar`.
4. In `backend/config.py`, verify that `user` is set to `root` and `password` is empty (`""`).

### Step 3: Initialize and Seed MySQL Database
Run the seed script to create all tables and populate tariffs and industry benchmarks:
```powershell
python backend/seed_data.py
```

Note: If MySQL is not running on your machine during development, the application automatically serves data from `data/state_tariffs.csv` and `data/industry_benchmarks.csv` without throwing unhandled exceptions.

---

## 4. Running the Model Verification Test

Verify the Random Forest pipeline against unseen test split records (dates on or after June 13, 2020):
```powershell
python backend/test_model.py
```
This prints sample actual vs predicted AC power values, individual discrepancies, and sample Mean Absolute Error (MAE).

---

## 5. Starting the Web Application

### One-Click Launch (Windows)
Double-click `start.bat` in either the workspace folder or the `industrial-solar-system` directory. It automatically verifies dependencies, starts the Flask server on port 5000, and opens your default browser at `http://localhost:5000`.

### Manual Terminal Command
```powershell
python backend/app.py
```

Once started, open your web browser and navigate to:
```
http://localhost:5000
```

The application automatically detects your location, queries live weather, loads the applicable state tariff, and evaluates factory solar feasibility.

---

## 6. Live External APIs and Verification Endpoints

The system relies on five live, free external endpoints without requiring commercial API keys:

| API Service | Endpoint URL | Purpose in Project |
| :--- | :--- | :--- |
| Open-Meteo Forecast | `https://api.open-meteo.com/v1/forecast` | Current weather and 48-hour shortwave solar radiation (W/m2) |
| NASA POWER Climatology | `https://power.larc.nasa.gov/api/temporal/climatology/point` | Long-term monthly daily solar radiation (`ALLSKY_SFC_SW_DWN` in kWh/m2/day) |
| OpenStreetMap Nominatim | `https://nominatim.openstreetmap.org/reverse` | Reverse geocoding GPS coordinates to Indian state names |
| Open-Meteo Geocoding | `https://geocoding-api.open-meteo.com/v1/search` | Search cities and extract Indian state from `admin1` |
| IP Geolocation | `https://ipapi.co/json/` | Automatic location fallback when browser GPS is blocked |

### Testing Live APIs Directly via Flask Backend:
- Location detection: `http://localhost:5000/api/location`
- Live weather and suitability score: `http://localhost:5000/api/weather?lat=17.385&lon=78.486`
- NASA solar radiation: `http://localhost:5000/api/solar-potential?lat=17.385&lon=78.486`
- Forward 48-hour generation forecast: `http://localhost:5000/api/prediction?lat=17.385&lon=78.486&capacity=100`
- State industrial electricity tariff: `http://localhost:5000/api/tariff?state=Telangana`
- Automated feasibility simulation: `http://localhost:5000/api/feasibility?lat=17.385&lon=78.486&state=Telangana&industry=Light%20Manufacturing`
- Cross-state ranking: `http://localhost:5000/api/states-comparison`
- Historical deviation replay: `http://localhost:5000/api/deviation?plant_id=4135001`

---

## 7. Key Project Highlights for Faculty Review

- Industries Only: All load profiles, tariff structures, and sizing equations are built specifically for manufacturing units and commercial parks.
- No Invented Data: Every metric on the interface carries a visible source label (`LIVE API`, `HISTORICAL API`, `MODEL PREDICTION`, `BENCHMARK ESTIMATE`, or `ASSUMPTION`).
- Explainable Physical Equations: Back-of-panel module temperature is calculated via empirical linear regression (`R2 = 0.9709`) to account for thermal derating.
- Automatic Workflow: Coordinates, weather, solar insolation, and state tariffs are resolved automatically without requiring manual parameter typing.
- Academic Rigor: MAE, RMSE, and R2 are treated strictly as evaluation metrics rather than algorithms. Deviations are classified as "unusual deviations" rather than equipment failures.
