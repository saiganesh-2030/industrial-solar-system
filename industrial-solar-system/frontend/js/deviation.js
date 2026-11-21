// Performance Deviation Detection module.
// Renders the historical replay timeline chart (actual vs predicted with outlier highlights)
// and provides a simple single-point deviation evaluation tool.

let timelineChart = null;

document.addEventListener("DOMContentLoaded", () => {
    renderNavigation("deviation");
    renderLimitationsPanel();

    const currentPlant = getCurrentPlantId();
    updateActivePlantBadge(currentPlant);

    // 1. Load the historical replay timeline chart
    loadDeviationTimeline();

    // 2. Run initial single-point check
    runDeviationCheck();

    // Listen for global plant change
    window.addEventListener("plantUpdated", (e) => {
        updateActivePlantBadge(e.detail.plantId);
        loadDeviationTimeline();
        loadScenario("normal");
    });
});

function updateActivePlantBadge(plantId) {
    const badge = document.getElementById("active-dev-plant");
    if (badge) {
        const isP2 = plantId === 4136001;
        badge.textContent = isP2 ? "Plant 2 (4136001 - Plateau Limited)" : "Plant 1 (4135001 - Standard Field)";
        badge.className = isP2 ? "badge badge-warning" : "badge badge-info";
    }
}

// 1. Historical Replay Timeline Chart (the previous graph)
async function loadDeviationTimeline() {
    const plantId = getCurrentPlantId();
    updateActivePlantBadge(plantId);

    try {
        const res = await fetch(`${API_BASE}/api/deviation?plant_id=${plantId}&limit=60`);
        const json = await res.json();
        if (json.status === "success") {
            const data = json.data;
            document.getElementById("threshold-val").textContent = `${data.threshold_kw.toFixed(1)} kW`;
            document.getElementById("unusual-count-val").textContent = `${data.summary.total_unusual} / ${data.total_records_replayed}`;

            renderTimelineChart(data.records);
        }
    } catch (err) {
        console.error("Failed to load deviation replay timeline", err);
    }
}

function renderTimelineChart(records) {
    const ctx = document.getElementById("deviation-chart");
    if (!ctx) return;

    const labels = records.map(r => r.timestamp.slice(5)); // MM-DD HH:MM
    const actuals = records.map(r => r.actual_kw);
    const preds = records.map(r => r.predicted_kw);

    if (timelineChart) {
        timelineChart.destroy();
    }

    timelineChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Actual Generation (kW)",
                    data: actuals,
                    borderColor: "#0284c7",
                    backgroundColor: "transparent",
                    borderWidth: 2,
                    pointRadius: (ctx) => {
                        const idx = ctx.dataIndex;
                        return records[idx] && records[idx].is_unusual ? 5 : 2;
                    },
                    pointBackgroundColor: (ctx) => {
                        const idx = ctx.dataIndex;
                        return records[idx] && records[idx].is_unusual ? "#dc2626" : "#0284c7";
                    }
                },
                {
                    label: "Predicted Generation (kW)",
                    data: preds,
                    borderColor: "#d97706",
                    backgroundColor: "transparent",
                    borderWidth: 2,
                    borderDash: [3, 3],
                    pointRadius: 2
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            scales: {
                x: { ticks: { maxTicksLimit: 14 }, grid: { display: false } },
                y: { title: { display: true, text: "Generation (kW)" }, beginAtZero: true }
            }
        }
    });
}

// 2. Simple Single-Point Deviation Checker
async function runDeviationCheck() {
    const plantId = getCurrentPlantId();
    updateActivePlantBadge(plantId);

    const timeEl = document.getElementById("check-time");
    const irradEl = document.getElementById("check-irrad");
    const tempEl = document.getElementById("check-temp");
    const actualEl = document.getElementById("check-actual");

    const timeStr = timeEl ? timeEl.value : "12:30";
    const irrad = irradEl ? parseFloat(irradEl.value) : 780.0;
    const temp = tempEl ? parseFloat(tempEl.value) : 34.0;
    const actualKw = actualEl ? parseFloat(actualEl.value) : 21500.0;

    try {
        const url = `${API_BASE}/api/check-deviation?plant_id=${plantId}&actual_kw=${actualKw}&ambient_temp=${temp}&irradiation=${irrad}&time_str=${encodeURIComponent(timeStr)}`;
        const res = await fetch(url);
        const json = await res.json();

        if (json.status === "success") {
            const data = json.data;
            document.getElementById("res-expected-kw").textContent = `${formatNumber(data.predicted_kw, 1)} kW`;
            document.getElementById("res-actual-kw").textContent = `${formatNumber(data.actual_kw, 1)} kW`;

            const devEl = document.getElementById("res-deviation-kw");
            const devSign = data.deviation_kw >= 0 ? "+" : "";
            devEl.textContent = `${devSign}${formatNumber(data.deviation_kw, 1)} kW`;

            const pctEl = document.getElementById("res-deviation-pct");
            const pctSign = data.deviation_percent >= 0 ? "+" : "";
            pctEl.textContent = `${pctSign}${formatNumber(data.deviation_percent, 1)}% from expected`;

            if (data.status === "Normal") {
                devEl.style.color = "var(--success)";
            } else if (data.status === "Unusual underperformance") {
                devEl.style.color = "var(--warning)";
            } else if (data.status === "Possible sensor issue") {
                devEl.style.color = "var(--danger)";
            } else {
                devEl.style.color = "var(--primary)";
            }

            let badgeClass = "badge-success";
            if (data.status === "Unusual underperformance") badgeClass = "badge-warning";
            else if (data.status === "Unusual overperformance") badgeClass = "badge-info";
            else if (data.status === "Possible sensor issue") badgeClass = "badge-danger";

            document.getElementById("res-status-wrap").innerHTML = `<span class="badge ${badgeClass}" style="font-size: 0.88rem; padding: 0.35rem 0.65rem;">${data.status}</span>`;
            document.getElementById("res-status-subtext").textContent = `Threshold: ${data.threshold_kw.toFixed(1)} kW`;

            const expBox = document.getElementById("res-explanation-box");
            expBox.innerHTML = `<strong>Evaluation:</strong> ${data.explanation}`;
        }
    } catch (err) {
        console.error("Single-point deviation check failed", err);
    }
}

function loadScenario(scenario) {
    const plantId = getCurrentPlantId();
    updateActivePlantBadge(plantId);

    const timeEl = document.getElementById("check-time");
    const irradEl = document.getElementById("check-irrad");
    const tempEl = document.getElementById("check-temp");
    const actualEl = document.getElementById("check-actual");

    if (plantId === 4135001) {
        if (scenario === "normal") {
            if (timeEl) timeEl.value = "12:30";
            if (irradEl) irradEl.value = "780";
            if (tempEl) tempEl.value = "34.0";
            if (actualEl) actualEl.value = "21500";
        } else if (scenario === "underperformance") {
            if (timeEl) timeEl.value = "12:30";
            if (irradEl) irradEl.value = "780";
            if (tempEl) tempEl.value = "34.0";
            if (actualEl) actualEl.value = "16500";
        } else if (scenario === "overperformance") {
            if (timeEl) timeEl.value = "12:30";
            if (irradEl) irradEl.value = "780";
            if (tempEl) tempEl.value = "34.0";
            if (actualEl) actualEl.value = "24200";
        } else if (scenario === "sensor_fault") {
            if (timeEl) timeEl.value = "12:30";
            if (irradEl) irradEl.value = "820";
            if (tempEl) tempEl.value = "35.0";
            if (actualEl) actualEl.value = "15";
        }
    } else {
        if (scenario === "normal") {
            if (timeEl) timeEl.value = "12:30";
            if (irradEl) irradEl.value = "780";
            if (tempEl) tempEl.value = "36.5";
            if (actualEl) actualEl.value = "13200";
        } else if (scenario === "underperformance") {
            if (timeEl) timeEl.value = "12:30";
            if (irradEl) irradEl.value = "780";
            if (tempEl) tempEl.value = "36.5";
            if (actualEl) actualEl.value = "8500";
        } else if (scenario === "overperformance") {
            if (timeEl) timeEl.value = "12:30";
            if (irradEl) irradEl.value = "780";
            if (tempEl) tempEl.value = "36.5";
            if (actualEl) actualEl.value = "17500";
        } else if (scenario === "sensor_fault") {
            if (timeEl) timeEl.value = "12:30";
            if (irradEl) irradEl.value = "820";
            if (tempEl) tempEl.value = "36.5";
            if (actualEl) actualEl.value = "20";
        }
    }

    runDeviationCheck();
}
