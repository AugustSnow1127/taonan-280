# Taonan 280

Race-plan page for the 2026 TIS Taoyuan → Tainan 280 km ride (31 Oct 2026).

- 3D route map (MapLibre + free terrain tiles, no API keys)
- Line colour by strategy / grade / segment
- Pace simulator: ETA and cutoff buffer per stop
- Live wind forecast per segment (Open-Meteo, available ~16 days before race day)
- Prep tab: 20-day plan, fuel maths, gear checklist

## Run locally

    python -m http.server 8765
    # open http://localhost:8765/

## Data

- `data/route.json`, `data/stops.json` — built by `scripts/build_route.py` (OSM reconstruction, see `data/README.md`)
- `data/taonan-280.gpx` — `python scripts/export_gpx.py`
- Plan numbers and text — `js/plan.js`

TODO: replace the reconstructed route with the official GPX when the organiser releases it.
