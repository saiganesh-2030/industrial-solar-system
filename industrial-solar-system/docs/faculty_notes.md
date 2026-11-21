# Faculty Project Notes and Viva Reference Manual

Project Title: Industrial Solar Power Prediction and Energy Feasibility Analysis System
Target Scope: Industrial manufacturing facilities and commercial parks in India
Tech Stack: Python Flask, MySQL, Scikit-Learn, Vanilla HTML/CSS/JavaScript, Chart.js

---

## 1. Project Motivation and Academic Objectives

Most solar rooftop calculators either ask users to guess their weather and solar radiation numbers, or assume a generic household electricity bill. This project is built specifically for industrial facilities. 

In an industrial plant, power tariffs run under High Tension (HT) or Large Supply categories, daily demand follows factory shifts, and solar generation directly offsets expensive daytime grid power. 

The system automates three tasks:
1. Detects the factory location and fetches live weather and multi-year solar insolation.
2. Predicts solar generation using a trained machine learning pipeline that accounts for panel temperature and cyclic solar geometry.
3. Performs an hourly financial feasibility analysis comparing grid-only, optimized hybrid, and full solar systems across a 25-year lifecycle.

---

## 2. System Architecture

The project uses a clean three-layer architecture:

1. Frontend Layer:
Plain HTML5, CSS3, and JavaScript using the Fetch API and Chart.js. There are no heavy frameworks like React or Angular. Each page has a single purpose, loads its own script, and shares common styling and location state through `common.js`.

2. Backend Service Layer:
A modular Python Flask application with single-purpose services:
- `location_service.py`: Resolves coordinates to Indian state names using OpenStreetMap Nominatim and Open-Meteo.
- `weather_service.py`: Fetches 48-hour forecasts from Open-Meteo and computes an explainable solar weather suitability score.
- `solar_potential_service.py`: Fetches long-term monthly daily solar radiation from the NASA POWER API.
- `model_service.py`: Prepares inputs and runs predictions through the trained Random Forest pipeline.
- `tariff_service.py`: Retrieves industrial HT tariffs by state.
- `cost_service.py`: Provides capital expenditure and maintenance benchmarks.
- `feasibility_engine.py`: Runs 24-hour time-aligned energy balance simulations across system sizes.
- `deviation_service.py`: Replays test split data to detect unusual generation deviations.

3. Database Layer:
MySQL using `mysql-connector-python`. Tables store fetched weather logs, ML predictions, tariff schedules, industry demand profiles, and feasibility outputs.

---

## 3. External Live APIs, Endpoints, and Ingestion Mechanics

The system operates automatically without asking users to type weather, radiation, tariff, or coordinate values. It integrates five external endpoints across weather, solar climatology, and geocoding:

### 3.1. Open-Meteo Weather Forecast API (Live Weather & Solar Irradiance)
- Endpoint URL: `https://api.open-meteo.com/v1/forecast`
- Authentication: Free, public access without API keys.
- Method: HTTP GET
- Request Parameters:
  - `latitude`: Site latitude in decimal degrees (e.g. 17.3850).
  - `longitude`: Site longitude in decimal degrees (e.g. 78.4867).
  - `current`: List of current variables (`temperature_2m`, `relative_humidity_2m`, `cloud_cover`, `wind_speed_10m`, `precipitation`, `shortwave_radiation`).
  - `hourly`: List of hourly forecast variables (same parameters for next 48 hours).
  - `timezone`: `auto` (resolves to Asia/Kolkata automatically).
  - `forecast_days`: 2 (retrieves full 48-hour forward projection).
- Example Request:
  `https://api.open-meteo.com/v1/forecast?latitude=17.385&longitude=78.486&current=temperature_2m,relative_humidity_2m,cloud_cover,wind_speed_10m,precipitation,shortwave_radiation&hourly=temperature_2m,relative_humidity_2m,cloud_cover,wind_speed_10m,precipitation,shortwave_radiation&timezone=auto&forecast_days=2`
- Field Extraction and Conversions:
  - `current.temperature_2m`: Ambient air temperature at 2m elevation in degrees Celsius.
  - `current.relative_humidity_2m`: Relative humidity percentage.
  - `current.cloud_cover`: Total cloud coverage percentage (0% = clear sky, 100% = total overcast).
  - `current.wind_speed_10m`: Wind velocity at 10m elevation in km/h.
  - `current.precipitation`: Liquid rainfall accumulation in mm.
  - `current.shortwave_radiation`: Global horizontal solar irradiance in W/m2.
- Conversion to ML Input:
  The Random Forest model requires `IRRADIATION` in kW/m2. The API value is converted using:
  `IRRADIATION (kW/m2) = shortwave_radiation (W/m2) / 1000.0`
- Caching and Database Persistence:
  Every successful fetch is written to the `weather_records` table with location, state, coordinates, timestamp, and source label `LIVE API`.
- Fallback Policy:
  If network connection drops or Open-Meteo returns an error, the backend queries `weather_records` for the latest cached record for that state. The frontend labels this data as `cached at <timestamp>` per project rule 6. If no database records exist, an offline baseline is loaded with label `ASSUMPTION`.

### 3.2. NASA POWER Climatology API (Long-Term Solar Potential)
- Endpoint URL: `https://power.larc.nasa.gov/api/temporal/climatology/point`
- Authentication: Free, public access provided by NASA Langley Research Center.
- Method: HTTP GET
- Request Parameters:
  - `parameters`: `ALLSKY_SFC_SW_DWN` (All Sky Surface Shortwave Downward Irradiance).
  - `community`: `RE` (Renewable Energy user profile).
  - `latitude`: Site latitude.
  - `longitude`: Site longitude.
  - `format`: `JSON`
- Example Request:
  `https://power.larc.nasa.gov/api/temporal/climatology/point?parameters=ALLSKY_SFC_SW_DWN&community=RE&longitude=78.4867&latitude=17.3850&format=JSON`
- Field Extraction:
  - Multi-year climatological monthly daily averages: JAN through DEC values in kWh/m2/day.
  - `ANN`: Annual average daily insolation in kWh/m2/day.
- Engineering Significance:
  One Peak Sun Hour (PSH) equals 1 kWh/m2 of solar energy. The annual average `ANN` (e.g. 4.80 kWh/m2/day in central India) serves as the base PSH parameter in the solar sizing formula:
  `Capacity (kW) = Daily Demand (kWh) / (PSH * Performance Ratio)`
- Caching:
  Coordinates are rounded to 2 decimal places and cached in memory. Monthly values are permanently saved to prevent repeated calls for the same district.
- Fallback:
  If NASA servers time out, the backend supplies standard regional insolation benchmarks for central India (4.80 kWh/m2/day annual mean) with label `BENCHMARK ESTIMATE`.

### 3.3. OpenStreetMap Nominatim Reverse Geocoding API
- Endpoint URL: `https://nominatim.openstreetmap.org/reverse`
- Method: HTTP GET
- Request Parameters:
  - `lat`: Browser GPS latitude.
  - `lon`: Browser GPS longitude.
  - `format`: `jsonv2`
  - `addressdetails`: 1
- Headers:
  Requires a custom `User-Agent` header (`IndustrialSolarFeasibility/1.0 (academic college project)`). Calling Nominatim without a custom User-Agent causes immediate HTTP 403 blocks.
- State Resolution Logic:
  The response `address` dictionary is parsed in priority order:
  `state = address.get("state") or address.get("province") or "Telangana"`
  `city = address.get("city") or address.get("town") or address.get("county") or "Detected Industrial Hub"`
  Resolving the Indian state is essential because electricity tariffs differ across DISCOMs.
- Rate Limiting and Caching:
  Nominatim limits traffic to 1 request per second. The backend rounds coordinates to 3 decimal places (~100m grid) and caches responses in memory.

### 3.4. Open-Meteo Geocoding Search API (City and District Lookup)
- Endpoint URL: `https://geocoding-api.open-meteo.com/v1/search`
- Method: HTTP GET
- Request Parameters:
  - `name`: User search string (e.g. "Surat", "Pune", "Coimbatore").
  - `count`: 8 (returns up to 8 candidate cities).
  - `language`: `en`
  - `format`: `json`
- State Resolution:
  The returned items contain `admin1`, which holds the official state name (such as Gujarat for Surat, or Maharashtra for Pune). When users select a city from the search dropdown, `admin1` directly maps to the tariff table.

### 3.5. IP Geolocation Fallback APIs (Automatic Location Detection)
When a user accesses the site from a computer where browser GPS is unavailable or blocked, the backend detects the location using free IP geolocation services:
- Primary: `https://ipapi.co/json/`
- Secondary Fallback: `http://ip-api.com/json/`
- Extracted Fields: `latitude`, `longitude`, `city`, `region` (state).
- UI Labeling: Whenever IP detection is used, the navigation bar displays `approximate (IP based)` and carries the badge `LIVE API`. If entirely offline, the site defaults to Hyderabad, Telangana with badge `ASSUMPTION`.

---

## 4. Machine Learning Model Architecture

The model was trained on 15-minute operational generation records from two utility-scale solar plants in India (Plant 4135001 and Plant 4136001), spanning May 15 to June 17, 2020.

### Input Features (Exact Order)
1. `PLANT_ID`: Categorical identifier (4135001 or 4136001), processed via OneHotEncoder.
2. `TIME_SIN`: Cyclical sine transform of time of day: `sin(2 * pi * minutes / 1440)`.
3. `TIME_COS`: Cyclical cosine transform of time of day: `cos(2 * pi * minutes / 1440)`.
4. `AMBIENT_TEMPERATURE`: Outdoor ambient temperature in degrees Celsius.
5. `MODULE_TEMPERATURE`: PV panel surface temperature in degrees Celsius.
6. `IRRADIATION`: Solar irradiance in kW/m2.

### Target Variable
`AC_POWER`: Inverter AC power output in kW.

### Time-Based Split
Records were sorted chronologically and split without shuffling:
- Training split: First 70% of unique timestamps
- Validation split: Middle 15% of timestamps
- Testing split: Final 15% of timestamps (dates on or after June 13, 2020)

### Algorithm Evaluation on Validation Set
- Linear Regression: MAE 1690.87 kW, RMSE 2341.52 kW, R2 0.8921
- Tuned Ridge: MAE 1689.45 kW, RMSE 2339.80 kW, R2 0.8923
- Tuned Lasso: MAE 1688.92 kW, RMSE 2338.15 kW, R2 0.8925
- Tuned SVR: MAE 1120.45 kW, RMSE 1890.30 kW, R2 0.9298
- Tuned Random Forest: MAE 414.63 kW, RMSE 1188.86 kW, R2 0.9721

### Final Test Split Metrics (Selected Random Forest)
- Mean Absolute Error (MAE): 500.72 kW
- Root Mean Squared Error (RMSE): 1363.42 kW
- Coefficient of Determination (R2): 0.9628

---

## 5. Engineering Conversions and Physics Equations

### Unit Conversion for Irradiance
Open-Meteo returns global horizontal solar radiation in W/m2. The training dataset recorded IRRADIATION in kW/m2 with a mean of 0.2314 kW/m2 and peak values around 1.22 kW/m2. 
Conversion: `IRRADIATION (kW/m2) = shortwave_radiation (W/m2) / 1000.0`.

### Module Temperature Estimation
Weather APIs do not report solar cell surface temperature. Silicon panels warm up under sunlight, degrading efficiency by roughly 0.4% per degree Celsius above 25 degrees. We fitted a linear regression on the training dataset:
`MODULE_TEMPERATURE = -2.1415 + (1.0303 * AMBIENT_TEMPERATURE) + (27.9989 * IRRADIATION)`
This linear fit achieves an R2 score of 0.9709.

### Normalised Yield Fraction
The training dataset belongs to multi-megawatt utility plants (Plant 4135001 observed peak is 29,150.21 kW). To scale output to any factory size:
`yield_fraction = predicted_ac / plant_reference_peak`
`factory_hourly_generation = yield_fraction * target_factory_capacity_kw`

---

## 6. Energy Feasibility Formulas with Worked Numeric Example

Consider a Light Manufacturing facility in Hyderabad, Telangana.

### Step 1: Factory Demand
- Industry connected load: 250 kW
- 24-hour demand profile sum: 11.23 load fractions
- Daily demand: `250 kW * 11.23 = 2,807.5 kWh/day`
- Annual demand: `2,807.5 * 365 = 1,024,737.5 kWh/year`

### Step 2: Solar Sizing Capacity
- Location Peak Sun Hours (PSH): 4.80 kWh/m2/day
- Performance Ratio (PR): 0.75
- 100% capacity: `2,807.5 / (4.80 * 0.75) = 779.8 kW`
- Sizing options:
  - 25% sizing: 195.0 kW
  - 50% sizing: 389.9 kW
  - 75% sizing: 584.9 kW
  - 100% sizing: 779.8 kW

### Step 3: Hourly Energy Balance (for 50% sizing = 389.9 kW)
For each hour t of the day:
- `SelfConsumption_t = min(Generation_t, Demand_t)`
- `GridImport_t = max(0, Demand_t - Generation_t)`
- `Export_t = max(0, Generation_t - Demand_t)`
Summing across 24 hours and scaling to the year:
- Annual generation: `389.9 kW * 1,314 kWh/kW = 512,328 kWh`
- Annual self-consumed: `486,712 kWh`
- Annual grid import: `1,024,738 - 486,712 = 538,026 kWh`

### Step 4: Financial Calculations
- Grid tariff (Telangana HT-1): Rs 7.65 / kWh
- Installation capex benchmark: Rs 42,000 / kW
- Total capex: `389.9 kW * Rs 42,000 = Rs 1,63,75,800`
- Annual O&M (1% of capex): `Rs 1,63,758 / year`
- Grid-only annual bill: `1,024,738 * 7.65 = Rs 78,39,246`
- Hybrid annual cost: `(538,026 * 7.65) + 1,63,758 = Rs 42,79,657`
- Annual net savings: `78,39,246 - 42,79,657 = Rs 35,59,589`
- Simple payback: `1,63,75,800 / 35,59,589 = 4.60 years`
- ROI: `(35,59,589 / 1,63,75,800) * 100 = 21.74%`

### Step 5: Levelized Cost of Solar (T_solar)
Over 25 years with 0.5% annual degradation:
- Cumulative generation: ~12,050,000 kWh
- Capex per kWh: `1,63,75,800 / 12,050,000 = Rs 1.36 / kWh`
- O&M per kWh: `1,63,758 / 482,000 = Rs 0.34 / kWh`
- `T_solar = 1.36 + 0.34 = Rs 1.70 / kWh` (compared to Rs 7.65 / kWh grid power)

### Step 6: Environmental Carbon Offset (CO2 Metric)
The Central Electricity Authority (CEA) of India sets the national baseline grid emission factor at approximately 0.82 kg CO2 per kWh generated by thermal fossil plants.
For this 50% sizing system generating 512,328 kWh/year:
`Annual CO2 Avoided = (512,328 kWh * 0.82 kg/kWh) / 1000 = 420.1 metric tonnes/year`

---

## 7. Recommendation Rules

The system compares three options: Grid Only, Hybrid (best net savings among 25%, 50%, and 75%), and Solar-Max (100%).
- If simple payback is 7.0 years or less with positive net savings: Recommend Hybrid or Solar-Max (whichever achieves higher 25-year net economic savings).
- If simple payback exceeds 10.0 years or savings are negative: Recommend continuing with Grid Only.
- In intermediate cases (payback between 7 and 10 years): Recommend Hybrid with a marginal suitability note.

Confidence Scoring:
- High: Live weather API connected + verified SERC tariff + NASA POWER climatology.
- Medium: Live weather API connected + unverified SERC tariff schedule.
- Low: Unverified tariff or fallback assumption used.

---

## 8. Statistical Deviation Detection Method

Inverter monitoring cannot run live without real hardware telemetry. The system provides a historical replay on unseen test data (dates on or after June 13, 2020).

Threshold Formula:
`threshold = Q3 + 1.5 * IQR`
Where Q1 is the 25th percentile, Q3 is the 75th percentile, and `IQR = Q3 - Q1` of absolute deviations on the validation set.
- Plant 4135001 threshold: 752.93 kW
- Plant 4136001 threshold: 1565.40 kW

Classification Categories:
- Normal: Absolute deviation is within the threshold.
- Unusual underperformance: Actual generation is below predicted by more than the threshold.
- Unusual overperformance: Actual generation exceeds predicted by more than the threshold.
- Possible sensor issue: Irradiance is high (> 0.25 kW/m2) but actual generation is 50 kW or less while predicted is above 1000 kW.

Academic terminology note: In accordance with academic guidelines, deviations are never labeled as equipment failures or faults.

---

## 9. Known Academic Limitations

1. Training Data Duration: The machine learning model was trained on one month of data (May 15 to June 17, 2020). Predictions outside summer months are scaled using NASA POWER monthly solar radiation profiles.
2. Estimated Module Temperature: Live weather APIs do not measure back-of-panel temperatures, so panel temperatures are estimated through linear regression.
3. Benchmark Demand Profiles: Hourly factory consumption is based on representative industry profiles rather than real-time factory smart meters.
4. Tariff Verification: State electricity tariffs reflect published SERC schedules, but remain marked as unverified until audited against active DISCOM billing circulars.

---

## 10. Likely Faculty Viva Questions and Concise Answers

Q1: Why did you choose Random Forest instead of Deep Learning (like LSTM or ANN)?
Answer: The dataset consists of tabular environmental features (temperature, time, irradiance) with 6,417 records. Random Forest avoids overfitting on small datasets, trains quickly without GPU requirements, handles non-linear relationships naturally, and achieved an R2 score of 0.963 on unseen test data.

Q2: Are MAE, RMSE, and R2 machine learning models?
Answer: No. MAE, RMSE, and R2 are statistical evaluation metrics used to quantify error and variance. The algorithms evaluated were Linear Regression, Ridge, Lasso, SVR, and Random Forest.

Q3: How do you get live solar generation without physical sensors on the factory roof?
Answer: The system fetches live weather forecasts from Open-Meteo, estimates panel surface temperature through our fitted regression equation, runs the features through the Random Forest pipeline, and scales the resulting yield fraction to the factory's target capacity.

Q4: What is the difference between peak sun hours and sunshine duration?
Answer: Sunshine duration counts any hour the sun is visible regardless of intensity. Peak Sun Hours (PSH) measures total daily solar radiation normalized to standard test conditions of 1,000 W/m2 (1 kW/m2). A location receiving 4.8 kWh/m2 of solar energy in a day has 4.8 Peak Sun Hours.

Q5: Why evaluate 25%, 50%, 75%, and 100% sizes instead of only 100%?
Answer: Industrial factories have specific shifts. Sizing solar for 100% of daily demand often causes massive generation surplus at midday when factory demand drops (such as during lunch breaks or single-shift factories). Without a high net-metering export credit, excess solar exported to the grid loses money. Evaluating multiple sizes identifies the point of maximum self-consumption and shortest payback.

Q6: Why is Plant 2 power generation lower than Plant 1, and why are their deviation thresholds different?
Answer: In the dataset, Plant 1 reaches peak generation of 29,150 kW and follows an unconstrained bell curve matching sunlight intensity. Plant 2 exhibits severe inverter clipping and thermal saturation, capping midday output at approximately 13,000 kW despite strong sunlight, and runs about 2.5 deg C hotter on average. Because Plant 2 clips generation, its power-to-irradiance ratio is roughly 81.4% of Plant 1. This higher variance at midday widens Plant 2's interquartile range, giving it a threshold of 1565.40 kW compared to 752.93 kW for Plant 1.

Q7: How does selecting Plant 1 or Plant 2 change feasibility and state rankings?
Answer: When Plant 2 is selected, its lower yield fraction directly scales down expected hourly kWh generation. Lower generation means lower displaced grid electricity, reducing annual financial savings. This causes the payback period to lengthen (for example, from ~3.99 years to ~4.41 years for standard manufacturing in Telangana) and alters state feasibility rankings across DISCOMs.

Q8: How does the interactive deviation evaluator work without hardware telemetry?
Answer: Instead of passively browsing an old 60-row static table, users or examiners enter an operational timestamp, irradiance, ambient temperature, and actual measured inverter output. The system runs the ML model to get the theoretical expected power, calculates the exact deviation in kW and percentage, compares the gap against the statistical IQR threshold, and classifies the status into Normal, Unusual underperformance, Unusual overperformance, or Possible sensor issue with a physical explanation.
