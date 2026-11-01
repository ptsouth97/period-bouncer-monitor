import pandas as pd

from visibility import get_visibility_metrics

targets = pd.read_csv(
    "dummy_targets.csv"
)

observatories = pd.read_csv(
    "observatories.csv"
)
'''CHANGE ME CHANGE ME CHANGE ME
visibility = classify_visibility(
    metrics["observable_hours"]
)

site, metrics = find_best_observatory(
    target,
    observatories
)
'''
for _, target in targets.iterrows():

    print("\n" + target["name"])

    best_site = None
    best_alt = 0
    best_hours = 0

    for _, site in observatories.iterrows():

        metrics = get_visibility_metrics(
            target["ra"],
            target["dec"],
            site["latitude"],
            site["longitude"],
            site["elevation_m"]
        )

        print(
            f"  {site['name']}: "
            f"{metrics['max_altitude']:.1f} deg, "
            f"{metrics['observable_hours']:.1f} hr, "
            f"best {metrics['best_time']}"
        )

        if (
            metrics["observable_hours"] > best_hours
        ):

            best_hours = (
                metrics["observable_hours"]
            )

            best_site = site["name"]

            best_alt = (
                metrics["max_altitude"]
            )

    print(
        f"Best: {best_site} "
        f"({best_hours:.1f} hr, "
        f"({best_alt:.1f} deg)"
    )
