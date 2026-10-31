import requests
import pandas as pd
import matplotlib.pyplot as plt
import os
from datetime import datetime, timezone, timedelta
from astropy.time import Time
import time
import base64
from datetime import datetime
from config import API_TOKEN


update_time = datetime.now().strftime(
    "%Y-%m-%d %H:%M:%S"
)

headers = {
    "Authorization": f"Token {API_TOKEN}"
}

os.makedirs("dashboard", exist_ok=True)

targets_df = pd.read_csv("dummy_targets.csv")

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
        f"plots/{filename}.png",
        dpi=150
    )

    plt.close()

    print(f"Saved plots/{filename}.png")


### Main program ###

os.makedirs("plots", exist_ok=True)

for target in targets:

    print(f"Downloading {target}")

    df = get_aavso_data(target)

    make_lightcurve(df, target)


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

<div class="grid">
"""

for target in targets:

    filename = target.replace(" ", "_")

    filepath = f"plots/{filename}.png"

    if os.path.exists(filepath):

        with open(filepath, "rb") as f:
            encoded = base64.b64encode(
                f.read()
            ).decode("utf-8")

        img_html = f'''
        <img src="data:image/png;base64,{encoded}">
        '''

    else:

        img_html = '''
        <p>No plot available.</p>
        '''

    html += f"""
    <div class="card">
        <h2>{target}</h2>
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
