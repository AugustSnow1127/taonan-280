#!/usr/bin/env python3
"""Build route + stop data for the 2026 TIS Taoyuan -> Tainan 280 km ride.

This is an OpenStreetMap-based reconstruction of the official route description,
NOT the official GPX. Re-run any time:  python scripts/build_route.py
Network responses are cached in scripts/.cache/ (delete it to force fresh data).

Sources:
  - Geocoding:  Nominatim (https://nominatim.openstreetmap.org)
  - Routing:    OSRM bike profile (https://routing.openstreetmap.de/routed-bike)
  - Elevation:  Open-Meteo elevation API (Copernicus DEM GLO-90)
  - POIs:       Overpass API (OSM shop=convenience / highway=rest_area)
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
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# ---------------------------------------------------------------- official points
# Coordinates verified via Nominatim / Overpass (see verify_officials()).
OFFICIALS = [
    dict(id="start", name_en="Qingpu Start", name_zh="青埔棒球場 (樂天桃園棒球場)",
         lat=25.00098, lon=121.20039, official_km=0.0, cutoff="05:30",
         query="樂天桃園棒球場"),
    dict(id="cp1", name_en="CP1 Hsinchu Coast", name_zh="新竹市 風情海岸",
         lat=24.77880, lon=120.91445, official_km=44.8, cutoff="08:30",
         query="風情海岸 新竹市"),
    dict(id="cp2", name_en="CP2 Wanggong", name_zh="彰化芳苑 王功福海宮",
         lat=23.95323, lon=120.33471, official_km=163.0, cutoff="14:30",
         query="王功福海宮"),
    dict(id="finish", name_en="Luermen Finish", name_zh="正統鹿耳門聖母廟",
         lat=23.06785, lon=120.12721, official_km=280.0, cutoff="21:00",
         query=None),  # Nominatim has no hit; OSM way 163307398 "土城正統鹿耳門聖母廟"
]

# ---------------------------------------------------------------- shaping waypoints
# (lat, lon). Inserted between officials so OSRM follows the described highways.
WAYPOINTS_START_CP1 = [
    (24.96616, 121.16789),  # Hwy 31 高鐵南路五段
    (24.93519, 121.10755),  # Hwy 31 高鐵南路八段
    (24.90544, 121.08485),  # Hwy 31 高鐵南路十段
    (24.87720, 120.95460),  # Hwy 15 西濱路二段 (Xinfeng)
    (24.83340, 120.92900),  # Hwy 15 西濱路一段 (Hsinchu Nanliao)
]
WAYPOINTS_CP1_CP2 = [
    # Hwy 61 corridor (Miaoli / Taichung): mainline is mostly bicycle=no in OSM,
    # so OSRM is left to pick the frontage / parallel roads by itself.
    # NOTE: no explicit point at the Hwy 17 north end (臨港路七段, 24.3042,120.5945):
    # it added a ~4 km detour; OSRM still enters Hwy 17 there via Hwy 1 (Qingshui).
    (24.28920, 120.54050),  # Hwy 17 臨港路五段
    (24.23750, 120.51740),  # Hwy 17 臨港路三段
    (24.20400, 120.50800),  # Hwy 17 臨港路一段
    (24.16600, 120.48850),  # Hwy 17 中興路二段 (Shengang)
    (24.12510, 120.45930),  # Hwy 17 沿海路一段
    (24.07600, 120.41880),  # Hwy 17 臨海路三段 (Lukang)
    (24.01820, 120.39520),  # Hwy 17 沿海路一段 (Fangyuan)
]
WAYPOINTS_CP2_FINISH = [
    (23.86690, 120.29480),  # Hwy 17 西部濱海公路 (Dacheng)
    (23.77520, 120.26690),  # Hwy 17 (Mailiao)
    (23.72070, 120.21560),  # Hwy 17 (Mailiao / Taixi)
    (23.65900, 120.17710),  # Hwy 17 中華路 (Taixi)
    (23.59150, 120.15510),  # Hwy 17 (Kouhu)
    (23.51330, 120.17720),  # Hwy 17 雲嘉大橋
    (23.42900, 120.17270),  # Hwy 17 (Dongshi, Chiayi)
    (23.34840, 120.17720),  # Hwy 17 (Budai)
    (23.27280, 120.12690),  # Hwy 17 (Beimen)
    (23.19330, 120.13350),  # Hwy 17 (Jiangjun)
    (23.10920, 120.13160),  # Hwy 17 (Qigu / Annan)
    # Shaping points on divided Hwy 17 are sent with an OSRM `bearings` hint (direction
    # of travel +/-90 deg) so they snap to the southbound carriageway (no U-turn spurs).
]

STORE_TARGETS_KM = [90, 125, 205, 245]
STORE_RADIUS_M = 300
STORE_WINDOW_KM = 10  # search target +/- this window along the route
REST_SEARCH_KM = (44, 165)  # Hwy 61 corridor (CP1 -> CP2)
REST_RADIUS_M = 600


# ---------------------------------------------------------------- helpers
def log(*a):
    print(*a, flush=True)


def cached_get(url, data=None, timeout=120, retries=8, sleep=0.0):
    os.makedirs(CACHE, exist_ok=True)
    key = hashlib.sha1((url + "|" + (data or "")).encode("utf-8")).hexdigest()
    path = os.path.join(CACHE, key + ".json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    last = None
    for i in range(retries):
        try:
            body = data.encode("utf-8") if data is not None else None
            req = urllib.request.Request(url, data=body, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                res = json.load(r)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(res, f, ensure_ascii=False)
            if sleep:
                time.sleep(sleep)
            return res
        except Exception as ex:  # noqa: BLE001
            last = ex
            log("   retry", i + 1, url[:60], ex)
            time.sleep(3 + 2 * i)
    raise RuntimeError("request failed: " + url + " " + str(last))


def overpass(q):
    payload = urllib.parse.urlencode({"data": q})
    os.makedirs(CACHE, exist_ok=True)
    key = hashlib.sha1(q.encode("utf-8")).hexdigest()
    path = os.path.join(CACHE, "ov_" + key + ".json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    last = None
    for i in range(40):
        ep = OVERPASS[i % len(OVERPASS)]
        try:
            req = urllib.request.Request(ep, data=payload.encode(), headers=UA)
            with urllib.request.urlopen(req, timeout=180) as r:
                res = json.load(r)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(res, f, ensure_ascii=False)
            return res
        except Exception as ex:  # noqa: BLE001
            last = ex
            log("   overpass retry", i + 1, ep, ex)
            time.sleep(min(5 + i, 20))
    raise RuntimeError("overpass failed: " + str(last))


def hav(lat1, lon1, lat2, lon2):
    R = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def bearing(a, b):
    """Initial bearing (deg) from a=(lat, lon) to b=(lat, lon)."""
    la1, la2 = math.radians(a[0]), math.radians(b[0])
    dl = math.radians(b[1] - a[1])
    y = math.sin(dl) * math.cos(la2)
    x = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def project(route, cum, lat, lon, km_lo=None, km_hi=None):
    """Nearest point on polyline. Returns (km_along, dist_m, (lat, lon))."""
    best = (None, float("inf"), None)
    coslat = math.cos(math.radians(lat))
    for i in range(len(route) - 1):
        if km_lo is not None and cum[i + 1] / 1000 < km_lo:
            continue
        if km_hi is not None and cum[i] / 1000 > km_hi:
            break
        (ax, ay), (bx, by) = route[i], route[i + 1]  # lon, lat
        # local equirectangular plane (metres)
        Ax, Ay = (ax - lon) * coslat * 111320, (ay - lat) * 110540
        Bx, By = (bx - lon) * coslat * 111320, (by - lat) * 110540
        dx, dy = Bx - Ax, By - Ay
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, -(Ax * dx + Ay * dy) / L2))
        px, py = Ax + t * dx, Ay + t * dy
        d = math.hypot(px, py)
        if d < best[1]:
            km = (cum[i] + t * (cum[i + 1] - cum[i])) / 1000
            best = (km, d, (ay + t * (by - ay), ax + t * (bx - ax)))
    return best


def interp_at(route, cum, s):
    """Point (lon, lat) at distance s metres along the route."""
    lo, hi = 0, len(cum) - 1
    while lo < hi - 1:
        mid = (lo + hi) // 2
        if cum[mid] <= s:
            lo = mid
        else:
            hi = mid
    seg = cum[hi] - cum[lo]
    t = 0 if seg == 0 else (s - cum[lo]) / seg
    (ax, ay), (bx, by) = route[lo], route[hi]
    return ax + t * (bx - ax), ay + t * (by - ay)


# ---------------------------------------------------------------- steps
def verify_officials():
    log("== 1. Official points (Nominatim check)")
    for p in OFFICIALS:
        msg = "(no Nominatim query; from OSM Overpass)"
        if p["query"]:
            url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
                {"q": p["query"], "format": "json", "limit": 1, "countrycodes": "tw"})
            res = cached_get(url, sleep=1.1)
            if res:
                d = hav(p["lat"], p["lon"], float(res[0]["lat"]), float(res[0]["lon"]))
                msg = "Nominatim %.5f,%.5f (offset %.0f m)" % (
                    float(res[0]["lat"]), float(res[0]["lon"]), d)
            else:
                msg = "Nominatim: no result"
        log("  %-7s %-26s %.5f, %.5f  %s" % (p["id"], p["name_zh"], p["lat"], p["lon"], msg))


def build_route():
    log("== 2. OSRM bike routing")
    o = OFFICIALS
    wps = ([(o[0]["lat"], o[0]["lon"])] + WAYPOINTS_START_CP1 + [(o[1]["lat"], o[1]["lon"])]
           + WAYPOINTS_CP1_CP2 + [(o[2]["lat"], o[2]["lon"])] + WAYPOINTS_CP2_FINISH
           + [(o[3]["lat"], o[3]["lon"])])
    coords = ";".join("%.5f,%.5f" % (lon, lat) for lat, lon in wps)
    official_set = {(p["lat"], p["lon"]) for p in o}
    bearings = []
    for i, w in enumerate(wps):
        if w in official_set:
            bearings.append("")  # officials: snap anywhere
        else:
            bearings.append("%d,90" % round(bearing(wps[i - 1], wps[i + 1])))
    url = ("https://routing.openstreetmap.de/routed-bike/route/v1/driving/" + coords
           + "?overview=full&geometries=geojson&steps=true&bearings=" + ";".join(bearings))
    res = cached_get(url, timeout=180)
    if res.get("code") != "Ok":
        raise RuntimeError("OSRM error: " + str(res.get("code")))
    r = res["routes"][0]
    line = r["geometry"]["coordinates"]  # [lon, lat]
    # drop consecutive duplicates
    route = [line[0]]
    for p in line[1:]:
        if p != route[-1]:
            route.append(p)
    cum = [0.0]
    for a, b in zip(route, route[1:]):
        cum.append(cum[-1] + hav(a[1], a[0], b[1], b[0]))
    log("  OSRM distance %.2f km, geometry length %.2f km, %d vertices" % (
        r["distance"] / 1000, cum[-1] / 1000, len(route)))
    # road refs summary per leg + step-level overview
    road_log = []
    km = 0.0
    for leg in r["legs"]:
        for s in leg["steps"]:
            road_log.append((km, s.get("ref") or "", s.get("name") or "", s["distance"]))
            km += s["distance"] / 1000
    return route, cum, r, road_log


def detect_overlaps(route, cum, near_m=25, min_gap_m=400):
    """Flag places where the route passes again within near_m of a point it already
    visited >= min_gap_m earlier (out-and-back spurs / U-turns)."""
    cell = 0.0003
    grid = {}
    hits = []
    for i, (lon, lat) in enumerate(route):
        gx, gy = int(lon / cell), int(lat / cell)
        found = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in grid.get((gx + dx, gy + dy), ()):
                    if cum[i] - cum[j] >= min_gap_m and hav(lat, lon, route[j][1], route[j][0]) < near_m:
                        found = j
                        break
                if found is not None:
                    break
            if found is not None:
                break
        if found is not None:
            hits.append((cum[found] / 1000, cum[i] / 1000, lat, lon))
        grid.setdefault((gx, gy), []).append(i)
    # merge consecutive hits into spans
    spans = []
    for h in hits:
        if spans and h[1] - spans[-1][3] < 0.3:
            spans[-1][3] = h[1]
        else:
            spans.append([h[0], h[2], h[3], h[1]])
    return spans  # [first_visit_km, lat, lon, revisit_end_km]


def elevation(route, cum):
    log("== 3. Elevation (Open-Meteo, 200 m sampling)")
    total = cum[-1]
    n = int(total // 200) + 1
    s_list = [min(i * 200.0, total) for i in range(n)]
    if s_list[-1] < total:
        s_list.append(total)
    pts = [interp_at(route, cum, s) for s in s_list]
    ele = []
    for k in range(0, len(pts), 100):
        chunk = pts[k:k + 100]
        url = "https://api.open-meteo.com/v1/elevation?" + urllib.parse.urlencode({
            "latitude": ",".join("%.5f" % p[1] for p in chunk),
            "longitude": ",".join("%.5f" % p[0] for p in chunk),
        })
        res = cached_get(url, sleep=0.3)
        ele.extend(float(e) for e in res["elevation"])
    # light smoothing: centred 5-sample moving average (~1 km window)
    sm = []
    for i in range(len(ele)):
        w = ele[max(0, i - 2): i + 3]
        sm.append(sum(w) / len(w))
    gain = sum(max(0.0, b - a) for a, b in zip(sm, sm[1:]))
    loss = sum(max(0.0, a - b) for a, b in zip(sm, sm[1:]))
    log("  samples %d  raw min/max %.1f/%.1f  smoothed min/max %.1f/%.1f  gain %.0f m  loss %.0f m" % (
        len(ele), min(ele), max(ele), min(sm), max(sm), gain, loss))
    return s_list, sm, dict(min=min(sm), max=max(sm), gain=gain, loss=loss,
                            raw_min=min(ele), raw_max=max(ele))


def ele_at(s_list, sm, s):
    if s <= 0:
        return sm[0]
    if s >= s_list[-1]:
        return sm[-1]
    i = int(s // 200)
    i = min(i, len(s_list) - 2)
    t = (s - s_list[i]) / (s_list[i + 1] - s_list[i])
    return sm[i] + t * (sm[i + 1] - sm[i])


def overpass_corridor(route, cum, km_lo, km_hi, filters, chunk_km=10, pad_deg=0.006):
    """Query Overpass with small bboxes covering the route between km_lo and km_hi.
    bboxes are rounded outward to 0.01 deg so the cache survives small route edits.
    filters: list of Overpass selectors, e.g. 'node["shop"="convenience"]'."""
    elements = {}
    k = max(0.0, km_lo)
    while k < min(km_hi, cum[-1] / 1000):
        k2 = min(k + chunk_km, km_hi)
        lats, lons = [], []
        s = k * 1000
        while s <= k2 * 1000:
            lon, lat = interp_at(route, cum, min(s, cum[-1]))
            lats.append(lat)
            lons.append(lon)
            s += 200
        south = math.floor((min(lats) - pad_deg) * 100) / 100
        west = math.floor((min(lons) - pad_deg) * 100) / 100
        north = math.ceil((max(lats) + pad_deg) * 100) / 100
        east = math.ceil((max(lons) + pad_deg) * 100) / 100
        bb = "(%.2f,%.2f,%.2f,%.2f)" % (south, west, north, east)
        q = "[out:json][timeout:30];(" + "".join(f + bb + ";" for f in filters) + ");out center tags;"
        for e in overpass(q)["elements"]:
            elements[(e["type"], e["id"])] = e
        k = k2
    return list(elements.values())


def english_area(lat, lon):
    url = "https://nominatim.openstreetmap.org/reverse?" + urllib.parse.urlencode({
        "lat": "%.5f" % lat, "lon": "%.5f" % lon, "format": "json", "zoom": 14,
        "accept-language": "en"})
    try:
        res = cached_get(url, sleep=1.1)
    except RuntimeError:
        return None
    a = res.get("address", {})
    for k in ("village", "suburb", "town", "city_district", "county", "city"):
        v = a.get(k)
        if v and all(ord(c) < 128 for c in v):
            for suf in (" Township", " District", " Village", " City", " County", " Town"):
                v = v.replace(suf, "")
            return v.strip()
    return None


def find_stores(route, cum):
    log("== 4. Convenience stores (Overpass)")
    BRAND_RE = "7-Eleven|7-ELEVEN|7-11|統一超商|FamilyMart|全家"
    stores = []
    for n, target in enumerate(STORE_TARGETS_KM, 1):
        lo, hi = target - STORE_WINDOW_KM, target + STORE_WINDOW_KM
        elems = overpass_corridor(route, cum, lo, hi,
                                  ['node["shop"="convenience"]', 'way["shop"="convenience"]'])
        cands = []
        for e in elems:
            t = e.get("tags", {})
            label = " ".join(t.get(k, "") for k in ("brand", "name", "brand:en", "name:en", "operator"))
            if not any(b.lower() in label.lower() for b in BRAND_RE.split("|")):
                continue
            c = e.get("center", e)
            km, d, _ = project(route, cum, c["lat"], c["lon"], lo - 1, hi + 1)
            if km is None or d > STORE_RADIUS_M:
                continue
            cands.append(dict(km=km, off_m=d, lat=c["lat"], lon=c["lon"], tags=t, osm=e["type"] + "/" + str(e["id"])))
        if not cands:
            log("  target %d km: no branded store within %d m" % (target, STORE_RADIUS_M))
            continue
        cands.sort(key=lambda c: (abs(c["km"] - target), c["off_m"]))
        best = cands[0]
        t = best["tags"]
        is711 = any(x in (t.get("brand", "") + t.get("name", "") + t.get("brand:en", ""))
                    for x in ("7-Eleven", "7-ELEVEN", "7-11", "統一超商"))
        brand_en = "7-Eleven" if is711 else "FamilyMart"
        brand_zh = "7-ELEVEN" if is711 else "全家便利商店"
        branch = t.get("branch") or ""
        area = english_area(best["lat"], best["lon"]) or ("km " + str(target))
        name_zh = (brand_zh + " " + branch).strip() if branch else brand_zh
        log("  target %d km -> %s %s @ %.2f km, %.0f m off route (%d candidates) %s" % (
            target, brand_en, name_zh, best["km"], best["off_m"], len(cands), best["osm"]))
        stores.append(dict(type="store", name_en=brand_en + " " + area, name_zh=name_zh,
                           km=best["km"], lat=best["lat"], lon=best["lon"],
                           off_route_m=round(best["off_m"]), osm=best["osm"], target_km=target))
    return stores


def find_rest(route, cum):
    log("== 4b. Rest areas on Hwy 61 corridor (Overpass)")
    lo, hi = REST_SEARCH_KM
    elems = overpass_corridor(route, cum, lo, hi,
                              ['nwr["highway"~"^(rest_area|services)$"]', 'nwr["name"~"休息站"]'],
                              chunk_km=20)
    out = []
    seen = set()
    for e in elems:
        t = e.get("tags", {})
        c = e.get("center", e)
        if "lat" not in c:
            continue
        name = t.get("name", "")
        if t.get("highway") == "motorway_junction":
            continue  # an exit named after the rest area, not the facility itself
        km, d, _ = project(route, cum, c["lat"], c["lon"], lo - 1, hi + 1)
        log("  candidate %s %s (%s) km %.2f, %.0f m off" % (
            e["type"], e["id"], name or "(unnamed " + t.get("highway", "?") + ")", km, d))
        if d > REST_RADIUS_M or not name or name in seen:
            continue
        seen.add(name)
        out.append(dict(type="rest", name_zh=name, name_en=t.get("name:en") or None,
                        km=km, lat=c["lat"], lon=c["lon"], off_route_m=round(d),
                        osm=e["type"] + "/" + str(e["id"])))
    # Also explicitly check 大安休息站 via Nominatim
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": "大安休息站", "format": "json", "limit": 3, "countrycodes": "tw"})
    for h in cached_get(url, sleep=1.1):
        if h.get("type") == "motorway_junction":
            continue
        la, lo_ = float(h["lat"]), float(h["lon"])
        km, d, _ = project(route, cum, la, lo_)
        log("  Nominatim 大安休息站: %.5f,%.5f -> km %.2f, %.0f m off route" % (la, lo_, km, d))
        if d <= REST_RADIUS_M and "大安休息站" not in seen:
            seen.add("大安休息站")
            out.append(dict(type="rest", name_zh="大安休息站", name_en=None, km=km,
                            lat=la, lon=lo_, off_route_m=round(d), osm=h.get("osm_type", "") + "/" + str(h.get("osm_id"))))
    for r in out:
        if not r["name_en"]:
            area = english_area(r["lat"], r["lon"])
            r["name_en"] = ((area + " ") if area else "") + "Rest Area"
        if "施工" in r["name_zh"]:
            r["name_en"] += " (under construction)"
    out.sort(key=lambda r: r["km"])
    return out


def main():
    os.makedirs(DATA, exist_ok=True)
    verify_officials()
    route, cum, osrm, road_log = build_route()
    total_km = cum[-1] / 1000

    # official checkpoints along our route
    log("  Official checkpoints along reconstructed route:")
    off_kms = {}
    prev = 0.0
    for p in OFFICIALS:
        if p["id"] == "start":
            km, d = 0.0, hav(p["lat"], p["lon"], route[0][1], route[0][0])
        elif p["id"] == "finish":
            km, d = total_km, hav(p["lat"], p["lon"], route[-1][1], route[-1][0])
        else:
            km, d, _ = project(route, cum, p["lat"], p["lon"], prev)
        off_kms[p["id"]] = km
        prev = km
        log("    %-7s route km %7.2f  official %6.1f  diff %+6.2f  (%.0f m from route)" % (
            p["id"], km, p["official_km"], km - p["official_km"], d))

    spans = detect_overlaps(route, cum)
    log("  Overlap / out-and-back spans (route revisits itself):")
    for s in spans:
        log("    first pass km %.2f, revisited until km %.2f near %.5f,%.5f" % (s[0], s[3], s[1], s[2]))
    if not spans:
        log("    none")

    log("  Road summary (steps >= 3 km):")
    for km, ref, name, dist in road_log:
        if dist >= 3000:
            log("    km %6.1f  %-8s %-14s %.1f km" % (km, ref, name, dist / 1000))

    s_list, sm, estats = elevation(route, cum)

    # route.json: resample every 100 m
    pts = []
    s = 0.0
    while s < cum[-1]:
        lon, lat = interp_at(route, cum, s)
        pts.append([round(lon, 5), round(lat, 5), round(ele_at(s_list, sm, s), 1), round(s / 1000, 3)])
        s += 100.0
    pts.append([round(route[-1][0], 5), round(route[-1][1], 5), round(sm[-1], 1), round(total_km, 3)])
    with open(os.path.join(DATA, "route.json"), "w", encoding="utf-8") as f:
        json.dump({"distance_km": round(total_km, 3), "points": pts}, f, separators=(",", ":"))
    log("  wrote data/route.json (%d points)" % len(pts))

    stores = find_stores(route, cum)
    rests = find_rest(route, cum)

    stops = []
    for p in OFFICIALS:
        stops.append(dict(id=p["id"], name_en=p["name_en"], name_zh=p["name_zh"], type="official",
                          km=round(off_kms[p["id"]], 2), official_km=p["official_km"],
                          lon=round(p["lon"], 5), lat=round(p["lat"], 5), cutoff=p["cutoff"]))
    for i, st in enumerate(sorted(stores, key=lambda x: x["km"]), 1):
        stops.append(dict(id="s%d" % i, name_en=st["name_en"], name_zh=st["name_zh"], type="store",
                          km=round(st["km"], 2), lon=round(st["lon"], 5), lat=round(st["lat"], 5)))
    for i, r in enumerate(rests, 1):
        stops.append(dict(id="r%d" % i, name_en=r["name_en"], name_zh=r["name_zh"], type="rest",
                          km=round(r["km"], 2), lon=round(r["lon"], 5), lat=round(r["lat"], 5)))
    stops.sort(key=lambda x: x["km"])
    with open(os.path.join(DATA, "stops.json"), "w", encoding="utf-8") as f:
        json.dump(stops, f, ensure_ascii=False, indent=2)
    log("  wrote data/stops.json (%d stops)" % len(stops))
    for st in stops:
        log("    %-6s %-8s km %7.2f  %.5f,%.5f  %s / %s" % (
            st["id"], st["type"], st["km"], st["lat"], st["lon"], st["name_en"], st["name_zh"]))

    summary = dict(distance_km=round(total_km, 3), osrm_distance_km=round(osrm["distance"] / 1000, 3),
                   elevation=estats, overlaps=spans, stores=stores, rests=rests)
    with open(os.path.join(CACHE, "last_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    main()
