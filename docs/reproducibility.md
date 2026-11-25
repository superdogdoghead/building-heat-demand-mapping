# Reproducing the synthetic demonstration

## Environment and execution

Use Python 3.11 or newer. The program and tests use the standard library and local files. The reference run used Windows and Python 3.12.14 in an isolated environment created with python -m venv --without-pip .venv. Use the virtual environment's Python executable if you create one.

Run the following commands from the project root. The [default configuration](../configs/demo.json) is in configs/.

    python -B src/demo.py --config configs/demo.json
    python -B -m unittest discover -s tests -v

Input and default output paths in the configuration resolve from the configuration directory. An explicit --output override resolves from the current working directory. The command rejects output paths that identify the configuration or input file, and writes the report after a successful calculation.

## Inputs and output

The [synthetic fixture](../data/synthetic/demo.json) uses a local plane in metres with origin (0, 0) and no real-world coordinate reference system. It contains rectangular footprint bounds and storey counts, point coordinates and year–size tuples, fictional 1 km cell counts and hypothetical scenario intensities. The area proxy is in square metres and the intensities are in kWh/(m²·a). The report gives building heat in MWh/a and aggregate heat in GWh/a.

The command generates outputs/demo-results.json. The local virtual environment and generated output are excluded from tracking. The JSON labels the dataset synthetic and records the seed, number of draws, area factor and grid scales. For each building it reports assignment route, cross-owner flag, floor area, calculation status and B0/B1 heat. Missing estimates are null and omitted from the city aggregation.

| Synthetic scenario | B0 (GWh/a) | B1 (GWh/a) |
| --- | ---: | ---: |
| Existing | 0.314000 | 0.266900 |
| Usual | 0.189800 | 0.161330 |
| Advanced | 0.112600 | 0.095710 |

The default fixture contains ten fictional buildings. Eight are calculated, one is missing floor information and one is unresolved. S02 illustrates equal allocation. Its 400 m² area is split across two candidates with Existing intensities of 100 and 70 kWh/(m²·a), yielding 34 MWh/a for B0 and 28.9 MWh/a for B1. S09 illustrates an evidence point inside another footprint. The Existing B0 value is 16 MWh/a. Its fictional equal-probability year alternatives give B2 outcomes of 16 and 9.6 MWh/a.

The default seed is 20261125 and each dependence setting uses 2,000 draws. Existing P05–P95 widths on the reference runtime are approximately 0.0576 GWh/a for independent year ranks and 0.0704 GWh/a for grouped ranks. Reference JSON size is 6,685 bytes. Verify its SHA-256 using:

    python -B -c "from pathlib import Path; import hashlib; print(hashlib.sha256(Path('outputs/demo-results.json').read_bytes()).hexdigest())"

Expected on the tested runtime:

    bc5ad9541b79869e3ba0973d1922866edc318ac9442a4d3ec36f3c479b267cd5

## Verification and method scope

The 21 tests cover matching distance and boundary cases, ties, missing inputs, numeric validation, unit conversion, CLI output protection and reproducibility. B2 tests exercise asymmetric probabilities at and below cumulative boundaries, prescribed ranks in the grouped simulation, and joint year–size selection. They detect hybrid draws even when a missing lookup would otherwise route the draw through B0.

The demonstration implements selected thesis ideas with simplified geometry and supplied synthetic inputs. It uses a prefilled fallback size and abstains on tied cell-age counts. B2 shares a year rank within each 500 m block in the grouped setting, with a common stream of whole candidate tuples in both settings. The demonstration does not train attribute models, decompose variance or evaluate external consumption measurements.

[Project overview and method references](../README.md)
