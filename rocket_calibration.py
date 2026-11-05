"""Apogee calibration for one rocket configuration and motor designation."""

import argparse
import csv
from dataclasses import dataclass
from datetime import date
import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import t


CONTEXT = ("configuration", "motor")
NUMERIC = (
    "launch_mass_g", "ballast_g", "wind_speed_m_s", "temperature_c",
    "station_pressure_hpa", "simulated_apogee_ft",
)
RULES_URL = "https://www.rocketrychallenge.org/wp-content/uploads/2027-American-Rocketry-Challenge-Rules-.pdf"


def flight_score(apogee_ft, duration_s, target_ft=800.0):
    """Altitude plus duration penalty, for an otherwise valid flight only."""
    return abs(apogee_ft - target_ft) + 4 * max(37 - duration_s, 0, duration_s - 40)


def read_records(path, *, flights):
    """Read explicit units; reject incomplete rows instead of silently dropping them."""
    identifier = "flight_id" if flights else "candidate_id"
    required = {identifier, *CONTEXT, *NUMERIC}
    if flights:
        required.update(("launch_date", "measured_apogee_ft"))
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing columns: {', '.join(sorted(missing))}")
        records, seen = [], set()
        for line, source in enumerate(reader, 2):
            prefix = f"{path}:{line}"
            if None in source:
                raise ValueError(f"{prefix}: too many CSV fields")
            row = {key: (value or "").strip() for key, value in source.items()}
            for key in required:
                if not row[key]:
                    raise ValueError(f"{prefix}: missing {key}")
            if row[identifier] in seen:
                raise ValueError(f"{prefix}: duplicate {identifier}")
            seen.add(row[identifier])
            fields = [*NUMERIC]
            if flights:
                fields.append("measured_apogee_ft")
                try:
                    if date.fromisoformat(row["launch_date"]).isoformat() != row["launch_date"]:
                        raise ValueError("date is not in canonical ISO format")
                except ValueError as error:
                    raise ValueError(f"{prefix}: launch_date must be YYYY-MM-DD") from error
                if row.get("duration_s"):
                    fields.append("duration_s")
            for key in fields:
                try:
                    row[key] = float(row[key])
                except ValueError as error:
                    raise ValueError(f"{prefix}: {key} must be numeric") from error
                if not math.isfinite(row[key]):
                    raise ValueError(f"{prefix}: {key} must be finite")
            if row["launch_mass_g"] <= 0 or not 0 <= row["ballast_g"] < row["launch_mass_g"]:
                raise ValueError(f"{prefix}: require 0 <= ballast_g < launch_mass_g")
            if row["station_pressure_hpa"] <= 0 or row["temperature_c"] <= -273.15:
                raise ValueError(f"{prefix}: invalid pressure or temperature")
            nonnegative = ["wind_speed_m_s", "simulated_apogee_ft"]
            if flights:
                nonnegative.append("measured_apogee_ft")
                if "duration_s" in fields:
                    nonnegative.append("duration_s")
            if any(row[key] < 0 for key in nonnegative):
                raise ValueError(f"{prefix}: speed, altitude, and duration cannot be negative")
            records.append(row)
    if not records:
        raise ValueError(f"{path}: no records; fill the CSV template first")
    return records


@dataclass
class Calibration:
    kind: str
    reference_mass_g: float
    coefficients: np.ndarray
    covariance_factor: np.ndarray
    residual_sd_ft: float
    degrees_of_freedom: int

    def vector(self, mass_g):
        return np.array([1.0] if self.kind == "offset" else [1.0, mass_g - self.reference_mass_g])

    def correction(self, mass_g):
        return float(self.vector(mass_g) @ self.coefficients)

    def predict(self, mass_g, simulated_ft):
        x = self.vector(mass_g)
        mean = simulated_ft + self.correction(mass_g)
        # The 1 includes variation in the next flight, beyond uncertainty in its mean.
        scale = self.residual_sd_ft * math.sqrt(1 + float(x @ self.covariance_factor @ x))
        half_width = float(t.ppf(0.975, self.degrees_of_freedom)) * scale
        return mean, scale, [mean - half_width, mean + half_width]


def fit(records, kind):
    masses = np.array([row["launch_mass_g"] for row in records])
    residuals = np.array([row["measured_apogee_ft"] - row["simulated_apogee_ft"] for row in records])
    center = float(masses.mean())
    design = np.ones((len(records), 1))
    if kind == "linear":
        design = np.column_stack((design, masses - center))
    elif kind != "offset":
        raise ValueError("model must be offset or linear")
    parameters = design.shape[1]
    if len(records) < parameters + 2:
        raise ValueError("insufficient flights for residual uncertainty")
    coefficients, _, rank, _ = np.linalg.lstsq(design, residuals, rcond=None)
    if rank != parameters:
        raise ValueError("mass correction requires different launch masses")
    df = len(records) - parameters
    sd = math.sqrt(float(np.sum((residuals - design @ coefficients) ** 2)) / df)
    return Calibration(kind, center, coefficients, np.linalg.inv(design.T @ design), sd, df)


def validation(records, kind, grouped):
    """Each held-out flight is predicted without using its altitude in training."""
    groups = sorted({row["launch_date"] for row in records}) if grouped else range(len(records))
    errors = []
    for group in groups:
        held = [i for i, row in enumerate(records) if (row["launch_date"] == group if grouped else i == group)]
        training = [row for i, row in enumerate(records) if i not in held]
        try:
            model = fit(training, kind)
        except ValueError:
            return None
        for i in held:
            row = records[i]
            estimate = row["simulated_apogee_ft"] + model.correction(row["launch_mass_g"])
            errors.append(abs(estimate - row["measured_apogee_ft"]))
    return float(np.mean(errors))


def expected_altitude_penalty(mean_ft, scale_ft, df, target_ft):
    """Expected absolute error under the fitted Student t predictive distribution."""
    difference = mean_ft - target_ft
    if scale_ft == 0:
        return abs(difference)
    z = difference / scale_ft
    return float(difference * (2 * t.cdf(z, df) - 1) + 2 * scale_ft * (df + z*z) / (df - 1) * t.pdf(z, df))


def analyze(flights, candidates, *, target_ft=800.0, model_choice="auto", synthetic=False):
    if not math.isfinite(target_ft) or target_ft <= 0:
        raise ValueError("target altitude must be finite and positive")
    if model_choice not in {"auto", "offset", "linear"}:
        raise ValueError("model must be auto, offset, or linear")
    if len(flights) < 4:
        raise ValueError("at least four measured flights are required")
    if not candidates:
        raise ValueError("at least one candidate is required")
    if any(len({row[key] for row in flights + candidates}) != 1 for key in CONTEXT):
        raise ValueError("all flights and candidates must use one configuration and motor")

    grouped = len({row["launch_date"] for row in flights}) >= 3
    offset_mae = validation(flights, "offset", grouped)
    can_fit_linear = len(flights) >= 6 and len({row["launch_mass_g"] for row in flights}) >= 3
    linear_mae = validation(flights, "linear", grouped) if can_fit_linear else None
    if model_choice == "linear" and (not can_fit_linear or linear_mae is None):
        raise ValueError("linear model needs six flights, three mass settings, and estimable validation folds")
    selected = model_choice
    if selected == "auto":
        selected = "linear" if linear_mae is not None and offset_mae is not None and linear_mae < offset_mae and linear_mae <= 0.9 * offset_mae else "offset"
    model = fit(flights, selected)
    warnings = [
        "Altitude-only ranking; duration, egg survival, stability, rail departure, and safe recovery are not certified.",
        "Prediction intervals assume independent normal errors with constant variance and correctly matched simulations; model selection uncertainty is not included.",
        "The best result is selected only from the supplied candidate simulations, not a continuous ballast optimum.",
    ]
    if not grouped:
        warnings.append("Fewer than three launch dates: validation leaves out individual flights and does not establish performance on a new launch day.")
    if offset_mae is None:
        warnings.append("Insufficient independent launch dates for the selected validation scheme; no validation error is available.")
    if model.residual_sd_ft < 1e-8:
        warnings.append("Near-zero residual variation: prediction intervals cannot establish real flight repeatability.")
    raw_mae = float(np.mean([abs(row["measured_apogee_ft"] - row["simulated_apogee_ft"]) for row in flights]))
    selected_mae = linear_mae if selected == "linear" else offset_mae
    if selected_mae is not None and selected_mae >= raw_mae:
        warnings.append("The selected correction has not improved validation MAE over the raw simulation; treat recommendations as unvalidated.")
    bounds = {key: (min(row[key] for row in flights), max(row[key] for row in flights)) for key in NUMERIC if key != "simulated_apogee_ft"}
    # Candidates describe one prospective launch setup; only ballast and mass vary.
    for key in ("wind_speed_m_s", "temperature_c", "station_pressure_hpa"):
        if len({row[key] for row in candidates}) != 1:
            raise ValueError("candidate simulations must share the same forecast weather")
    base_masses = [row["launch_mass_g"] - row["ballast_g"] for row in candidates]
    if max(base_masses) - min(base_masses) > 0.1:
        raise ValueError("candidate launch mass minus ballast must be constant within 0.1 g")

    results = []
    for row in candidates:
        mean, scale, interval = model.predict(row["launch_mass_g"], row["simulated_apogee_ft"])
        reasons = []
        if row["launch_mass_g"] > 650:
            reasons.append("exceeds_650_g_launch_mass_limit")
        for key in ("launch_mass_g", "ballast_g"):
            low, high = bounds[key]
            if not low <= row[key] <= high:
                reasons.append(f"outside_tested_{key}_range")
        weather_extrapolation = [key for key in ("wind_speed_m_s", "temperature_c", "station_pressure_hpa") if not bounds[key][0] <= row[key] <= bounds[key][1]]
        if weather_extrapolation:
            reasons.append("weather_outside_tested_ranges")
        results.append({
            "candidate_id": row["candidate_id"], "ballast_g": row["ballast_g"],
            "launch_mass_g": row["launch_mass_g"], "simulated_apogee_ft": row["simulated_apogee_ft"],
            "predicted_apogee_ft": mean, "prediction_interval_95_ft": interval,
            "expected_altitude_penalty_points": expected_altitude_penalty(mean, scale, model.degrees_of_freedom, target_ft),
            "eligible_for_recommendation": not reasons, "exclusion_reasons": reasons,
        })
    eligible = [row for row in results if row["eligible_for_recommendation"]]
    recommendation = min(eligible, key=lambda row: (row["expected_altitude_penalty_points"], row["ballast_g"])) if eligible else None
    observed = []
    for row in flights:
        result = {"flight_id": row["flight_id"], "simulation_error_ft": row["measured_apogee_ft"] - row["simulated_apogee_ft"]}
        duration = row.get("duration_s")
        result["altitude_duration_penalty_points"] = flight_score(row["measured_apogee_ft"], duration, target_ft) if isinstance(duration, (float, int)) else None
        observed.append(result)
    return {
        "dataset_kind": "synthetic_demonstration" if synthetic else "user_supplied",
        "target_apogee_ft": target_ft, "maximum_launch_mass_g": 650, "rules_source": RULES_URL,
        "configuration": flights[0]["configuration"], "motor": flights[0]["motor"], "flight_count": len(flights),
        "model": {"kind": selected, "reference_mass_g": model.reference_mass_g,
                  "offset_ft": float(model.coefficients[0]),
                  "mass_slope_ft_per_g": float(model.coefficients[1]) if selected == "linear" else 0.0,
                  "residual_sd_ft": model.residual_sd_ft, "degrees_of_freedom": model.degrees_of_freedom},
        "validation": {"method": "leave_one_launch_date_out" if grouped else "leave_one_flight_out",
                       "raw_simulation_mae_ft": raw_mae,
                       "offset_mae_ft": offset_mae, "linear_mae_ft": linear_mae,
                       "selection_rule": "Auto selects linear only with at least 10% lower validation MAE."},
        "tested_ranges": {key: list(value) for key, value in bounds.items()},
        "recommendation": recommendation, "candidates": results, "observed_flights": observed, "warnings": warnings,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flights", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--target-ft", type=float, default=800.0)
    parser.add_argument("--model", choices=("auto", "offset", "linear"), default="auto")
    parser.add_argument("--synthetic", action="store_true", help="Label output as synthetic demonstration data")
    parser.add_argument("--output", type=Path, help="Write JSON to this path instead of stdout")
    args = parser.parse_args(argv)
    try:
        report = analyze(read_records(args.flights, flights=True), read_records(args.candidates, flights=False),
                         target_ft=args.target_ft, model_choice=args.model, synthetic=args.synthetic)
        report["inputs"] = {"flights": str(args.flights), "candidates": str(args.candidates)}
        payload = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.output:
            if args.output.resolve() in {args.flights.resolve(), args.candidates.resolve()}:
                raise ValueError("output must not overwrite an input CSV")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload, encoding="utf-8")
        else:
            print(payload, end="")
    except (ValueError, OSError) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
