// Weather and NASA POWER solar climatology visualization module.

let weatherTrendChart = null;
let monthlyInsolationChart = null;

document.addEventListener("DOMContentLoaded", async () => {
    renderNavigation("weather");
    renderLimitationsPanel();

    const loc = getCurrentLocation();
    loadWeatherData(loc);

    window.addEventListener("locationUpdated", (e) => {
        loadWeatherData(e.detail);
    });
});

async function loadWeatherData(loc) {
    fetchLiveWeather(loc);
    fetchSolarPotential(loc);
}

async function fetchLiveWeather(loc) {
    try {
        const res = await fetch(`${API_BASE}/api/weather?lat=${loc.latitude}&lon=${loc.longitude}&city=${encodeURIComponent(loc.city)}&state=${encodeURIComponent(loc.state)}`);
        const json = await res.json();
        if (json.status === "success") {
            const data = json.data;
            const curr = data.current;
            const suit = data.suitability;

            document.getElementById("weather-tag").innerHTML = renderSourceTag(data.source_label);
            document.getElementById("weather-timestamp").textContent = `Fetched: ${curr.fetched_at}`;

            document.getElementById("w-temp").textContent = `${curr.temperature} °C`;
            document.getElementById("w-rad").textContent = `${curr.solar_radiation_wm2} W/m²`;
            document.getElementById("w-irrad").textContent = `${curr.model_irradiation_kwm2} kW/m²`;
            document.getElementById("w-cloud").textContent = `${curr.cloud_cover} %`;
            document.getElementById("w-hum").textContent = `${curr.humidity} %`;
            document.getElementById("w-wind").textContent = `${curr.wind_speed} km/h`;
            document.getElementById("w-precip").textContent = `${curr.precipitation} mm`;

            // Suitability breakdown
            document.getElementById("suit-val").textContent = `${suit.score} / 100`;
            document.getElementById("suit-cat").textContent = `Category: ${suit.category}`;
            document.getElementById("suit-summary-full").textContent = suit.summary;

            document.getElementById("pts-rad").textContent = `${suit.breakdown.radiation_points} / 40 pts`;
            document.getElementById("pts-cloud").textContent = `${suit.breakdown.cloud_points} / 30 pts`;
            document.getElementById("pts-rain").textContent = `${suit.breakdown.precipitation_points} / 15 pts`;
            document.getElementById("pts-temp").textContent = `${suit.breakdown.temperature_points} / 15 pts`;

            renderHourlyTrend(data.hourly);
        }
    } catch (err) {
        console.error("Failed to load live weather", err);
    }
}

async function fetchSolarPotential(loc) {
    try {
        const res = await fetch(`${API_BASE}/api/solar-potential?lat=${loc.latitude}&lon=${loc.longitude}`);
        const json = await res.json();
        if (json.status === "success") {
            const data = json.data;
            document.getElementById("psh-val").textContent = `${data.annual_average_peak_sun_hours} PSH`;
            renderMonthlyChart(data.monthly_radiation_kwh_m2_day, data.annual_average_peak_sun_hours);
        }
    } catch (err) {
        console.error("Failed to load solar potential", err);
    }
}

function renderHourlyTrend(hourly) {
    const ctx = document.getElementById("hourly-weather-chart");
    if (!ctx) return;

    const labels = hourly.map(h => {
        const parts = h.time.split("T");
        return parts[1]; // HH:MM
    });
    const temps = hourly.map(h => h.temperature);
    const clouds = hourly.map(h => h.cloud_cover);

    if (weatherTrendChart) {
        weatherTrendChart.destroy();
    }

    weatherTrendChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Temperature (°C)",
                    data: temps,
                    borderColor: "#ef4444",
                    backgroundColor: "transparent",
                    borderWidth: 2,
                    yAxisID: "y"
                },
                {
                    label: "Cloud Cover (%)",
                    data: clouds,
                    borderColor: "#64748b",
                    backgroundColor: "rgba(100, 116, 139, 0.1)",
                    borderWidth: 1.5,
                    fill: true,
                    yAxisID: "y1"
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            scales: {
                x: { ticks: { maxTicksLimit: 12 }, grid: { display: false } },
                y: { title: { display: true, text: "Temperature (°C)" }, beginAtZero: false },
                y1: { title: { display: true, text: "Cloud Cover (%)" }, position: "right", min: 0, max: 100, grid: { drawOnChartArea: false } }
            }
        }
    });
}

function renderMonthlyChart(monthlyDict, annualAverage) {
    const ctx = document.getElementById("monthly-radiation-chart");
    if (!ctx) return;

    const months = Object.keys(monthlyDict);
    const values = Object.values(monthlyDict);

    if (monthlyInsolationChart) {
        monthlyInsolationChart.destroy();
    }

    monthlyInsolationChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels: months,
            datasets: [
                {
                    label: "Monthly Daily Radiation (kWh/m²/day)",
                    data: values,
                    backgroundColor: "#f59e0b",
                    borderRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { grid: { display: false } },
                y: {
                    title: { display: true, text: "Insolation (kWh/m²/day)" },
                    beginAtZero: true
                }
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        afterBody: () => `Annual Mean: ${annualAverage} kWh/m²/day`
                    }
                }
            }
        }
    });
}
