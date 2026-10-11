"""Build data/pois.json + data/brands.json (+ img/logos/*.png) from data/pois_raw.json.

- keeps rest points within MAX_DIST_M of the route
- normalises brands to short keys
- downloads each brand logo once (Wikidata P154 -> Wikimedia Commons PNG thumbnail)
Re-runnable; logos already on disk are not downloaded again.
"""
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_DIST_M = 300
UA = {'User-Agent': 'taonan-280-planner/1.0 (personal race map)'}

CATEGORY = {
    'convenience': 'convenience',
    'fast_food': 'food', 'restaurant': 'food', 'cafe': 'food',
    'fuel': 'fuel',
    'police': 'police',
    'bicycle': 'bicycle',
}
# Parcel lockers etc. are not rest points.
SKIP_BRANDS = {'蝦皮店到店'}
SKIP_NAMES = ('蝦皮',)

# brand name (as tagged) -> (key, display name, wikidata id)
# Brands without a Commons logo get a colour badge from BADGE: key -> (short text, bg colour, text colour)
BRANDS = {
    '7-Eleven': ('7eleven', '7-ELEVEN', 'Q259340'),
    'FamilyMart': ('familymart', '全家', 'Q10891564'),
    'Hi-Life': ('hilife', '萊爾富', 'Q11326216'),
    'OK mart': ('okmart', 'OK 超商', 'Q10851968'),
    'CPC': ('cpc', '台灣中油', 'Q698024'),
    'Formosa': ('formosa', '台塑石油', 'Q1437742'),
    'NPC': ('npc', '全國加油站', 'Q20410455'),
    'Starbucks': ('starbucks', '星巴克', 'Q37158'),
    'Louisa Coffee': ('louisa', '路易莎', 'Q96390921'),
    '85°C': ('85c', '85度C', 'Q4644852'),
    '八方雲集': ('bafang', '八方雲集', 'Q28417381'),
    '四海遊龍': ('sihai', '四海遊龍', 'Q28417394'),
    '拉亞漢堡': ('laya', '拉亞漢堡', 'Q67933743'),
    '早安美芝城': ('mjc', '早安美芝城', 'Q30941219'),
    '巨林美而美': ('meiermei', '美而美', 'Q105722219'),
    '麥味登': ('mwd', '麥味登', None),
    'CoCo都可': ('coco', 'CoCo都可', 'Q65084369'),
    '清心福全': ('chingshin', '清心福全', 'Q10391229'),
    '茶的魔手': ('teamagic', '茶的魔手', 'Q67933727'),
    '三媽臭臭鍋': ('sanma', '三媽臭臭鍋', 'Q108212222'),
    "McDonald's": ('mcdonalds', '麥當勞', 'Q38076'),
    'KFC': ('kfc', '肯德基', 'Q524757'),
    'MOS Burger': ('mos', '摩斯漢堡', 'Q1204169'),
    'Pizza Hut': ('pizzahut', '必勝客', 'Q191615'),
}
BADGE = {
    'hilife': ('萊', '#e60012', '#fff'), 'formosa': ('台塑', '#d7000f', '#fff'), 'louisa': ('L', '#1b1b1b', '#fff'),
    '85c': ('85', '#9b1b30', '#fff'), 'bafang': ('八方', '#c8102e', '#fff'), 'sihai': ('四海', '#d32f2f', '#fff'),
    'laya': ('拉亞', '#f39800', '#fff'), 'mjc': ('美芝', '#e4007f', '#fff'), 'meiermei': ('美', '#e60012', '#fff'),
    'mwd': ('麥', '#e85298', '#fff'), 'coco': ('CoCo', '#f08200', '#fff'), 'chingshin': ('清心', '#00913a', '#fff'),
    'teamagic': ('魔手', '#e60012', '#fff'), 'sanma': ('三媽', '#c30d23', '#fff'), 'pizzahut': ('Pizza', '#ee3124', '#fff'),
}


def get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def logo_file(qid):
    """Commons file name of the brand's logo (Wikidata P154), or None."""
    data = get_json('https://www.wikidata.org/wiki/Special:EntityData/%s.json' % qid)
    claims = data['entities'][qid]['claims'].get('P154', [])
    for c in claims:
        snak = c['mainsnak']
        if snak.get('datavalue'):
            return snak['datavalue']['value']
    return None


def download_logo(key, qid, out_dir):
    out = out_dir / (key + '.png')
    if out.exists():
        return out
    if not qid:
        return None
    try:
        name = logo_file(qid)
        if not name:
            print('  no logo on Wikidata:', key, qid)
            return None
        url = 'https://commons.wikimedia.org/wiki/Special:FilePath/%s?width=128' % urllib.parse.quote(name)
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            out.write_bytes(r.read())
        time.sleep(0.5)
        print('  logo', key, '<-', name)
        return out
    except Exception as e:  # keep going; the page falls back to a category icon
        print('  logo failed:', key, e)
        return None


def main():
    raw = json.loads((ROOT / 'data/pois_raw.json').read_text(encoding='utf8'))['pois']
    logos = ROOT / 'img/logos'
    logos.mkdir(parents=True, exist_ok=True)

    pois, used = [], {}
    for p in raw:
        cat = CATEGORY.get(p['category'])
        if not cat or p['dist_m'] > MAX_DIST_M or p.get('brand') in SKIP_BRANDS or (p.get('name') or '').startswith(SKIP_NAMES):
            continue
        brand = BRANDS.get(p.get('brand') or '')
        key = brand[0] if brand else None
        if brand:
            used[key] = brand
        pois.append({
            'id': p['osm_id'],
            'name': (p.get('name') or '') + ((' ' + p['branch']) if p.get('branch') and p['branch'] not in (p.get('name') or '') else ''),
            'brand': key,
            'cat': cat,
            'km': round(p['km'], 2),
            'off': round(p['dist_m']),
            'lon': round(p['lon'], 6),
            'lat': round(p['lat'], 6),
            'oh': p.get('opening_hours'),
        })

    brands = {}
    for key, (_, label, qid) in sorted(used.items()):
        path = download_logo(key, qid, logos)
        b = {'name': label, 'logo': 'img/logos/' + path.name if path else ''}
        if key in BADGE:
            b['short'], b['bg'], b['fg'] = BADGE[key]
        brands[key] = b

    pois.sort(key=lambda x: x['km'])
    (ROOT / 'data/pois.json').write_text(json.dumps(pois, ensure_ascii=False, separators=(',', ':')), encoding='utf8')
    (ROOT / 'data/brands.json').write_text(json.dumps(brands, ensure_ascii=False, indent=1), encoding='utf8')
    print('pois:', len(pois), 'brands:', len(brands), 'with logo:', sum(1 for b in brands.values() if b['logo']))


if __name__ == '__main__':
    main()
