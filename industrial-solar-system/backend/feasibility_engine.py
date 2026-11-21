# Energy Feasibility Engine for Industrial Solar Sizing and Economic Analysis.
# Performs 24-hour hourly time-aligned simulation across 4 system sizing options (25%, 50%, 75%, 100%).
# Evaluates 25-year lifecycle metrics including degradation, O&M, levelized solar cost, ROI, and payback.

import json
import os
import csv
from datetime import datetime
from config import DATA_DIR, ASSUMPTIONS
from model_service import predict_ac_power, calculate_yield_fraction
from solar_potential_service import fetch_solar_potential
from tariff_service import get_tariff_for_state
from cost_service import get_installation_cost_per_kw
from database import insert_row, fetch_one, fetch_all

def get_industry_benchmark(industry_type=None):
    # Retrieves industry connected load and 24-hour load profile.
    # Uses database first; falls back to CSV file if database is offline.
    if industry_type:
        db_row = fetch_one("SELECT * FROM industry_benchmarks WHERE industry_type = %s", (industry_type,))
        if db_row:
            return {
                "industry_type": db_row["industry_type"],
                "description": db_row["description"],
                "connected_load_kw": float(db_row["connected_load_kw"]),
                "hourly_profile": json.loads(db_row["hourly_profile_json"]),
                "source_note": db_row["source_note"]
            }

    csv_path = os.path.join(DATA_DIR, "industry_benchmarks.csv")
    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not industry_type or row["industry_type"].lower() == industry_type.lower():
                    return {
                        "industry_type": row["industry_type"],
                        "description": row["description"],
                        "connected_load_kw": float(row["connected_load_kw"]),
                        "hourly_profile": json.loads(row["hourly_profile_json"]),
                        "source_note": row["source_note"]
                    }

    # Safe fallback if file is missing
    return {
        "industry_type": "Light Manufacturing",
        "description": "Component assembly and packaging unit operating daytime shift",
        "connected_load_kw": 250.0,
        "hourly_profile": [0.15, 0.15, 0.15, 0.15, 0.15, 0.18, 0.25, 0.45, 0.88, 0.92, 0.95, 0.90, 0.85, 0.90, 0.92, 0.95, 0.90, 0.85, 0.50, 0.30, 0.20, 0.18, 0.15, 0.15],
        "source_note": "BENCHMARK ESTIMATE, not measured factory data (Bureau of Energy Efficiency industrial audit guidelines)"
    }

def get_all_industry_types():
    # Returns list of available industry types for user selection dropdown
    csv_path = os.path.join(DATA_DIR, "industry_benchmarks.csv")
    if os.path.exists(csv_path):
        types = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                types.append({
                    "industry_type": row["industry_type"],
                    "description": row["description"],
                    "connected_load_kw": float(row["connected_load_kw"])
                })
        return types
    return [{"industry_type": "Light Manufacturing", "description": "Standard assembly", "connected_load_kw": 250.0}]

def generate_hourly_yield_profile(latitude, longitude, weather_hourly=None, plant_id=4135001):
    # Generates standard 24-hour solar generation in kWh per kW of installed capacity.
    # Uses ML model predictions for the selected plant and normalizes against observed plant peak.
    yield_profile_kwh_per_kw = []
    plant_id = int(plant_id)

    if weather_hourly and len(weather_hourly) >= 24:
        # Use first 24 hours of forecast
        for h in range(24):
            item = weather_hourly[h]
            amb_temp = item["temperature"]
            irrad = item["model_irradiation_kwm2"]
            hour_ts = datetime.strptime(item["time"].split("+")[0], "%Y-%m-%dT%H:%M")

            if irrad > 0.001:
                # ML model predict for selected plant
                pred_ac = predict_ac_power(
                    plant_id=plant_id,
                    timestamp=hour_ts,
                    ambient_temperature=amb_temp,
                    irradiation=irrad
                )
                fraction = calculate_yield_fraction(pred_ac, plant_id=plant_id)
                yield_profile_kwh_per_kw.append(round(fraction, 4))
            else:
                yield_profile_kwh_per_kw.append(0.0)
    else:
        # Synthetic solar curve matching selected plant model behavior
        for h in range(24):
            if 6 <= h <= 18:
                # Bell curve peaking at hour 12-13
                factor = max(0.0, 1.0 - abs(h - 12.5) / 6.0)
                irrad = 0.85 * factor
                dummy_time = datetime(2020, 6, 15, h, 0)
                pred_ac = predict_ac_power(plant_id, dummy_time, 32.0, irradiation=irrad)
                fraction = calculate_yield_fraction(pred_ac, plant_id)
                yield_profile_kwh_per_kw.append(round(fraction, 4))
            else:
                yield_profile_kwh_per_kw.append(0.0)

    return yield_profile_kwh_per_kw

def run_feasibility_analysis(location_info, weather_data=None, industry_type=None, plant_id=4135001):
    # Main simulation function executing the 9-step feasibility process.
    lat = float(location_info.get("latitude", 17.3850))
    lon = float(location_info.get("longitude", 78.4867))
    location_name = location_info.get("city", "Detected Location")
    state_name = location_info.get("state", "Telangana")
    plant_id = int(plant_id)

    # Step 1: Tariffs & Benchmarks
    tariff_data = get_tariff_for_state(state_name)
    grid_tariff = float(tariff_data["energy_charge_per_kwh"])
    export_credit = float(tariff_data.get("export_credit_per_kwh") or 0.0)

    cost_info = get_installation_cost_per_kw()
    cost_per_kw = float(cost_info["cost_per_kw"])

    industry = get_industry_benchmark(industry_type)
    connected_load = float(industry["connected_load_kw"])
    profile_fractions = industry["hourly_profile"]

    # Step 2: Solar Potential (NASA POWER)
    solar_pot = fetch_solar_potential(lat, lon)
    psh = float(solar_pot["annual_average_peak_sun_hours"])
    monthly_psh = solar_pot["monthly_radiation_kwh_m2_day"]

    # Step 3: Hourly Factory Demand
    # D_t = Connected Load * Profile Fraction
    hourly_demand = [round(connected_load * frac, 2) for frac in profile_fractions]
    daily_demand_kwh = round(sum(hourly_demand), 2)
    annual_demand_kwh = round(daily_demand_kwh * 365, 2)

    # Step 4: Solar Sizing Formula
    # Capacity (kW) = Daily Demand (kWh) / (Peak Sun Hours * Performance Ratio)
    pr = ASSUMPTIONS["performance_ratio"]
    base_capacity_kw = round(daily_demand_kwh / (psh * pr), 1)

    # Step 5: Hourly 1-kW Solar Yield Shape for Selected Plant
    weather_hourly = weather_data.get("hourly") if weather_data else None
    yield_1kw_hourly = generate_hourly_yield_profile(lat, lon, weather_hourly, plant_id=plant_id)
    daily_1kw_kwh = sum(yield_1kw_hourly)

    # Step 6: 12-Month Representative Annual Generation Estimation
    # Note for faculty: model was trained on May-June data. We scale representative monthly shapes
    # using NASA POWER monthly solar radiation values.
    month_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    month_keys = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    annual_yield_per_kw = 0.0
    for i, m in enumerate(month_keys):
        month_radiation = monthly_psh.get(m, psh)
        # Scale daily shape by ratio of month radiation to baseline
        scale = (month_radiation / psh) if psh > 0 else 1.0
        month_daily_yield = daily_1kw_kwh * scale
        annual_yield_per_kw += month_daily_yield * month_days[i]
    annual_yield_per_kw = round(annual_yield_per_kw, 1)

    # Step 7: Simulate System Sizes (25%, 50%, 75%, 100%)
    size_percentages = [25, 50, 75, 100]
    evaluations = {}

    annual_om_rate = ASSUMPTIONS["annual_om_rate_of_capex"]
    annual_deg_rate = ASSUMPTIONS["annual_degradation_rate"]
    system_life = ASSUMPTIONS["system_life_years"]

    for pct in size_percentages:
        cap = round(base_capacity_kw * (pct / 100.0), 1)
        # 24-Hour simulation
        hourly_gen = [round(cap * y, 2) for y in yield_1kw_hourly]
        self_cons_hourly = [round(min(g, d), 2) for g, d in zip(hourly_gen, hourly_demand)]
        import_hourly = [round(max(0.0, d - g), 2) for g, d in zip(hourly_gen, hourly_demand)]
        export_hourly = [round(max(0.0, g - d), 2) for g, d in zip(hourly_gen, hourly_demand)]

        day_gen = sum(hourly_gen)
        day_self_cons = sum(self_cons_hourly)
        day_import = sum(import_hourly)
        day_export = sum(export_hourly)

        # Scale to year 1
        year_gen = round(cap * annual_yield_per_kw, 2)
        # Proportionate annual self-consumption
        self_cons_ratio = (day_self_cons / day_gen) if day_gen > 0 else 1.0
        annual_self_consumption = round(year_gen * self_cons_ratio, 2)
        annual_grid_import = round(max(0.0, annual_demand_kwh - annual_self_consumption), 2)
        annual_export = round(max(0.0, year_gen - annual_self_consumption), 2)

        # Year 1 Costs
        installation_cost = round(cap * cost_per_kw, 2)
        annual_om = round(installation_cost * annual_om_rate, 2)
        grid_only_annual_cost = round(annual_demand_kwh * grid_tariff, 2)

        import_cost = annual_grid_import * grid_tariff
        export_revenue = annual_export * export_credit
        hybrid_annual_cost = round(annual_om + import_cost - export_revenue, 2)
        annual_savings = round(grid_only_annual_cost - hybrid_annual_cost, 2)

        payback_years = round(installation_cost / annual_savings, 2) if annual_savings > 0 else 99.0
        roi_percent = round((annual_savings / installation_cost) * 100.0, 2) if installation_cost > 0 else 0.0

        # 25-Year Lifecycle Cashflow Simulation
        cumulative_generation_25yr = 0.0
        cumulative_savings_25yr = 0.0
        for yr in range(1, system_life + 1):
            deg_factor = (1.0 - annual_deg_rate) ** (yr - 1)
            yr_gen = year_gen * deg_factor
            cumulative_generation_25yr += yr_gen

            yr_self_cons = min(annual_demand_kwh, yr_gen * self_cons_ratio)
            yr_import = annual_demand_kwh - yr_self_cons
            yr_export = max(0.0, yr_gen - yr_self_cons)

            yr_grid_bill = yr_import * grid_tariff
            yr_export_credit = yr_export * export_credit
            yr_hybrid_cost = yr_grid_bill + annual_om - yr_export_credit
            yr_savings = grid_only_annual_cost - yr_hybrid_cost
            cumulative_savings_25yr += yr_savings

        net_25yr_savings = round(cumulative_savings_25yr - installation_cost, 2)

        # Levelized Solar Cost (T_solar in Rs/kWh)
        # T_solar = (Installation Cost / Total 25yr Generation) + (Annual O&M / Annual Average Generation)
        t_solar = 0.0
        if cumulative_generation_25yr > 0:
            capex_per_kwh = installation_cost / cumulative_generation_25yr
            avg_annual_gen = cumulative_generation_25yr / system_life
            om_per_kwh = annual_om / avg_annual_gen if avg_annual_gen > 0 else 0.0
            t_solar = round(capex_per_kwh + om_per_kwh, 2)

        # Environmental metric: CO2 offset using CEA grid factor (0.82 kg CO2 / kWh)
        co2_factor = ASSUMPTIONS.get("co2_emission_factor_kg_per_kwh", 0.82)
        annual_co2_tonnes = round((year_gen * co2_factor) / 1000.0, 1)

        evaluations[str(pct)] = {
            "percentage": pct,
            "capacity_kw": cap,
            "installation_cost": installation_cost,
            "annual_om_cost": annual_om,
            "annual_generation_kwh": year_gen,
            "annual_self_consumption_kwh": annual_self_consumption,
            "annual_grid_import_kwh": annual_grid_import,
            "annual_export_kwh": annual_export,
            "annual_savings": annual_savings,
            "payback_years": payback_years,
            "roi_percent": roi_percent,
            "net_25yr_savings": net_25yr_savings,
            "t_solar_per_kwh": t_solar,
            "annual_co2_offset_tonnes": annual_co2_tonnes,
            "day_hourly": {
                "demand": hourly_demand,
                "generation": hourly_gen,
                "self_consumption": self_cons_hourly,
                "grid_import": import_hourly,
                "export": export_hourly
            }
        }

    # Step 8: Select Best Hybrid Size (highest 25-year net savings among 25, 50, 75%)
    sub_sizes = ["25", "50", "75"]
    best_hybrid_pct = max(sub_sizes, key=lambda s: evaluations[s]["net_25yr_savings"])
    best_hybrid = evaluations[best_hybrid_pct]
    solar_max = evaluations["100"]

    # Step 9: Three-Option Comparison (GRID ONLY vs HYBRID vs SOLAR-MAX)
    grid_only_option = {
        "name": "GRID ONLY",
        "capacity_kw": 0.0,
        "installation_cost": 0.0,
        "annual_cost": round(annual_demand_kwh * grid_tariff, 2),
        "annual_savings": 0.0,
        "payback_years": 0.0,
        "roi_percent": 0.0,
        "cost_per_kwh": grid_tariff,
        "net_25yr_savings": 0.0
    }

    hybrid_option = {
        "name": f"HYBRID ({best_hybrid['percentage']}% Sizing)",
        "percentage": best_hybrid["percentage"],
        "capacity_kw": best_hybrid["capacity_kw"],
        "installation_cost": best_hybrid["installation_cost"],
        "annual_cost": round(grid_only_option["annual_cost"] - best_hybrid["annual_savings"], 2),
        "annual_savings": best_hybrid["annual_savings"],
        "payback_years": best_hybrid["payback_years"],
        "roi_percent": best_hybrid["roi_percent"],
        "cost_per_kwh": best_hybrid["t_solar_per_kwh"],
        "net_25yr_savings": best_hybrid["net_25yr_savings"]
    }

    solar_max_option = {
        "name": "SOLAR-MAX (100% Sizing)",
        "percentage": 100,
        "capacity_kw": solar_max["capacity_kw"],
        "installation_cost": solar_max["installation_cost"],
        "annual_cost": round(grid_only_option["annual_cost"] - solar_max["annual_savings"], 2),
        "annual_savings": solar_max["annual_savings"],
        "payback_years": solar_max["payback_years"],
        "roi_percent": solar_max["roi_percent"],
        "cost_per_kwh": solar_max["t_solar_per_kwh"],
        "net_25yr_savings": solar_max["net_25yr_savings"]
    }

    # Step 10: Recommendation Logic
    # - Payback <= 7 years and positive savings: recommend HYBRID or SOLAR-MAX (whichever has higher 25-yr net savings)
    # - Payback > 10 years or negative savings: recommend GRID
    # - Otherwise: recommend HYBRID with marginal note
    chosen_solar = solar_max if solar_max["net_25yr_savings"] > best_hybrid["net_25yr_savings"] else best_hybrid
    chosen_option_name = "SOLAR-MAX" if chosen_solar == solar_max else "HYBRID"

    if chosen_solar["payback_years"] <= 7.0 and chosen_solar["annual_savings"] > 0:
        recommendation = chosen_option_name
        rec_summary = (
            f"Recommend {chosen_option_name} system ({chosen_solar['capacity_kw']} kW). "
            f"Attractive payback period of {chosen_solar['payback_years']} years with estimated annual net savings of Rs {chosen_solar['annual_savings']:,.2f}."
        )
    elif chosen_solar["payback_years"] > 10.0 or chosen_solar["annual_savings"] <= 0:
        recommendation = "GRID ONLY"
        rec_summary = (
            "Recommend continuing with GRID ONLY power. "
            f"Solar payback extends beyond 10 years ({chosen_solar['payback_years']} years) under prevailing tariff and insolation conditions."
        )
    else:
        recommendation = "HYBRID (Marginal)"
        rec_summary = (
            f"Recommend HYBRID installation ({best_hybrid['capacity_kw']} kW) with caution. "
            f"Payback is moderate at {best_hybrid['payback_years']} years. Suitable if future grid tariff escalation is anticipated."
        )

    # Confidence calculation:
    # High: live weather + verified tariff + NASA POWER
    # Medium: live weather + unverified official tariff + NASA POWER
    # Low: unverified tariff or fallback assumption used
    if tariff_data.get("is_fallback") or not tariff_data.get("verified"):
        confidence = "Low"
        confidence_reason = (
            "Electricity tariff for this state has not been officially verified by regulatory order audit, "
            "or uses a fallback assumption."
        )
    elif weather_data and weather_data.get("source_label") == "LIVE API":
        confidence = "High"
        confidence_reason = "Live weather forecast, verified SERC industrial tariff, and NASA POWER climatology were used."
    else:
        confidence = "Medium"
        confidence_reason = "Verified tariff combined with regional benchmark radiation data."

    # Save to database table energy_analysis
    db_record = {
        "location": location_name[:150],
        "state": state_name[:100],
        "industry_type": industry["industry_type"][:100],
        "estimated_daily_demand_kwh": daily_demand_kwh,
        "recommended_capacity_kw": chosen_solar["capacity_kw"],
        "annual_solar_generation_kwh": chosen_solar["annual_generation_kwh"],
        "grid_cost": grid_only_option["annual_cost"],
        "hybrid_cost": hybrid_option["annual_cost"],
        "solar_cost": chosen_solar["installation_cost"],
        "annual_savings": chosen_solar["annual_savings"],
        "installation_cost": chosen_solar["installation_cost"],
        "roi_percent": chosen_solar["roi_percent"],
        "payback_years": min(99.9, chosen_solar["payback_years"]),
        "recommendation": recommendation,
        "confidence": confidence,
        "created_at": datetime.now()
    }
    insert_row("energy_analysis", db_record)

    return {
        "inputs": {
            "location": location_name,
            "state": state_name,
            "latitude": lat,
            "longitude": lon,
            "industry_type": industry["industry_type"],
            "industry_description": industry["description"],
            "connected_load_kw": connected_load,
            "grid_tariff_per_kwh": grid_tariff,
            "export_credit_per_kwh": export_credit,
            "capital_cost_per_kw": cost_per_kw,
            "peak_sun_hours": psh,
            "performance_ratio": pr,
            "system_life_years": system_life,
            "plant_id": plant_id,
            "tariff_verified": tariff_data.get("verified", False),
            "tariff_source": tariff_data.get("source_name", ""),
            "tariff_url": tariff_data.get("source_url", ""),
            "tariff_date": tariff_data.get("effective_date", "")
        },
        "intermediate_calculations": {
            "daily_demand_kwh": daily_demand_kwh,
            "annual_demand_kwh": annual_demand_kwh,
            "sizing_formula": "Capacity (kW) = Daily Demand / (Peak Sun Hours * Performance Ratio)",
            "sizing_calculation": f"{daily_demand_kwh} / ({psh} * {pr}) = {base_capacity_kw} kW",
            "base_100pct_capacity_kw": base_capacity_kw,
            "annual_yield_per_kw": annual_yield_per_kw,
            "model_training_limitation_note": "ML model was trained on May-June data. Other months are scaled using NASA POWER monthly solar radiation."
        },
        "system_sizes_evaluated": evaluations,
        "options_comparison": {
            "grid_only": grid_only_option,
            "hybrid": hybrid_option,
            "solar_max": solar_max_option
        },
        "recommendation": {
            "decision": recommendation,
            "summary": rec_summary,
            "recommended_capacity_kw": chosen_solar["capacity_kw"],
            "payback_years": chosen_solar["payback_years"],
            "annual_savings": chosen_solar["annual_savings"],
            "roi_percent": chosen_solar["roi_percent"],
            "annual_co2_offset_tonnes": round((chosen_solar["annual_generation_kwh"] * ASSUMPTIONS.get("co2_emission_factor_kg_per_kwh", 0.82)) / 1000.0, 1),
            "confidence": confidence,
            "confidence_reason": confidence_reason
        },
        "disclaimer": "Academic simulation for engineering feasibility study. Not a certified supplier quotation or financial advice."
    }
