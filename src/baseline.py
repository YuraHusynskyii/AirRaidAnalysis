"""Baseline forecasting models for time-series evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from statsmodels.tsa.statespace.sarimax import SARIMAX

from src.evaluation import compute_regression_metrics
from src.features import build_features_from_series
from src.ingestion import load_alerts_csv
from src.preprocessing import ensure_datetime_index, resample_alert_counts


def time_series_train_test_split(
    series: pd.Series, test_size: float
) -> Tuple[pd.Series, pd.Series]:
    """Split a time series chronologically into train and test segments.

    Args:
        series: Ordered target series.
        test_size: Fraction of observations reserved for testing.

    Returns:
        Tuple[pd.Series, pd.Series]: Train and test splits.

    Raises:
        ValueError: If split parameters are invalid or series is too short.
    """
    if not 0.0 < test_size < 1.0:
        raise ValueError("test_size must be between 0 and 1.")

    if len(series) < 3:
        raise ValueError("Series is too short for train/test split.")

    split_idx = int(len(series) * (1.0 - test_size))
    if split_idx < 1 or split_idx >= len(series):
        raise ValueError("Split index falls outside valid range for series length.")

    train = series.iloc[:split_idx]
    test = series.iloc[split_idx:]
    return train, test


def load_hourly_alert_series(
    raw_path: Path | str,
    datetime_column: str,
    timezone: str,
    region_column: Optional[str] = None,
) -> pd.Series:
    """Load raw alerts and return hourly aggregated target series.

    Args:
        raw_path: Path to source CSV file.
        datetime_column: Datetime column name.
        timezone: IANA timezone for normalization.
        region_column: Optional region column for validation on load.

    Returns:
        pd.Series: Hourly alert counts indexed by datetime.

    Raises:
        RuntimeError: If loading or resampling fails.
    """
    try:
        raw_df = load_alerts_csv(
            file_path=raw_path,
            datetime_column=datetime_column,
            region_column=region_column,
        )
        indexed_df = ensure_datetime_index(
            df=raw_df,
            datetime_column=datetime_column,
            timezone=timezone,
        )
        processed_df = resample_alert_counts(indexed_df, rule="1h")
        return processed_df["alert_count"]
    except Exception as exc:
        raise RuntimeError(f"Failed to load hourly alert series from {raw_path}.") from exc


def seasonal_naive_forecast(
    history: pd.Series,
    horizon_index: pd.Index,
    season_period: int = 24,
) -> pd.Series:
    """Forecast using the value observed ``season_period`` steps earlier.

    Args:
        history: Known target values indexed in chronological order.
        horizon_index: Index of timestamps to forecast.
        season_period: Seasonal lag in number of observations.

    Returns:
        pd.Series: Forecast values aligned with ``horizon_index``.

    Raises:
        ValueError: If inputs are invalid or history is insufficient.
        RuntimeError: If forecast generation fails unexpectedly.
    """
    if season_period < 1:
        raise ValueError("season_period must be >= 1.")
    if len(history) < season_period:
        raise ValueError(
            f"History length ({len(history)}) is shorter than season_period "
            f"({season_period})."
        )

    try:
        combined_index = history.index.union(horizon_index)
        combined = history.reindex(combined_index).sort_index()
        positions = {timestamp: idx for idx, timestamp in enumerate(combined.index)}

        forecasts: list[float] = []
        for timestamp in horizon_index:
            position = positions[timestamp]
            lag_position = position - season_period
            if lag_position < 0:
                raise ValueError(
                    f"Insufficient history to forecast timestamp: {timestamp}"
                )
            forecasts.append(float(combined.iloc[lag_position]))
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError("Failed to generate seasonal naive forecast.") from exc

    return pd.Series(forecasts, index=horizon_index, name="prediction")


def evaluate_seasonal_naive(
    series: pd.Series,
    test_size: float,
    season_period: int = 24,
) -> Dict[str, float]:
    """Evaluate seasonal naive baseline on a chronological holdout split.

    Args:
        series: Target time series.
        test_size: Holdout fraction for evaluation.
        season_period: Seasonal lag used by the baseline.

    Returns:
        Dict[str, float]: Regression metrics for the baseline forecast.

    Raises:
        ValueError: If split or forecast preconditions fail.
        RuntimeError: If evaluation fails unexpectedly.
    """
    train, test = time_series_train_test_split(series, test_size=test_size)
    if len(train) < season_period:
        raise ValueError(
            f"Train split ({len(train)}) is shorter than season_period ({season_period})."
        )

    try:
        history = pd.concat([train, test])
        predictions = seasonal_naive_forecast(
            history=history,
            horizon_index=test.index,
            season_period=season_period,
        )
        metrics = compute_regression_metrics(
            y_true=test.to_numpy(dtype=float),
            y_pred=predictions.to_numpy(dtype=float),
        )
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError("Failed to evaluate seasonal naive baseline.") from exc

    return metrics


def evaluate_arima(
    series: pd.Series,
    test_size: float,
    order: tuple[int, int, int] = (1, 0, 0),
    seasonal_order: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> Dict[str, float]:
    """Evaluate ARIMA/SARIMAX baseline on a chronological holdout split.

    Args:
        series: Target time series.
        test_size: Holdout fraction for evaluation.
        order: ARIMA (p, d, q) order.
        seasonal_order: Seasonal (P, D, Q, s) order.

    Returns:
        Dict[str, float]: Regression metrics for ARIMA forecast.

    Raises:
        ValueError: If split preconditions fail.
        RuntimeError: If model fitting or forecasting fails.
    """
    train, test = time_series_train_test_split(series, test_size=test_size)
    seasonal_period = seasonal_order[3]
    minimum_train = max(sum(order), seasonal_period if seasonal_period else 0, 3)
    if len(train) < minimum_train:
        raise ValueError(
            f"Train split ({len(train)}) is too short for ARIMA order {order}."
        )

    try:
        model = SARIMAX(
            train,
            order=order,
            seasonal_order=seasonal_order,
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        fitted = model.fit(disp=False)
        predictions = fitted.forecast(steps=len(test))
        pred_array = np.asarray(predictions, dtype=float)
        metrics = compute_regression_metrics(
            y_true=test.to_numpy(dtype=float),
            y_pred=pred_array,
        )
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError("Failed to evaluate ARIMA baseline.") from exc

    return metrics


def split_feature_matrix(
    featured_df: pd.DataFrame,
    target_column: str,
    test_size: float,
) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
    """Split feature matrix chronologically into train and test sets.

    Args:
        featured_df: Feature-enriched dataframe indexed by datetime.
        target_column: Name of target column to predict.
        test_size: Holdout fraction for evaluation.

    Returns:
        Tuple containing X_train, y_train, X_test and y_test.

    Raises:
        ValueError: If target column is missing or split is invalid.
    """
    if target_column not in featured_df.columns:
        raise ValueError(f"Target column '{target_column}' is missing.")

    if len(featured_df) < 3:
        raise ValueError("Feature matrix is too short for train/test split.")

    split_idx = int(len(featured_df) * (1.0 - test_size))
    if split_idx < 1 or split_idx >= len(featured_df):
        raise ValueError("Split index falls outside valid range for feature matrix.")

    train_df = featured_df.iloc[:split_idx]
    test_df = featured_df.iloc[split_idx:]
    feature_columns = [column for column in featured_df.columns if column != target_column]

    return (
        train_df[feature_columns],
        train_df[target_column],
        test_df[feature_columns],
        test_df[target_column],
    )


def evaluate_linear_regression(
    featured_df: pd.DataFrame,
    target_column: str,
    test_size: float,
) -> Dict[str, float]:
    """Evaluate linear regression baseline on chronological holdout split.

    Args:
        featured_df: Feature-enriched dataframe.
        target_column: Target column name.
        test_size: Holdout fraction for evaluation.

    Returns:
        Dict[str, float]: Regression metrics for ML baseline.

    Raises:
        ValueError: If split preconditions fail.
        RuntimeError: If model training or evaluation fails.
    """
    try:
        x_train, y_train, x_test, y_test = split_feature_matrix(
            featured_df=featured_df,
            target_column=target_column,
            test_size=test_size,
        )
        model = LinearRegression()
        model.fit(x_train, y_train)
        predictions = model.predict(x_test)
        metrics = compute_regression_metrics(
            y_true=y_test.to_numpy(dtype=float),
            y_pred=predictions,
        )
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError("Failed to evaluate linear regression baseline.") from exc

    return metrics


def evaluate_xgboost(
    featured_df: pd.DataFrame,
    target_column: str,
    test_size: float,
    random_seed: int = 42,
    n_estimators: int = 100,
) -> Dict[str, float]:
    """Evaluate XGBoost regressor on chronological holdout split.

    Args:
        featured_df: Feature-enriched dataframe.
        target_column: Target column name.
        test_size: Holdout fraction for evaluation.
        random_seed: Random seed for reproducibility.
        n_estimators: Number of boosting rounds.

    Returns:
        Dict[str, float]: Regression metrics for XGBoost model.

    Raises:
        ValueError: If split preconditions fail.
        RuntimeError: If model training or evaluation fails.
    """
    try:
        x_train, y_train, x_test, y_test = split_feature_matrix(
            featured_df=featured_df,
            target_column=target_column,
            test_size=test_size,
        )
        import xgboost as xgb

        model = xgb.XGBRegressor(
            n_estimators=n_estimators,
            random_state=random_seed,
            objective="reg:squarederror",
        )
        model.fit(x_train, y_train)
        predictions = model.predict(x_test)
        metrics = compute_regression_metrics(
            y_true=y_test.to_numpy(dtype=float),
            y_pred=predictions,
        )
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError("Failed to evaluate XGBoost baseline.") from exc

    return metrics


def fit_xgboost_with_params(
    featured_df: pd.DataFrame,
    target_column: str,
    test_size: float,
    random_seed: int,
    params: dict[str, float | int],
) -> tuple[Any, Dict[str, float], list[str]]:
    """Train XGBoost model using explicit hyperparameters.

    Args:
        featured_df: Feature-enriched dataframe.
        target_column: Target column name.
        test_size: Holdout fraction for evaluation.
        random_seed: Random seed for reproducibility.
        params: XGBoost hyperparameters.

    Returns:
        tuple: Fitted model, holdout metrics and feature column names.

    Raises:
        RuntimeError: If model training fails.
    """
    try:
        x_train, y_train, x_test, y_test = split_feature_matrix(
            featured_df=featured_df,
            target_column=target_column,
            test_size=test_size,
        )
        import xgboost as xgb

        model = xgb.XGBRegressor(
            random_state=random_seed,
            objective="reg:squarederror",
            **params,
        )
        model.fit(x_train, y_train)
        predictions = model.predict(x_test)
        metrics = compute_regression_metrics(
            y_true=y_test.to_numpy(dtype=float),
            y_pred=predictions,
        )
        return model, metrics, list(x_train.columns)
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError("Failed to fit XGBoost model with params.") from exc


def fit_xgboost_production_model(
    featured_df: pd.DataFrame,
    target_column: str,
    test_size: float,
    random_seed: int = 42,
    n_estimators: int = 100,
) -> tuple[Any, Dict[str, float], list[str]]:
    """Train XGBoost model on train split and evaluate on holdout.

    Args:
        featured_df: Feature-enriched dataframe.
        target_column: Target column name.
        test_size: Holdout fraction for evaluation.
        random_seed: Random seed for reproducibility.
        n_estimators: Number of boosting rounds.

    Returns:
        tuple: Fitted model, holdout metrics and feature column names.

    Raises:
        ValueError: If split preconditions fail.
        RuntimeError: If model training fails.
    """
    try:
        x_train, y_train, x_test, y_test = split_feature_matrix(
            featured_df=featured_df,
            target_column=target_column,
            test_size=test_size,
        )
        import xgboost as xgb

        model = xgb.XGBRegressor(
            n_estimators=n_estimators,
            random_state=random_seed,
            objective="reg:squarederror",
        )
        model.fit(x_train, y_train)
        predictions = model.predict(x_test)
        metrics = compute_regression_metrics(
            y_true=y_test.to_numpy(dtype=float),
            y_pred=predictions,
        )
        return model, metrics, list(x_train.columns)
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError("Failed to fit production XGBoost model.") from exc


def evaluate_lightgbm(
    featured_df: pd.DataFrame,
    target_column: str,
    test_size: float,
    random_seed: int = 42,
    n_estimators: int = 100,
) -> Dict[str, float]:
    """Evaluate LightGBM regressor on chronological holdout split.

    Args:
        featured_df: Feature-enriched dataframe.
        target_column: Target column name.
        test_size: Holdout fraction for evaluation.
        random_seed: Random seed for reproducibility.
        n_estimators: Number of boosting rounds.

    Returns:
        Dict[str, float]: Regression metrics for LightGBM model.

    Raises:
        ValueError: If split preconditions fail.
        RuntimeError: If model training or evaluation fails.
    """
    try:
        x_train, y_train, x_test, y_test = split_feature_matrix(
            featured_df=featured_df,
            target_column=target_column,
            test_size=test_size,
        )
        import lightgbm as lgb

        model = lgb.LGBMRegressor(
            n_estimators=n_estimators,
            random_state=random_seed,
            verbosity=-1,
        )
        model.fit(x_train, y_train)
        predictions = model.predict(x_test)
        metrics = compute_regression_metrics(
            y_true=y_test.to_numpy(dtype=float),
            y_pred=predictions,
        )
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError("Failed to evaluate LightGBM baseline.") from exc

    return metrics


def evaluate_regional_models(
    regional_df: pd.DataFrame,
    target_column: str,
    test_size: float,
    season_period: int,
    lag_periods: list[int],
    random_seed: int,
    n_estimators: int,
) -> Dict[str, Dict[str, Dict[str, float]]]:
    """Evaluate seasonal naive and LightGBM models per region.

    Args:
        regional_df: Hourly counts with one column per region.
        target_column: Target column name used for feature building.
        test_size: Holdout fraction for evaluation.
        season_period: Seasonal lag for naive baseline.
        lag_periods: Lag steps for regional feature engineering.
        random_seed: Random seed for LightGBM.
        n_estimators: Number of trees for LightGBM.

    Returns:
        Dict[str, Dict[str, Dict[str, float]]]: Region -> model -> metrics.

    Raises:
        RuntimeError: If regional evaluation fails unexpectedly.
    """
    results: Dict[str, Dict[str, Dict[str, float]]] = {}
    try:
        for region_name in regional_df.columns:
            series = regional_df[region_name]
            if series.sum() <= 0:
                continue

            region_results: Dict[str, Dict[str, float]] = {}
            try:
                region_results["seasonal_naive"] = evaluate_seasonal_naive(
                    series=series,
                    test_size=test_size,
                    season_period=season_period,
                )
            except ValueError:
                pass

            try:
                featured = build_features_from_series(
                    series=series,
                    target_column=target_column,
                    lags=lag_periods,
                )
                if len(featured) >= 5:
                    region_results["lightgbm"] = evaluate_lightgbm(
                        featured_df=featured,
                        target_column=target_column,
                        test_size=test_size,
                        random_seed=random_seed,
                        n_estimators=n_estimators,
                    )
            except (ValueError, RuntimeError):
                pass

            if region_results:
                results[str(region_name)] = region_results
    except Exception as exc:
        raise RuntimeError("Failed to evaluate regional models.") from exc

    return results


def evaluate_all_baselines(
    processed_df: pd.DataFrame,
    featured_df: pd.DataFrame,
    regional_df: pd.DataFrame,
    target_column: str,
    test_size: float,
    season_period: int,
    arima_order: list[int],
    seasonal_order: list[int],
    sarimax_seasonal_order: list[int],
    datetime_column: str,
    timezone: str,
    region_column: Optional[str],
    extended_raw_data_path: Optional[Path],
    random_seed: int,
    lag_periods: list[int],
    boosting_n_estimators: int,
) -> Dict[str, Any]:
    """Evaluate global and regional baselines.

    Args:
        processed_df: Hourly processed dataframe.
        featured_df: Feature-enriched dataframe.
        regional_df: Hourly counts per region.
        target_column: Target column name.
        test_size: Holdout fraction for evaluation.
        season_period: Seasonal lag for naive baseline.
        arima_order: ARIMA (p, d, q) order.
        seasonal_order: Non-seasonal SARIMAX seasonal tuple.
        sarimax_seasonal_order: Seasonal SARIMAX order with ``s=24``.
        datetime_column: Datetime column for extended dataset loading.
        timezone: Timezone for extended dataset loading.
        region_column: Region column for extended dataset validation.
        extended_raw_data_path: Optional larger dataset path for SARIMAX s=24.
        random_seed: Seed for boosting models.
        lag_periods: Lag steps for regional feature engineering.
        boosting_n_estimators: Tree count for boosting models.

    Returns:
        Dict[str, Any]: Metrics with ``global`` and ``regional`` sections.

    Raises:
        RuntimeError: If any baseline evaluation fails.
    """
    try:
        order_tuple = (arima_order[0], arima_order[1], arima_order[2])
        seasonal_tuple = (
            seasonal_order[0],
            seasonal_order[1],
            seasonal_order[2],
            seasonal_order[3],
        )
        sarimax_tuple = (
            sarimax_seasonal_order[0],
            sarimax_seasonal_order[1],
            sarimax_seasonal_order[2],
            sarimax_seasonal_order[3],
        )

        sarimax_series = processed_df[target_column]
        if extended_raw_data_path is not None and Path(extended_raw_data_path).exists():
            sarimax_series = load_hourly_alert_series(
                raw_path=extended_raw_data_path,
                datetime_column=datetime_column,
                timezone=timezone,
                region_column=region_column,
            )

        return {
            "global": {
                "seasonal_naive": evaluate_seasonal_naive(
                    series=processed_df[target_column],
                    test_size=test_size,
                    season_period=season_period,
                ),
                "linear_regression": evaluate_linear_regression(
                    featured_df=featured_df,
                    target_column=target_column,
                    test_size=test_size,
                ),
                "arima": evaluate_arima(
                    series=processed_df[target_column],
                    test_size=test_size,
                    order=order_tuple,
                    seasonal_order=seasonal_tuple,
                ),
                "sarimax_s24": evaluate_arima(
                    series=sarimax_series,
                    test_size=test_size,
                    order=order_tuple,
                    seasonal_order=sarimax_tuple,
                ),
                "xgboost": evaluate_xgboost(
                    featured_df=featured_df,
                    target_column=target_column,
                    test_size=test_size,
                    random_seed=random_seed,
                    n_estimators=boosting_n_estimators,
                ),
                "lightgbm": evaluate_lightgbm(
                    featured_df=featured_df,
                    target_column=target_column,
                    test_size=test_size,
                    random_seed=random_seed,
                    n_estimators=boosting_n_estimators,
                ),
            },
            "regional": evaluate_regional_models(
                regional_df=regional_df,
                target_column=target_column,
                test_size=test_size,
                season_period=season_period,
                lag_periods=lag_periods,
                random_seed=random_seed,
                n_estimators=boosting_n_estimators,
            ),
        }
    except Exception as exc:
        raise RuntimeError("Failed to evaluate baseline models.") from exc
