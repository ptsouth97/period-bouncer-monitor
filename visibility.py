import numpy as np
import astropy.units as u
import warnings

from astropy.coordinates import (
    SkyCoord,
    EarthLocation,
    AltAz,
    get_sun
)

from astropy.time import Time
from astropy.utils import iers


iers.conf.auto_download = False
iers.conf.iers_degraded_accuracy = "ignore"

warnings.filterwarnings(
    "ignore",
    message=".*polar motions.*"
)
warnings.filterwarnings(
    "ignore",
    category=iers.IERSWarning
)


def classify_visibility(observable_hours):

    if observable_hours >= 6:
        return "Excellent"

    elif observable_hours >= 3:
        return "Good"

    elif observable_hours >= 1:
        return "Marginal"

    else:
        return "Poor"


def find_best_observatory(
    target,
    observatories
):

    best_site = None
    best_metrics = None

    for _, site in observatories.iterrows():

        metrics = get_visibility_metrics(
            target["ra"],
            target["dec"],
            site["latitude"],
            site["longitude"],
            site["elevation_m"]
        )

        if (
            best_metrics is None
            or
            metrics["observable_hours"]
            >
            best_metrics["observable_hours"]
        ):
            best_site = site["name"]
            best_metrics = metrics

    return best_site, best_metrics


def get_visibility_metrics(
    ra,
    dec,
    latitude,
    longitude,
    elevation_m,
    min_target_alt=30,
    max_sun_alt=-18
):
    """
    Returns nighttime visibility metrics.

    min_target_alt : degrees
        Minimum altitude considered observable.

    max_sun_alt : degrees
        Sun altitude defining astronomical night.
    """

    location = EarthLocation(
        lat=float(latitude) * u.deg,
        lon=float(longitude) * u.deg,
        height=float(elevation_m) * u.m
    )

    target = SkyCoord(
        ra,
        dec,
        unit=(u.hourangle, u.deg)
    )

    now = Time.now()

    times = now + np.linspace(
        0,
        24,
        289
    ) * u.hour

    frame = AltAz(
        obstime=times,
        location=location
    )

    target_altitudes = (
        target
        .transform_to(frame)
        .alt
        .degree
    )

    sun_altitudes = (
        get_sun(times)
        .transform_to(frame)
        .alt
        .degree
    )

    night_mask = (
        sun_altitudes < max_sun_alt
    )

    if not np.any(night_mask):

        return {
            "observable": False,
            "max_altitude": 0,
            "observable_hours": 0
        }

    night_target_altitudes = target_altitudes[
        night_mask
    ]

    max_altitude = np.max(
        night_target_altitudes
    )

    observable_mask = (
        night_target_altitudes >= min_target_alt
    )

    time_step_hours = 24 / 288

    observable_hours = (
        observable_mask.sum()
        * time_step_hours
    )

    night_times = times[night_mask]

    max_index = np.argmax(
        night_target_altitudes
    )

    best_time = (
        night_times[max_index]
        .to_datetime()
        .strftime("%Y-%m-%d %H:%M UTC")
    )

    return {
        "observable": observable_hours > 0,
        "max_altitude": round(max_altitude, 1),
        "observable_hours": round(
            observable_hours,
            1
        ),
        "best_time": best_time
    }
