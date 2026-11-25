"""Regression checks for the fictional demo's spatial and calculation contracts."""

import json
from pathlib import Path
from random import Random
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from math import nextafter
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data" / "synthetic" / "demo.json"
sys.path.insert(0, str(ROOT / "src"))

from demo import load_fixture, run_demo
from heat_demand import dominant_period, estimate_building
from matching import Assignment, EvidencePoint, Footprint, assign_building, audit_point_assignment, cell_index, point_owners
from uncertainty import draw_period, grouped_year_ranks, probability_thresholds, simulate, summarise


class MatchingTests(unittest.TestCase):
    def test_distance_bands_and_abstentions(self):
        target = Footprint("a", (0, 0, 10, 10), 2, "compact")
        cases = (
            (((5, 5),), "strict"),
            (((5, 5), (8, 8)), "multi_candidate"),
            (((20, 5),), "nearest_10m"),
            (((30, 5),), "nearest_20m"),
            (((31, 5),), "unmatched"),
            (((10, 5),), "unmatched"),
            (((-2, 5), (12, 5)), "unmatched"),
        )
        for coordinates, route in cases:
            with self.subTest(coordinates=coordinates):
                points = [EvidencePoint(str(i), xy, ("early", "compact")) for i, xy in enumerate(coordinates)]
                self.assertEqual(assign_building(target, points, point_owners([target], points)).route, route)

    def test_ambiguous_ownership_is_not_used(self):
        a = Footprint("a", (0, 0, 10, 10), 2, "compact")
        b = Footprint("b", (4, 0, 14, 10), 2, "compact")
        points = [EvidencePoint("p", (6, 5), ("early", "compact"))]
        owners = point_owners([a, b], points)
        self.assertEqual(owners["p"], ("a", "b"))
        self.assertEqual(assign_building(a, points, owners).route, "unmatched")
        self.assertEqual(assign_building(b, points, owners).route, "unmatched")

    def test_grid_cell_assignment_and_ties(self):
        self.assertEqual(cell_index((999, -1), 1000), (0, -1))
        self.assertEqual(cell_index((1000, 0), 1000), (1, 0))
        self.assertEqual(dominant_period({"early": 4, "late": 2}), "early")
        self.assertIsNone(dominant_period({"early": 2, "late": 2}))
        self.assertIsNone(dominant_period({"early": 0}))

    def test_boundary_contact_has_its_own_match_note(self):
        target = Footprint("a", (0, 0, 10, 10), 2, "compact")
        point = EvidencePoint("edge", (10, 5), ("early", "compact"))
        owners = point_owners([target], [point])
        self.assertEqual(owners["edge"], ())
        result = assign_building(target, [point], owners)
        self.assertEqual(result.route, "unmatched")
        self.assertEqual(result.reason, "boundary_contact_excluded")

    def test_centroid_tie_is_excluded_from_both_audit_counts(self):
        a = Footprint("a", (0, 0, 20, 10), 2, "compact")
        b = Footprint("b", (20, 0, 26, 10), 2, "compact")
        points = [EvidencePoint("p", (16.5, 5), ("early", "compact"))]
        owners = point_owners([a, b], points)
        self.assertEqual(owners["p"], ("a",))
        self.assertEqual(audit_point_assignment([a, b], points, owners), {
            "evaluated_unique_owner_points": 0,
            "excluded_centroid_ties": 1,
            "distance_only_cross_building_transfers": 0,
            "owner_constrained_cross_building_transfers": 0,
        })


class HeatDemandTests(unittest.TestCase):
    def test_baseline_closure_area_allocation_and_units(self):
        report = run_demo(FIXTURE, seed=20261125, draws=2000)
        self.assertEqual(report["building_count"], 10)
        self.assertEqual(report["status_counts"], {"calculated": 8, "missing_floor": 1, "unresolved": 1})
        buildings = {row["building_id"]: row for row in report["buildings"]}
        self.assertEqual(buildings["S02"]["assignment_route"], "multi_candidate")
        self.assertEqual(buildings["S02"]["floor_area_m2"], 400)
        self.assertEqual(buildings["S02"]["b0_mwh_a"]["existing"], (200 * 100 + 200 * 70) / 1000)
        self.assertEqual(buildings["S03"]["assignment_route"], "statistical_fallback")
        self.assertTrue(buildings["S09"]["nearest_cross_owner_flag"])
        self.assertEqual(buildings["S09"]["b0_mwh_a"]["existing"], 16)
        self.assertIsNone(buildings["S06"]["b0_mwh_a"])
        self.assertIsNone(buildings["S07"]["b1_mwh_a"])
        audit = report["point_assignment_audit"]
        self.assertEqual(audit["evaluated_unique_owner_points"], 4)
        self.assertEqual(audit["distance_only_cross_building_transfers"], 1)
        self.assertEqual(audit["owner_constrained_cross_building_transfers"], 0)
        totals = report["baseline"]
        for scenario, expected in {"existing": 0.314, "usual": 0.1898, "advanced": 0.1126}.items():
            self.assertAlmostEqual(totals[scenario]["b0_gwh_a"], expected)
            self.assertAlmostEqual(totals[scenario]["b1_gwh_a"], 0.85 * expected)
        self.assertGreater(
            report["b2"]["grouped_500m"]["scenarios"]["existing"]["p05_p95_width_gwh_a"],
            report["b2"]["independent"]["scenarios"]["existing"]["p05_p95_width_gwh_a"],
        )

    def test_grouped_ranks_are_shared_only_within_blocks(self):
        blocks = [(0, 0), (1, 0), (0, 0)]
        reference = Random(9)
        first, second = reference.random(), reference.random()
        self.assertEqual(grouped_year_ranks(blocks, Random(9)), [first, second, first])

    def test_asymmetric_year_weights_select_by_cumulative_rank(self):
        thresholds = probability_thresholds((("early", 0.125), ("middle", 0.625), ("late", 0.25)))
        self.assertEqual(thresholds, (("early", 0.125), ("middle", 0.75), ("late", 1.0)))
        cases = (
            (0.0, "early"),
            (nextafter(0.125, 0.0), "early"),
            (0.125, "middle"),
            (0.20, "middle"),
            (nextafter(0.75, 0.0), "middle"),
            (0.75, "late"),
            (nextafter(1.0, 0.0), "late"),
        )
        for rank, period in cases:
            with self.subTest(rank=rank):
                self.assertEqual(draw_period(thresholds, rank), period)

    def test_grouped_b2_uses_configured_year_weights_for_given_ranks(self):
        weights = (("early", 0.125), ("middle", 0.625), ("late", 0.25))
        building = Footprint("weighted", (0, 0, 10, 10), 1, "compact", year_weights=weights)
        point = EvidencePoint("early", (2, 2), ("early", "compact"))
        lookup = {
            ("early", "compact"): (100, 60, 30),
            ("middle", "compact"): (80, 50, 25),
            ("late", "compact"): (60, 40, 20),
        }
        estimate = estimate_building(building, Assignment("strict", (point,)), {}, lookup)
        with patch("uncertainty.grouped_year_ranks", side_effect=([0.20], [0.75])):
            result = simulate([estimate], lookup, seed=11, draw_count=2)
        existing = result["grouped_500m"]["scenarios"]["existing"]
        # The two ranks select middle and late, giving 8 and 6 MWh/a.
        self.assertAlmostEqual(existing["mean_gwh_a"], 0.007)

    def test_joint_candidate_draws_are_reused_across_dependence_settings(self):
        building = Footprint("a", (0, 0, 10, 10), 1, "compact")
        options = (
            EvidencePoint("p1", (2, 2), ("early", "compact")),
            EvidencePoint("p2", (3, 3), ("late", "spacious")),
        )
        lookup = {("early", "compact"): (100, 60, 30), ("late", "spacious"): (70, 30, 20)}
        estimate = estimate_building(building, Assignment("multi_candidate", options), {}, lookup)
        result = simulate([estimate], lookup, seed=11, draw_count=40)
        self.assertEqual(result["independent"], result["grouped_500m"])
        self.assertAlmostEqual(result["independent"]["scenarios"]["existing"]["p05_gwh_a"], 0.007)
        self.assertAlmostEqual(result["independent"]["scenarios"]["existing"]["p95_gwh_a"], 0.010)

    def test_b2_draws_keep_year_and_size_together_even_if_hybrids_are_missing(self):
        building = Footprint("joint", (0, 0, 10, 10), 1, "compact")
        points = (
            EvidencePoint("p1", (2, 2), ("early", "compact")),
            EvidencePoint("p2", (3, 3), ("late", "spacious")),
        )
        valid = {("early", "compact"): (100, 60, 30), ("late", "spacious"): (70, 30, 20)}
        hybrids = {("early", "spacious"): (160, 90, 60), ("late", "compact"): (40, 20, 10)}
        # On 100 m², a legitimate draw uses a whole tuple and produces one of these vectors in MWh/a.
        expected_draws = {(10.0, 6.0, 3.0), (7.0, 3.0, 2.0)}
        for lookup in (valid | hybrids, valid):
            with self.subTest(hybrid_lookup_present=lookup is not valid):
                estimate = estimate_building(building, Assignment("multi_candidate", points), {}, lookup)
                # A missing hybrid would silently produce the B0 vector, which also lies outside the allowed set.
                self.assertNotIn(estimate.b0_mwh, expected_draws)
                with patch("uncertainty.summarise", wraps=summarise) as summary:
                    simulate([estimate], lookup, seed=11, draw_count=40)
                self.assertEqual(summary.call_count, 2)
                for call in summary.call_args_list:
                    self.assertEqual(set(call.args[0]), expected_draws)

    def test_accepted_size_and_unsupported_lookup_use_documented_rules(self):
        point = EvidencePoint("p", (2, 2), ("early", "compact"))
        assigned = Assignment("strict", (point,))
        lookup = {point.archetype: (100, 60, 30), ("early", "spacious"): (120, 72, 45)}
        large = Footprint("large", (0, 0, 10, 10), 1, "compact", accepted_size="spacious")
        unmatched = Footprint(
            "unmapped", (0, 0, 10, 10), 1, "compact", year_weights=(("unavailable", 1),)
        )
        estimates = [estimate_building(b, assigned, {}, lookup) for b in [large, unmatched]]
        result = simulate(estimates, lookup, seed=4, draw_count=10)
        self.assertEqual(result["independent"], result["grouped_500m"])
        self.assertAlmostEqual(result["independent"]["scenarios"]["existing"]["mean_gwh_a"], 0.022)
        self.assertEqual(result["independent"]["unsupported_lookup_building_draws"], 10)

    def test_cross_owner_nearest_s09_participates_in_both_b2_settings(self):
        buildings, points, grids, lookup = load_fixture(FIXTURE)
        building = next(b for b in buildings if b.building_id == "S09")
        self.assertEqual(building.year_weights, (("early", 0.5), ("late", 0.5)))
        assignment = assign_building(building, points, point_owners(buildings, points))
        estimate = estimate_building(building, assignment, grids, lookup)
        self.assertEqual(assignment.route, "nearest_10m")
        self.assertTrue(assignment.owner_conflict)
        for summary in simulate([estimate], lookup, seed=20261125, draw_count=2000).values():
            existing = summary["scenarios"]["existing"]
            self.assertAlmostEqual(existing["p05_gwh_a"], 0.0096)
            self.assertAlmostEqual(existing["p95_gwh_a"], 0.016)

    def test_missing_baseline_lookup_leaves_the_building_uncalculated(self):
        point = EvidencePoint("p", (2, 2), ("early", "compact"))
        building = Footprint("a", (0, 0, 10, 10), 1, "compact")
        estimate = estimate_building(building, Assignment("strict", (point,)), {}, {})
        self.assertEqual(estimate.status, "missing_baseline_intensity")
        self.assertIsNone(estimate.b0_mwh)

    def test_multi_candidate_parameters_conflict_with_tuple_sampling(self):
        options = (
            EvidencePoint("p1", (2, 2), ("early", "compact")),
            EvidencePoint("p2", (3, 3), ("late", "spacious")),
        )
        lookup = {p.archetype: (100, 60, 30) for p in options}
        for weights, size in (((("early", 1),), None), ((), "spacious")):
            with self.subTest(weights=weights, size=size):
                building = Footprint("a", (0, 0, 10, 10), 1, "compact", weights, size)
                estimate = estimate_building(building, Assignment("multi_candidate", options), {}, lookup)
                with self.assertRaisesRegex(ValueError, "Multi-candidate inputs"):
                    simulate([estimate], lookup, seed=11, draw_count=40)

    def test_invalid_year_probabilities_are_rejected(self):
        for weights in (
            (("early", True),), (("early", 0), ("late", 1)),
            (("early", -0.1), ("late", 1.1)), (("early", float("nan")),),
            (("early", float("inf")),), (("early", 0.4), ("early", 0.6)),
            (("early", 0.2), ("late", 0.4)), (),
        ):
            with self.subTest(weights=weights), self.assertRaises(ValueError):
                probability_thresholds(weights)

    def test_json_booleans_are_rejected_in_fixture_numeric_fields(self):
        paths = (
            ("buildings", 0, "bounds_m", 0), ("buildings", 0, "storeys"),
            ("evidence_points", 0, "xy_m", 1), ("cells_1km", 0, "index", 0),
            ("cells_1km", 0, "period_counts", "early"),
            ("intensities_kwh_m2a", 0, "existing"),
            ("buildings", 2, "year_options", 0, "probability"),
        )
        with TemporaryDirectory() as folder:
            fixture = Path(folder) / "fixture.json"
            for path in paths:
                with self.subTest(path=path), self.assertRaises(ValueError):
                    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
                    parent = data
                    for key in path[:-1]:
                        parent = parent[key]
                    parent[path[-1]] = True
                    fixture.write_text(json.dumps(data), encoding="utf-8")
                    run_demo(fixture, seed=1, draws=2)

    def test_json_boolean_config_parameters_are_rejected(self):
        for seed, draws in ((True, 2), (1, True)):
            with self.subTest(seed=seed, draws=draws), self.assertRaisesRegex(ValueError, "integer"):
                run_demo(FIXTURE, seed=seed, draws=draws)


class CommandLineTests(unittest.TestCase):
    def test_config_relative_paths_and_byte_for_byte_repeat(self):
        with TemporaryDirectory() as folder:
            base = Path(folder)
            conf = base / "config"
            conf.mkdir()
            (base / "fixture.json").write_bytes(FIXTURE.read_bytes())
            config = conf / "demo.json"
            config.write_text(
                json.dumps({
                    "input_file": "../fixture.json", "output_file": "../result.json",
                    "seed": 20261125, "draws": 2000,
                }),
                encoding="utf-8",
            )
            cmd = [sys.executable, "-B", str(ROOT / "src" / "demo.py"), "--config", str(config)]
            subprocess.run(cmd, cwd=base, check=True, capture_output=True)
            first = (base / "result.json").read_bytes()
            subprocess.run(cmd, cwd=conf, check=True, capture_output=True)
            self.assertEqual(first, (base / "result.json").read_bytes())
            self.assertEqual(json.loads(first)["dataset"], "synthetic demonstration")

    def test_output_cannot_overwrite_the_config(self):
        with TemporaryDirectory() as folder:
            config = Path(folder) / "demo.json"
            original = json.dumps({
                "input_file": str(FIXTURE), "output_file": "demo.json", "seed": 100, "draws": 2,
            })
            config.write_text(original, encoding="utf-8")
            run = subprocess.run(
                [sys.executable, "-B", str(ROOT / "src" / "demo.py"), "--config", str(config)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(run.returncode, 2)
            self.assertIn("distinct", run.stderr)
            self.assertEqual(config.read_text(encoding="utf-8"), original)

    def test_output_override_uses_working_directory_and_protects_fixture(self):
        with TemporaryDirectory() as folder:
            base = Path(folder)
            workdir = base / "run"
            workdir.mkdir()
            input_path = base / "fixture.json"
            fixture_bytes = FIXTURE.read_bytes()
            input_path.write_bytes(fixture_bytes)
            config = base / "demo.json"
            config.write_text(json.dumps({
                "input_file": "fixture.json", "output_file": "unused.json",
                "seed": 42, "draws": 20,
            }), encoding="utf-8")
            cmd = [sys.executable, "-B", str(ROOT / "src" / "demo.py"), "--config", str(config)]
            subprocess.run(cmd + ["--output", "nested/override.json"], cwd=workdir, check=True, capture_output=True)
            result = json.loads((workdir / "nested" / "override.json").read_text(encoding="utf-8"))
            self.assertEqual(result["simulation"]["draws"], 20)
            self.assertFalse((base / "unused.json").exists())
            denied = subprocess.run(cmd + ["--output", "../fixture.json"], cwd=workdir, capture_output=True, text=True)
            self.assertEqual(denied.returncode, 2)
            self.assertIn("distinct", denied.stderr)
            self.assertEqual(input_path.read_bytes(), fixture_bytes)


if __name__ == "__main__":
    unittest.main()
