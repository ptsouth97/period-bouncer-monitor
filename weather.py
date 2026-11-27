import requests


def get_weather_forecast(
    latitude,
    longitude
):

    url = (
        "https://api.open-meteo.com/v1/forecast"
    )

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "cloud_cover",
        "forecast_days": 1
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        cloud_cover = (
            data["hourly"]
            ["cloud_cover"]
        )

        avg_cloud = (
            sum(cloud_cover)
            / len(cloud_cover)
        )

        return round(
            avg_cloud,
            1
        )

    except Exception as e:

        print(
            f"Weather lookup failed: {e}"
        )

        return 100.0


def cloud_quality(
    cloud_cover
):

    if cloud_cover < 20:
        return "Excellent"

    elif cloud_cover < 40:
        return "Good"

    elif cloud_cover < 60:
        return "Fair"

    elif cloud_cover < 80:
        return "Poor"

    else:
        return "Very Poor"
