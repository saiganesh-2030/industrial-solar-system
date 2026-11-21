-- MySQL database schema for Industrial Solar Power System
-- Database name: industrial_solar

CREATE DATABASE IF NOT EXISTS industrial_solar;
USE industrial_solar;

-- 1. Live and historical weather readings fetched from APIs
CREATE TABLE IF NOT EXISTS weather_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    location VARCHAR(150) NOT NULL,
    state VARCHAR(100) NOT NULL,
    latitude DECIMAL(9, 6) NOT NULL,
    longitude DECIMAL(9, 6) NOT NULL,
    temperature DECIMAL(5, 2) NOT NULL,
    humidity DECIMAL(5, 2) NOT NULL,
    cloud_cover DECIMAL(5, 2) NOT NULL,
    wind_speed DECIMAL(5, 2) NOT NULL,
    precipitation DECIMAL(5, 2) NOT NULL,
    solar_radiation DECIMAL(7, 2) NOT NULL,
    source VARCHAR(50) NOT NULL,
    fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2. Solar model predictions log
CREATE TABLE IF NOT EXISTS solar_predictions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    location VARCHAR(150) NOT NULL,
    plant_id INT NOT NULL,
    input_measurements TEXT NOT NULL,
    predicted_kw DECIMAL(10, 2) NOT NULL,
    predicted_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 3. Actual generation records from plant loggers
CREATE TABLE IF NOT EXISTS actual_generation (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plant_id INT NOT NULL,
    actual_ac_power DECIMAL(10, 2) NOT NULL,
    record_time DATETIME NOT NULL
);

-- 4. Anomaly and unusual deviation logs
CREATE TABLE IF NOT EXISTS anomaly_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plant_id INT NOT NULL,
    record_time DATETIME NOT NULL,
    actual DECIMAL(10, 2) NOT NULL,
    predicted DECIMAL(10, 2) NOT NULL,
    deviation DECIMAL(10, 2) NOT NULL,
    threshold DECIMAL(10, 2) NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 5. Verified and unverified state electricity tariffs
CREATE TABLE IF NOT EXISTS state_tariffs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    state VARCHAR(100) NOT NULL UNIQUE,
    discom VARCHAR(150) NOT NULL,
    category VARCHAR(100) NOT NULL,
    energy_charge_per_kwh DECIMAL(6, 2) NULL,
    fixed_charge_note TEXT,
    export_credit_per_kwh DECIMAL(6, 2) NULL,
    source_name VARCHAR(200) NOT NULL,
    source_url VARCHAR(300) NOT NULL,
    effective_date VARCHAR(50) NOT NULL,
    verified BOOLEAN DEFAULT FALSE,
    notes TEXT,
    last_checked VARCHAR(50) NOT NULL
);

-- 6. Capital cost benchmarks per kW
CREATE TABLE IF NOT EXISTS cost_benchmarks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    region VARCHAR(100) NOT NULL,
    cost_per_kw DECIMAL(10, 2) NOT NULL,
    source_name VARCHAR(200) NOT NULL,
    source_url VARCHAR(300) NOT NULL,
    as_of_date VARCHAR(50) NOT NULL,
    notes TEXT
);

-- 7. Factory industry demand benchmarks and hourly load profiles
CREATE TABLE IF NOT EXISTS industry_benchmarks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    industry_type VARCHAR(100) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    connected_load_kw DECIMAL(10, 2) NOT NULL,
    hourly_profile_json TEXT NOT NULL,
    source_note TEXT NOT NULL
);

-- 8. Energy feasibility analysis results
CREATE TABLE IF NOT EXISTS energy_analysis (
    id INT AUTO_INCREMENT PRIMARY KEY,
    location VARCHAR(150) NOT NULL,
    state VARCHAR(100) NOT NULL,
    industry_type VARCHAR(100) NOT NULL,
    estimated_daily_demand_kwh DECIMAL(10, 2) NOT NULL,
    recommended_capacity_kw DECIMAL(10, 2) NOT NULL,
    annual_solar_generation_kwh DECIMAL(12, 2) NOT NULL,
    grid_cost DECIMAL(12, 2) NOT NULL,
    hybrid_cost DECIMAL(12, 2) NOT NULL,
    solar_cost DECIMAL(12, 2) NOT NULL,
    annual_savings DECIMAL(12, 2) NOT NULL,
    installation_cost DECIMAL(12, 2) NOT NULL,
    roi_percent DECIMAL(6, 2) NOT NULL,
    payback_years DECIMAL(5, 2) NOT NULL,
    recommendation VARCHAR(50) NOT NULL,
    confidence VARCHAR(20) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
