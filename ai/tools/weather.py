"""OpenWeatherMap wrapper, used only by the in-trip node."""
import requests
import config


def current_weather(lat: float, lon: float) -> dict:
    default_weather = {
        "condition": "Clear",
        "description": "clear sky",
        "temp_c": 28.0,
        "is_outdoor_friendly": True,
    }
    if not getattr(config, "OPENWEATHER_KEY", None):
        return default_weather
    try:
        resp = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"lat": lat, "lon": lon, "appid": config.OPENWEATHER_KEY, "units": "metric"},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "condition": data["weather"][0]["main"],
            "description": data["weather"][0]["description"],
            "temp_c": data["main"]["temp"],
            "is_outdoor_friendly": data["weather"][0]["main"] not in {"Rain", "Thunderstorm", "Snow"},
        }
    except Exception:
        return default_weather
