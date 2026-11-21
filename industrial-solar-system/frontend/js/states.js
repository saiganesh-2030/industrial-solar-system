// State Tariff and Payback Ranking visualization module.

let stateChart = null;

document.addEventListener("DOMContentLoaded", async () => {
    renderNavigation("states");
    renderLimitationsPanel();

    loadStateComparison();

    // Listen for global plant change
    window.addEventListener("plantUpdated", () => {
        loadStateComparison();
    });
});

async function loadStateComparison() {
    const plantId = getCurrentPlantId();
    try {
        const res = await fetch(`${API_BASE}/api/states-comparison?plant_id=${plantId}`);
        const json = await res.json();
        if (json.status === "success") {
            const ranked = json.ranked_states;
            renderTariffsBarChart(ranked);
            populateStatesTable(ranked);
        }
    } catch (err) {
        console.error("Failed to load state comparison", err);
    }
}

function renderTariffsBarChart(states) {
    const ctx = document.getElementById("state-tariffs-chart");
    if (!ctx) return;

    // Filter valid tariffs and sort by rate descending
    const valid = states.filter(s => s.tariff_per_kwh !== null);
    const sorted = [...valid].sort((a, b) => b.tariff_per_kwh - a.tariff_per_kwh);

    const labels = sorted.map(s => s.state);
    const rates = sorted.map(s => s.tariff_per_kwh);

    if (stateChart) stateChart.destroy();

    stateChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Industrial Tariff (INR / kWh)",
                    data: rates,
                    backgroundColor: "#0284c7",
                    borderRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { ticks: { autoSkip: false, maxRotation: 45, minRotation: 30 } },
                y: { title: { display: true, text: "Rate (INR / kWh)" }, beginAtZero: true }
            }
        }
    });
}

function populateStatesTable(states) {
    const tbody = document.getElementById("states-table-body");
    if (!tbody) return;

    let rowsHtml = "";
    states.forEach(s => {
        const hasTariff = s.tariff_per_kwh !== null;
        const tariffDisplay = hasTariff ? `Rs ${s.tariff_per_kwh.toFixed(2)}` : '<span style="color: var(--danger); font-weight: 600;">NOT FOUND</span>';
        const savingsDisplay = hasTariff ? formatINR(s.annual_savings) : "N/A";
        const paybackDisplay = hasTariff ? `${s.payback_years.toFixed(1)} Yrs` : "N/A";

        const badgeClass = s.verified ? "badge-success" : "badge-warning";
        const badgeLabel = s.verified_badge || (s.verified ? "Verified" : "Not yet verified");

        const sourceLink = s.source_url ? `<a href="${s.source_url}" target="_blank" rel="noopener" style="color: var(--primary); text-decoration: none;">SERC Schedule &rarr;</a>` : "Not Available";

        rowsHtml += `
        <tr>
            <td><strong>#${s.rank}</strong></td>
            <td><strong>${s.state}</strong></td>
            <td style="font-size: 0.8rem; color: var(--text-secondary);">${s.discom}</td>
            <td style="font-weight: 600;">${tariffDisplay}</td>
            <td>${s.annual_solar_yield_per_kw} kWh/kW</td>
            <td style="color: var(--success); font-weight: 600;">${savingsDisplay}</td>
            <td style="font-weight: 700; color: ${s.payback_years && s.payback_years <= 6 ? 'var(--success)' : 'var(--text-primary)'};">${paybackDisplay}</td>
            <td><span class="badge ${badgeClass}">${badgeLabel}</span></td>
            <td style="font-size: 0.8rem;">${sourceLink}</td>
        </tr>
        `;
    });
    tbody.innerHTML = rowsHtml;
}
