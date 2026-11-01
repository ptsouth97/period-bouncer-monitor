import requests
import pandas as pd
import matplotlib.pyplot as plt
import os
from datetime import datetime, timezone, timedelta
from astropy.time import Time
import time
from datetime import datetime
from config import API_TOKEN
from visibility import get_visibility_metrics


update_time = datetime.now().strftime(
    "%Y-%m-%d %H:%M:%S"
)

headers = {
    "Authorization": f"Token {API_TOKEN}"
}

os.makedirs("dashboard/plots", exist_ok=True)

os.makedirs("cache", exist_ok=True)
USE_CACHE = True

targets_df = pd.read_csv("dummy_targets.csv")

observatories = pd.read_csv(
    "observatories.csv"
)

targets = targets_df["name"].tolist()


def get_aavso_data(target, days=100):
    """
    Download AAVSO photometry for the last 'days' days.
    Returns a pandas DataFrame.
    """

    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days)

    base_url = "https://api.aavso.org/v2/api/observations/photometry/"

    params = {
        "target": target,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat()
    }

    results = []
    url = base_url

    while url:

        response = requests.get(
            url,
            headers=headers,
            params=params if url == base_url else None
        )

        # Handle rate limits
        if response.status_code == 429:
            print("Rate limit reached. Waiting 60 seconds...")
            time.sleep(60)
            continue

        response.raise_for_status()

        data = response.json()

        results.extend(data["results"])

        print(
            f"{target}: {len(results)} / {data['count']} observations"
        )

        url = data["next"]

        # Respect AAVSO limits
        if url:
            time.sleep(10)

    df = pd.DataFrame(results)

    if len(df) == 0:
        return df

    # Clean up numeric columns
    for col in ["jd_dbl", "magnitude", "uncertainty"]:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            )

    return df


def make_lightcurve(df, target):

    if len(df) == 0:
        print(f"No data found for {target}")
        return

    df = df.copy()

    df["magnitude"] = pd.to_numeric(
        df["magnitude"],
        errors="coerce"
    )

    df["date"] = Time(
        df["jd_dbl"],
        format="jd"
    ).datetime

    plt.figure(figsize=(10, 5))

    plt.scatter(
        df["date"],
        df["magnitude"],
        s=12,
        alpha=0.7
    )

    plt.gca().invert_yaxis()

    plt.title(f"{target} - Last 100 Days")
    plt.xlabel("Date")
    plt.ylabel("Magnitude")

    plt.grid(alpha=0.3)
    plt.tight_layout()

    filename = target.replace(" ", "_")

    plt.savefig(
        f"dashboard/plots/{filename}.png",
        dpi=150
    )

    plt.close()

    print(f"Saved plots/{filename}.png")


### Main program ###

os.makedirs("plots", exist_ok=True)

all_data = {}

for target in targets:

    print(f"Downloading {target}")

    filename = target.replace(" ", "_")

    cache_file = f"cache/{filename}.csv"

    if USE_CACHE and os.path.exists(cache_file):

        print(
            f"Loading cached data for {target}"
        )

        try:

            df = pd.read_csv(cache_file)

        except pd.errors.EmptyDataError:

            print(
                f"Empty cache file for {target}"
            )

            df = pd.DataFrame()
       

    else:

        df = get_aavso_data(target)

        if len(df) > 0:

            df.to_csv(
                cache_file,
                index=False
            )

    all_data[target] = df

    filename = target.replace(" ", "_")

    df.to_csv(
        f"cache/{filename}.csv",
        index=False
    )

    make_lightcurve(df, target)


outburst_scores = {}
days_since_observation = {}
priority_scores = {}
needs_observations = []

for target in targets:

    df = all_data[target]

    if len(df) == 0:

        outburst_scores[target] = float("-inf")

        days_since_observation[target] = 999

        target_row = targets_df[
            targets_df["name"] == target
        ].iloc[0]

        tier = target_row["tier"]

        tier_weight = {
            1: 100,
            2: 50,
            3: 0
        }

        priority_scores[target] = (
            tier_weight[tier] + 999
        )

        continue


    mags = pd.to_numeric(
        df["magnitude"],
        errors="coerce"
    ).dropna()

    if len(mags) < 5:

        outburst_scores[target] = -999

        latest_jd = df["jd_dbl"].max()

        latest_obs = Time(
            latest_jd,
            format="jd"
        ).to_datetime()

        age_days = (
            datetime.utcnow()
            - latest_obs
        ).days

        days_since_observation[target] = age_days

        priority_scores[target] = age_days

        continue


    baseline = mags.median()

    recent_mag = mags.tail(
        min(5, len(mags))
    ).median()

    score = baseline - recent_mag

    outburst_scores[target] = score

    latest_jd = df["jd_dbl"].max()

    latest_obs = Time(
        latest_jd,
        format="jd"
    ).to_datetime()

    age_days = (
        datetime.utcnow()
        - latest_obs
    ).days

    days_since_observation[target] = age_days

    target_row = targets_df[
        targets_df["name"] == target
    ].iloc[0]

    tier = target_row["tier"]

    tier_weight = {
        1: 100,
        2: 50,
        3: 0
    }

    priority = (
        tier_weight[tier]
        + max(0, score) * 20
        + min(age_days, 60)
    )

    priority_scores[target] = priority

    if age_days >= 30:
        needs_observations.append(
            (target, age_days)
        )

sorted_targets = sorted(
    targets,
    key=lambda t: priority_scores.get(t, -999),
    reverse=True
)

visibility_data = {}

for target in targets:

    target_row = targets_df[
        targets_df["name"] == target
    ].iloc[0]

    best_site = None
    best_metrics = None
    best_hours = -1

    for _, site in observatories.iterrows():

        metrics = get_visibility_metrics(
            target_row["ra"],
            target_row["dec"],
            site["latitude"],
            site["longitude"],
            site["elevation_m"]
        )

        if (
            metrics["observable_hours"]
            > best_hours
        ):

            best_hours = (
                metrics["observable_hours"]
            )

            best_site = (
                site["name"]
            )

            best_metrics = metrics

    visibility_data[target] = {
        "site": best_site,
        "hours": best_metrics["observable_hours"],
        "altitude": best_metrics["max_altitude"],
        "best_time": best_metrics["best_time"]
    }


needs_observations.sort(
    key=lambda x: x[1],
    reverse=True
)

html = """
<!DOCTYPE html>
<html>
<head>
<title>Period Bouncer Monitor</title>

<style>

body {
    font-family: Arial, sans-serif;
    margin: 20px;
    background-color: #f5f5f5;
}

.grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(500px, 1fr));
    gap: 20px;
}

.card {
    background: white;
    padding: 10px;
    border-radius: 10px;
    box-shadow: 0px 2px 5px rgba(0,0,0,0.2);
}

.card img {
    width: 100%;
}

</style>

</head>

<body>

<h1>Period Bouncer Monitor</h1>

<p>
Last Updated: """ + update_time + """
</p>

<h2>Needs Observations</h2>

<ul>
"""

if len(needs_observations) == 0:

    html += """
    <p>No targets currently require additional observations.</p>
    """

else:

    for target, age_days in needs_observations:

        html += f"""
        <li>
        {target}: {age_days} days since last observation
        </li>
        """

html += """
</ul>

<div class="grid">
"""

for target in sorted_targets:

    filename = target.replace(" ", "_")

    filepath = f"dashboard/plots/{filename}.png"
    score = outburst_scores.get(target, 0)

    age_days = days_since_observation.get(
    target,
    "Unknown"
)

    site = visibility_data[target]["site"]
    hours = visibility_data[target]["hours"]
    altitude = visibility_data[target]["altitude"]
    best_time = visibility_data[target]["best_time"]
    priority = priority_scores[target]

    stats_html = f"""
    <div style="margin-bottom:15px; line-height:1.6;">
    <b>Priority Score:</b> {priority:.1f}<br>
    <b>Outburst Score:</b> {score:.2f}<br>
    <b>Days Since Observation:</b> {age_days}<br>
    <b>Best Observatory:</b> {site}<br>
    <b>Observable Hours:</b> {hours}<br>
    <b>Max Altitude:</b> {altitude:.1f} <br>
    <b>Best Time:</b> {best_time}
    </div>
    """

    if os.path.exists(filepath):

        img_html = f'''
        <img src="plots/{filename}.png"
        alt="{target} Lightcurve">
        '''

    else:

        img_html = '''
        <p>No plot available.</p>
        '''

    html += f"""
    <div class="card">
        <h2>{target}</h2>

        {stats_html}

        {img_html}

    </div>
    """

html += """
</div>
</body>
</html>
"""

with open(
    "dashboard/dashboard.html",
    "w",
    encoding="utf-8"
) as f:

    f.write(html)

print("Dashboard created.")
print("Finished")
