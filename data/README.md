# Route data — 2026 TIS Taoyuan → Tainan 280 km

**This is an OpenStreetMap reconstruction of the official route description, NOT the official GPX.**
Distances, checkpoint km, elevation and stores are approximate. Replace with the organiser's GPX when it is published.
<!-- TODO: swap in the official GPX once TIS releases it, and re-check checkpoint km -->

Regenerate with `python scripts/build_route.py` (stdlib only; responses cached in `scripts/.cache/`, delete it to refresh).

## Files

- `route.json` — `{"distance_km", "points": [[lon, lat, ele_m, km], ...]}`, resampled every 100 m.
- `stops.json` — official points (`start`, `cp1`, `cp2`, `finish`, with `official_km` and `cutoff`), convenience stores (`s1`..`s4`) and rest areas (`r1`..), sorted by `km` along this reconstructed route.

## How it was built

1. **Official points** — geocoded with Nominatim (start, CP1, CP2); the finish (正統鹿耳門聖母廟) has no Nominatim hit and was taken from OSM way 163307398 via Overpass.
2. **Routing** — OSRM bike profile (`routing.openstreetmap.de/routed-bike`), with shaping waypoints to follow the described roads: Prov. Hwy 31 (高鐵南路) → Hwy 15 (Xinfeng / Hsinchu coast) → Hwy 61 corridor (Miaoli / Taichung) → Hwy 17 (臨港路 in Taichung, then Changhua / Yunlin / Chiayi / Tainan).
3. **Elevation** — Open-Meteo elevation API (Copernicus DEM, ~90 m) sampled every 200 m, then a 5-sample (~1 km) moving average. Gain figures from a 90 m DEM on a flat coastal route are rough.
4. **Stores / rest areas** — Overpass API, `shop=convenience` with 7-Eleven / 統一超商 / FamilyMart / 全家 brand or name, within 300 m of the route, closest to target km 90 / 125 / 205 / 245. Rest areas: `highway=rest_area|services` or name containing 休息站, within 600 m of the route between CP1 and CP2.

## Known deviations

- Hwy 61 corridor: the reconstruction follows Hwy 61 surface sections / side roads from Hsinchu to about km 79 (Tongxiao, Miaoli). From km ~79 to ~112 (Tongxiao → Yuanli → Da'an → Dajia → Qingshui) OSRM uses Prov. Hwy 1 and 苗37 instead, because the Hwy 61 mainline there is a `trunk` expressway mostly tagged `bicycle=no`. The organiser's "Hwy 61 side road" through this stretch may differ.
- Hwy 17 is entered at its northern end (臨港路, Qingshui) and followed to Annan; shaping points on the divided highway use OSRM `bearings` so they snap to the southbound carriageway.
- Checkpoint km vs official: CP1 45.98 (44.8), CP2 165.01 (163.0), finish 280.30 (280.0).
- Da'an Rest Area (大安休息站) sits on the Hwy 61 mainline ~440 m from this route; check bicycle access before relying on it. The Lukang rest area (台61線179K) is tagged "under construction" in OSM.
- Elevation min of about -4 m near Budai is a DEM artefact over fish ponds / coast.

## Sources

- © OpenStreetMap contributors (ODbL) — map data, Nominatim, Overpass
- OSRM / FOSSGIS routing service (routing.openstreetmap.de)
- Open-Meteo elevation API (Copernicus DEM GLO-90)
- Official route description and checkpoints: 2026 TIS 桃園→台南 280 km event information
