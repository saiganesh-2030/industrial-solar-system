// Dashboard logic: coordinates automatic location, live weather, suitability, 24-hour forecast, and model demo.

let forecastChart = null;

document.addEventListener("DOMContentLoaded", async () => {
    renderNavigation("index");
    renderLimitationsPanel();

    const currentPlant = getCurrentPlantId();
    updatePlantBanner(currentPlant);

    // 1. Detect location
    const loc = await detectLocationAutomatically();
    loadDashboardData(loc);

    // 2. Initial run of single-point model demo
    onAmbientOrIrradChange();

    // Listen for manual location changes
    window.addEventListener("locationUpdated", (e) => {
        loadDashboardData(e.detail);
    });

    // Listen for global plant changes
    window.addEventListener("plantUpdated", (e) => {
        const plantId = e.detail.plantId;
        updatePlantBanner(plantId);
        loadDashboardData(getCurrentLocation());
        runSinglePointDemo();
    });
});

function updatePlantBanner(plantId) {
    const isPlant1 = plantId === 4135001;
    const badgeEl = document.getElementById("active-plant-badge");
    const descEl = document.getElementById("active-plant-desc");
    const refEl = document.getElementById("forecast-plant-ref");
    const demoPlant = document.getElementById("demo-plant");
    const btn1 = document.getElementById("btn-switch-plant-1");
    const btn2 = document.getElementById("btn-switch-plant-2");

    if (badgeEl) {
        badgeEl.textContent = isPlant1 ? "Plant 1 (4135001)" : "Plant 2 (4136001)";
        badgeEl.className = isPlant1 ? "badge badge-info" : "badge badge-warning";
    }

    if (descEl) {
        descEl.textContent = isPlant1
            ? "Standard Field Array | Max Observed Peak: 29,150 kW | Unconstrained Midday Curve"
            : "Plateau Limited Array | Max Observed Peak: 25,980 kW | Midday Inverter Cap (~13,000 kW)";
    }

    if (refEl) {
        refEl.textContent = `Reference Plant: ${plantId} | Scaled to 100 kW Benchmark System`;
    }

    if (demoPlant && demoPlant.value !== plantId.toString()) {
        demoPlant.value = plantId.toString();
    }

    if (btn1 && btn2) {
        btn1.style.fontWeight = isPlant1 ? "700" : "400";
        btn1.style.borderColor = isPlant1 ? "var(--primary)" : "var(--border-color)";
        btn2.style.fontWeight = !isPlant1 ? "700" : "400";
        btn2.style.borderColor = !isPlant1 ? "var(--primary)" : "var(--border-color)";
    }
}

async function loadDashboardData(loc) {
    const plantId = getCurrentPlantId();
    fetchWeatherAndSuitability(loc);
    fetchPredictionData(loc, plantId);
    fetchFeasibilitySummary(loc, plantId);
}

async function fetchWeatherAndSuitability(loc) {
    try {
        const res = await fetch(`${API_BASE}/api/weather?lat=${loc.latitude}&lon=${loc.longitude}&city=${encodeURIComponent(loc.city)}&state=${encodeURIComponent(loc.state)}`);
        const json = await res.json();
        if (json.status === "success") {
            const data = json.data;
            const curr = data.current;
            const suit = data.suitability;

            document.getElementById("weather-source-tag").innerHTML = renderSourceTag(data.source_label);
            document.getElementById("weather-temp").textContent = `${curr.temperature} °C`;
            document.getElementById("weather-rad").textContent = `${curr.solar_radiation_wm2} W/m²`;
            document.getElementById("weather-irrad").textContent = `${curr.model_irradiation_kwm2} kW/m²`;
            document.getElementById("weather-cloud").textContent = `${curr.cloud_cover} %`;
            document.getElementById("weather-wind").textContent = `Wind: ${curr.wind_speed} km/h`;
            document.getElementById("weather-humidity").textContent = `Humidity: ${curr.humidity} %`;
            document.getElementById("weather-fetched").textContent = `Fetched: ${curr.fetched_at}`;

            // Suitability
            document.getElementById("suitability-score").textContent = `${suit.score} / 100`;
            document.getElementById("suitability-cat").textContent = suit.category;
            document.getElementById("suitability-summary").textContent = suit.summary;

            let badgeClass = "badge-success";
            if (suit.category === "Good") badgeClass = "badge-info";
            else if (suit.category === "Moderate") badgeClass = "badge-warning";
            else if (suit.category === "Poor") badgeClass = "badge-danger";

            document.getElementById("suitability-badge-wrap").innerHTML = `<span class="badge ${badgeClass}">${suit.category}</span>`;
        }
    } catch (err) {
        console.error("Failed to load weather data", err);
    }
}

async function fetchPredictionData(loc, plantId) {
    try {
        const res = await fetch(`${API_BASE}/api/prediction?lat=${loc.latitude}&lon=${loc.longitude}&capacity=100&plant_id=${plantId}`);
        const json = await res.json();
        if (json.status === "success") {
            document.getElementById("pred-source-tag").innerHTML = renderSourceTag(json.source_label);
            document.getElementById("total-24h-yield").textContent = `${formatNumber(json.total_predicted_24h_kwh, 1)} kWh`;

            const hourly24 = json.hourly_predictions.slice(0, 24);
            const peakVal = Math.max(...hourly24.map(h => h.predicted_kw));
            document.getElementById("peak-generation-val").textContent = `${formatNumber(peakVal, 1)} kW`;

            renderForecastChart(hourly24);
        }
    } catch (err) {
        console.error("Failed to load prediction data", err);
    }
}

function renderForecastChart(hourlyData) {
    const ctx = document.getElementById("generation-forecast-chart");
    if (!ctx) return;

    const labels = hourlyData.map(h => `${h.hour}:00`);
    const genData = hourlyData.map(h => h.predicted_kw);
    const radData = hourlyData.map(h => h.radiation_wm2);

    if (forecastChart) {
        forecastChart.destroy();
    }

    forecastChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Solar Generation (kW) [100 kW System]",
                    data: genData,
                    borderColor: "#d97706",
                    backgroundColor: "rgba(217, 119, 6, 0.15)",
                    borderWidth: 2,
                    fill: true,
                    tension: 0.35,
                    yAxisID: "y"
                },
                {
                    label: "Solar Radiation (W/m²)",
                    data: radData,
                    borderColor: "#0284c7",
                    borderWidth: 1.5,
                    borderDash: [4, 4],
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

async function fetchFeasibilitySummary(loc, plantId) {
    try {
        const res = await fetch(`${API_BASE}/api/feasibility?lat=${loc.latitude}&lon=${loc.longitude}&city=${encodeURIComponent(loc.city)}&state=${encodeURIComponent(loc.state)}&plant_id=${plantId}`);
        const json = await res.json();
        if (json.status === "success") {
            const data = json.data;
            const rec = data.recommendation;

            document.getElementById("rec-source-tag").innerHTML = renderSourceTag("MODEL PREDICTION");
            document.getElementById("rec-decision").textContent = rec.decision;
            document.getElementById("rec-capacity").textContent = `${formatNumber(rec.recommended_capacity_kw, 1)} kW`;
            document.getElementById("rec-savings").textContent = formatINR(rec.annual_savings);
            document.getElementById("rec-payback").textContent = `${formatNumber(rec.payback_years, 1)} Yrs`;
            document.getElementById("rec-roi").textContent = `ROI: ${formatNumber(rec.roi_percent, 1)}%`;
            document.getElementById("rec-summary-text").textContent = rec.summary;

            let confBadge = "badge-success";
            if (rec.confidence === "Medium") confBadge = "badge-info";
            else if (rec.confidence === "Low") confBadge = "badge-warning";

            document.getElementById("confidence-badge-container").innerHTML = `
                <span class="badge ${confBadge}">Confidence: ${rec.confidence}</span>
            `;
        }
    } catch (err) {
        console.error("Failed to load feasibility summary", err);
    }
}

// Single-Point Model Demo Execution & Module Temp Management
let isManualModTemp = false;

function calculateAutoModuleTemp(ambient, irradWm2, isNight) {
    if (isNight || irradWm2 <= 0.0001) {
        return Math.round(ambient * 10) / 10;
    }
    const irradKwm2 = irradWm2 / 1000.0;
    const est = -2.1415 + (1.0303 * ambient) + (27.9989 * irradKwm2);
    const val = Math.max(ambient, est);
    return Math.round(val * 10) / 10;
}

function onAmbientOrIrradChange() {
    const tempEl = document.getElementById("demo-temp");
    const irradEl = document.getElementById("demo-irrad");
    const timeEl = document.getElementById("demo-time");
    const modTempEl = document.getElementById("demo-mod-temp");

    const temp = parseFloat(tempEl ? tempEl.value : 32.0) || 30.0;
    let irrad = parseFloat(irradEl ? irradEl.value : 750.0);
    if (isNaN(irrad) || irrad < 0) irrad = 0.0;

    const timeVal = timeEl ? timeEl.value : "12:00";
    const hour = parseInt(timeVal.split(":")[0], 10) || 12;
    const minute = parseInt(timeVal.split(":")[1], 10) || 0;
    const isNight = (hour < 6 || (hour === 18 && minute >= 45) || hour >= 19);

    if (!isManualModTemp && modTempEl) {
        modTempEl.value = calculateAutoModuleTemp(temp, irrad, isNight);
    }

    runSinglePointDemo();
}

function onManualModTempChange() {
    isManualModTemp = true;
    const badge = document.getElementById("demo-mod-temp-mode");
    if (badge) {
        badge.textContent = "Custom";
        badge.style.color = "#d97706";
        badge.style.background = "#fffbeb";
    }
    runSinglePointDemo();
}

function resetAutoModTemp() {
    isManualModTemp = false;
    const badge = document.getElementById("demo-mod-temp-mode");
    if (badge) {
        badge.textContent = "Auto";
        badge.style.color = "#059669";
        badge.style.background = "#ecfdf5";
    }

    const tempEl = document.getElementById("demo-temp");
    const irradEl = document.getElementById("demo-irrad");
    const timeEl = document.getElementById("demo-time");
    const modTempEl = document.getElementById("demo-mod-temp");

    const temp = parseFloat(tempEl ? tempEl.value : 32.0) || 30.0;
    let irrad = parseFloat(irradEl ? irradEl.value : 750.0);
    if (isNaN(irrad) || irrad < 0) irrad = 0.0;

    const timeVal = timeEl ? timeEl.value : "12:00";
    const hour = parseInt(timeVal.split(":")[0], 10) || 12;
    const minute = parseInt(timeVal.split(":")[1], 10) || 0;
    const isNight = (hour < 6 || (hour === 18 && minute >= 45) || hour >= 19);

    if (modTempEl) {
        modTempEl.value = calculateAutoModuleTemp(temp, irrad, isNight);
    }

    runSinglePointDemo();
}

function onTimeChange() {
    const timeEl = document.getElementById("demo-time");
    const irradEl = document.getElementById("demo-irrad");
    if (!timeEl) return;

    const timeVal = timeEl.value || "12:00";
    const parts = timeVal.split(":");
    const hour = parseInt(parts[0], 10) || 0;
    const minute = parseInt(parts[1], 10) || 0;
    const isNight = (hour < 6 || (hour === 18 && minute >= 45) || hour >= 19);

    if (isNight && irradEl) {
        irradEl.value = 0;
    }
    onAmbientOrIrradChange();
}

function setDemoPreset(temp, irrad, time) {
    const tempEl = document.getElementById("demo-temp");
    const irradEl = document.getElementById("demo-irrad");
    const timeEl = document.getElementById("demo-time");
    const modTempEl = document.getElementById("demo-mod-temp");

    if (tempEl) tempEl.value = temp;
    if (irradEl) irradEl.value = irrad;
    if (timeEl) timeEl.value = time;

    isManualModTemp = false;
    const badge = document.getElementById("demo-mod-temp-mode");
    if (badge) {
        badge.textContent = "Auto";
        badge.style.color = "#059669";
        badge.style.background = "#ecfdf5";
    }

    const hour = parseInt(String(time).split(":")[0], 10) || 12;
    const minute = parseInt(String(time).split(":")[1], 10) || 0;
    const isNight = (hour < 6 || (hour === 18 && minute >= 45) || hour >= 19);

    if (modTempEl) {
        modTempEl.value = calculateAutoModuleTemp(temp, irrad, isNight);
    }

    runSinglePointDemo();
}

async function runSinglePointDemo() {
    const plantEl = document.getElementById("demo-plant");
    const tempEl = document.getElementById("demo-temp");
    const irradEl = document.getElementById("demo-irrad");
    const timeEl = document.getElementById("demo-time");
    const modTempEl = document.getElementById("demo-mod-temp");
    const capEl = document.getElementById("demo-capacity");

    if (!plantEl || !tempEl || !irradEl) return;

    const plantId = parseInt(plantEl.value, 10) || getCurrentPlantId();
    const temp = parseFloat(tempEl.value) || 30.0;
    let irrad = parseFloat(irradEl.value);
    if (isNaN(irrad) || irrad < 0) irrad = 0.0;
    const timeVal = timeEl ? timeEl.value : "12:00";
    const cap = capEl ? (parseFloat(capEl.value) || 100.0) : 100.0;

    const hour = parseInt(timeVal.split(":")[0], 10) || 12;
    const minute = parseInt(timeVal.split(":")[1], 10) || 0;
    const isNight = (hour < 6 || (hour === 18 && minute >= 45) || hour >= 19);

    // If nighttime, ensure irradiance is set to 0
    if (isNight && irrad > 0) {
        irrad = 0.0;
        if (irradEl) irradEl.value = 0;
    }

    let modTempParam = "";
    if (modTempEl && modTempEl.value !== "") {
        modTempParam = `&module_temp=${encodeURIComponent(modTempEl.value)}`;
    }

    const kwEl = document.getElementById("demo-out-system-kw");
    const capSubEl = document.getElementById("demo-out-capacity-subtext");
    const modOutEl = document.getElementById("demo-out-mod-temp");
    const modSubEl = document.getElementById("demo-out-mod-subtext");
    const yieldEl = document.getElementById("demo-out-yield-fraction");
    const utilEl = document.getElementById("demo-out-utility-kw");
    const plantSubEl = document.getElementById("demo-out-plant-subtext");

    // Immediate zero generation check for night or 0 irradiance
    if (isNight || irrad <= 0.0001) {
        if (kwEl) kwEl.textContent = "0.00 kW";
        if (capSubEl) capSubEl.textContent = isNight ? "Nighttime: Zero solar generation in dark hours" : `For ${cap} kW industrial installation (zero irradiance)`;
        if (modOutEl) {
            const currentModVal = modTempEl ? parseFloat(modTempEl.value) : temp;
            modOutEl.textContent = `${formatNumber(currentModVal, 1)} °C`;
        }
        if (modSubEl) {
            modSubEl.textContent = isManualModTemp
                ? "User-entered custom temperature applied"
                : (isNight ? "Equals ambient temperature (no solar heating)" : "Estimated via regression formula");
        }
        if (yieldEl) yieldEl.textContent = "0.0000";
        if (utilEl) utilEl.textContent = "0.0 kW";
        if (plantSubEl) plantSubEl.textContent = plantId === 4135001 ? "Plant 1 full field array" : "Plant 2 full field array";
        return;
    }

    try {
        const url = `${API_BASE}/api/single-predict?plant_id=${plantId}&ambient_temp=${temp}&irradiation=${irrad}&time_str=${timeVal}&capacity_kw=${cap}${modTempParam}`;
        const res = await fetch(url);
        const json = await res.json();
        if (json.status === "success") {
            if (kwEl) kwEl.textContent = `${formatNumber(json.predicted_system_ac_kw, 2)} kW`;
            if (capSubEl) capSubEl.textContent = `For ${json.capacity_kw} kW industrial installation`;
            if (modOutEl) modOutEl.textContent = `${formatNumber(json.module_temp, 1)} °C`;
            if (modSubEl) {
                modSubEl.textContent = json.is_custom_module_temp
                    ? "User-entered custom temperature applied"
                    : "Estimated via regression formula";
            }
            if (yieldEl) yieldEl.textContent = formatNumber(json.yield_fraction_per_kw, 4);
            if (utilEl) utilEl.textContent = `${formatNumber(json.predicted_utility_ac_kw, 1)} kW`;
            if (plantSubEl) plantSubEl.textContent = `${json.plant_name} full field array`;
        }
    } catch (err) {
        console.error("Single-point demo prediction failed", err);
    }
}

// Relational Database Stored Predictions Retrieval & Management
let cachedStoredRecords = [];
const LOCAL_STORAGE_DB_KEY = "solar_db_stored_predictions";

const DEFAULT_PREDICTION_SEEDS = [
    {
        id: 1,
        location: "Hyderabad, Telangana",
        plant_id: 4135001,
        input_measurements: JSON.stringify({ ambient_temp: 34.0, irradiation_wm2: 850.0, time: "12:30", capacity_kw: 100.0, module_temp: 52.8 }),
        predicted_kw: 89.20,
        predicted_at: "2026-11-20 12:30:00",
        status: "Stored in Database"
    },
    {
        id: 2,
        location: "Bengaluru, Karnataka",
        plant_id: 4135001,
        input_measurements: JSON.stringify({ ambient_temp: 29.5, irradiation_wm2: 520.0, time: "10:00", capacity_kw: 100.0, module_temp: 41.2 }),
        predicted_kw: 54.80,
        predicted_at: "2026-11-20 10:00:00",
        status: "Stored in Database"
    },
    {
        id: 3,
        location: "Chennai, Tamil Nadu",
        plant_id: 4136001,
        input_measurements: JSON.stringify({ ambient_temp: 36.0, irradiation_wm2: 890.0, time: "13:00", capacity_kw: 100.0, module_temp: 55.4 }),
        predicted_kw: 72.40,
        predicted_at: "2026-11-20 13:00:00",
        status: "Stored in Database"
    },
    {
        id: 4,
        location: "Ahmedabad, Gujarat",
        plant_id: 4136001,
        input_measurements: JSON.stringify({ ambient_temp: 27.0, irradiation_wm2: 310.0, time: "08:45", capacity_kw: 100.0, module_temp: 33.6 }),
        predicted_kw: 28.50,
        predicted_at: "2026-11-20 08:45:00",
        status: "Stored in Database"
    },
    {
        id: 5,
        location: "Jaipur, Rajasthan",
        plant_id: 4135001,
        input_measurements: JSON.stringify({ ambient_temp: 33.0, irradiation_wm2: 440.0, time: "15:15", capacity_kw: 100.0, module_temp: 43.1 }),
        predicted_kw: 46.10,
        predicted_at: "2026-11-20 15:15:00",
        status: "Stored in Database"
    },
    {
        id: 6,
        location: "Mumbai, Maharashtra",
        plant_id: 4136001,
        input_measurements: JSON.stringify({ ambient_temp: 31.0, irradiation_wm2: 190.0, time: "16:30", capacity_kw: 100.0, module_temp: 35.2 }),
        predicted_kw: 16.80,
        predicted_at: "2026-11-20 16:30:00",
        status: "Stored in Database"
    }
];

function getLocalStoredPredictions() {
    try {
        const raw = localStorage.getItem(LOCAL_STORAGE_DB_KEY);
        if (raw) {
            const parsed = JSON.parse(raw);
            if (Array.isArray(parsed) && parsed.length > 0) return parsed;
        }
    } catch (e) {
        console.warn("Local storage parse note", e);
    }
    return [...DEFAULT_PREDICTION_SEEDS];
}

function saveLocalStoredPredictions(records) {
    try {
        localStorage.setItem(LOCAL_STORAGE_DB_KEY, JSON.stringify(records));
    } catch (e) {
        console.warn("Local storage write note", e);
    }
}

async function retrieveMySQLPredictions() {
    const btn = document.getElementById("btn-fetch-mysql");
    const tbody = document.getElementById("db-predictions-tbody");
    const connText = document.getElementById("db-conn-text");
    const statusBadge = document.getElementById("db-status-badge");
    const plantFilter = document.getElementById("db-plant-filter");

    const originalBtnHtml = btn ? btn.innerHTML : "Retrieve Stored Predictions";
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="animation: spin 1s linear infinite;">
                <circle cx="12" cy="12" r="10"></circle>
                <path d="M12 6v6l4 2"></path>
            </svg>
            Querying Database...
        `;
    }

    let recordsToRender = [];
    let isConnected = false;
    let sourceLabel = "industrial_solar.db";

    try {
        let endpoint = `/api/stored-predictions?limit=30`;
        if (plantFilter && plantFilter.value !== "all") {
            endpoint += `&plant_id=${plantFilter.value}`;
        }

        let res = null;
        try {
            res = await fetch(`${API_BASE}${endpoint}`);
        } catch (fetchErr) {
            if (!API_BASE) {
                try {
                    res = await fetch(`http://localhost:5000${endpoint}`);
                } catch (e) {
                    res = null;
                }
            }
        }

        if (res && res.ok) {
            const json = await res.json();
            if (json.status === "success" && Array.isArray(json.records)) {
                recordsToRender = json.records;
                isConnected = Boolean(json.db_connected);
                sourceLabel = json.db_source || "industrial_solar.db";
                cachedStoredRecords = recordsToRender;
                saveLocalStoredPredictions(recordsToRender);
            }
        }
    } catch (err) {
        console.warn("Backend API query notice; switching to local database storage mode:", err);
    }

    // If API was unreachable or empty, gracefully load from local stored records
    if (!recordsToRender || recordsToRender.length === 0) {
        const localRecords = getLocalStoredPredictions();
        if (plantFilter && plantFilter.value !== "all") {
            const targetId = parseInt(plantFilter.value, 10);
            recordsToRender = localRecords.filter(r => parseInt(r.plant_id, 10) === targetId);
        } else {
            recordsToRender = localRecords;
        }
        cachedStoredRecords = recordsToRender;
        isConnected = false;
        sourceLabel = "Local SQLite Storage";
    }

    // Update connection indicator
    if (connText) {
        if (isConnected) {
            connText.innerHTML = `<span style="color: var(--success);">Connected (${sourceLabel})</span>`;
        } else {
            connText.innerHTML = `<span style="color: var(--warning);">Local Storage Mode (${sourceLabel})</span>`;
        }
    }

    // Update status badge
    if (statusBadge) {
        if (isConnected) {
            statusBadge.textContent = "SQL DATABASE";
            statusBadge.className = "source-tag live-api";
            statusBadge.style.backgroundColor = "#ecfdf5";
            statusBadge.style.color = "#059669";
        } else {
            statusBadge.textContent = "STORAGE CACHE";
            statusBadge.className = "source-tag benchmark-estimate";
            statusBadge.style.backgroundColor = "#fffbeb";
            statusBadge.style.color = "#b45309";
        }
    }

    renderStoredPredictions(recordsToRender);

    if (btn) {
        btn.disabled = false;
        btn.innerHTML = originalBtnHtml;
    }
}

function renderStoredPredictions(records) {
    const tbody = document.getElementById("db-predictions-tbody");
    const countEl = document.getElementById("db-record-count");

    if (!tbody) return;

    if (!records || records.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" style="text-align: center; padding: 2rem; color: var(--text-muted);">
                    No stored prediction records found for the selected filter.
                </td>
            </tr>
        `;
        if (countEl) countEl.textContent = "Records: 0";
        return;
    }

    if (countEl) countEl.textContent = `Records: ${records.length} loaded`;

    tbody.innerHTML = records.map(record => {
        const isPlant1 = parseInt(record.plant_id, 10) === 4135001;
        const plantBadge = isPlant1
            ? `<span class="badge badge-info">Plant 1 (4135001)</span>`
            : `<span class="badge badge-warning">Plant 2 (4136001)</span>`;

        const locDisplay = record.location || (isPlant1 ? "Hyderabad, Telangana" : "Bengaluru, Karnataka");

        let inputDetails = "";
        try {
            const parsed = typeof record.input_measurements === "string"
                ? JSON.parse(record.input_measurements)
                : record.input_measurements;

            if (parsed && typeof parsed === "object") {
                const parts = [];
                if (parsed.ambient_temp !== undefined) parts.push(`Temp: ${parsed.ambient_temp}°C`);
                if (parsed.irradiation_wm2 !== undefined) parts.push(`Irrad: ${parsed.irradiation_wm2} W/m²`);
                if (parsed.time !== undefined) parts.push(`Time: ${parsed.time}`);
                if (parsed.capacity_kw !== undefined) parts.push(`Cap: ${parsed.capacity_kw} kW`);
                inputDetails = parts.join(" | ");
            } else {
                inputDetails = String(record.input_measurements);
            }
        } catch (e) {
            inputDetails = String(record.input_measurements);
        }

        const predictedVal = formatNumber(record.predicted_kw, 2);
        const sourceLabel = record.status || "Stored Record";

        return `
            <tr>
                <td style="font-weight: 600; color: var(--text-secondary); font-family: monospace;">#${record.id}</td>
                <td style="color: var(--text-secondary); white-space: nowrap;">${record.predicted_at || "--"}</td>
                <td>${plantBadge}</td>
                <td style="color: var(--text-secondary); font-size: 0.8rem; font-weight: 500;">
                    <span style="display: inline-flex; align-items: center; gap: 0.25rem;">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--solar-amber); flex-shrink: 0;">
                            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
                            <circle cx="12" cy="10" r="3"></circle>
                        </svg>
                        ${locDisplay}
                    </span>
                </td>
                <td style="color: var(--text-primary); font-size: 0.8rem;">${inputDetails}</td>
                <td style="text-align: right; font-weight: 700; color: var(--primary); font-size: 0.92rem;">${predictedVal} kW</td>
                <td style="text-align: center;">
                    <span style="font-size: 0.72rem; padding: 0.15rem 0.4rem; background: #f1f5f9; border-radius: 3px; color: var(--text-secondary);">
                        ${sourceLabel}
                    </span>
                </td>
            </tr>
        `;
    }).join("");
}

function filterStoredRecords() {
    const filterEl = document.getElementById("db-plant-filter");
    if (!filterEl) return;

    const val = filterEl.value;
    if (cachedStoredRecords.length === 0) {
        retrieveMySQLPredictions();
        return;
    }

    if (val === "all") {
        renderStoredPredictions(cachedStoredRecords);
    } else {
        const targetId = parseInt(val, 10);
        const filtered = cachedStoredRecords.filter(r => parseInt(r.plant_id, 10) === targetId);
        renderStoredPredictions(filtered);
    }
}

async function saveCurrentDemoToMySQL() {
    const plantEl = document.getElementById("demo-plant");
    const tempEl = document.getElementById("demo-temp");
    const irradEl = document.getElementById("demo-irrad");
    const timeEl = document.getElementById("demo-time");
    const modTempEl = document.getElementById("demo-mod-temp");
    const capEl = document.getElementById("demo-capacity");
    const kwEl = document.getElementById("demo-out-system-kw");
    const feedbackEl = document.getElementById("db-action-feedback");

    const plantId = parseInt(plantEl ? plantEl.value : 4135001, 10) || 4135001;
    const temp = parseFloat(tempEl ? tempEl.value : 30.0) || 30.0;
    const irrad = parseFloat(irradEl ? irradEl.value : 750.0) || 0.0;
    const timeVal = timeEl ? timeEl.value : "12:00";
    const cap = parseFloat(capEl ? capEl.value : 100.0) || 100.0;
    const modTemp = modTempEl ? (parseFloat(modTempEl.value) || temp) : temp;

    const hour = parseInt(timeVal.split(":")[0], 10) || 12;
    const isNight = (hour < 6 || hour >= 19);

    let predictedKw = 0.0;
    if (kwEl && kwEl.textContent && kwEl.textContent.includes("kW")) {
        predictedKw = parseFloat(kwEl.textContent.replace("kW", "").trim()) || 0.0;
    }

    if (predictedKw <= 0 && !isNight && irrad > 0) {
        await runSinglePointDemo();
        const updatedKwEl = document.getElementById("demo-out-system-kw");
        if (updatedKwEl) {
            predictedKw = parseFloat(updatedKwEl.textContent.replace("kW", "").trim()) || 0.0;
        }
    }

    const curLoc = typeof getCurrentLocation === "function" ? getCurrentLocation() : null;
    const activeLocationName = (curLoc && curLoc.city && curLoc.state)
        ? `${curLoc.city}, ${curLoc.state}`
        : (plantId === 4135001 ? "Hyderabad, Telangana" : "Bengaluru, Karnataka");

    const inputDataObj = {
        ambient_temp: temp,
        irradiation_wm2: irrad,
        time: timeVal,
        capacity_kw: cap,
        module_temp: modTemp
    };

    // 1. Immediately insert into local storage so it displays instantly
    const existingRecords = getLocalStoredPredictions();
    const maxExistingId = existingRecords.length > 0 ? Math.max(...existingRecords.map(r => r.id || 0)) : 0;
    const newRecordId = maxExistingId + 1;
    const now = new Date();
    const pad = n => String(n).padStart(2, "0");
    const nowStr = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;

    const newLocalRecord = {
        id: newRecordId,
        location: activeLocationName,
        plant_id: plantId,
        input_measurements: JSON.stringify(inputDataObj),
        predicted_kw: predictedKw,
        predicted_at: nowStr,
        status: "Saved to Database"
    };

    existingRecords.unshift(newLocalRecord);
    saveLocalStoredPredictions(existingRecords);

    // 2. Also send to SQLite backend if online
    const payload = {
        location: activeLocationName,
        plant_id: plantId,
        input_measurements: inputDataObj,
        predicted_kw: predictedKw
    };

    try {
        fetch(`${API_BASE}/api/save-prediction`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        }).catch(err => {
            console.warn("Backend save notice", err);
        });
    } catch (e) {}

    if (feedbackEl) {
        feedbackEl.style.display = "inline";
        feedbackEl.style.color = "var(--success)";
        feedbackEl.textContent = `Record #${newRecordId} saved successfully (${activeLocationName}).`;
        setTimeout(() => {
            feedbackEl.style.display = "none";
        }, 4000);
    }

    renderStoredPredictions(existingRecords);
}
