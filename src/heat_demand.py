"""Calculate synthetic useful space heat and retain assignment provenance."""

from dataclasses import dataclass
from math import fsum

from matching import Footprint, cell_index


SCENARIOS = ("existing", "usual", "advanced")
AREA_FACTOR = 0.85
FALLBACK_CELL_M = 1000


@dataclass(frozen=True)
class BuildingEstimate:
    building: Footprint
    route: str
    status: str
    point_ids: tuple[str, ...]
    owner_conflict: bool
    reason: str | None
    archetypes: tuple[tuple[str, str], ...]
    b0_mwh: tuple[float, ...] | None


def scenario_heat(area_m2, intensities):
    return tuple(area_m2 * intensity / 1000 for intensity in intensities)


def dominant_period(counts):
    """Use the unique positive maximum. A tie yields no synthetic assignment."""
    if not counts:
        return None
    maximum = max(counts.values())
    winners = [period for period, count in counts.items() if count == maximum]
    return winners[0] if maximum > 0 and len(winners) == 1 else None


def estimate_building(building, assignment, grids, lookup):
    route = assignment.route
    reason = assignment.reason
    archetypes = tuple(point.archetype for point in assignment.points)
    if route == "unmatched":
        cell = cell_index(building.centroid, FALLBACK_CELL_M)
        period = dominant_period(grids.get(cell, {}))
        if period is not None:
            route = "statistical_fallback"
            archetypes = ((period, building.fallback_size),)
        else:
            reason = f"{reason}; missing_or_tied_grid_period"

    area = building.floor_area_m2
    if area is None:
        status, b0 = "missing_floor", None
    elif not archetypes:
        status, b0 = "unresolved", None
    elif any(key not in lookup for key in archetypes):
        status, b0 = "missing_baseline_intensity", None
    else:
        allocated_area = area / len(archetypes)
        candidate_heat = [scenario_heat(allocated_area, lookup[key]) for key in archetypes]
        status, b0 = "calculated", tuple(fsum(values) for values in zip(*candidate_heat))

    return BuildingEstimate(
        building, route, status, tuple(p.point_id for p in assignment.points),
        assignment.owner_conflict, reason, archetypes, b0,
    )


def building_result(estimate):
    b0 = estimate.b0_mwh
    return {
        "building_id": estimate.building.building_id,
        "assignment_route": estimate.route,
        "status": estimate.status,
        "match_note": estimate.reason,
        "point_ids": estimate.point_ids,
        "nearest_cross_owner_flag": estimate.owner_conflict,
        "floor_area_m2": estimate.building.floor_area_m2,
        "b0_mwh_a": dict(zip(SCENARIOS, b0)) if b0 is not None else None,
        "b1_mwh_a": dict(zip(SCENARIOS, (v * AREA_FACTOR for v in b0))) if b0 is not None else None,
    }


def aggregate_baseline(estimates):
    calculated = [e.b0_mwh for e in estimates if e.b0_mwh is not None]
    totals = [fsum(values) / 1000 for values in zip(*calculated)] if calculated else [0.0] * len(SCENARIOS)
    return {
        scenario: {"b0_gwh_a": total, "b1_gwh_a": total * AREA_FACTOR}
        for scenario, total in zip(SCENARIOS, totals)
    }
