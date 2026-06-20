"""Hyperparameter tuning utilities using Optuna."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import numpy as np
import optuna
import pandas as pd

from src.baseline import evaluate_arima, split_feature_matrix
from src.evaluation import compute_regression_metrics


def _split_arrays(
    featured_df: pd.DataFrame, target_column: str, test_size: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    x_train, y_train, x_test, y_test = split_feature_matrix(
        featured_df=featured_df,
        target_column=target_column,
        test_size=test_size,
    )
    return (
        x_train.to_numpy(dtype=float),
        y_train.to_numpy(dtype=float),
        x_test.to_numpy(dtype=float),
        y_test.to_numpy(dtype=float),
    )


def tune_xgboost(
    featured_df: pd.DataFrame,
    target_column: str,
    test_size: float,
    random_seed: int = 42,
    n_trials: int = 10,
) -> Dict[str, Any]:
    """Tune XGBoost hyperparameters on chronological holdout split.

    Args:
        featured_df: Feature-enriched dataframe.
        target_column: Target column name.
        test_size: Holdout fraction for evaluation.
        random_seed: Random seed for reproducibility.
        n_trials: Number of Optuna trials.

    Returns:
        Dict[str, Any]: Best params, validation MAE and trial count.

    Raises:
        RuntimeError: If tuning fails unexpectedly.
    """
    try:
        import xgboost as xgb

        x_train, y_train, x_test, y_test = _split_arrays(
            featured_df=featured_df,
            target_column=target_column,
            test_size=test_size,
        )

        def objective(trial: optuna.Trial) -> float:
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 20, 200),
                "max_depth": trial.suggest_int("max_depth", 2, 8),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            }
            model = xgb.XGBRegressor(
                random_state=random_seed,
                objective="reg:squarederror",
                **params,
            )
            model.fit(x_train, y_train)
            predictions = model.predict(x_test)
            metrics = compute_regression_metrics(y_test, predictions)
            return metrics["mae"]

        study = optuna.create_study(direction="minimize")
        study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

        return {
            "best_params": study.best_params,
            "best_mae": float(study.best_value),
            "n_trials": n_trials,
        }
    except Exception as exc:
        raise RuntimeError("Failed to tune XGBoost hyperparameters.") from exc


def tune_sarimax(
    series: pd.Series,
    test_size: float,
    season_period: int = 24,
    n_trials: int = 8,
) -> Dict[str, Any]:
    """Tune SARIMAX orders on chronological holdout split.

    Args:
        series: Target time series.
        test_size: Holdout fraction for evaluation.
        season_period: Seasonal period ``s`` for SARIMAX.
        n_trials: Number of Optuna trials.

    Returns:
        Dict[str, Any]: Best orders, validation MAE and trial count.

    Raises:
        RuntimeError: If tuning fails unexpectedly.
    """
    try:
        if len(series) < max(season_period + 5, 10):
            return {
                "skipped": True,
                "reason": "Series too short for SARIMAX tuning.",
                "n_trials": 0,
            }

        def objective(trial: optuna.Trial) -> float:
            order = (
                trial.suggest_int("p", 0, 2),
                trial.suggest_int("d", 0, 1),
                trial.suggest_int("q", 0, 2),
            )
            seasonal_order = (
                trial.suggest_int("sp", 0, 1),
                0,
                trial.suggest_int("sq", 0, 1),
                season_period,
            )
            try:
                metrics = evaluate_arima(
                    series=series,
                    test_size=test_size,
                    order=order,
                    seasonal_order=seasonal_order,
                )
            except ValueError:
                return float("inf")
            return metrics["mae"]

        study = optuna.create_study(direction="minimize")
        study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

        best = study.best_params
        best_order = [best["p"], best["d"], best["q"]]
        best_seasonal = [best["sp"], 0, best["sq"], season_period]
        return {
            "skipped": False,
            "best_order": best_order,
            "best_seasonal_order": best_seasonal,
            "best_mae": float(study.best_value),
            "n_trials": n_trials,
        }
    except Exception as exc:
        raise RuntimeError("Failed to tune SARIMAX hyperparameters.") from exc


def run_tuning(
    featured_df: pd.DataFrame,
    processed_series: pd.Series,
    target_column: str,
    test_size: float,
    random_seed: int,
    season_period: int,
    n_trials: int,
) -> Dict[str, Any]:
    """Run XGBoost and SARIMAX tuning workflows.

    Args:
        featured_df: Feature-enriched dataframe.
        processed_series: Hourly target series for SARIMAX tuning.
        target_column: Target column name.
        test_size: Holdout fraction.
        random_seed: Seed for XGBoost tuning.
        season_period: Seasonal period for SARIMAX.
        n_trials: Number of trials per model.

    Returns:
        Dict[str, Any]: Nested tuning results.

    Raises:
        RuntimeError: If tuning workflow fails.
    """
    try:
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        return {
            "xgboost": tune_xgboost(
                featured_df=featured_df,
                target_column=target_column,
                test_size=test_size,
                random_seed=random_seed,
                n_trials=n_trials,
            ),
            "sarimax": tune_sarimax(
                series=processed_series,
                test_size=test_size,
                season_period=season_period,
                n_trials=max(4, n_trials // 2),
            ),
        }
    except Exception as exc:
        raise RuntimeError("Hyperparameter tuning workflow failed.") from exc


def save_tuning_report(results: Dict[str, Any], output_path: Path | str) -> Path:
    """Persist tuning results to JSON.

    Args:
        results: Tuning output dictionary.
        output_path: Destination JSON path.

    Returns:
        Path: Written report path.

    Raises:
        RuntimeError: If serialization fails.
    """
    destination = Path(output_path)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8") as handle:
            json.dump(results, handle, indent=2)
    except Exception as exc:
        raise RuntimeError(f"Failed to save tuning report: {destination}") from exc
    return destination


def register_tuned_xgboost_model(
    featured_df: pd.DataFrame,
    target_column: str,
    test_size: float,
    random_seed: int,
    tuning_results: Dict[str, Any],
    model_name: str,
    registry_dir: Path | str,
) -> Path:
    """Train and register XGBoost model using Optuna best params.

    Args:
        featured_df: Feature-enriched dataframe.
        target_column: Target column name.
        test_size: Holdout fraction for evaluation.
        random_seed: Random seed for reproducibility.
        tuning_results: Output of ``run_tuning()``.
        model_name: Registry model name.
        registry_dir: Registry root directory.

    Returns:
        Path: Saved artifact directory.

    Raises:
        RuntimeError: If tuned model registration fails.
    """
    from src.baseline import fit_xgboost_with_params
    from src.registry import save_model_artifact

    try:
        best_params = tuning_results["xgboost"]["best_params"]
        model, metrics, feature_columns = fit_xgboost_with_params(
            featured_df=featured_df,
            target_column=target_column,
            test_size=test_size,
            random_seed=random_seed,
            params=best_params,
        )
        return save_model_artifact(
            model=model,
            model_name=model_name,
            registry_dir=registry_dir,
            metrics=metrics,
            feature_columns=feature_columns,
            metadata={
                "tuned": True,
                "best_params": best_params,
                "tuning_mae": tuning_results["xgboost"]["best_mae"],
            },
        )
    except Exception as exc:
        raise RuntimeError("Failed to register tuned XGBoost model.") from exc
