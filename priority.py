from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pandas as pd

from astropy.time import Time


@dataclass
class TargetState:

    outburst_score: Optional[float]

    priority_score: float

    tonight_priority: float

    days_since_observation: Optional[int]

    needs_observation: bool

    no_recent_data: bool


def observation_threshold(
    tier
):

    return {
        1: 4,
        2: 7,
        3: 14
    }[tier]


def calculate_age_days(
    latest_jd
):

    latest_obs = Time(
        latest_jd,
        format="jd"
    ).to_datetime()

    return (
        datetime.utcnow()
        - latest_obs
    ).days


def calculate_outburst_score(
    df
):

    mags = pd.to_numeric(
        df["magnitude"],
        errors="coerce"
    ).dropna()

    if len(mags) < 5:
        return None

    baseline = mags.median()

    recent_mag = mags.tail(
        min(5, len(mags))
    ).median()

    return (
        baseline
        - recent_mag
    )


def calculate_priority_score(
    tier,
    age_days,
    outburst_score
):

    tier_weight = {
        1: 100,
        2: 50,
        3: 0
    }

    return (
        tier_weight[tier]
        + max(
            0,
            outburst_score or 0
        ) * 20
        + min(age_days, 60)
    )


def calculate_tonight_priority(
    priority_score,
    observable_hours
):

    if observable_hours < 1:
        return 0

    return (
        priority_score
        + observable_hours * 5
    )


def evaluate_target(
    df,
    tier,
    observable_hours
):

    if len(df) == 0:

        priority_score = 200

        return TargetState(
            outburst_score=None,
            priority_score=priority_score,
            tonight_priority=calculate_tonight_priority(
                priority_score,
                observable_hours
            ),
            days_since_observation=None,
            needs_observation=True,
            no_recent_data=True
        )

    latest_jd = df["jd_dbl"].max()

    age_days = calculate_age_days(
        latest_jd
    )

    outburst_score = (
        calculate_outburst_score(
            df
        )
    )

    if outburst_score is None:
        outburst_score = -999

    priority_score = (
        calculate_priority_score(
            tier,
            age_days,
            outburst_score
        )
    )

    return TargetState(
        outburst_score=outburst_score,
        priority_score=priority_score,
        tonight_priority=(
            calculate_tonight_priority(
                priority_score,
                observable_hours
            )
        ),
        days_since_observation=age_days,
        needs_observation=(
            age_days >=
            observation_threshold(
                tier
            )
        ),
        no_recent_data=False
    )
