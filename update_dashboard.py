import requests
import markdown
import pandas as pd
import matplotlib.pyplot as plt
import os
from datetime import datetime, timezone, timedelta
from astropy.time import Time
import time
from datetime import datetime
from config import (
    API_TOKEN,
    EMAIL_SENDER,
    EMAIL_PASSWORD,
    EMAIL_RECIPIENT
)
from visibility import get_visibility_metrics
import smtplib

from email.message import EmailMessage

headers = {
    "Authorization": f"Token {API_TOKEN}"
}

os.makedirs("dashboard/plots", exist_ok=True)

os.makedirs(
    "dashboard/targets",
    exist_ok=True
)

os.makedirs("cache", exist_ok=True)

targets_df = pd.read_csv("targets.csv")

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


def update_cached_data(
    target,
    cache_file
):

    print(
        f"Using cache file: {cache_file}"
    )

    if not os.path.exists(cache_file):

        print(
            f"No cache for {target}, "
            f"performing full download"
        )

        df = get_aavso_data(target)

        if len(df) > 0:

            df.to_csv(
                cache_file,
                index=False
            )

        else:

            pd.DataFrame(
                columns=[
                    "jd_dbl",
                    "magnitude"
                ]
            ).to_csv(
                cache_file,
                index=False
            )

        return df

    try:

        cached_df = pd.read_csv(
            cache_file
        )

    except pd.errors.EmptyDataError:

        print(
            f"Empty cache file for {target}, "
            f"rebuilding cache"
        )

    os.remove(cache_file)

    df = get_aavso_data(target)

    if len(df) > 0:

        df.to_csv(
            cache_file,
            index=False
        )

    return df


    if len(cached_df) == 0:

        return cached_df

    latest_jd = (
        cached_df["jd_dbl"]
        .max()
    )

    print(
        f"Latest cached JD: {latest_jd}"
    )

    latest_date = Time(
        latest_jd,
        format="jd"
    ).datetime.date()

    end_date = (
        datetime.now(
            timezone.utc
        ).date()
    )

    if latest_date >= end_date:

        print(
            f"{target}: cache up to date"
        )

        return cached_df    

    if latest_date >= end_date:

        print(
            f"{target}: cache up to date"
        )

        return cached_df

    print(
        f"{target}: checking for updates"
    )

    new_df = get_aavso_data(
        target,
        days=30
    )

    if len(new_df) == 0:

        return cached_df

    combined_df = pd.concat(
        [
            cached_df,
            new_df
        ],
        ignore_index=True
    )

    combined_df = (
        combined_df
        .drop_duplicates(
            subset=["jd_dbl"]
        )
        .sort_values(
            "jd_dbl"
        )
    )

    combined_df.to_csv(
        cache_file,
        index=False
    )

    return combined_df


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


def send_summary_email(
    subject,
    body
):

    msg = EmailMessage()

    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECIPIENT

    msg.set_content(body)

    with smtplib.SMTP_SSL(
        "smtp.gmail.com",
        465
    ) as server:

        server.login(
            EMAIL_SENDER,
            EMAIL_PASSWORD
        )

        server.send_message(msg)


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

        avg_cloud = sum(
            cloud_cover
        ) / len(cloud_cover)

        return round(avg_cloud, 1)

    except Exception as e:

        print(
            f"Weather lookup failed:"
            f" {e}"
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


def create_target_page(
    target
):

    filename = (
        target
        .replace(" ", "_")
    )

    synopsis_file = (
        f"synopses/{filename}.md"
    )

    output_file = (
        f"dashboard/targets/{filename}.html"
    )

    if os.path.exists(
        synopsis_file
    ):

        with open(
            synopsis_file,
            "r",
            encoding="utf-8"
        ) as f:

            md_text = (
                f.read()
            )

        body_html = (
            markdown.markdown(
                md_text,
                extensions=[
                    "tables"
                ]
            )
        )

    else:

        body_html = """
        <p>
        Synopsis not yet available.
        </p>
        """

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            f"""
            <html>

            <head>

            <title>
            {target}
            </title>

            <style>

            body {{
                font-family: Arial, sans-serif;
                margin: 40px;
                max-width: 900px;
            }}

            table {{
                border-collapse: collapse;
            }}

            td, th {{
                border: 1px solid #ccc;
                padding: 8px;
            }}

            </style>

            </head>

            <body>

            <p>
            <a href="../dashboard.html">
            &larr; Back to Dashboard
            </a>
            </p>

            {body_html}

            </body>

            </html>
            """
        )


### Main program ###

weather_data = {}

for _, site in observatories.iterrows():

    cloud_cover = get_weather_forecast(
        site["latitude"],
        site["longitude"]
    )

    weather_data[
        site["name"]
    ] = cloud_cover

    print(
        f"{site['name']}: "
        f"{cloud_cover}% clouds"
    )

os.makedirs("plots", exist_ok=True)

all_data = {}

for target in targets:

    print(f"Downloading {target}")

    filename = (
        target
        .replace(" ", "_")
    )

    cache_file = (
        f"cache/{filename}.csv"
    )

    df = update_cached_data(
        target,
        cache_file
    )

    all_data[target] = df

    make_lightcurve(df, target)

    create_target_page(
        target
    )


outburst_scores = {}
days_since_observation = {}
priority_scores = {}
needs_observations = []

for target in targets:

    df = all_data[target]

    if len(df) == 0:

        outburst_scores[target] = None

        days_since_observation[target] = None

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
            tier_weight[tier] + 100
        )

        needs_observations.append(
            (
                target,
                float("inf")
            )
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
    
    tier_thresholds = {
        1: 4,
        2: 7,
        3: 14
    }

    threshold = tier_thresholds[tier]

    if age_days >= threshold:
        needs_observations.append(
            (
                target,
                age_days
            )
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

    site_rankings = []

    for _, site in observatories.iterrows():

        metrics = get_visibility_metrics(
            target_row["ra"],
            target_row["dec"],
            site["latitude"],
            site["longitude"],
            site["elevation_m"]
        )

        cloud_cover = weather_data[
            site["name"]
        ]

        weather_adjusted_score = (
            metrics["observable_hours"]
            + metrics["max_altitude"] / 20
            - cloud_cover / 20
        )

        site_rankings.append(
            {
                "site": site["name"],
                "hours": metrics["observable_hours"],
                "altitude": metrics["max_altitude"],
                "best_time": metrics["best_time"],
                "cloud_cover": cloud_cover,
                "quality": cloud_quality(
                    cloud_cover
                ),
                "score": weather_adjusted_score
            }
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

            site_rankings.sort(
                key=lambda x: x["score"],
                reverse=True
            )


    visibility_data[target] = {
        "site": best_site,
        "hours": best_metrics["observable_hours"],
        "altitude": best_metrics["max_altitude"],
        "best_time": best_metrics["best_time"],
        "rankings": site_rankings
    }

print()

print(target)

for site in site_rankings[:3]:

    print(
        site["site"],
        site["cloud_cover"],
        site["hours"]
    )

needs_observations.sort(
    key=lambda x: x[1],
    reverse=True
)

tonight_priority_scores = {}

for target in targets:

    hours = visibility_data[target]["hours"]

    if hours < 1:

        tonight_priority = 0

    else:

        tonight_priority = (
            priority_scores[target]
            + hours * 5
        )

    tonight_priority_scores[target] = tonight_priority

sorted_tonight_targets = sorted(
    targets,
    key=lambda t: tonight_priority_scores[t],
    reverse=True
)

update_time = datetime.now().strftime(
    "%Y-%m-%d %H:%M:%S"
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

.summary-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 30px;
    margin-bottom: 30px;
}

.summary-box {
    background: white;
    padding: 15px;
    border-radius: 10px;
    box-shadow: 0px 2px 5px rgba(0,0,0,0.2);
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
"""
html += """
<div class="summary-grid">

<div class="summary-box">

<h2>Tonight's Highest Priority Targets</h2>

<ul>
"""

for target in sorted_tonight_targets[:5]:

    top_sites = (
        visibility_data[target]
        ["rankings"][:3]
    )

    best_hours = top_sites[0]["hours"]

    if best_hours < 1:

        if info == float("inf"):

            html += f"""
            <li>
            <b>{target}</b><br>
            No observations in last 100 days<br>
            Visibility: Not Observable Tonight
            </li>
            """
        else:

            html += f"""
            <li>
            <b>{target}</b><br>
            {info} days since last observation<br>
            Visibility: Not Observable Tonight
            </li>
            """

        continue

    recommendations = ""

    for site_info in top_sites:

        recommendations += (
            f"{site_info['site']} "
            f"({site_info['hours']:.1f} hr, "
            f"{site_info['quality']}, "
            f"{site_info['cloud_cover']:.1f}% clouds)"
            "<br>"
        )

    if best_hours < 1:

        html += f"""
        <li>
        <b>{target}</b><br>
        Priority: {tonight_priority_scores[target]:.1f}<br>
        Recommended Observatories:<br>
        {recommendations}
        </li>
        """

    else:
        
        html += f"""
        <li>
        <b>{target}</b><br>
        Priority: {tonight_priority_scores[target]:.1f}<br>
        Recommended Observatories:<br>
        {recommendations}
        </li>
        """

html += """
</ul>

</div>

<div class="summary-box">

<h2>Needs Observations</h2>

<ul>
"""

if len(needs_observations) == 0:

    html += """
    <p>No targets currently require additional observations.</p>
    """

else:

    for target, info in needs_observations:

        top_sites = (
            visibility_data[target]
            ["rankings"][:3]
        )

        best_hours = top_sites[0]["hours"]

        if best_hours < 1:

            if info == float("inf"):

                html += f"""
                <li>
                <b>{target}</b><br>
                No observations in last 100 days<br>
                Visibility: Not Observable Tonight
                </li>
                """

            else:

                html += f"""
                <li>
                <b>{target}</b><br>
                {info} days since last observation<br>
                Visibility: Not Observable Tonight
                </li>
                """

            continue

        recommendations = ""

        for site_info in top_sites:

            recommendations += (
                f"{site_info['site']} "
                f"({site_info['hours']:.1f} hr, "
                f"{site_info['quality']}, "
                f"{site_info['cloud_cover']:.1f}% clouds)"
                "<br>"
            )

        if info == float("inf"):

            html += f"""
            <li>
            <b>{target}</b><br>
            No observations in last 100 days<br>
            Recommended Observatories:<br>
            {recommendations}
            </li>
            """

        else:

            html += f"""
            <li>
            <b>{target}</b><br>
            {info} days since last observation<br>
            Recommended Observatories:<br>
            {recommendations}
            </li>
            """

html += """
</ul>

</div>

</div>
"""
html += """
<div class="grid">
"""

for target in sorted_targets:

    filename = target.replace(" ", "_")

    filepath = f"dashboard/plots/{filename}.png"

    score = outburst_scores.get(target)
    
    priority = priority_scores[target]

    age_days = days_since_observation.get(
        target,
        "Unknown"
    )

    site = visibility_data[target]["site"]
    hours = visibility_data[target]["hours"]
    altitude = visibility_data[target]["altitude"]
    best_time = visibility_data[target]["best_time"]
    observable_tonight = hours >= 1
    top_sites = (
        visibility_data[target]
        ["rankings"][:3]
    )

    recommendations_html = ""

    for rank, site_info in enumerate(
        top_sites,
        start=1
    ):

        recommendations_html += f"""
        {rank}. {site_info['site']}<br>
        &nbsp;&nbsp;&nbsp;
        {site_info['hours']:.1f} hr,
        {site_info['quality']}
        {site_info['cloud_cover']:.1f}% clouds
        <br>
        """    

    if not observable_tonight:

        visibility_html = (
            "<b>Visibility:</b> "
            "Not Observable Tonight"
        )

    else:

        visibility_html = f"""
        <b>Recommended Observatories:</b><br>
        {recommendations_html}
        <b>Max Altitude:</b> {altitude:.1f}<br>
        <b>Best Time:</b> {best_time}
        """

    if score is None:

        stats_html = f"""
        <div style="margin-bottom:15px; line-height:1.6;">
        <b>Priority Score:</b> {priority:.1f}<br>
        <b>Status:</b> No AAVSO observations during the last 100 days.<br>

        {visibility_html}

        </div>
        """

    else: 

        stats_html = f"""
        <div style="margin-bottom:15px; line-height:1.6;">
        <b>Priority Score:</b> {priority:.1f}<br>
        <b>Outburst Score:</b> {score:.2f}<br>
        <b>Days Since Observation:</b> {age_days}<br>

        {visibility_html}

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
        <h2>
        <a href="targets/{filename}.html">
        {target}
        </a>
        </h2>

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

email_body = ""

email_body += (
    "Period Bouncer Monitor\n\n"
)

email_body += (
    "Tonight's Highest Priority Targets\n"
)

email_body += (
    "----------------------------\n"
)

for target in sorted_tonight_targets[:5]:

    score = (
        tonight_priority_scores[target]
    )

    top_sites = (
        visibility_data[target]
        ["rankings"][:3]
    )

    best_hours = top_sites[0]["hours"]

    if best_hours < 1:

        email_body += (
            f"{target}\n"
            f"  Priority: {score:.1f}\n"
            "  Visibility: Not Observable Tonight\n\n"
        )

        continue
 
    email_body += (
        f"{target}\n"
        f"  Priority: {score:.1f}\n"
        f"  Recommended Observatories:\n"
    )

    for site_info in top_sites:

        email_body += (
            f"    - "
            f"{site_info['site']} "
            f"({site_info['hours']:.1f} hr, "
            f"{site_info['quality']}, "
            f"{site_info['cloud_cover']:.1f}% clouds)\n"
        )

    email_body += "\n"

email_body += (
    "\nNeeds Observations\n"
)

email_body += (
    "------------------\n"
)

for target, info in needs_observations:

    top_sites = (
        visibility_data[target]
        ["rankings"][:3]
    )

    best_hours = top_sites[0]["hours"]

    if best_hours < 1:

        if info == float("inf"):

            email_body += (
                f"\n{target}\n"
                "No observations in last 100 days\n"
                "Visibility: Not Observable Tonight\n\n"
            )

        else:

            email_body += (
                f"\n{target}\n"
                f"{info} days since last observation\n"
                "Visibility: Not Observable Tonight\n\n"
            )

        continue

    if info == float("inf"):

        email_body += (
            f"\n{target}\n"
            "No observations in last 100 days\n"
            "Recommended Observatories:\n"
        )

    else:

        email_body += (
            f"\n{target}\n"
            f"{info} days since last observation\n"
            "Recommended Observatories:\n"
        )

    for site_info in top_sites:

        email_body += (
            f"  - "
            f"{site_info['site']} "
            f"({site_info['hours']:.1f} hr, "
            f"{site_info['quality']}, "
            f"{site_info['cloud_cover']:.1f}% clouds)\n"
        )

    email_body += "\n"

try:

    send_summary_email(
        subject="Period Bouncer Monitor - Daily Summary",
        body=email_body
    )

except Exception as e:

    print(
        f"Email failed: {e}"
    )

print("Finished")
