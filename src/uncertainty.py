"""Independent and 500 m grouped sensitivity on synthetic year distributions."""

from math import fsum, isclose, isfinite
from random import Random
from statistics import fmean, quantiles

from heat_demand import SCENARIOS, scenario_heat
from matching import cell_index


DEPENDENCE_BLOCK_M = 500


def probability_thresholds(weights):
    if not weights:
        raise ValueError("Provide at least one year option")
    periods, probabilities = zip(*weights)
    if len(set(periods)) != len(periods) or any(
        type(v) not in (int, float) or not isfinite(v) or v <= 0 for v in probabilities
    ):
        raise ValueError("Year options must have distinct periods and positive finite weights")
    if not isclose(fsum(probabilities), 1, rel_tol=0, abs_tol=1e-9):
        raise ValueError("Year weights must sum to one")
    return tuple((period, fsum(probabilities[:i + 1])) for i, period in enumerate(periods))


def draw_period(thresholds, rank):
    return next((period for period, upper in thresholds if rank < upper), thresholds[-1][0])


def grouped_year_ranks(blocks, rng):
    ranks_per_block = {}
    for block in blocks:
        if block not in ranks_per_block:
            ranks_per_block[block] = rng.random()
    return [ranks_per_block[key] for key in blocks]


def sampled_heat(estimate, key, lookup):
    if key not in lookup:
        return estimate.b0_mwh, True
    return scenario_heat(estimate.building.floor_area_m2, lookup[key]), False


def summarise(draws):
    scenario_stats = {}
    for scenario, mwh in zip(SCENARIOS, zip(*draws)):
        gwh = [value / 1000 for value in mwh]
        pct = quantiles(gwh, n=100, method="inclusive")
        scenario_stats[scenario] = {
            "mean_gwh_a": fmean(gwh),
            "p05_gwh_a": pct[4],
            "p95_gwh_a": pct[94],
            "p05_p95_width_gwh_a": pct[94] - pct[4],
        }
    return scenario_stats


def simulate(estimates, lookup, seed, draw_count):
    candidates, year_cases, fixed = [], [], []
    fixed_fallbacks = 0
    for estimate in estimates:
        building = estimate.building
        multiple = len(estimate.archetypes) > 1
        if multiple and (building.year_weights or building.accepted_size is not None):
            raise ValueError(f"Multi-candidate inputs must retain their tuples: {building.building_id}")
        thresholds = probability_thresholds(building.year_weights) if building.year_weights else ()
        if estimate.b0_mwh is None:
            continue
        if multiple:
            candidates.append(estimate)
            continue

        period, size = estimate.archetypes[0]
        b2_size = building.accepted_size or size
        if thresholds:
            year_cases.append((estimate, thresholds, b2_size))
        else:
            heat, unsupported = sampled_heat(estimate, (period, b2_size), lookup)
            fixed.append(heat)
            fixed_fallbacks += unsupported

    if not any((candidates, year_cases, fixed)):
        raise ValueError("B2 requires at least one successfully calculated building")

    blocks = [cell_index(e.building.centroid, DEPENDENCE_BLOCK_M) for e, _, _ in year_cases]
    seed_stream = Random(seed)
    candidate_rng, independent_rng, grouped_rng = [Random(seed_stream.getrandbits(64)) for _ in range(3)]
    samples = {"independent": [], "grouped_500m": []}
    fallback_counts = {key: 0 for key in samples}
    for _ in range(draw_count):
        candidate_heat = [
            sampled_heat(e, candidate_rng.choice(e.archetypes), lookup)[0]
            for e in candidates
        ]
        ranks_by_setting = {
            "independent": [independent_rng.random() for _ in year_cases],
            "grouped_500m": grouped_year_ranks(blocks, grouped_rng),
        }
        for setting, ranks in ranks_by_setting.items():
            heat = fixed + candidate_heat
            fallback_counts[setting] += fixed_fallbacks
            for (estimate, thresholds, size), rank in zip(year_cases, ranks):
                result, unsupported = sampled_heat(estimate, (draw_period(thresholds, rank), size), lookup)
                heat.append(result)
                fallback_counts[setting] += unsupported
            samples[setting].append(tuple(fsum(values) for values in zip(*heat)))

    return {
        setting: {
            "scenarios": summarise(draws),
            "unsupported_lookup_building_draws": fallback_counts[setting],
        }
        for setting, draws in samples.items()
    }
