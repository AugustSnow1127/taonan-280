#!/usr/bin/env python3
"""Fetch rider-relevant POIs within 500 m of data/route.json from OpenStreetMap (Overpass).

Re-run any time:  python scripts/fetch_pois.py
Raw Overpass responses are cached in scripts/.cache/ (prefix "poi_"); delete them to refresh.
Output: data/pois_raw.json  (unfiltered by brand; every POI has km along route + offset in m).
Only Python stdlib is used.
"""
import hashlib
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
CACHE = os.path.join(ROOT, "scripts", ".cache")
UA = {"User-Agent": "taonan-280-planner"}
OVERPASS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
MAX_DIST_M = 500
CHUNK_KM = 10
PAD_DEG = 0.007  # ~700 m, > MAX_DIST_M

BRAND_NAMES_RE = "麥當勞|McDonald|肯德基|KFC|摩斯|MOS|星巴克|Starbucks|路易莎|Louisa|85度C|85°C|85C"
FILTERS = [
    'nwr["shop"="convenience"]',
    'nwr["amenity"="fast_food"]',
    'nwr["amenity"~"^(restaurant|cafe)$"]["brand"]',
    'nwr["amenity"~"^(restaurant|cafe)$"]["name"~"' + BRAND_NAMES_RE + '",i]',
    'nwr["amenity"="fuel"]',
    'nwr["highway"~"^(services|rest_area)$"]',
    'nwr["amenity"="toilets"]',
    'nwr["amenity"="place_of_worship"]',
    'nwr["shop"="bicycle"]',
    'nwr["amenity"="police"]',
    'nwr["amenity"="drinking_water"]',
]

# (canonical brand, category hint or None, [match substrings, lower-case], [wikidata ids])
BRANDS = [
    ("7-Eleven", "convenience", ["7-eleven", "7-11", "7–eleven", "統一超商", "seven-eleven", "7eleven"], ["Q259340"]),
    ("FamilyMart", "convenience", ["familymart", "family mart", "全家"], ["Q10891564", "Q11247682"]),
    ("Hi-Life", "convenience", ["hi-life", "hilife", "萊爾富"], ["Q11326216"]),
    ("OK mart", "convenience", ["ok mart", "okmart", "ok超商", "ok便利", "來來超商"], ["Q10851968"]),
    ("Simple Mart", "convenience", ["simple mart", "美廉社"], ["Q15914017"]),
    ("McDonald's", None, ["mcdonald", "麥當勞"], ["Q38076"]),
    ("KFC", None, ["kfc", "肯德基", "kentucky"], ["Q524757"]),
    ("MOS Burger", None, ["mos burger", "摩斯"], ["Q1204169"]),
    ("Starbucks", None, ["starbucks", "星巴克"], ["Q37158"]),
    ("Louisa Coffee", None, ["louisa", "路易莎"], ["Q30924326"]),
    ("85°C", None, ["85°c", "85度c", "85c", "85度"], ["Q4644852"]),
    ("Burger King", None, ["burger king", "漢堡王"], ["Q177054"]),
    ("Subway", None, ["subway", "賽百味"], ["Q244457"]),
    ("CPC", "fuel", ["台灣中油", "中油", "cpc"], ["Q1050946"]),
    ("Formosa", "fuel", ["台塑", "formosa", "台亞"], ["Q1068051"]),
    ("NPC", "fuel", ["全國加油站", "全國"], []),
]


def log(*a):
    print(*a, flush=True)


STATS = {"queries": 0, "cache_hits": 0, "failed_attempts": [], "failed_chunks": []}


def overpass(q, tag):
    os.makedirs(CACHE, exist_ok=True)
    key = hashlib.sha1(q.encode("utf-8")).hexdigest()
    path = os.path.join(CACHE, "poi_" + key + ".json")
    STATS["queries"] += 1
    if os.path.exists(path):
        STATS["cache_hits"] += 1
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    payload = urllib.parse.urlencode({"data": q}).encode()
    last = None
    for i in range(30):
        ep = OVERPASS[i % len(OVERPASS)]
        try:
            req = urllib.request.Request(ep, data=payload, headers=UA)
            with urllib.request.urlopen(req, timeout=200) as r:
                res = json.load(r)
            rem = res.get("remark", "")
            if "runtime error" in rem or "timed out" in rem:
                raise RuntimeError("overpass remark: " + rem[:120])
            with open(path, "w", encoding="utf-8") as f:
                json.dump(res, f, ensure_ascii=False)
            log("   %s ok via %s (%d elements)" % (tag, ep.split("/")[2], len(res.get("elements", []))))
            return res
        except Exception as ex:  # noqa: BLE001
            last = ex
            STATS["failed_attempts"].append(dict(chunk=tag, endpoint=ep, error=str(ex)[:160]))
            log("   %s retry %d %s %s" % (tag, i + 1, ep.split("/")[2], ex))
            time.sleep(min(4 + i, 20))
    STATS["failed_chunks"].append(tag)
    log("   %s FAILED: %s" % (tag, last))
    return None


def load_route():
    with open(os.path.join(DATA, "route.json"), encoding="utf-8") as f:
        r = json.load(f)
    return r["points"], r["distance_km"]


def chunk_bboxes(pts):
    """Yield (tag, (s, w, n, e)) for CHUNK_KM slices; rounded outward to 0.01 deg."""
    total = pts[-1][3]
    k = 0.0
    while k < total:
        k2 = min(k + CHUNK_KM, total)
        sel = [p for p in pts if k - 0.1 <= p[3] <= k2 + 0.1]
        lats = [p[1] for p in sel]
        lons = [p[0] for p in sel]
        bb = (math.floor((min(lats) - PAD_DEG) * 100) / 100, math.floor((min(lons) - PAD_DEG) * 100) / 100,
              math.ceil((max(lats) + PAD_DEG) * 100) / 100, math.ceil((max(lons) + PAD_DEG) * 100) / 100)
        yield "km%03d-%03d" % (k, k2), bb
        k = k2


class Projector:
    """Nearest-segment projection with a coarse grid index over route segments."""
    CELL = 0.01  # deg (~1 km)

    def __init__(self, pts):
        self.pts = pts
        self.grid = {}
        for i in range(len(pts) - 1):
            (ax, ay), (bx, by) = pts[i][:2], pts[i + 1][:2]
            for gx in range(int(math.floor(min(ax, bx) / self.CELL)), int(math.floor(max(ax, bx) / self.CELL)) + 1):
                for gy in range(int(math.floor(min(ay, by) / self.CELL)), int(math.floor(max(ay, by) / self.CELL)) + 1):
                    self.grid.setdefault((gx, gy), []).append(i)

    def project(self, lat, lon):
        gx, gy = int(math.floor(lon / self.CELL)), int(math.floor(lat / self.CELL))
        cand = set()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cand.update(self.grid.get((gx + dx, gy + dy), ()))
        best = (None, float("inf"))
        coslat = math.cos(math.radians(lat))
        for i in sorted(cand):
            a, b = self.pts[i], self.pts[i + 1]
            Ax, Ay = (a[0] - lon) * coslat * 111320, (a[1] - lat) * 110540
            Bx, By = (b[0] - lon) * coslat * 111320, (b[1] - lat) * 110540
            dx, dy = Bx - Ax, By - Ay
            L2 = dx * dx + dy * dy
            t = 0.0 if L2 == 0 else max(0.0, min(1.0, -(Ax * dx + Ay * dy) / L2))
            d = math.hypot(Ax + t * dx, Ay + t * dy)
            if d < best[1]:
                best = (a[3] + t * (b[3] - a[3]), d)
        return best


def category(t):
    if t.get("shop") == "convenience":
        return "convenience"
    a = t.get("amenity")
    if a in ("fast_food", "restaurant", "cafe", "fuel", "toilets", "police", "drinking_water"):
        return a
    if a == "place_of_worship":
        return "place_of_worship"
    if t.get("highway") in ("services", "rest_area"):
        return "rest_area"
    if t.get("shop") == "bicycle":
        return "bicycle_shop"
    return "other"


def normalize_brand(t, cat):
    """Return (brand, source) where source is 'brand'|'brand:wikidata'|'name'|'operator'|None."""
    wd = t.get("brand:wikidata", "")
    if wd:
        for canon, _, _, ids in BRANDS:
            if wd in ids:
                return canon, "brand:wikidata"
    for src in ("brand", "brand:en", "brand:zh", "name", "name:en", "name:zh", "operator"):
        v = t.get(src, "").lower()
        if not v:
            continue
        for canon, hint, keys, _ in BRANDS:
            if hint and hint != cat:
                continue
            if canon == "NPC" and src not in ("brand", "operator") and "加油" not in v:
                continue  # "全國" alone is too generic outside brand/operator
            if any(k in v for k in keys):
                return canon, ("brand" if src.startswith("brand") else src)
    raw = t.get("brand") or t.get("brand:en")
    if raw:
        return raw, "brand"
    return None, None


def main():
    pts, total_km = load_route()
    log("route %.2f km, %d points" % (total_km, len(pts)))
    proj = Projector(pts)
    elements = {}
    chunks = list(chunk_bboxes(pts))
    for tag, bb in chunks:
        bbs = "(%.2f,%.2f,%.2f,%.2f)" % bb
        q = "[out:json][timeout:120];(" + "".join(f + bbs + ";" for f in FILTERS) + ");out center tags;"
        res = overpass(q, tag)
        if res is None:
            continue
        for e in res.get("elements", []):
            elements[(e["type"], e["id"])] = e
    log("unique OSM elements in bboxes: %d" % len(elements))

    pois = []
    for (typ, oid), e in elements.items():
        t = e.get("tags", {})
        c = e.get("center") or e
        if "lat" not in c:
            continue
        km, d = proj.project(c["lat"], c["lon"])
        if km is None or d > MAX_DIST_M:
            continue
        cat = category(t)
        brand, bsrc = normalize_brand(t, cat)
        if cat in ("restaurant", "cafe") and not brand:
            continue  # only branded restaurants / cafes were requested
        pois.append(dict(
            osm_id=typ + "/" + str(oid), category=cat,
            name=t.get("name") or None, name_en=t.get("name:en") or None,
            brand=brand, brand_source=bsrc, brand_tag=t.get("brand") or None,
            brand_wikidata=t.get("brand:wikidata") or None, branch=t.get("branch") or None,
            religion=t.get("religion") if cat == "place_of_worship" else None,
            highway=t.get("highway") if cat == "rest_area" else None,
            lon=round(c["lon"], 6), lat=round(c["lat"], 6),
            opening_hours=t.get("opening_hours") or None,
            km=round(km, 3), dist_m=round(d, 1)))
    pois.sort(key=lambda p: (p["km"], p["category"]))

    # duplicate candidates: same category + brand/name within 60 m
    dups = []
    for i, a in enumerate(pois):
        for b in pois[i + 1:]:
            if b["km"] - a["km"] > 0.3:
                break
            if a["category"] != b["category"]:
                continue
            same = (a["brand"] and a["brand"] == b["brand"]) or (a["name"] and a["name"] == b["name"])
            if not same:
                continue
            coslat = math.cos(math.radians(a["lat"]))
            dd = math.hypot((a["lon"] - b["lon"]) * coslat * 111320, (a["lat"] - b["lat"]) * 110540)
            if dd <= 60:
                dups.append(dict(a=a["osm_id"], b=b["osm_id"], category=a["category"],
                                 label=a["brand"] or a["name"], sep_m=round(dd, 1), km=a["km"]))

    out = dict(
        generated=time.strftime("%Y-%m-%dT%H:%M:%S"),
        route_km=total_km, max_dist_m=MAX_DIST_M, chunk_km=CHUNK_KM,
        source="OpenStreetMap contributors (ODbL), via Overpass API",
        overpass=dict(endpoints=OVERPASS, queries=STATS["queries"], cache_hits=STATS["cache_hits"],
                      failed_chunks=STATS["failed_chunks"], failed_attempts=STATS["failed_attempts"]),
        duplicate_candidates=dups,
        pois=pois)
    with open(os.path.join(DATA, "pois_raw.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    log("wrote data/pois_raw.json: %d POIs, %d duplicate candidates, %d failed chunks" % (
        len(pois), len(dups), len(STATS["failed_chunks"])))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    main()
