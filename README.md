# Evidence-Conditioned Building-Level Residential Heat-Demand Mapping

This standalone Python demonstration shows how incomplete building evidence can be turned into traceable annual useful space-heating estimates. It uses fictional footprints, point attributes, grid counts and reference intensities. Every result produced by the example describes that fictional dataset.

## Research context

The project draws on Jianing Zhang's TUM ESPACE master's thesis, *Urban Building Energy Mapping and the Development of a Baseline Heat Demand Dataset* (September 2026). The thesis studied residential buildings in Flensburg, Germany. It examined how to combine spatial evidence with different levels of support and how area assumptions, uncertain attributes and spatial dependence affect aggregated heat-demand estimates.

The thesis used official building geometry, candidate attributes from ETHOS.BUILDA, Zensus 2022 construction-age statistics and TABULA building typologies. This portfolio project is a separate implementation of selected methods on synthetic data. It can be run without the thesis inputs, original research software or GIS tools.

## Methods demonstrated

1. **Spatial matching.** Associate synthetic points with rectangular footprints using containment and nearest-distance rules. Preserve multiple candidate tuples and flag cross-building ownership risk.
2. **Statistical fallback.** Use a dominant age class from a fictional 1 km cell when usable point evidence is unavailable. Tied or empty cells can leave an estimate unresolved.
3. **B0 and B1.** Compute deterministic annual useful heat from a floor-area proxy and fictional archetype intensities. B1 applies a uniform 0.85 area factor with the attributes held fixed.
4. **B2.** Sample retained year–size candidate tuples jointly and propagate supplied year probabilities or accepted size alternatives. Compare independent year draws with draws that share a random rank within 500 m blocks.

## Quick start

Use Python 3.11 or newer. The demo and tests use only the standard library. From this directory, run:

    python -B src/demo.py --config configs/demo.json
    python -B -m unittest discover -s tests -v

The first command writes outputs/demo-results.json locally. The default fixture has ten fictional buildings, eight with heat estimates, one with missing floor information and one unresolved. Its Existing B0 and B1 totals are 0.314 and 0.2669 GWh/a. The 21 tests check assignment and abstention, unit conversion, CLI behavior, random-rank boundaries and preservation of candidate tuples.

See the [reproducibility guide](docs/reproducibility.md) for the input, output conventions, and reference hash.

## Limitations

The demo uses rectangular footprints in a fictional local metre grid and takes year probabilities and size alternatives as inputs. The intensities illustrate a calculation. They do not represent official TABULA values or measured heat. The B2 percentiles describe the configured simulation. Spatial assignment checks provide evidence about geometry, while attribute accuracy would require independent reference data. The demo does not reproduce the full thesis workflow.

## Citation and acknowledgements

Zhang, Jianing. (2026). *Urban Building Energy Mapping and the Development of a Baseline Heat Demand Dataset*. Master's thesis, Technical University of Munich, Earth Oriented Space Science and Technology (ESPACE).

The thesis drew on building geometry from [LVermGeo Schleswig-Holstein](https://geodaten.schleswig-holstein.de/gaialight-sh/_apps/dladownload/), building attributes from [Forschungszentrum Jülich's ETHOS.BUILDA project](https://ethos-builda.fz-juelich.de/), and age statistics from [Zensus 2022](https://www.destatis.de/DE/Themen/Gesellschaft-Umwelt/Bevoelkerung/Zensus2022/_inhalt.html). Building typology and scenario concepts are credited to [TABULA and Institut Wohnen und Umwelt](https://www.iwu.de/index.php?id=205).

## Licence and development

Jianing Zhang developed this synthetic portfolio demonstration with AI assistance. The [MIT licence](LICENSE) covers the original code and tests, documentation, configuration and synthetic fixture included here. The thesis, referenced third-party datasets and methods, and any other external materials remain subject to their own terms.
