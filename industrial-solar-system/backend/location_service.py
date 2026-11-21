# Location detection and reverse geocoding service.
# Resolves coordinates to Indian state names using OpenStreetMap Nominatim and Open-Meteo.

import requests
import json
from config import API_URLS, HTTP_HEADERS

# Simple in-memory cache to avoid duplicate network queries
_location_cache = {}

def get_location_from_ip():
    # Attempts to detect approximate location using free IP geolocation services.
    # Returns dictionary with lat, lon, city, state, method label.
    try:
        resp = requests.get(API_URLS["ip_geolocation"], headers=HTTP_HEADERS, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "latitude": float(data.get("latitude", 17.3850)),
                "longitude": float(data.get("longitude", 78.4867)),
                "city": data.get("city", "Hyderabad"),
                "state": data.get("region", "Telangana"),
                "country": data.get("country_name", "India"),
                "detection_method": "approximate (IP based)",
                "source_label": "LIVE API"
            }
    except Exception as e:
        print(f"[Location Notice] Primary IP geolocation failed: {e}")

    # Fallback to secondary IP geolocation API
    try:
        resp = requests.get(API_URLS["ip_geolocation_fallback"], timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "latitude": float(data.get("lat", 17.3850)),
                "longitude": float(data.get("lon", 78.4867)),
                "city": data.get("city", "Hyderabad"),
                "state": data.get("regionName", "Telangana"),
                "country": data.get("country", "India"),
                "detection_method": "approximate (IP based)",
                "source_label": "LIVE API"
            }
    except Exception as e:
        print(f"[Location Notice] Secondary IP geolocation failed: {e}")

    # Default fallback when entirely offline
    return {
        "latitude": 17.3850,
        "longitude": 78.4867,
        "city": "Hyderabad",
        "state": "Telangana",
        "country": "India",
        "detection_method": "default fallback (Hyderabad)",
        "source_label": "ASSUMPTION"
    }

def reverse_geocode_nominatim(latitude, longitude):
    # Resolves coordinates to city and Indian state name using OpenStreetMap Nominatim.
    cache_key = f"{round(latitude, 3)},{round(longitude, 3)}"
    if cache_key in _location_cache:
        return _location_cache[cache_key]

    params = {
        "lat": latitude,
        "lon": longitude,
        "format": "jsonv2",
        "addressdetails": 1
    }

    try:
        resp = requests.get(
            API_URLS["nominatim_reverse"],
            params=params,
            headers=HTTP_HEADERS,
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            address = data.get("address", {})
            state = address.get("state") or address.get("province") or "Telangana"
            city = (
                address.get("city") or
                address.get("town") or
                address.get("municipality") or
                address.get("county") or
                "Detected Industrial Hub"
            )

            result = {
                "city": city,
                "state": state,
                "country": address.get("country", "India"),
                "source_label": "LIVE API"
            }
            _location_cache[cache_key] = result
            return result
    except Exception as e:
        print(f"[Location Error] Reverse geocoding failed: {e}")

    return {
        "city": "Unknown City",
        "state": "Telangana",
        "country": "India",
        "source_label": "ASSUMPTION"
    }

def search_locations_open_meteo(query_text):
    # Searches Indian cities and states using Open-Meteo Geocoding API.
    # admin1 contains the state name.
    params = {
        "name": query_text,
        "count": 8,
        "language": "en",
        "format": "json"
    }

    try:
        resp = requests.get(API_URLS["geocoding"], params=params, headers=HTTP_HEADERS, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            results = []
            for item in data.get("results", []):
                # Filter or prioritize Indian entries
                results.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "latitude": item.get("latitude"),
                    "longitude": item.get("longitude"),
                    "state": item.get("admin1") or item.get("country") or "Unknown State",
                    "country": item.get("country", "India")
                })
            return results
    except Exception as e:
        print(f"[Location Error] Geocoding search failed: {e}")

    return []
