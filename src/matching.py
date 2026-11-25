"""Spatial assignment on fictional rectangular footprints in a local metre grid."""

from dataclasses import dataclass
from math import floor, hypot, isclose, isfinite


@dataclass(frozen=True)
class Footprint:
    building_id: str
    bounds: tuple[float, float, float, float]
    storeys: int | None
    fallback_size: str
    year_weights: tuple[tuple[str, float], ...] = ()
    accepted_size: str | None = None

    def __post_init__(self):
        xmin, ymin, xmax, ymax = self.bounds
        if any(type(v) not in (int, float) or not isfinite(v) for v in self.bounds) or xmin >= xmax or ymin >= ymax:
            raise ValueError(f"Invalid footprint bounds for {self.building_id}")
        if self.storeys is not None and (type(self.storeys) is not int or self.storeys < 1):
            raise ValueError(f"Invalid storey count for {self.building_id}")

    @property
    def centroid(self):
        xmin, ymin, xmax, ymax = self.bounds
        return ((xmin + xmax) / 2, (ymin + ymax) / 2)

    @property
    def floor_area_m2(self):
        if self.storeys is None:
            return None
        xmin, ymin, xmax, ymax = self.bounds
        return (xmax - xmin) * (ymax - ymin) * self.storeys

    def contains(self, xy):
        xmin, ymin, xmax, ymax = self.bounds
        x, y = xy
        return xmin < x < xmax and ymin < y < ymax

    def distance(self, xy):
        xmin, ymin, xmax, ymax = self.bounds
        x, y = xy
        return hypot(max(xmin - x, 0, x - xmax), max(ymin - y, 0, y - ymax))


@dataclass(frozen=True)
class EvidencePoint:
    point_id: str
    xy: tuple[float, float]
    archetype: tuple[str, str]


@dataclass(frozen=True)
class Assignment:
    route: str
    points: tuple[EvidencePoint, ...] = ()
    owner_conflict: bool = False
    reason: str | None = None


def cell_index(xy, cell_width_m):
    """Index a half-open cell in the fictional metre grid anchored at (0, 0)."""
    return tuple(floor(value / cell_width_m) for value in xy)


def point_owners(buildings, points):
    return {
        point.point_id: tuple(b.building_id for b in buildings if b.contains(point.xy))
        for point in points
    }


def assign_building(building, points, owners):
    contained = tuple(
        point for point in points if owners[point.point_id] == (building.building_id,)
    )
    if contained:
        route = "strict" if len(contained) == 1 else "multi_candidate"
        return Assignment(route, contained)

    eligible = []
    boundary_contact = False
    for point in points:
        distance = building.distance(point.xy)
        boundary_contact |= distance == 0 and not building.contains(point.xy)
        if len(owners[point.point_id]) <= 1 and 0 < distance <= 20:
            eligible.append((distance, point))
    if not eligible:
        reason = "boundary_contact_excluded" if boundary_contact else "no_eligible_point_within_20m"
        return Assignment("unmatched", reason=reason)

    distance = min(d for d, _ in eligible)
    nearest = [p for d, p in eligible if isclose(d, distance, rel_tol=0, abs_tol=1e-9)]
    if len(nearest) != 1:
        return Assignment("unmatched", reason="equal_nearest_distance")
    point = nearest[0]
    point_owner = owners[point.point_id]
    conflict = bool(point_owner and point_owner != (building.building_id,))
    return Assignment("nearest_10m" if distance <= 10 else "nearest_20m", (point,), conflict)


def audit_point_assignment(buildings, points, owners):
    """Compare nearest-centroid assignment with a unique-owner rule.

    The constraint selects the known geometric owner by definition.
    This audit checks transfers, without evaluating the point attributes.
    """
    evaluated = false_transfers = constrained_transfers = ties = 0
    for point in points:
        owner = owners[point.point_id]
        if len(owner) != 1:
            continue
        distances = sorted(
            (hypot(point.xy[0] - b.centroid[0], point.xy[1] - b.centroid[1]), b.building_id)
            for b in buildings if b.distance(point.xy) <= 20
        )
        if len(distances) > 1 and isclose(distances[0][0], distances[1][0], rel_tol=0, abs_tol=1e-9):
            ties += 1
            continue
        evaluated += 1
        false_transfers += distances[0][1] != owner[0]
        selected = next(bid for _, bid in distances if bid in owner)
        constrained_transfers += selected != owner[0]
    return {
        "evaluated_unique_owner_points": evaluated,
        "excluded_centroid_ties": ties,
        "distance_only_cross_building_transfers": false_transfers,
        "owner_constrained_cross_building_transfers": constrained_transfers,
    }
