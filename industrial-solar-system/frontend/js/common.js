// Shared JavaScript module for navigation, location detection, and common UI helpers.

// Automatically detects backend URL whether opened via localhost, IP address, or file protocol
const API_BASE = (typeof window !== "undefined" && (window.location.protocol === "file:" || (window.location.port !== "5000" && window.location.port !== "")))
    ? "http://localhost:5000"
    : "";

// Default location (Hyderabad, Telangana)
const DEFAULT_LOCATION = {
    latitude: 17.3850,
    longitude: 78.4867,
    city: "Hyderabad",
    state: "Telangana",
    country: "India",
    detection_method: "default fallback",
    source_label: "ASSUMPTION"
};

// Get current saved location from localStorage or default
function getCurrentLocation() {
    const saved = localStorage.getItem("solar_location");
    if (saved) {
        try {
            return JSON.parse(saved);
        } catch (e) {
            console.error("Failed to parse saved location", e);
        }
    }
    return DEFAULT_LOCATION;
}

// Save location to localStorage
function saveLocation(loc) {
    localStorage.setItem("solar_location", JSON.stringify(loc));
    updateLocationDisplay();
    // Dispatch event for page listeners
    window.dispatchEvent(new CustomEvent("locationUpdated", { detail: loc }));
}

// Get current saved plant ID (4135001 or 4136001)
function getCurrentPlantId() {
    const saved = localStorage.getItem("solar_plant_id");
    return saved ? parseInt(saved, 10) : 4135001;
}

// Save active plant ID and notify all pages
function savePlantId(id) {
    const plantId = parseInt(id, 10) || 4135001;
    localStorage.setItem("solar_plant_id", plantId.toString());

    // Synchronize any plant selector dropdowns present in the DOM
    const selects = document.querySelectorAll("#global-plant-select, #demo-plant");
    selects.forEach(sel => {
        if (sel && sel.value !== plantId.toString()) {
            sel.value = plantId.toString();
        }
    });

    // Dispatch global event for page listeners
    window.dispatchEvent(new CustomEvent("plantUpdated", { detail: { plantId: plantId } }));
}

// Automatic location detection sequence:
// 1. Browser geolocation -> 2. IP geolocation API -> 3. Fallback
async function detectLocationAutomatically() {
    // If already saved in this session, keep it
    if (localStorage.getItem("solar_location")) {
        return getCurrentLocation();
    }

    return new Promise((resolve) => {
        if ("geolocation" in navigator) {
            navigator.geolocation.getCurrentPosition(
                async (position) => {
                    const lat = position.coords.latitude;
                    const lon = position.coords.longitude;
                    try {
                        const res = await fetch(`${API_BASE}/api/location?lat=${lat}&lon=${lon}`);
                        const data = await res.json();
                        if (data.status === "success") {
                            const loc = {
                                latitude: lat,
                                longitude: lon,
                                city: data.city || "Detected City",
                                state: data.state || "Telangana",
                                country: data.country || "India",
                                detection_method: "Browser GPS",
                                source_label: data.source_label || "LIVE API"
                            };
                            saveLocation(loc);
                            return resolve(loc);
                        }
                    } catch (err) {
                        console.warn("Reverse geocode failed, falling to IP", err);
                    }
                    fallbackToIP(resolve);
                },
                (err) => {
                    console.log("Browser geolocation denied or unavailable:", err.message);
                    fallbackToIP(resolve);
                },
                { timeout: 5000 }
            );
        } else {
            fallbackToIP(resolve);
        }
    });
}

async function fallbackToIP(resolve) {
    try {
        const res = await fetch(`${API_BASE}/api/location`);
        const data = await res.json();
        if (data.status === "success") {
            const loc = {
                latitude: data.latitude,
                longitude: data.longitude,
                city: data.city,
                state: data.state,
                country: data.country || "India",
                detection_method: data.detection_method,
                source_label: data.source_label
            };
            saveLocation(loc);
            return resolve(loc);
        }
    } catch (e) {
        console.warn("IP geolocation failed", e);
    }
    saveLocation(DEFAULT_LOCATION);
    resolve(DEFAULT_LOCATION);
}

// Update location text in header
function updateLocationDisplay() {
    const loc = getCurrentLocation();
    const cityEl = document.getElementById("header-city");
    const stateEl = document.getElementById("header-state");
    const barEl = document.getElementById("location-bar");

    if (cityEl) cityEl.textContent = loc.city;
    if (stateEl) stateEl.textContent = loc.state;
    if (barEl && loc.detection_method) {
        barEl.setAttribute("title", `Source: ${loc.detection_method}`);
    }
}

// Render standard navigation bar
function renderNavigation(activePage) {
    const navContainer = document.getElementById("navbar-container");
    if (!navContainer) return;

    const navHtml = `
    <nav class="navbar">
        <a href="index.html" class="nav-brand">
            <svg class="brand-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="5"></circle>
                <line x1="12" y1="1" x2="12" y2="3"></line>
                <line x1="12" y1="21" x2="12" y2="23"></line>
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
                <line x1="1" y1="12" x2="3" y2="12"></line>
                <line x1="21" y1="12" x2="23" y2="12"></line>
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
            </svg>
            <span>SolarIndustrial</span>
        </a>
        <ul class="nav-links">
            <li><a href="index.html" class="${activePage === 'index' ? 'active' : ''}">Dashboard</a></li>
            <li><a href="prediction.html" class="${activePage === 'prediction' ? 'active' : ''}">Prediction</a></li>
            <li><a href="weather.html" class="${activePage === 'weather' ? 'active' : ''}">Weather</a></li>
            <li><a href="feasibility.html" class="${activePage === 'feasibility' ? 'active' : ''}">Feasibility</a></li>
            <li><a href="comparison.html" class="${activePage === 'comparison' ? 'active' : ''}">Comparison</a></li>
            <li><a href="states.html" class="${activePage === 'states' ? 'active' : ''}">Tariffs</a></li>
            <li><a href="deviation.html" class="${activePage === 'deviation' ? 'active' : ''}">Deviation</a></li>
            <li><a href="model.html" class="${activePage === 'model' ? 'active' : ''}">Model</a></li>
        </ul>
    </nav>
    <div class="subbar">
        <div class="location-display" id="location-bar">
            <svg class="location-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
                <circle cx="12" cy="10" r="3"></circle>
            </svg>
            <span class="location-text">
                <strong id="header-city">Detecting...</strong>, <span id="header-state">...</span>
            </span>
        </div>
        <div style="display: flex; gap: 0.75rem; align-items: center;">
            <div style="display: flex; align-items: center; gap: 0.4rem; background: #ffffff; border: 1px solid var(--border-color); padding: 0.25rem 0.6rem; border-radius: 6px;">
                <label for="global-plant-select" style="font-size: 0.8rem; font-weight: 600; color: var(--text-secondary); margin: 0;">Plant:</label>
                <select id="global-plant-select" style="border: none; background: transparent; font-size: 0.82rem; font-weight: 600; color: var(--text-primary); cursor: pointer; outline: none;" onchange="savePlantId(this.value)">
                    <option value="4135001">Plant 1 (4135001)</option>
                    <option value="4136001">Plant 2 (4136001)</option>
                </select>
            </div>
            <button class="btn-location" onclick="openLocationModal()">Change Location</button>
        </div>
    </div>
    `;
    navContainer.innerHTML = navHtml;
    updateLocationDisplay();

    // Set initial selected value of plant dropdown
    const plantSel = document.getElementById("global-plant-select");
    if (plantSel) {
        plantSel.value = getCurrentPlantId().toString();
    }
}

// Render standard bottom limitations panel
function renderLimitationsPanel(containerId = "limitations-container") {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = `
    <div class="limitations-panel">
        <h3>Data Sources, Methodologies and Academic Limitations</h3>
        <ul>
            <li><strong>Model Input Scope:</strong> Trained on Plant 4135001 and 4136001 operational telemetry (May 15 to June 17, 2020). Predictions outside summer months are scaled via NASA POWER climatological solar insolation curves.</li>
            <li><strong>Module Temperature Estimation:</strong> Panel surface temperature is estimated using linear regression (R2 = 0.9709) based on ambient temperature and irradiation, as commercial weather forecast APIs do not measure PV back-of-module temperature.</li>
            <li><strong>Industrial Demand Benchmarks:</strong> Factory load shapes are derived from Bureau of Energy Efficiency (BEE) and industrial sector benchmarks, not real-time sub-metered factory lines.</li>
            <li><strong>State Electricity Tariffs:</strong> Based on published State Electricity Regulatory Commission (SERC) tariff schedules. Users should verify applicable demand charges, power factor surcharges, and Time-of-Day rules with local DISCOMs.</li>
            <li><strong>Deviation Replay:</strong> Inverter performance deviation analysis is executed as a historical replay against unseen test data, not as a live SCADA equipment diagnostic.</li>
        </ul>
    </div>
    `;
}

// Location selection modal logic
function setupLocationModal() {
    let modal = document.getElementById("location-modal");
    if (!modal) {
        modal = document.createElement("div");
        modal.id = "location-modal";
        modal.className = "modal-overlay";
        modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3 style="font-size: 1.1rem; font-weight: 600;">Select Industrial Location</h3>
                <button class="modal-close" onclick="closeLocationModal()">&times;</button>
            </div>
            <div class="form-group">
                <label>Search Indian City or Industrial District</label>
                <div style="display: flex; gap: 0.5rem;">
                    <input type="text" id="city-search-input" class="form-control" placeholder="e.g. Hyderabad, Pune, Surat, Chennai">
                    <button class="btn-primary" onclick="searchLocation()">Search</button>
                </div>
            </div>
            <div id="search-results-list" style="max-height: 200px; overflow-y: auto; margin-bottom: 1rem;"></div>
            <div style="border-top: 1px solid var(--border-color); padding-top: 0.75rem; display: flex; justify-content: space-between;">
                <button class="btn-sm" onclick="useBrowserGPS()">Use Device GPS</button>
                <button class="btn-sm" onclick="closeLocationModal()">Close</button>
            </div>
        </div>
        `;
        document.body.appendChild(modal);
    }
}

function openLocationModal() {
    setupLocationModal();
    document.getElementById("location-modal").style.display = "flex";
}

function closeLocationModal() {
    const modal = document.getElementById("location-modal");
    if (modal) modal.style.display = "none";
}

async function searchLocation() {
    const input = document.getElementById("city-search-input");
    const query = input.value.trim();
    if (!query) return;

    const list = document.getElementById("search-results-list");
    list.innerHTML = `<div style="padding: 0.5rem; font-size: 0.85rem; color: var(--text-muted);">Searching...</div>`;

    try {
        const res = await fetch(`${API_BASE}/api/location?search=${encodeURIComponent(query)}`);
        const data = await res.json();
        if (data.results && data.results.length > 0) {
            let html = '<div style="list-style: none;">';
            data.results.forEach(item => {
                html += `
                <div onclick="selectSearchedLocation(${item.latitude}, ${item.longitude}, '${item.name}', '${item.state}')" 
                     style="padding: 0.5rem; border-bottom: 1px solid #f1f5f9; cursor: pointer; font-size: 0.85rem;"
                     onmouseover="this.style.backgroundColor='#f8fafc'" onmouseout="this.style.backgroundColor='transparent'">
                    <strong>${item.name}</strong>, <span style="color: var(--text-secondary);">${item.state} (${item.country})</span>
                </div>`;
            });
            html += '</div>';
            list.innerHTML = html;
        } else {
            list.innerHTML = `<div style="padding: 0.5rem; font-size: 0.85rem; color: var(--text-muted);">No matching Indian locations found.</div>`;
        }
    } catch (err) {
        list.innerHTML = `<div style="padding: 0.5rem; font-size: 0.85rem; color: var(--danger);">Search error. Please try again.</div>`;
    }
}

function selectSearchedLocation(lat, lon, city, state) {
    const loc = {
        latitude: lat,
        longitude: lon,
        city: city,
        state: state,
        country: "India",
        detection_method: "User Search",
        source_label: "LIVE API"
    };
    saveLocation(loc);
    closeLocationModal();
}

function useBrowserGPS() {
    if ("geolocation" in navigator) {
        navigator.geolocation.getCurrentPosition(
            async (pos) => {
                const lat = pos.coords.latitude;
                const lon = pos.coords.longitude;
                try {
                    const res = await fetch(`${API_BASE}/api/location?lat=${lat}&lon=${lon}`);
                    const data = await res.json();
                    const loc = {
                        latitude: lat,
                        longitude: lon,
                        city: data.city || "Detected City",
                        state: data.state || "Telangana",
                        country: data.country || "India",
                        detection_method: "Browser GPS",
                        source_label: "LIVE API"
                    };
                    saveLocation(loc);
                    closeLocationModal();
                } catch (e) {
                    alert("GPS coordinates resolved, but reverse lookup failed.");
                }
            },
            () => alert("Location permission denied.")
        );
    }
}

// Formatting helpers
function formatINR(val) {
    if (val === null || val === undefined || isNaN(val)) return "N/A";
    return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(val);
}

function formatNumber(val, decimals = 1) {
    if (val === null || val === undefined || isNaN(val)) return "N/A";
    return Number(val).toLocaleString("en-IN", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function renderSourceTag(type) {
    const safeType = (type || "ASSUMPTION").toUpperCase();
    let cssClass = "assumption";
    if (safeType.includes("LIVE")) cssClass = "live-api";
    else if (safeType.includes("HISTORICAL")) cssClass = "historical-api";
    else if (safeType.includes("MODEL")) cssClass = "model-prediction";
    else if (safeType.includes("BENCHMARK")) cssClass = "benchmark-estimate";

    return `<span class="source-tag ${cssClass}">${type || "ASSUMPTION"}</span>`;
}
