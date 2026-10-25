"""Build data/stations.json: TRA (台鐵) and THSR (高鐵) stations within MAX_OFF_KM of the route.

Input: scripts/.cache/stations_tw.json — one nationwide Overpass query:
  [out:json];(node["railway"="station"](21.8,119.9,25.4,122.1);
              node["public_transport"="station"]["train"="yes"](21.8,119.9,25.4,122.1););out tags center;
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_OFF_KM = 30
NEAR_KM = 10
# Beyond NEAR_KM only main stations with frequent trains are worth riding to.
MAJOR_FAR = {('TRA', '彰化'), ('TRA', '員林'), ('TRA', '斗六'), ('TRA', '嘉義'), ('TRA', '新營'), ('TRA', '臺南'),
             ('THSR', '彰化'), ('THSR', '雲林'), ('THSR', '嘉義'), ('THSR', '台南')}


# TRA stations where a whole (unbagged) bike may board/alight a local train with a half-price bike ticket.
# Source: https://www.railway.gov.tw/tra-tip-web/tip/tip00D/tipD11/goBikeStation (checked 2026-10-26).
# Stations near this route NOT on the list: 內壢, 新富, 談文, 大山, 龍港, 新埔, 嘉北 ... (others unverified).
BIKE_OK = {'桃園', '中壢', '埔心', '楊梅', '富岡', '北湖', '湖口', '竹南', '後龍', '白沙屯', '通霄', '苑裡', '日南', '大甲',
           '清水', '沙鹿', '龍井', '大肚', '追分', '成功', '彰化', '花壇', '員林', '社頭', '田中', '二水', '林內', '斗六',
           '斗南', '大林', '民雄', '嘉義', '新營', '隆田', '善化', '南科', '新市', '永康', '臺南', '保安'}
BIKE_NO = {'內壢', '新富', '談文', '大山', '龍港', '新埔', '大村', '永靖', '石榴', '石龜', '嘉北', '水上', '南靖',
           '後壁', '柳營', '林鳳營', '拔林', '大橋'}


def bike_rule(op, name):
    if op == 'THSR':
        return 'bag'          # wheels off, fully in a bike bag; no unbagged service
    if name in BIKE_OK:
        return 'yes'
    if name in BIKE_NO:
        return 'no'
    return 'unknown'


def operator(tags):
    text = ' '.join(tags.get(k, '') for k in ('operator', 'network', 'operator:en', 'network:en', 'name:en'))
    if '高速鐵路' in text or 'High Speed' in text or 'THSR' in text:
        return 'THSR'
    if '臺灣鐵路' in text or '台灣鐵路' in text or '臺鐵' in text or '台鐵' in text or 'Taiwan Railway' in text or 'TRA' in text.split():
        return 'TRA'
    return None


def snap(points, lon, lat):
    kx = math.cos(math.radians(lat)) * 111.32
    ky = 110.54
    best = (1e9, 0.0)
    for a, b in zip(points, points[1:]):
        ax, ay = (a[0] - lon) * kx, (a[1] - lat) * ky
        bx, by = (b[0] - lon) * kx, (b[1] - lat) * ky
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy
        t = max(0.0, min(1.0, -(ax * dx + ay * dy) / l2)) if l2 else 0.0
        px, py = ax + t * dx, ay + t * dy
        d = math.hypot(px, py)
        if d < best[0]:
            best = (d, a[3] + t * (b[3] - a[3]))
    return best


def main():
    route = json.loads((ROOT / 'data/route.json').read_text(encoding='utf8'))['points']
    raw = json.loads((ROOT / 'scripts/.cache/stations_tw.json').read_text(encoding='utf8'))['elements']
    seen, out = set(), []
    for e in raw:
        tags = e.get('tags', {})
        op = operator(tags)
        name = tags.get('name')
        if not op or not name:
            continue
        lon, lat = e.get('lon', e.get('center', {}).get('lon')), e.get('lat', e.get('center', {}).get('lat'))
        off, km = snap(route, lon, lat)
        if off > MAX_OFF_KM or (op, name) in seen or (off > NEAR_KM and (op, name) not in MAJOR_FAR):
            continue
        seen.add((op, name))
        out.append({'id': '%s/%s' % (e['type'], e['id']), 'name': name, 'name_en': tags.get('name:en', ''), 'op': op,
                    'lon': round(lon, 6), 'lat': round(lat, 6), 'km': round(km, 2), 'off': round(off, 2), 'bike': bike_rule(op, name)})
    out.sort(key=lambda s: s['km'])
    (ROOT / 'data/stations.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf8')
    for s in out:
        print('%-5s %-8s km %6.1f  off %4.1f km  %s' % (s['op'], s['name'], s['km'], s['off'], s['bike']))
    print(len(out), 'stations')


if __name__ == '__main__':
    main()
