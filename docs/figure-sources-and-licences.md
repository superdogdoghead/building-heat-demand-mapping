# Figure sources and licences

## Figure 1 · Flensburg study area

The map uses two official ALKIS geometry layers supplied by the Landesamt für Vermessung und Geoinformation Schleswig-Holstein (LVermGeo SH) through the simplified ALKIS OGC API. Both layers carry **© GeoBasis-DE / LVermGeo SH / CC BY 4.0 (Quelle verändert)**. [Provider attribution terms](https://geodaten.schleswig-holstein.de/gaialight-sh/_apps/dladownload/lizenz.html)

| Layer | Source | Licence | Acquisition evidence (UTC) | Processing and map modifications |
| --- | --- | --- | --- | --- |
| Municipal boundary | [Verwaltungseinheit](https://dienste.gdi-sh.de/ogcapi_aaa/alkis-vereinf-gid7/v1/collections/verwaltungseinheit?f=json) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | 2026-03-20. The archived OGC feature response records `16:35:54Z`. | Selected the Flensburg municipality (AGS 01001000) from the local-area query. The retained boundary was reprojected from EPSG:4326 to EPSG:25832 and drawn as an outline in both panels. |
| Building footprints | [Gebäude, Bauwerk](https://dienste.gdi-sh.de/ogcapi_aaa/alkis-vereinf-gid7/v1/collections/gebaeude_bauwerk?f=json) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | Acquired by 2026-03-20. The earliest retained raw GeoPackage export records `17:46:40.429Z`. The original request time is unrecorded. | The source layer was reprojected from EPSG:3857 to EPSG:25832. The rendering uses the retained cleaned Flensburg-area subset and draws its polygons in a uniform fill. That extract retains seven features with neighbouring municipality codes. |

The acquisition entries describe the archived response and export. The collection metadata and licence links were rechecked on 2026-11-25. The cartography adds the overview and inset frames, inset locator, legend, grid-north arrow and scale bars. Only geometry from the retained extracts was used for rendering. The published repository contains the rendered map PNG. The underlying geographic extracts, building attributes and real building-level heat-demand estimates are outside the published scope.

## Published figures and reuse

The author approved all five figures for public display in this repository.

| Figure | Source |
| --- | --- |
| Figure 1 cartography | Original portfolio rendering of the two official geometry layers |
| Figure 2 · Research workflow | Original portfolio schematic of the thesis methods |
| Figure 3 · Spatial matching | Original diagram using the included fictional fixture for containment, nearest-neighbour fallback with an ownership conflict, and abstention |
| Figure 4 · Synthetic uncertainty | Original chart of the included synthetic simulation |
| Figure 5 · Synthetic heat scenarios | Original chart of the included synthetic simulation |

The author reserves the rights they control in the original figure designs. The official geographic layers in Figure 1 retain CC BY 4.0. The existing [MIT licence](../LICENSE) continues to cover the original V1.0 code and accompanying materials.

The thesis source credits in the README are bibliographic references. The showcase uses official geographic layers only in Figure 1 and synthetic numerical inputs in Figures 3–5.

[Asset licence scope and reuse permissions](../ASSET_LICENSES.md)
