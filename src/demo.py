"""Run the self-contained fictional case study with the Python standard library."""

import argparse
from collections import Counter
import json
from math import isfinite
from pathlib import Path
from tempfile import NamedTemporaryFile

from heat_demand import AREA_FACTOR, FALLBACK_CELL_M, SCENARIOS, aggregate_baseline, building_result, estimate_building
from matching import EvidencePoint, Footprint, assign_building, audit_point_assignment, point_owners
from uncertainty import DEPENDENCE_BLOCK_M, simulate


def read_json(path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def load_fixture(path):
    data = read_json(path)
    if data["coordinate_system"] != "synthetic_local_metres":
        raise ValueError("Use the fictional local metre grid supported by this demonstration")
    buildings = [
        Footprint(
            entry["id"], tuple(entry["bounds_m"]), entry["storeys"], entry["fallback_size"],
            tuple((option["period"], option["probability"]) for option in entry.get("year_options", [])),
            entry.get("accepted_size"),
        )
        for entry in data["buildings"]
    ]
    points = [
        EvidencePoint(row["id"], tuple(row["xy_m"]), (row["period"], row["size"]))
        for row in data["evidence_points"]
    ]
    for ids in ([b.building_id for b in buildings], [p.point_id for p in points]):
        if len(set(ids)) != len(ids) or any(not isinstance(value, str) or not value for value in ids):
            raise ValueError("Building and point IDs must be non-empty and unique in each table")
    if not buildings or any(
        len(point.xy) != 2
        or any(type(v) not in (int, float) or not isfinite(v) for v in point.xy)
        for point in points
    ):
        raise ValueError("Provide at least one footprint and finite XY coordinates for evidence points")

    grids = {}
    for row in data["cells_1km"]:
        key = tuple(row["index"])
        counts = row["period_counts"]
        if len(key) != 2 or any(type(i) is not int for i in key) or key in grids:
            raise ValueError(f"Duplicate or invalid 1 km cell {key}")
        if any(type(n) is not int or n < 0 for n in counts.values()):
            raise ValueError(f"Invalid counts for 1 km cell {key}")
        grids[key] = counts

    lookup = {}
    for row in data["intensities_kwh_m2a"]:
        key = (row["period"], row["size"])
        intensities = tuple(row[scenario] for scenario in SCENARIOS)
        if key in lookup or any(type(v) not in (int, float) or not isfinite(v) or v < 0 for v in intensities):
            raise ValueError(f"Duplicate or invalid lookup intensities for {key}")
        lookup[key] = intensities
    return buildings, points, grids, lookup


def run_demo(input_path, seed, draws):
    if type(seed) is not int or type(draws) is not int or draws < 2:
        raise ValueError("Set an integer seed and at least two draws")
    buildings, points, grids, lookup = load_fixture(input_path)
    owners = point_owners(buildings, points)
    estimates = [
        estimate_building(b, assign_building(b, points, owners), grids, lookup)
        for b in buildings
    ]
    return {
        "dataset": "synthetic demonstration",
        "coordinate_system": "synthetic_local_metres",
        "simulation": {
            "seed": seed,
            "draws": draws,
            "area_factor_b1": AREA_FACTOR,
            "statistical_cell_m": FALLBACK_CELL_M,
            "dependence_block_m": DEPENDENCE_BLOCK_M,
        },
        "building_count": len(buildings),
        "status_counts": dict(Counter(e.status for e in estimates)),
        "point_assignment_audit": audit_point_assignment(buildings, points, owners),
        "buildings": [building_result(e) for e in estimates],
        "baseline": aggregate_baseline(estimates),
        "b2": simulate(estimates, lookup, seed, draws),
    }


def write_report(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as stream:
            pending = Path(stream.name)
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write("\n")
        pending.replace(path)
    finally:
        if pending is not None:
            pending.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", type=Path, help="Override the output path. Resolved from the working directory.")
    arguments = parser.parse_args()
    try:
        config_path = arguments.config.resolve()
        config = read_json(config_path)
        input_path = (config_path.parent / config["input_file"]).resolve()
        output_path = (
            arguments.output.resolve() if arguments.output else
            (config_path.parent / config["output_file"]).resolve()
        )
        if any(
            output_path == source or (output_path.exists() and output_path.samefile(source))
            for source in (config_path, input_path)
        ):
            raise ValueError("Use an output path distinct from the configuration and fixture")
        report = run_demo(input_path, config["seed"], config["draws"])
        write_report(output_path, report)
    except (ValueError, TypeError, KeyError, OSError) as error:
        parser.exit(2, f"Demo failed: {error}\n")
    print(f"Wrote synthetic heat-demand report to {output_path}")


if __name__ == "__main__":
    main()
