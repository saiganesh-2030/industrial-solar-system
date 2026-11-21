# Capital cost and O&M budgeting service for industrial solar systems.

from config import ASSUMPTIONS
from database import fetch_one

def get_installation_cost_per_kw():
    # Returns capital cost per kW from cost_benchmarks table or configuration fallback.
    db_row = fetch_one("SELECT * FROM cost_benchmarks WHERE region LIKE %s LIMIT 1", ("%National Average%",))
    if db_row and db_row.get("cost_per_kw"):
        return {
            "cost_per_kw": float(db_row["cost_per_kw"]),
            "source_name": db_row.get("source_name", "MNRE Benchmark Cost"),
            "source_url": db_row.get("source_url", "https://mnre.gov.in"),
            "as_of_date": str(db_row.get("as_of_date", "2024-01-01")),
            "notes": db_row.get("notes", "Turnkey industrial rooftop solar benchmark."),
            "source_label": "ASSUMPTION, not a supplier quotation"
        }

    return {
        "cost_per_kw": ASSUMPTIONS["default_cost_per_kw"],
        "source_name": "MNRE Benchmark Rooftop Solar Guideline",
        "source_url": "https://mnre.gov.in",
        "as_of_date": "2024-01-01",
        "notes": "Standard national average assumption for turnkey industrial solar.",
        "source_label": "ASSUMPTION, not a supplier quotation"
    }

def calculate_installation_cost(capacity_kw, cost_per_kw=None):
    # Computes initial capital expenditure for a target solar capacity.
    # Formula: Installation Cost = Capacity (kW) * Cost per kW
    if cost_per_kw is None:
        cost_info = get_installation_cost_per_kw()
        cost_per_kw = cost_info["cost_per_kw"]

    total_cost = float(capacity_kw) * float(cost_per_kw)
    annual_om = total_cost * ASSUMPTIONS["annual_om_rate_of_capex"]

    return {
        "capacity_kw": capacity_kw,
        "cost_per_kw": cost_per_kw,
        "installation_cost": round(total_cost, 2),
        "annual_om_cost": round(annual_om, 2),
        "source_label": "ASSUMPTION, not a supplier quotation"
    }
