"""Export data/route.json + data/stops.json to a GPX file for the head unit."""
import json
from pathlib import Path
from xml.sax.saxutils import escape

root = Path(__file__).resolve().parent.parent
route = json.loads((root / "data/route.json").read_text(encoding="utf8"))
stops = json.loads((root / "data/stops.json").read_text(encoding="utf8"))

out = ['<?xml version="1.0" encoding="UTF-8"?>',
       '<gpx version="1.1" creator="taonan-280" xmlns="http://www.topografix.com/GPX/1/1">',
       '<metadata><name>Taonan 280 (OSM reconstruction)</name></metadata>']
for s in stops:
    out.append('<wpt lat="%s" lon="%s"><name>%s</name><desc>km %.1f%s</desc></wpt>' % (
        s["lat"], s["lon"], escape(s["name_en"]), s["km"],
        (" cutoff " + s["cutoff"]) if s.get("cutoff") else ""))
out.append('<trk><name>Taonan 280</name><trkseg>')
for lon, lat, ele, _km in route["points"]:
    out.append('<trkpt lat="%s" lon="%s"><ele>%s</ele></trkpt>' % (lat, lon, ele))
out.append('</trkseg></trk></gpx>')
(root / "data/taonan-280.gpx").write_text("\n".join(out), encoding="utf8")
print("wrote", len(route["points"]), "points,", len(stops), "waypoints")
