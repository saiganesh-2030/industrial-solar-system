# Verification test script for plant switching and new endpoints

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app

def test_endpoints():
    client = app.test_client()

    print("--- 1. Testing Single-Point Model Demo (/api/single-predict) ---")
    res1 = client.get("/api/single-predict?plant_id=4135001&ambient_temp=32&irradiation=750&time_str=12:30&capacity_kw=100")
    data1 = res1.get_json()
    print("Plant 1 Single Predict:", data1.get("status"), f"System kW: {data1.get('predicted_system_ac_kw')}, Utility kW: {data1.get('predicted_utility_ac_kw')}")
    assert data1.get("status") == "success"

    res2 = client.get("/api/single-predict?plant_id=4136001&ambient_temp=32&irradiation=750&time_str=12:30&capacity_kw=100")
    data2 = res2.get_json()
    print("Plant 2 Single Predict:", data2.get("status"), f"System kW: {data2.get('predicted_system_ac_kw')}, Utility kW: {data2.get('predicted_utility_ac_kw')}")
    assert data2.get("status") == "success"

    # Nighttime Single Predict (Must be 0 kW)
    res_night = client.get("/api/single-predict?plant_id=4135001&ambient_temp=24&irradiation=0&time_str=22:00&capacity_kw=100")
    data_night = res_night.get_json()
    print("Nighttime Single Predict (22:00):", data_night.get("status"), f"System kW: {data_night.get('predicted_system_ac_kw')}, Utility kW: {data_night.get('predicted_utility_ac_kw')}")
    assert data_night.get("predicted_system_ac_kw") == 0.0

    # Custom Module Temp Predict
    res_mod = client.get("/api/single-predict?plant_id=4135001&ambient_temp=32&irradiation=750&time_str=12:30&capacity_kw=100&module_temp=60.0")
    data_mod = res_mod.get_json()
    print("Custom Module Temp Single Predict (60 C):", data_mod.get("status"), f"System kW: {data_mod.get('predicted_system_ac_kw')}, Mod Temp: {data_mod.get('module_temp')} C")
    assert data_mod.get("is_custom_module_temp") == True

    print("\n--- 2. Testing Deviation Checker (/api/check-deviation) ---")
    # Normal Plant 1
    res_dev1 = client.get("/api/check-deviation?plant_id=4135001&actual_kw=21500&ambient_temp=34&irradiation=780&time_str=12:30")
    d_dev1 = res_dev1.get_json()["data"]
    print(f"Plant 1 Normal: Expected={d_dev1['predicted_kw']} kW, Actual={d_dev1['actual_kw']} kW, Status={d_dev1['status']}")
    assert d_dev1["status"] == "Normal"

    # Underperformance Plant 1
    res_dev2 = client.get("/api/check-deviation?plant_id=4135001&actual_kw=16500&ambient_temp=34&irradiation=780&time_str=12:30")
    d_dev2 = res_dev2.get_json()["data"]
    print(f"Plant 1 Underperformance: Expected={d_dev2['predicted_kw']} kW, Actual={d_dev2['actual_kw']} kW, Status={d_dev2['status']}")
    assert d_dev2["status"] == "Unusual underperformance"

    # Sensor Issue
    res_dev3 = client.get("/api/check-deviation?plant_id=4135001&actual_kw=15&ambient_temp=35&irradiation=800&time_str=12:30")
    d_dev3 = res_dev3.get_json()["data"]
    print(f"Plant 1 Sensor Issue: Status={d_dev3['status']}")
    assert d_dev3["status"] == "Possible sensor issue"

    # Plant 2 Plateau Normal
    res_dev4 = client.get("/api/check-deviation?plant_id=4136001&actual_kw=13200&ambient_temp=36.5&irradiation=780&time_str=12:30")
    d_dev4 = res_dev4.get_json()["data"]
    print(f"Plant 2 Plateau Normal: Expected={d_dev4['predicted_kw']} kW, Actual={d_dev4['actual_kw']} kW, Status={d_dev4['status']}")
    assert d_dev4["status"] == "Normal"

    print("\n--- 3. Testing Feasibility Engine Plant 1 vs Plant 2 ---")
    f_res1 = client.get("/api/feasibility?plant_id=4135001&state=Telangana&industry=Light%20Manufacturing")
    f_data1 = f_res1.get_json()["data"]
    rec1 = f_data1["recommendation"]
    savings1 = rec1["annual_savings"]
    payback1 = rec1["payback_years"]

    f_res2 = client.get("/api/feasibility?plant_id=4136001&state=Telangana&industry=Light%20Manufacturing")
    f_data2 = f_res2.get_json()["data"]
    rec2 = f_data2["recommendation"]
    savings2 = rec2["annual_savings"]
    payback2 = rec2["payback_years"]

    print(f"Plant 1 Feasibility: Annual Savings = Rs {savings1:,.0f}, Payback = {payback1} years")
    print(f"Plant 2 Feasibility: Annual Savings = Rs {savings2:,.0f}, Payback = {payback2} years")
    # Verify that Plant 2 generates lower savings and longer payback due to the midday plateau
    assert savings1 > savings2
    assert payback1 < payback2

    print("\n--- 4. Testing State Payback Rankings Plant 1 vs Plant 2 ---")
    st_res1 = client.get("/api/states-comparison?plant_id=4135001")
    st_data1 = st_res1.get_json()["ranked_states"]
    st_res2 = client.get("/api/states-comparison?plant_id=4136001")
    st_data2 = st_res2.get_json()["ranked_states"]

    p1_first = st_data1[0]
    p2_first = st_data2[0]
    print(f"Plant 1 Top State: {p1_first['state']}, Payback: {p1_first['payback_years']} yrs, Yield: {p1_first['annual_solar_yield_per_kw']} kWh/kW")
    print(f"Plant 2 Top State: {p2_first['state']}, Payback: {p2_first['payback_years']} yrs, Yield: {p2_first['annual_solar_yield_per_kw']} kWh/kW")
    assert p1_first['annual_solar_yield_per_kw'] > p2_first['annual_solar_yield_per_kw']

    print("\nAll feature tests passed successfully!")

if __name__ == "__main__":
    test_endpoints()
