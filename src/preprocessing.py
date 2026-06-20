"""Preprocessing helpers for air-raid time-series data."""

from __future__ import annotations

import pandas as pd

from src.schemas import validate_timezone


def ensure_datetime_index(
    df: pd.DataFrame, datetime_column: str, timezone: str
) -> pd.DataFrame:
    """Return a copy of DataFrame indexed by localized datetime.

    Args:
        df: Input dataframe with datetime column.
        datetime_column: Name of datetime column.
        timezone: IANA timezone name.

    Returns:
        pd.DataFrame: DataFrame sorted by datetime index.

    Raises:
        ValueError: If datetime column is missing.
        RuntimeError: If timezone conversion or indexing fails.
    """
    if datetime_column not in df.columns:
        raise ValueError(f"Column '{datetime_column}' was not found in DataFrame.")

    local_df = df.copy()
    try:
        local_df[datetime_column] = pd.to_datetime(
            local_df[datetime_column], errors="raise"
        )
        if local_df[datetime_column].dt.tz is None:
            local_df[datetime_column] = local_df[datetime_column].dt.tz_localize(
                timezone
            )
        else:
            local_df[datetime_column] = local_df[datetime_column].dt.tz_convert(
                timezone
            )
        local_df = local_df.set_index(datetime_column).sort_index()
        validate_timezone(local_df.index, expected_timezone=timezone)
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError("Failed to prepare datetime index.") from exc

    return local_df


def resample_alert_counts(df: pd.DataFrame, rule: str = "1h") -> pd.DataFrame:
    """Resample time-series to fixed intervals with count aggregation.

    Args:
        df: DataFrame with DatetimeIndex.
        rule: Pandas resample rule, e.g. '1h' or '1D'.

    Returns:
        pd.DataFrame: Resampled dataframe with 'alert_count'.

    Raises:
        RuntimeError: If resampling fails.
    """
    try:
        counts = df.resample(rule).size().rename("alert_count")
        return counts.to_frame()
    except Exception as exc:
        raise RuntimeError(f"Failed to resample series with rule '{rule}'.") from exc


def resample_regional_alert_counts(
    df: pd.DataFrame, region_column: str, rule: str = "1h"
) -> pd.DataFrame:
    """Resample alert counts per region to fixed hourly intervals.

    Args:
        df: DataFrame with DatetimeIndex and region column.
        region_column: Column containing region labels.
        rule: Pandas resample rule, e.g. '1h'.

    Returns:
        pd.DataFrame: Hourly counts with one column per region.

    Raises:
        ValueError: If region column is missing.
        RuntimeError: If regional resampling fails.
    """
    if region_column not in df.columns:
        raise ValueError(f"Column '{region_column}' was not found in DataFrame.")

    try:
        counts = (
            df.groupby(region_column)
            .resample(rule)
            .size()
            .unstack(level=0, fill_value=0)
            .sort_index()
        )
        return counts.astype(float)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to resample regional series with rule '{rule}'."
        ) from exc
