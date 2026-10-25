import httpx
from typing import Dict, Any, List
from app.config import settings

# Outil Météo (WeatherAPI / OpenWeather avec repli Open-Meteo sans clé)
def get_weather(cities: List[str] | str, days: int = 1) -> Dict[str, Any]:
    """
    Récupère les conditions météorologiques actuelles et les prévisions pour une ou plusieurs villes.
    Prend en charge la comparaison multi-villes.
    """
    if isinstance(cities, str):
        # Si une seule ville est passée sous forme de chaîne
        city_list = [c.strip() for c in cities.split(",") if c.strip()]
    else:
        city_list = cities

    if not city_list:
        return {"status": "error", "message": "Veuillez spécifier au moins une ville."}

    results = []

    for city in city_list:
        city_data = _fetch_single_city_weather(city, days)
        results.append(city_data)

    if len(results) == 1:
        return {
            "status": "success",
            "type": "single_city",
            "city": results[0].get("city"),
            "data": results[0]
        }
    else:
        # Comparaison multi-villes
        comparison = []
        for r in results:
            if r.get("status") == "success":
                comparison.append({
                    "city": r.get("city"),
                    "temp_c": r.get("temperature_c"),
                    "condition": r.get("condition"),
                    "humidity": r.get("humidity"),
                    "wind_kph": r.get("wind_kph")
                })
        return {
            "status": "success",
            "type": "multi_city_comparison",
            "comparison": comparison,
            "details": results
        }


# Coordonnées pré-enregistrées pour les villes fréquentes (résilience hors-ligne et rapidité)
PRESET_COORDS = {
    "lome": (6.1375, 1.2125, "Lomé", "Togo"),
    "lomé": (6.1375, 1.2125, "Lomé", "Togo"),
    "accra": (5.556, -0.1969, "Accra", "Ghana"),
    "cotonou": (6.3654, 2.4183, "Cotonou", "Bénin"),
    "lagos": (6.5244, 3.3792, "Lagos", "Nigeria"),
    "nairobi": (-1.2864, 36.8172, "Nairobi", "Kenya"),
    "paris": (48.8566, 2.3522, "Paris", "France")
}

def _fetch_single_city_weather(city: str, days: int = 1) -> Dict[str, Any]:
    """Interroge OpenWeatherMap, WeatherAPI ou Open-Meteo en repli sans clé."""
    city_clean = city.strip()

    # 1. Tentative avec OpenWeatherMap si clé fournie
    ow_key = (settings.OPENWEATHER_API_KEY or settings.WEATHER_API_KEY or "").strip()
    if ow_key and len(ow_key) == 32:
        try:
            url_w = f"https://api.openweathermap.org/data/2.5/weather?q={city_clean}&appid={ow_key}&units=metric&lang=fr"
            url_f = f"https://api.openweathermap.org/data/2.5/forecast?q={city_clean}&appid={ow_key}&units=metric&lang=fr"
            with httpx.Client(timeout=10.0) as client:
                res_w = client.get(url_w)
                if res_w.status_code == 200:
                    data_w = res_w.json()
                    res_f = client.get(url_f)
                    forecast_days = []
                    if res_f.status_code == 200:
                        data_f = res_f.json()
                        seen_dates = set()
                        for it in data_f.get("list", []):
                            dt_txt = it.get("dt_txt", "").split(" ")[0]
                            if dt_txt and dt_txt not in seen_dates:
                                seen_dates.add(dt_txt)
                                forecast_days.append({
                                    "date": dt_txt,
                                    "max_temp_c": round(it.get("main", {}).get("temp_max", 0), 1),
                                    "min_temp_c": round(it.get("main", {}).get("temp_min", 0), 1),
                                    "condition": it.get("weather", [{}])[0].get("description", "")
                                })
                    main_w = data_w.get("main", {})
                    wind_w = data_w.get("wind", {})
                    return {
                        "status": "success",
                        "city": data_w.get("name", city_clean),
                        "country": data_w.get("sys", {}).get("country", ""),
                        "temperature_c": round(main_w.get("temp", 0), 1),
                        "feels_like_c": round(main_w.get("feels_like", 0), 1),
                        "condition": data_w.get("weather", [{}])[0].get("description", ""),
                        "humidity": f"{main_w.get('humidity', 0)}%",
                        "wind_kph": f"{round(wind_w.get('speed', 0) * 3.6, 1)} km/h",
                        "forecast": forecast_days[:days] if forecast_days else [],
                        "provider": "OpenWeatherMap"
                    }
        except Exception:
            pass

    # 2. Tentative avec WeatherAPI si clé fournie
    if settings.WEATHER_API_KEY:
        try:
            url = f"https://api.weatherapi.com/v1/forecast.json?key={settings.WEATHER_API_KEY}&q={city_clean}&days={days}&lang=fr"
            with httpx.Client(timeout=10.0) as client:
                res = client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    current = data.get("current", {})
                    forecast_days = []
                    for fd in data.get("forecast", {}).get("forecastday", []):
                        forecast_days.append({
                            "date": fd.get("date"),
                            "max_temp_c": fd.get("day", {}).get("maxtemp_c"),
                            "min_temp_c": fd.get("day", {}).get("mintemp_c"),
                            "condition": fd.get("day", {}).get("condition", {}).get("text")
                        })
                    return {
                        "status": "success",
                        "city": data.get("location", {}).get("name", city_clean),
                        "country": data.get("location", {}).get("country"),
                        "temperature_c": current.get("temp_c"),
                        "feels_like_c": current.get("feelslike_c"),
                        "condition": current.get("condition", {}).get("text"),
                        "humidity": f"{current.get('humidity')}%",
                        "wind_kph": f"{current.get('wind_kph')} km/h",
                        "forecast": forecast_days,
                        "provider": "WeatherAPI"
                    }
        except Exception:
            pass

    # 2. Repli Open-Meteo (Zero-Key, API libre et gratuite sans authentification requise)
    try:
        lat, lon, resolved_city, country = None, None, city_clean, ""
        
        # Vérification si la ville est dans les coordonnées pré-définies
        key_norm = city_clean.lower()
        if key_norm in PRESET_COORDS:
            lat, lon, resolved_city, country = PRESET_COORDS[key_norm]
        else:
            # Géocodage dynamique
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_clean}&count=1&language=fr&format=json"
            with httpx.Client(timeout=12.0) as client:
                geo_res = client.get(geo_url)
                if geo_res.status_code == 200:
                    geo_data = geo_res.json()
                    if geo_data.get("results"):
                        loc = geo_data["results"][0]
                        lat, lon = loc["latitude"], loc["longitude"]
                        resolved_city = loc.get("name", city_clean)
                        country = loc.get("country", "")

        if lat is not None and lon is not None:
            weather_url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
                f"&daily=temperature_2m_max,temperature_2m_min,weather_code&timezone=auto&forecast_days={days}"
            )
            with httpx.Client(timeout=12.0) as client:
                w_res = client.get(weather_url)
                if w_res.status_code == 200:
                    w_data = w_res.json()
                    current = w_data.get("current", {})
                    daily = w_data.get("daily", {})
                    
                    forecast_days = []
                    if daily.get("time"):
                        for i, date_str in enumerate(daily.get("time", [])):
                            forecast_days.append({
                                "date": date_str,
                                "max_temp_c": daily.get("temperature_2m_max", [])[i] if i < len(daily.get("temperature_2m_max", [])) else None,
                                "min_temp_c": daily.get("temperature_2m_min", [])[i] if i < len(daily.get("temperature_2m_min", [])) else None,
                                "condition": _weather_code_to_text(daily.get("weather_code", [])[i] if i < len(daily.get("weather_code", [])) else 0)
                            })

                    return {
                        "status": "success",
                        "city": resolved_city,
                        "country": country,
                        "temperature_c": current.get("temperature_2m"),
                        "feels_like_c": current.get("temperature_2m"),
                        "condition": _weather_code_to_text(current.get("weather_code", 0)),
                        "humidity": f"{current.get('relative_humidity_2m')}%",
                        "wind_kph": f"{current.get('wind_speed_10m')} km/h",
                        "forecast": forecast_days,
                        "provider": "Open-Meteo (Zero-Key Fallback)"
                    }
    except Exception as e:
        return {"status": "error", "city": city_clean, "message": f"Erreur météo pour {city_clean} : {str(e)}"}

    return {"status": "error", "city": city_clean, "message": f"Impossible de récupérer la météo pour {city_clean}."}


def _weather_code_to_text(code: int) -> str:
    """Traduit les codes WMO en texte lisible en français."""
    codes = {
        0: "Ciel dégagé",
        1: "Principalement dégagé",
        2: "Partiellement nuageux",
        3: "Couvert",
        45: "Brouillard",
        48: "Brouillard givrant",
        51: "Bruine légère",
        53: "Bruine modérée",
        55: "Bruine dense",
        61: "Pluie légère",
        63: "Pluie modérée",
        65: "Forte pluie",
        71: "Chute de neige légère",
        73: "Neige modérée",
        75: "Forte neige",
        80: "Averses de pluie légères",
        81: "Averses de pluie modérées",
        82: "Averses violentes",
        95: "Orage",
        96: "Orage avec grêle légère",
        99: "Orage avec forte grêle"
    }
    return codes.get(code, "Temps variable")
