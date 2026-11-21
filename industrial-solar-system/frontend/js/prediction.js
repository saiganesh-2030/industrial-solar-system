// Interactive 48-hour solar prediction visualization and feature inspection.

let chart48 = null;
let currentPredictionData = null;

document.addEventListener("DOMContentLoaded", async () => {
    renderNavigation("prediction");
    renderLimitationsPanel();

    const loc = getCurrentLocation();
    loadPrediction(loc);

    // Slider listener
    const slider = document.getElementById("capacity-slider");
    slider.addEventListener("input", (e) => {
        const val = e.target.value;
        document.getElementById("capacity-slider-val").textContent = `${val} kW`;
        recalculateScaledPredictions(parseFloat(val));
    });

    // Listen for global plant change
    window.addEventListener("plantUpdated", () => {
        loadPrediction(getCurrentLocation());
    });

    window.addEventListener("locationUpdated", (e) => {
        loadPrediction(e.detail);
    });
});

async function loadPrediction(loc) {
    const slider = document.getElementById("capacity-slider");
    const cap = slider ? slider.value : 100;
    const plantId = getCurrentPlantId();

    const badge = document.getElementById("active-prediction-plant");
    if (badge) {
        const isP2 = plantId === 4136001;
        badge.textContent = isP2 ? "Plant 2 (4136001 - Plateau Limited)" : "Plant 1 (4135001 - Standard Field)";
        badge.className = isP2 ? "badge badge-warning" : "badge badge-info";
    }

    try {
        const res = await fetch(`${API_BASE}/api/prediction?lat=${loc.latitude}&lon=${loc.longitude}&capacity=${cap}&plant_id=${plantId}`);
        const json = await res.json();
        if (json.status === "success") {
            currentPredictionData = json;
            document.getElementById("total-48h-val").textContent = `${formatNumber(json.total_predicted_48h_kwh, 1)} kWh`;
            render48HourChart(json.hourly_predictions);
            populateTable(json.hourly_predictions);
        }
    } catch (err) {
        console.error("Failed to load predictions", err);
    }
}

function recalculateScaledPredictions(newCapacity) {
    if (!currentPredictionData || !currentPredictionData.hourly_predictions) return;

    let totalKwh = 0;
    const updated = currentPredictionData.hourly_predictions.map(item => {
        const scaled = roundNum(item.yield_fraction_per_kw * newCapacity, 2);
        totalKwh += scaled;
        return {
            ...item,
            predicted_kw: scaled
        };
    });

    document.getElementById("total-48h-val").textContent = `${formatNumber(totalKwh, 1)} kWh`;
    render48HourChart(updated);
    populateTable(updated);
}

function render48HourChart(hourlyList) {
    const ctx = document.getElementById("prediction-48h-chart");
    if (!ctx) return;

    const labels = hourlyList.map(h => {
        const parts = h.time.split("T");
        const date = parts[0].slice(5); // MM-DD
        return `${date} ${h.hour}:00`;
    });
    const genData = hourlyList.map(h => h.predicted_kw);
    const irradData = hourlyList.map(h => h.radiation_wm2);

    if (chart48) {
        chart48.destroy();
    }

    chart48 = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Predicted AC Power (kW)",
                    data: genData,
                    borderColor: "#d97706",
                    backgroundColor: "rgba(217, 119, 6, 0.15)",
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3,
                    yAxisID: "y"
                },
                {
                    label: "Solar Radiation (W/m²)",
                    data: irradData,
                    borderColor: "#0284c7",
                    borderWidth: 1.5,
                    borderDash: [3, 3],
                    pointRadius: 0,
                    fill: false,
                    yAxisID: "y1"
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: "index",
                intersect: false
            },
            scales: {
                x: {
                    ticks: { maxTicksLimit: 16 },
                    grid: { display: false }
                },
                y: {
                    title: { display: true, text: "Generation (kW)" },
                    beginAtZero: true
                },
                y1: {
                    title: { display: true, text: "Radiation (W/m²)" },
                    position: "right",
                    beginAtZero: true,
                    grid: { drawOnChartArea: false }
                }
            }
        }
    });
}

function populateTable(hourlyList) {
    const tbody = document.getElementById("prediction-table-body");
    if (!tbody) return;

    let rowsHtml = "";
    hourlyList.forEach(item => {
        const timeClean = item.time.replace("T", " ");
        rowsHtml += `
        <tr>
            <td><strong>${timeClean}</strong></td>
            <td>${item.ambient_temp.toFixed(1)}</td>
            <td>${item.module_temp_estimated.toFixed(1)}</td>
            <td>${item.radiation_wm2.toFixed(1)}</td>
            <td>${item.irradiation_kwm2.toFixed(4)}</td>
            <td>${item.yield_fraction_per_kw.toFixed(4)}</td>
            <td style="font-weight: 700; color: var(--solar-amber);">${item.predicted_kw.toFixed(2)}</td>
        </tr>
        `;
    });
    tbody.innerHTML = rowsHtml;
}

function roundNum(val, dec) {
    const mult = Math.pow(10, dec);
    return Math.round(val * mult) / mult;
}
