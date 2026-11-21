// Energy Feasibility Engine interactive simulation logic.

document.addEventListener("DOMContentLoaded", async () => {
    renderNavigation("feasibility");
    renderLimitationsPanel();

    const loc = getCurrentLocation();
    loadFeasibilityAnalysis(loc);

    const indSelect = document.getElementById("industry-select");
    indSelect.addEventListener("change", () => {
        loadFeasibilityAnalysis(getCurrentLocation());
    });

    window.addEventListener("locationUpdated", (e) => {
        loadFeasibilityAnalysis(e.detail);
    });

    // Listen for global plant change
    window.addEventListener("plantUpdated", () => {
        loadFeasibilityAnalysis(getCurrentLocation());
    });
});

function triggerReanalysis() {
    loadFeasibilityAnalysis(getCurrentLocation());
}

async function loadFeasibilityAnalysis(loc) {
    const indSelect = document.getElementById("industry-select");
    const industry = indSelect ? indSelect.value : "Light Manufacturing";
    const plantId = getCurrentPlantId();

    try {
        const res = await fetch(`${API_BASE}/api/feasibility?lat=${loc.latitude}&lon=${loc.longitude}&city=${encodeURIComponent(loc.city)}&state=${encodeURIComponent(loc.state)}&industry=${encodeURIComponent(industry)}&plant_id=${plantId}`);
        const json = await res.json();
        if (json.status === "success") {
            const data = json.data;
            renderFeasibilityDetails(data);
        }
    } catch (err) {
        console.error("Failed to run feasibility analysis", err);
    }
}

function renderFeasibilityDetails(data) {
    const inputs = data.inputs;
    const inter = data.intermediate_calculations;
    const sizes = data.system_sizes_evaluated;
    const rec = data.recommendation;

    // Tariff info
    document.getElementById("tariff-val-display").textContent = `Rs ${inputs.grid_tariff_per_kwh.toFixed(2)} / kWh`;
    document.getElementById("tariff-discom-text").textContent = `State: ${inputs.state} | Source: ${inputs.tariff_source}`;

    const badgeClass = inputs.tariff_verified ? "badge-success" : "badge-warning";
    const badgeText = inputs.tariff_verified ? "Verified SERC Tariff" : "Unverified Tariff (Order Audit Pending)";
    document.getElementById("tariff-badge-wrap").innerHTML = `<span class="badge ${badgeClass}">${badgeText}</span>`;

    // Step 1: Demand
    document.getElementById("step-daily-demand").textContent = `${formatNumber(inter.daily_demand_kwh, 1)} kWh`;
    document.getElementById("step-annual-demand").textContent = `${formatNumber(inter.annual_demand_kwh, 0)} kWh`;
    document.getElementById("industry-desc-text").textContent = `${inputs.industry_type}: ${inputs.industry_description}. Connected Load: ${inputs.connected_load_kw} kW.`;

    // Step 2: Sizing Formula
    document.getElementById("step-sizing-calc").textContent = `Substitution: ${inter.sizing_calculation}`;
    document.getElementById("step-100-capacity").textContent = `${inter.base_100pct_capacity_kw} kW`;

    // Step 3: Sizes Table
    const tbody = document.getElementById("sizes-table-body");
    let rowsHtml = "";

    const sizeKeys = ["25", "50", "75", "100"];
    sizeKeys.forEach(key => {
        const item = sizes[key];
        const isRec = (rec.recommended_capacity_kw === item.capacity_kw);
        const rowBg = isRec ? 'style="background-color: #ecfdf5; font-weight: 600;"' : '';

        rowsHtml += `
        <tr ${rowBg}>
            <td>
                <strong>${item.percentage}% Sizing</strong>
                ${isRec ? '<span class="badge badge-success" style="margin-left: 0.3rem;">Selected</span>' : ''}
            </td>
            <td>${item.capacity_kw} kW</td>
            <td>${formatINR(item.installation_cost)}</td>
            <td>${formatNumber(item.annual_generation_kwh, 0)}</td>
            <td>${formatNumber(item.annual_self_consumption_kwh, 0)}</td>
            <td>${formatNumber(item.annual_grid_import_kwh, 0)}</td>
            <td style="color: var(--success); font-weight: 700;">${formatINR(item.annual_savings)}</td>
            <td><strong>${item.payback_years.toFixed(1)}</strong></td>
            <td>${item.roi_percent.toFixed(1)}%</td>
            <td>Rs ${item.t_solar_per_kwh.toFixed(2)}</td>
            <td style="color: var(--primary); font-weight: 700;">${formatINR(item.net_25yr_savings)}</td>
            <td style="color: var(--success); font-weight: 600;">${item.annual_co2_offset_tonnes ? item.annual_co2_offset_tonnes.toFixed(1) : (item.annual_generation_kwh * 0.82 / 1000).toFixed(1)} t</td>
        </tr>
        `;
    });
    tbody.innerHTML = rowsHtml;

    // Step 4: Final Recommendation
    document.getElementById("final-decision-badge").textContent = rec.decision;
    document.getElementById("final-cap-val").textContent = `${rec.recommended_capacity_kw} kW`;
    document.getElementById("final-payback-val").textContent = `${rec.payback_years.toFixed(1)} Yrs`;
    document.getElementById("final-savings-val").textContent = formatINR(rec.annual_savings);
    const co2El = document.getElementById("final-co2-val");
    if (co2El) {
        const co2Val = rec.annual_co2_offset_tonnes ? rec.annual_co2_offset_tonnes.toFixed(1) : "--";
        co2El.textContent = `${co2Val} t/yr`;
    }
    const plantLabel = (inputs.plant_id === 4136001) ? "Plant 2 (Plateau Limited Array)" : "Plant 1 (Standard Field Array)";
    document.getElementById("final-rec-text").textContent = `${rec.summary} Reference basis: ${plantLabel}. Confidence level is ${rec.confidence}: ${rec.confidence_reason}`;

    let confClass = "badge-success";
    if (rec.confidence === "Medium") confClass = "badge-info";
    else if (rec.confidence === "Low") confClass = "badge-warning";

    document.getElementById("feas-conf-badge").innerHTML = `<span class="badge ${confClass}">Confidence: ${rec.confidence}</span>`;
}
