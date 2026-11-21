// Options Comparison visualization logic.

let costChart = null;
let cumulativeChart = null;

document.addEventListener("DOMContentLoaded", async () => {
    renderNavigation("comparison");
    renderLimitationsPanel();

    const loc = getCurrentLocation();
    loadComparison(loc);

    window.addEventListener("locationUpdated", (e) => {
        loadComparison(e.detail);
    });

    // Listen for global plant change
    window.addEventListener("plantUpdated", () => {
        loadComparison(getCurrentLocation());
    });
});

async function loadComparison(loc) {
    const plantId = getCurrentPlantId();
    try {
        const res = await fetch(`${API_BASE}/api/feasibility?lat=${loc.latitude}&lon=${loc.longitude}&city=${encodeURIComponent(loc.city)}&state=${encodeURIComponent(loc.state)}&plant_id=${plantId}`);
        const json = await res.json();
        if (json.status === "success") {
            const data = json.data;
            const opts = data.options_comparison;
            const grid = opts.grid_only;
            const hybrid = opts.hybrid;
            const smax = opts.solar_max;

            // Card 1: Grid Only
            document.getElementById("grid-cost-val").textContent = formatINR(grid.annual_cost);
            document.getElementById("grid-rate-val").textContent = `Rs ${grid.cost_per_kwh.toFixed(2)} / kWh`;

            // Card 2: Hybrid
            document.getElementById("hybrid-title").textContent = `Option 2: ${hybrid.name}`;
            document.getElementById("hybrid-cost-val").textContent = formatINR(hybrid.annual_cost);
            document.getElementById("hybrid-capex-val").textContent = formatINR(hybrid.installation_cost);
            document.getElementById("hybrid-payback-val").textContent = `${hybrid.payback_years.toFixed(1)} Yrs (${formatINR(hybrid.annual_savings)}/yr)`;

            // Card 3: Solar-Max
            document.getElementById("solarmax-cost-val").textContent = formatINR(smax.annual_cost);
            document.getElementById("solarmax-capex-val").textContent = formatINR(smax.installation_cost);
            document.getElementById("solarmax-payback-val").textContent = `${smax.payback_years.toFixed(1)} Yrs (${formatINR(smax.annual_savings)}/yr)`;

            renderCostBarChart(grid, hybrid, smax);
            renderCumulativeChart(hybrid, smax);
        }
    } catch (err) {
        console.error("Failed to load options comparison", err);
    }
}

function renderCostBarChart(grid, hybrid, smax) {
    const ctx = document.getElementById("annual-cost-chart");
    if (!ctx) return;

    if (costChart) costChart.destroy();

    costChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels: ["Grid Only (Baseline)", hybrid.name, "Solar-Max (100%)"],
            datasets: [
                {
                    label: "Annual Energy Bill (INR)",
                    data: [grid.annual_cost, hybrid.annual_cost, smax.annual_cost],
                    backgroundColor: ["#94a3b8", "#0284c7", "#d97706"],
                    borderRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    title: { display: true, text: "Annual Cost (INR)" },
                    beginAtZero: true,
                    ticks: {
                        callback: (v) => "Rs " + (v / 100000).toFixed(1) + " L"
                    }
                }
            }
        }
    });
}

function renderCumulativeChart(hybrid, smax) {
    const ctx = document.getElementById("cumulative-savings-chart");
    if (!ctx) return;

    const years = Array.from({ length: 26 }, (_, i) => `Yr ${i}`);

    // Generate cumulative cashflow starting at -Capex at Year 0
    const hybridCurve = [-hybrid.installation_cost];
    const smaxCurve = [-smax.installation_cost];

    let cumH = -hybrid.installation_cost;
    let cumS = -smax.installation_cost;

    for (let yr = 1; yr <= 25; yr++) {
        const deg = Math.pow(1 - 0.005, yr - 1);
        cumH += (hybrid.annual_savings * deg);
        cumS += (smax.annual_savings * deg);
        hybridCurve.push(Math.round(cumH));
        smaxCurve.push(Math.round(cumS));
    }

    if (cumulativeChart) cumulativeChart.destroy();

    cumulativeChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: years,
            datasets: [
                {
                    label: `Hybrid (${hybrid.percentage}%) Net Cashflow`,
                    data: hybridCurve,
                    borderColor: "#0284c7",
                    backgroundColor: "transparent",
                    borderWidth: 2
                },
                {
                    label: "Solar-Max (100%) Net Cashflow",
                    data: smaxCurve,
                    borderColor: "#d97706",
                    backgroundColor: "transparent",
                    borderWidth: 2
                },
                {
                    label: "Breakeven Baseline (Rs 0)",
                    data: Array(26).fill(0),
                    borderColor: "#dc2626",
                    borderWidth: 1.5,
                    borderDash: [4, 4],
                    pointRadius: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            scales: {
                y: {
                    title: { display: true, text: "Cumulative Net Position (INR)" },
                    ticks: {
                        callback: (v) => (v / 100000).toFixed(0) + " Lakhs"
                    }
                }
            }
        }
    });
}
