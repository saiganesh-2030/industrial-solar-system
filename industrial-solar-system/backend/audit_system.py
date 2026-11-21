# Comprehensive End-to-End Audit Script for Industrial Solar Feasibility System

import os
import sys
import json
import glob

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app

def run_comprehensive_audit():
    print("=================================================================")
    print("      COMPREHENSIVE END-TO-END INDUSTRIAL SOLAR SYSTEM AUDIT     ")
    print("=================================================================")

    client = app.test_client()
    passed = 0
    total = 0

    def assert_test(name, condition, details=""):
        nonlocal passed, total
        total += 1
        if condition:
            passed += 1
            print(f"[PASS] {name} {details}")
        else:
            print(f"[FAIL] {name} {details}")

    # 1. Static HTML Pages Routing Test
    print("\n--- 1. Static HTML Pages Routing ---")
    pages = [
        "/",
        "/index.html",
        "/prediction.html",
        "/weather.html",
        "/feasibility.html",
        "/comparison.html",
        "/states.html",
        "/deviation.html",
        "/model.html"
    ]
    for p in pages:
        res = client.get(p)
        assert_test(f"Page Route: {p}", res.status_code == 200, f"(HTTP {res.status_code})")

    # 2. Location API
    print("\n--- 2. Location API ---")
    res_loc = client.get("/api/location")
    d_loc = res_loc.get_json()
    assert_test("Default Location API", d_loc.get("status") == "success", f"City: {d_loc.get('city')}, State: {d_loc.get('state')}")

    # 3. Weather API
    print("\n--- 3. Weather API ---")
    res_w = client.get("/api/weather?lat=17.385&lon=78.4867")
    d_w = res_w.get_json()
    assert_test("Weather Forecast API", d_w.get("status") == "success", f"Temp: {d_w['data']['current']['temperature']} C, Suitability: {d_w['data']['suitability']['score']}/100")

    # 4. Solar Potential API
    print("\n--- 4. Solar Potential (NASA POWER) API ---")
    res_sp = client.get("/api/solar-potential?lat=17.385&lon=78.4867")
    d_sp = res_sp.get_json()
    assert_test("Solar Potential API", d_sp.get("status") == "success", f"Annual Average PSH: {d_sp['data']['annual_average_peak_sun_hours']}")

    # 5. Prediction API (Plant 1 vs Plant 2)
    print("\n--- 5. Prediction API ---")
    res_pred1 = client.get("/api/prediction?lat=17.385&lon=78.4867&capacity=100&plant_id=4135001")
    d_pred1 = res_pred1.get_json()
    res_pred2 = client.get("/api/prediction?lat=17.385&lon=78.4867&capacity=100&plant_id=4136001")
    d_pred2 = res_pred2.get_json()
    y24_p1 = d_pred1.get("total_predicted_24h_kwh", 0)
    y24_p2 = d_pred2.get("total_predicted_24h_kwh", 0)
    assert_test("Prediction Plant 1", d_pred1.get("status") == "success", f"24h Yield: {y24_p1} kWh")
    assert_test("Prediction Plant 2", d_pred2.get("status") == "success", f"24h Yield: {y24_p2} kWh")
    assert_test("Plant 1 > Plant 2 Yield (Plateau Effect)", y24_p1 > y24_p2, f"({y24_p1} kWh > {y24_p2} kWh)")

    # 6. Feasibility API (Plant 1 vs Plant 2)
    print("\n--- 6. Feasibility API ---")
    res_feas1 = client.get("/api/feasibility?lat=17.385&lon=78.4867&state=Telangana&industry=Light%20Manufacturing&plant_id=4135001")
    d_feas1 = res_feas1.get_json()["data"]["recommendation"]
    res_feas2 = client.get("/api/feasibility?lat=17.385&lon=78.4867&state=Telangana&industry=Light%20Manufacturing&plant_id=4136001")
    d_feas2 = res_feas2.get_json()["data"]["recommendation"]
    assert_test("Feasibility Plant 1", res_feas1.status_code == 200, f"Savings: Rs {d_feas1['annual_savings']:,.0f}, Payback: {d_feas1['payback_years']} yrs")
    assert_test("Feasibility Plant 2", res_feas2.status_code == 200, f"Savings: Rs {d_feas2['annual_savings']:,.0f}, Payback: {d_feas2['payback_years']} yrs")
    assert_test("Feasibility Savings P1 > P2", d_feas1['annual_savings'] > d_feas2['annual_savings'])
    assert_test("Feasibility Payback P1 < P2", d_feas1['payback_years'] < d_feas2['payback_years'])

    # 7. State Tariffs & Payback Comparison API
    print("\n--- 7. State Comparison API ---")
    res_st1 = client.get("/api/states-comparison?plant_id=4135001")
    d_st1 = res_st1.get_json()["ranked_states"][0]
    res_st2 = client.get("/api/states-comparison?plant_id=4136001")
    d_st2 = res_st2.get_json()["ranked_states"][0]
    assert_test("States Ranking Plant 1", res_st1.status_code == 200, f"Top State: {d_st1['state']}, Payback: {d_st1['payback_years']} yrs")
    assert_test("States Ranking Plant 2", res_st2.status_code == 200, f"Top State: {d_st2['state']}, Payback: {d_st2['payback_years']} yrs")
    assert_test("State Yield P1 > P2", d_st1['annual_solar_yield_per_kw'] > d_st2['annual_solar_yield_per_kw'])

    # 8. Deviation Detection Timeline API
    print("\n--- 8. Deviation Detection Timeline API ---")
    res_dev = client.get("/api/deviation?plant_id=4135001&limit=60")
    d_dev = res_dev.get_json()["data"]
    assert_test("Deviation Replay Timeline API", len(d_dev["records"]) == 60, f"Threshold: {d_dev['threshold_kw']} kW, Outliers: {d_dev['summary']['total_unusual']}")

    # 9. Single-Point Check Deviation API
    print("\n--- 9. Single-Point Check Deviation API ---")
    res_cdev = client.get("/api/check-deviation?plant_id=4135001&actual_kw=21500&ambient_temp=34&irradiation=780&time_str=12:30")
    d_cdev = res_cdev.get_json()["data"]
    assert_test("Check Deviation Normal", d_cdev["status"] == "Normal", f"Expected: {d_cdev['predicted_kw']} kW, Deviation: {d_cdev['deviation_kw']} kW")

    # 10. Dashboard Single-Point Model Demo API
    print("\n--- 10. Dashboard Single-Point Model Demo API ---")
    res_spred = client.get("/api/single-predict?plant_id=4135001&ambient_temp=32&irradiation=750&time_str=12:30&capacity_kw=100")
    d_spred = res_spred.get_json()
    assert_test("Single-Predict Demo API", d_spred.get("status") == "success", f"System Output: {d_spred.get('predicted_system_ac_kw')} kW, Module Temp: {d_spred.get('module_temp')} C")

    # 10b. Verification of Nighttime Generation = 0 kW and Custom Module Temp
    res_night = client.get("/api/single-predict?plant_id=4135001&ambient_temp=24&irradiation=0&time_str=22:00&capacity_kw=100")
    d_night = res_night.get_json()
    assert_test("Night Power Zero Check", d_night.get("predicted_system_ac_kw") == 0.0 and d_night.get("predicted_utility_ac_kw") == 0.0, f"Output at 22:00: {d_night.get('predicted_system_ac_kw')} kW")

    res_custom = client.get("/api/single-predict?plant_id=4135001&ambient_temp=32&irradiation=750&time_str=12:30&capacity_kw=100&module_temp=60.0")
    d_custom = res_custom.get_json()
    assert_test("Custom Module Temp Check", d_custom.get("is_custom_module_temp") == True and d_custom.get("predicted_system_ac_kw") != d_spred.get("predicted_system_ac_kw"), f"Entered 60 C output: {d_custom.get('predicted_system_ac_kw')} kW vs auto: {d_spred.get('predicted_system_ac_kw')} kW")

    # 11. Model Metrics API (Plant 1 vs Plant 2 R2 score verification)
    print("\n--- 11. Model Metrics API (R2 Scores) ---")
    res_m1 = client.get("/api/model-metrics?plant_id=4135001")
    d_m1 = res_m1.get_json()["final_test_evaluation"]
    res_m2 = client.get("/api/model-metrics?plant_id=4136001")
    d_m2 = res_m2.get_json()["final_test_evaluation"]
    assert_test("Model Metrics Plant 1 R2", d_m1["r2_score"] == 0.9954, f"(R2 = {d_m1['r2_score']}, MAE = {d_m1['mae']} kW)")
    assert_test("Model Metrics Plant 2 R2", d_m2["r2_score"] == 0.8881, f"(R2 = {d_m2['r2_score']}, MAE = {d_m2['mae']} kW)")

    # 11b. Stored Solar Predictions Database API
    print("\n--- 11b. Stored Predictions API ---")
    res_sp = client.get("/api/stored-predictions")
    d_sp = res_sp.get_json()
    assert_test("Stored Predictions GET API", res_sp.status_code == 200 and len(d_sp.get("records", [])) > 0, f"(Records: {len(d_sp.get('records', []))})")
    
    test_pred_payload = {
        "location": "Audit Facility",
        "plant_id": 4135001,
        "input_measurements": {"ambient_temp": 31.0, "irradiation_wm2": 700.0, "time": "11:00", "capacity_kw": 100},
        "predicted_kw": 70.5
    }
    res_save = client.post("/api/save-prediction", json=test_pred_payload)
    d_save = res_save.get_json()
    assert_test("Save Prediction POST API", res_save.status_code == 200 and d_save.get("status") == "success", f"(ID: {d_save.get('id')})")

    # 12. Frontend JS Syntax & Bracket Balancing
    print("\n--- 12. Frontend JavaScript Syntax Audit ---")
    js_files = glob.glob("industrial-solar-system/frontend/js/*.js")
    for jf in js_files:
        with open(jf, "r", encoding="utf-8") as fh:
            text = fh.read()
        opens = text.count("{")
        closes = text.count("}")
        open_p = text.count("(")
        close_p = text.count(")")
        open_b = text.count("[")
        close_b = text.count("]")
        is_balanced = (opens == closes) and (open_p == close_p) and (open_b == close_b)
        assert_test(f"JS Brackets: {os.path.basename(jf)}", is_balanced, f"({opens}/{closes})")

    # 13. Humanizer Rules Audit across all application source files
    print("\n--- 13. Humanizer Compliance Audit ---")
    em_dash = chr(8212)
    en_dash = chr(8211)
    buzzwords = ["delve", "testament", "pivotal", "robust", "vibrant", "tapestry", "crucial", "bolstered", "interplay"]
    
    # Check application files (exclude test/audit scripts that hold the blacklist strings)
    app_html = glob.glob("industrial-solar-system/frontend/*.html")
    app_js = glob.glob("industrial-solar-system/frontend/js/*.js")
    app_py = [p for p in glob.glob("industrial-solar-system/backend/*.py") if "audit_" not in p and "check_" not in p]
    all_files = app_html + app_js + app_py
    
    dash_count = 0
    buzz_count = 0
    for f in all_files:
        with open(f, "r", encoding="utf-8") as fh:
            content = fh.read()
        if em_dash in content or en_dash in content:
            dash_count += 1
            print(f"[FAIL] Dash found in {f}")
        for b in buzzwords:
            if b in content.lower():
                buzz_count += 1
                print(f"[FAIL] Buzzword '{b}' found in {f}")
    
    assert_test("Zero Em-dashes or En-dashes in App", dash_count == 0, f"({dash_count} found)")
    assert_test("Zero AI Buzzwords in App", buzz_count == 0, f"({buzz_count} found)")

    # Final Summary
    print("\n=================================================================")
    print(f"       AUDIT RESULT: {passed} / {total} CHECKS PASSED ({(passed/total)*100:.1f}%)")
    print("=================================================================")
    return passed == total

if __name__ == "__main__":
    success = run_comprehensive_audit()
    sys.exit(0 if success else 1)
