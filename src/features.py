"""Feature engineering functions for forecasting tasks."""

from __future__ import annotations

import pandas as pd


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add basic calendar features based on DatetimeIndex.

    Args:
        df: DataFrame indexed by datetime.

    Returns:
        pd.DataFrame: DataFrame with calendar features.

    Raises:
        RuntimeError: If feature creation fails.
    """
    output = df.copy()
    try:
        output["hour"] = output.index.hour
        output["day_of_week"] = output.index.dayofweek
        output["is_weekend"] = output["day_of_week"].isin([5, 6]).astype(int)
    except Exception as exc:
        raise RuntimeError("Failed to add time-based features.") from exc
    return output


def add_lag_features(
    df: pd.DataFrame, target_column: str, lags: list[int] | None = None
) -> pd.DataFrame:
    """Add lag features for the target signal.

    Args:
        df: Input dataframe.
        target_column: Name of target column.
        lags: List of lag values in timesteps.

    Returns:
        pd.DataFrame: Dataframe enriched with lag columns.

    Raises:
        ValueError: If target column is missing.
        RuntimeError: If lag creation fails.
    """
    if target_column not in df.columns:
        raise ValueError(f"Target column '{target_column}' is missing.")

    safe_lags = lags or [1, 24]
    output = df.copy()
    try:
        for lag in safe_lags:
            output[f"{target_column}_lag_{lag}"] = output[target_column].shift(lag)
    except Exception as exc:
        raise RuntimeError("Failed to add lag features.") from exc
    return output


def build_features(
    df: pd.DataFrame,
    target_column: str,
    lags: list[int] | None = None,
    drop_na: bool = True,
) -> pd.DataFrame:
    """Build calendar and lag features for forecasting.

    Args:
        df: Hourly dataframe indexed by datetime.
        target_column: Target signal column name.
        lags: Optional lag steps; defaults to ``[1, 24]``.
        drop_na: Whether to drop rows with missing lag values.

    Returns:
        pd.DataFrame: Feature-enriched dataframe.

    Raises:
        ValueError: If target column is missing.
        RuntimeError: If feature pipeline fails unexpectedly.
    """
    if target_column not in df.columns:
        raise ValueError(f"Target column '{target_column}' is missing.")

    try:
        featured = add_time_features(df)
        featured = add_lag_features(
            featured,
            target_column=target_column,
            lags=lags,
        )
        if drop_na:
            featured = featured.dropna()
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError("Failed to build feature matrix.") from exc

    return featured


def build_features_from_series(
    series: pd.Series,
    target_column: str = "alert_count",
    lags: list[int] | None = None,
    drop_na: bool = True,
) -> pd.DataFrame:
    """Build features for a univariate series indexed by datetime.

    Args:
        series: Hourly target series.
        target_column: Name assigned to the target column.
        lags: Optional lag steps.
        drop_na: Whether to drop rows with missing lag values.

    Returns:
        pd.DataFrame: Feature-enriched dataframe.
    """
    frame = series.rename(target_column).to_frame()
    return build_features(
        df=frame,
        target_column=target_column,
        lags=lags,
        drop_na=drop_na,
    )

