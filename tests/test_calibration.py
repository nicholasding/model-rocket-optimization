import contextlib
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

from scipy.integrate import quad
from scipy.stats import t

from rocket_calibration import (
    analyze, expected_altitude_penalty, fit, flight_score, main, read_records, validation,
)


ROOT = Path(__file__).resolve().parents[1]


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.flights = read_records(ROOT / "examples/synthetic_flights.csv", flights=True)
        self.candidates = read_records(ROOT / "examples/synthetic_candidates.csv", flights=False)

    def test_offset_recovers_known_bias_and_repeatability(self):
        errors = [-25, -15, -25, -15]
        rows = [dict(row, measured_apogee_ft=row["simulated_apogee_ft"] + error)
                for row, error in zip(self.flights, errors)]
        model = fit(rows, "offset")
        self.assertAlmostEqual(model.correction(520), -20)
        mean, scale, interval = model.predict(520, 820)
        self.assertAlmostEqual(mean, 800)
        self.assertAlmostEqual(scale, (100 / 3 * 1.25) ** 0.5)
        self.assertLess(interval[0], mean)
        self.assertGreater(interval[1], mean)

    def test_linear_recovers_known_mass_correction(self):
        rows = [dict(row, measured_apogee_ft=row["simulated_apogee_ft"] - 30 - 0.4 * (row["launch_mass_g"] - 520))
                for row in self.flights]
        model = fit(rows, "linear")
        self.assertAlmostEqual(model.correction(520), -30)
        self.assertAlmostEqual(model.coefficients[1], -0.4)
        self.assertAlmostEqual(model.correction(540), -38)

    def test_new_flight_interval_includes_irreducible_variation(self):
        model = fit(self.flights, "linear")
        _, scale, _ = model.predict(520, 850)
        self.assertGreater(scale, model.residual_sd_ft)
        _, edge_scale, _ = model.predict(540, 810)
        self.assertGreater(edge_scale, scale)

    def test_expected_penalty_matches_independent_numerical_integration(self):
        for mean in (760, 800, 825):
            for df in (2, 5, 20):
                scale = 12
                z = (800 - mean) / scale
                integrand = lambda x: abs(mean + scale * x - 800) * t.pdf(x, df)
                expected = quad(integrand, float("-inf"), z)[0] + quad(integrand, z, float("inf"))[0]
                self.assertAlmostEqual(expected_altitude_penalty(mean, scale, df, 800), expected, places=6)
        self.assertEqual(expected_altitude_penalty(790, 0, 3, 800), 10)

    def test_scoring_boundaries_and_penalties(self):
        for duration in (37, 38.5, 40):
            self.assertEqual(flight_score(800, duration), 0)
        self.assertAlmostEqual(flight_score(790, 36.5), 12)
        self.assertAlmostEqual(flight_score(805, 41), 9)
        self.assertEqual(flight_score(775, 38, 775), 0)

    def test_grouped_validation_holds_out_entire_date(self):
        rows = []
        for day, error in (("2026-10-01", -20), ("2026-10-02", 0), ("2026-10-03", 20)):
            for original in self.flights[:3]:
                rows.append(dict(original, launch_date=day,
                                 measured_apogee_ft=original["simulated_apogee_ft"] + error))
        self.assertAlmostEqual(validation(rows, "offset", True), 20)
        self.assertLess(validation(rows, "offset", False), 20)

    def test_auto_selects_slope_and_recommends_lowest_expected_penalty(self):
        report = analyze(self.flights, self.candidates, synthetic=True)
        self.assertEqual(report["dataset_kind"], "synthetic_demonstration")
        self.assertEqual(report["model"]["kind"], "linear")
        self.assertEqual(report["validation"]["method"], "leave_one_launch_date_out")
        self.assertEqual(report["recommendation"]["candidate_id"], "C30")
        self.assertAlmostEqual(report["recommendation"]["predicted_apogee_ft"], 798 + 1 / 3)
        self.assertGreater(report["recommendation"]["expected_altitude_penalty_points"], 1 + 2 / 3)

    def test_auto_retains_offset_without_mass_effect(self):
        rows = [dict(row, measured_apogee_ft=row["simulated_apogee_ft"] - 20 + (-1 if i < 6 else 1))
                for i, row in enumerate(self.flights)]
        self.assertEqual(analyze(rows, self.candidates)["model"]["kind"], "offset")

    def test_mass_limit_and_extrapolation_exclude_recommendations(self):
        rows = [dict(self.candidates[0], launch_mass_g=651, ballast_g=151)]
        report = analyze(self.flights, rows)
        self.assertIsNone(report["recommendation"])
        reasons = report["candidates"][0]["exclusion_reasons"]
        self.assertIn("exceeds_650_g_launch_mass_limit", reasons)
        self.assertIn("outside_tested_launch_mass_g_range", reasons)
        self.assertIn("outside_tested_ballast_g_range", reasons)

    def test_650_g_boundary_is_allowed_when_tested(self):
        flights = [dict(row, launch_mass_g=row["launch_mass_g"] + 110) for row in self.flights]
        candidates = [dict(row, launch_mass_g=row["launch_mass_g"] + 110) for row in self.candidates]
        report = analyze(flights, candidates)
        self.assertTrue(report["candidates"][-1]["eligible_for_recommendation"])

    def test_weather_extrapolation_excludes_all_candidates(self):
        candidates = [dict(row, wind_speed_m_s=10) for row in self.candidates]
        report = analyze(self.flights, candidates)
        self.assertIsNone(report["recommendation"])
        self.assertIn("weather_outside_tested_ranges", report["candidates"][0]["exclusion_reasons"])

    def test_rejects_incomparable_configurations_and_candidate_setups(self):
        for key, value in (("motor", "different"), ("configuration", "different"),
                           ("wind_speed_m_s", 2.1), ("launch_mass_g", 501)):
            rows = [dict(row) for row in self.candidates]
            rows[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                analyze(self.flights, rows)

    def test_small_samples_and_unidentifiable_mass_slope(self):
        with self.assertRaises(ValueError):
            analyze(self.flights[:3], self.candidates)
        rows = [dict(row, launch_mass_g=520) for row in self.flights]
        with self.assertRaises(ValueError):
            analyze(rows, self.candidates, model_choice="linear")
        with self.assertRaises(ValueError):
            fit(rows, "linear")

    def test_one_day_warns_and_duration_can_be_missing(self):
        rows = [dict(row, launch_date="2026-10-01", duration_s="") for row in self.flights]
        report = analyze(rows, self.candidates)
        self.assertEqual(report["validation"]["method"], "leave_one_flight_out")
        self.assertTrue(any("new launch day" in warning for warning in report["warnings"]))
        self.assertIsNone(report["observed_flights"][0]["altitude_duration_penalty_points"])

    def test_perfect_simulations_do_not_imply_validated_repeatability(self):
        rows = [dict(row, measured_apogee_ft=row["simulated_apogee_ft"]) for row in self.flights]
        report = analyze(rows, self.candidates)
        self.assertEqual(report["model"]["kind"], "offset")
        self.assertTrue(any("Near-zero" in warning for warning in report["warnings"]))
        self.assertTrue(any("has not improved" in warning for warning in report["warnings"]))

    def test_invalid_targets_are_rejected(self):
        for target in (float("nan"), float("inf"), 0, -800):
            with self.subTest(target=target), self.assertRaises(ValueError):
                analyze(self.flights, self.candidates, target_ft=target)

    def test_missing_columns_empty_templates_and_invalid_values(self):
        with self.assertRaisesRegex(ValueError, "no records"):
            read_records(ROOT / "data/flights.csv", flights=True)
        for key, value in (("launch_mass_g", "NaN"), ("wind_speed_m_s", "-1"),
                           ("station_pressure_hpa", "0"), ("ballast_g", "600"),
                           ("launch_date", "yesterday"), ("launch_date", "20261001"),
                           ("measured_apogee_ft", "")):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                row = dict(self.flights[0], **{key: value})
                path = Path(directory) / "flights.csv"
                with path.open("w", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(row))
                    writer.writeheader()
                    writer.writerow(row)
                with self.assertRaises(ValueError):
                    read_records(path, flights=True)

    def test_duplicate_flight_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "flights.csv"
            with path.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(self.flights[0]))
                writer.writeheader()
                writer.writerows([self.flights[0], self.flights[0]])
            with self.assertRaisesRegex(ValueError, "duplicate"):
                read_records(path, flights=True)

    def test_cli_writes_json_with_configurable_target(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "results/report.json"
            main(["--flights", str(ROOT / "examples/synthetic_flights.csv"),
                  "--candidates", str(ROOT / "examples/synthetic_candidates.csv"),
                  "--target-ft", "775", "--synthetic", "--output", str(output)])
            report = json.loads(output.read_text())
            self.assertEqual(report["target_apogee_ft"], 775)
            self.assertEqual(report["recommendation"]["candidate_id"], "C40")
            self.assertEqual(report["dataset_kind"], "synthetic_demonstration")

    def test_cli_rejects_bad_input_without_traceback(self):
        output = io.StringIO()
        with contextlib.redirect_stderr(output), self.assertRaises(SystemExit) as caught:
            main(["--flights", str(ROOT / "data/flights.csv"),
                  "--candidates", str(ROOT / "data/candidates.csv")])
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("fill the CSV template", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())

    def test_cli_does_not_overwrite_source_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "flights.csv"
            contents = (ROOT / "examples/synthetic_flights.csv").read_text()
            source.write_text(contents)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                main(["--flights", str(source),
                      "--candidates", str(ROOT / "examples/synthetic_candidates.csv"),
                      "--output", str(source)])
            self.assertEqual(caught.exception.code, 2)
            self.assertEqual(source.read_text(), contents)


if __name__ == "__main__":
    unittest.main()
