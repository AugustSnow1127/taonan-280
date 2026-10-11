(function () {
  'use strict';

  var P = window.PLAN;
  var C = P.colors;
  var state = { route: null, stops: null, colorMode: 'strategy', schedule: null, map: null, mapReady: false, wind: null, me: null, watchId: null, wakeLock: null, reportText: '' };

  // ---------- helpers ----------
  function hm(str) { var p = str.split(':'); return (+p[0]) * 60 + (+p[1]); }
  function fmt(min) {
    var m = Math.round(min);
    var h = Math.floor(m / 60) % 24;
    var mm = ((m % 60) + 60) % 60;
    return String(h).padStart(2, '0') + ':' + String(mm).padStart(2, '0');
  }
  function fmtDur(min) {
    var sign = min < 0 ? '−' : '+';
    var a = Math.abs(Math.round(min));
    var h = Math.floor(a / 60);
    var m = a % 60;
    return sign + (h > 0 ? h + ' 小時 ' + m + ' 分' : m + ' 分');
  }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function nameOf(stop) { return (P.stopNames && P.stopNames[stop.id]) || stop.name_en; }
  function bearing(a, b) {
    var toR = Math.PI / 180;
    var y = Math.sin((b[0] - a[0]) * toR) * Math.cos(b[1] * toR);
    var x = Math.cos(a[1] * toR) * Math.sin(b[1] * toR) - Math.sin(a[1] * toR) * Math.cos(b[1] * toR) * Math.cos((b[0] - a[0]) * toR);
    return (Math.atan2(y, x) / toR + 360) % 360;
  }

  // Minutes to ride from km a to km b, integrating the speed bands.
  function rideMinutes(a, b, factor) {
    var t = 0;
    P.speedBands.forEach(function (band) {
      var lo = Math.max(a, band.from), hi = Math.min(b, band.to);
      if (hi > lo) t += (hi - lo) / (band.kmh * factor) * 60;
    });
    return t;
  }
  function dwell(stop) {
    if (P.dwellById[stop.id] !== undefined) return P.dwellById[stop.id];
    return P.dwellByType[stop.type] || 0;
  }
  function bandOf(list, km) {
    for (var i = 0; i < list.length; i++) if (km >= list[i].from && km < list[i].to) return list[i];
    return list[list.length - 1];
  }

  // ---------- schedule ----------
  function computeSchedule() {
    var pace = +document.getElementById('pace').value / 100;
    var factor = pace;
    var start = hm(document.getElementById('startTime').value || '05:00');
    var stops = state.stops;
    var rows = [];
    var t = start;
    var stopTotal = 0;
    for (var i = 0; i < stops.length; i++) {
      if (i > 0) t += rideMinutes(stops[i - 1].km, stops[i].km, factor);
      var arrive = t;
      var d = (i === 0 || i === stops.length - 1) ? 0 : dwell(stops[i]);
      stopTotal += d;
      t += d;
      rows.push({ stop: stops[i], arrive: arrive, depart: t, dwell: d });
    }
    state.schedule = { rows: rows, factor: factor, start: start, stopTotal: stopTotal };
  }
  function etaAtKm(km) {
    var rows = state.schedule.rows;
    for (var i = rows.length - 1; i >= 0; i--) {
      if (km >= rows[i].stop.km) return rows[i].depart + rideMinutes(rows[i].stop.km, km, state.schedule.factor);
    }
    return state.schedule.start;
  }

  function renderSchedule() {
    var tbody = document.querySelector('#etaTable tbody');
    var html = '';
    var worst = Infinity;
    state.schedule.rows.forEach(function (r) {
      var cut = r.stop.cutoff ? hm(r.stop.cutoff) : null;
      var buf = (cut !== null && r.stop.km > 0) ? cut - r.arrive : null;
      var cls = '';
      if (buf !== null) {
        worst = Math.min(worst, buf);
        cls = buf < 0 ? 'bad' : (buf < 30 ? 'warn' : 'ok');
      }
      var name = esc(nameOf(r.stop)) + (r.dwell ? ' <span class="hint">（停 ' + r.dwell + ' 分）</span>' : '');
      html += '<tr class="' + r.stop.type + '"><td>' + name + '</td><td>' + r.stop.km.toFixed(0) +
        '</td><td>' + fmt(r.arrive) + '</td><td>' + (r.stop.cutoff || '') +
        '</td><td class="' + cls + '">' + (buf === null ? '' : fmtDur(buf)) + '</td></tr>';
    });
    tbody.innerHTML = html;

    var v = document.getElementById('verdict');
    var cp2 = state.schedule.rows.filter(function (r) { return r.stop.id === 'cp2'; })[0];
    var cp2Txt = cp2 ? ' · 王功 ' + fmt(cp2.arrive) : '';
    var stopTxt = ' · 停站合計 ' + state.schedule.stopTotal + ' 分';
    if (worst < 0) { v.className = 'verdict bad'; v.textContent = '會被關門：落後 ' + fmtDur(-worst).slice(1) + cp2Txt + stopTxt; }
    else if (worst < 30) { v.className = 'verdict warn'; v.textContent = '能完賽，但最緊的餘裕只有 ' + Math.round(worst) + ' 分' + cp2Txt + stopTxt; }
    else { v.className = 'verdict ok'; v.textContent = '全部關門都趕得上，最緊餘裕 ' + Math.round(worst) + ' 分' + cp2Txt + stopTxt; }
    document.getElementById('paceOut').textContent = Math.round(state.schedule.factor * 100) + '%';
  }

  // ---------- segment cards ----------
  function segmentsFromStops() {
    var s = state.stops, out = [];
    for (var i = 0; i < s.length - 1; i++) out.push({ idx: i, a: s[i], b: s[i + 1] });
    return out;
  }
  function contentFor(midKm) {
    return P.segments.filter(function (c) { return midKm >= c.from && midKm < c.to; })[0] || P.segments[P.segments.length - 1];
  }
  function strategyClass(km, eta) {
    var sunset = hm(P.sunset), sunrise = hm(P.sunrise);
    if (eta >= sunset || eta < sunrise) return 'night';
    return bandOf(P.strategyBands, km).cls;
  }

  function renderCards() {
    var root = document.getElementById('segCards');
    var html = '';
    var sched = state.schedule;
    segmentsFromStops().forEach(function (seg) {
      var mid = (seg.a.km + seg.b.km) / 2;
      var c = contentFor(mid);
      var dep = sched.rows[seg.idx].depart;
      var arr = sched.rows[seg.idx + 1].arrive;
      var dist = seg.b.km - seg.a.km;
      var avg = dist / ((arr - dep) / 60);
      var cls = strategyClass(mid, etaAtKm(mid));
      var w = windFor(seg.idx);
      html += '<div class="card seg" data-seg="' + seg.idx + '" style="border-left-color:' + C[cls] + '">' +
        '<h3>' + (seg.idx + 1) + '. ' + esc(nameOf(seg.a)) + ' → ' + esc(nameOf(seg.b)) + '</h3>' +
        '<div class="small hint">' + esc(c.title) + '</div>' +
        '<div class="meta">' +
          '<div><b>' + dist.toFixed(0) + ' km</b><span>距離</span></div>' +
          '<div><b>' + avg.toFixed(1) + '</b><span>目標 km/h</span></div>' +
          '<div><b>' + fmt(dep) + '–' + fmt(arr) + '</b><span>騎乘時段</span></div>' +
        '</div>' +
        '<dl>' +
          '<dt>踏頻</dt><dd>' + esc(c.cadence) + '</dd>' +
          '<dt>強度</dt><dd>' + esc(c.effort) + '</dd>' +
          '<dt>補給</dt><dd>' + esc(c.fuel) + '</dd>' +
          '<dt>風險</dt><dd>' + esc(c.risk) + '</dd>' +
          '<dt>戰術</dt><dd>' + esc(c.tactic) + '</dd>' +
          '<dt>風向</dt><dd>' + w + '</dd>' +
          '<dt>段末停站</dt><dd>' + (sched.rows[seg.idx + 1].dwell ? sched.rows[seg.idx + 1].dwell + ' 分：廁所 → 裝水 → 吃 → 出發' : '不停') + '</dd>' +
        '</dl>' +
        '<div class="planb"><b>備案：</b>' + esc(c.planB) + '</div>' +
      '</div>';
    });
    root.innerHTML = html;
    root.querySelectorAll('.seg').forEach(function (el) {
      el.addEventListener('click', function () { focusSegment(+el.dataset.seg); });
    });
  }

  // ---------- map ----------
  function buildChunks() {
    var pts = state.route.points;
    var segs = segmentsFromStops();
    var feats = [];
    var chunkKm = 0.5;
    var i = 0;
    while (i < pts.length - 1) {
      var startKm = pts[i][3];
      var coords = [[pts[i][0], pts[i][1]]];
      var j = i + 1;
      while (j < pts.length && pts[j][3] - startKm < chunkKm) { coords.push([pts[j][0], pts[j][1]]); j++; }
      if (j < pts.length) coords.push([pts[j][0], pts[j][1]]);
      var end = pts[Math.min(j, pts.length - 1)];
      var distM = (end[3] - startKm) * 1000;
      var grade = distM > 0 ? (end[2] - pts[i][2]) / distM * 100 : 0;
      var mid = (startKm + end[3]) / 2;
      var segIdx = 0;
      for (var k = 0; k < segs.length; k++) if (mid >= segs[k].a.km) segIdx = k;
      feats.push({
        type: 'Feature',
        properties: { km: mid, grade: Math.max(-6, Math.min(6, grade)), seg: segIdx, cls: strategyClass(mid, etaAtKm(mid)) },
        geometry: { type: 'LineString', coordinates: coords }
      });
      i = j;
    }
    return { type: 'FeatureCollection', features: feats };
  }

  // Ridden part of the route turns grey once a position is known.
  function colorExpr(mode) {
    var base = baseColorExpr(mode);
    if (!state.me) return base;
    return ['case', ['<', ['get', 'km'], state.me.km], '#9aa0a6', base];
  }
  function baseColorExpr(mode) {
    if (mode === 'grade') {
      return ['interpolate', ['linear'], ['get', 'grade'], -3, '#2b83ba', -1, '#4dac26', 1, '#a6d96a', 2, '#fdae61', 4, '#d7191c'];
    }
    if (mode === 'segment') {
      var m = ['match', ['get', 'seg']];
      C.segmentPalette.forEach(function (col, i) { m.push(i, col); });
      m.push('#888');
      return m;
    }
    return ['match', ['get', 'cls'], 'easy', C.easy, 'steady', C.steady, 'critical', C.critical, 'night', C.night, '#888'];
  }

  function renderLegend() {
    var el = document.getElementById('legend');
    var items;
    if (state.colorMode === 'grade') {
      items = [['#2b83ba', '下坡'], ['#4dac26', '平路'], ['#fdae61', '+2%'], ['#d7191c', '+4% 以上']];
    } else if (state.colorMode === 'segment') {
      items = segmentsFromStops().map(function (s, i) { return [C.segmentPalette[i % C.segmentPalette.length], (i + 1) + '. → ' + nameOf(s.b)]; });
    } else {
      items = [[C.easy, '輕鬆：不搶時間也不浪費'], [C.steady, '穩定 20 km/h：關門關鍵段'], [C.critical, '保體力：允許掉速'], [C.night, '夜騎（開燈）'], [C.stop, '停站']];
    }
    el.innerHTML = items.map(function (it) { return '<div><i style="background:' + it[0] + '"></i>' + esc(it[1]) + '</div>'; }).join('');
  }

  function stopsGeoJSON() {
    return {
      type: 'FeatureCollection',
      features: state.stops.map(function (s) {
        return { type: 'Feature', properties: { id: s.id, name: nameOf(s), zh: s.name_zh || '', type: s.type, km: s.km, cutoff: s.cutoff || '' }, geometry: { type: 'Point', coordinates: [s.lon, s.lat] } };
      })
    };
  }

  function initMap() {
    var pts = state.route.points;
    var bounds = pts.reduce(function (b, p) { return b.extend([p[0], p[1]]); }, new maplibregl.LngLatBounds([pts[0][0], pts[0][1]], [pts[0][0], pts[0][1]]));
    var map = new maplibregl.Map({
      container: 'map',
      style: 'https://tiles.openfreemap.org/styles/liberty',
      bounds: bounds,
      fitBoundsOptions: { padding: 40 },
      pitch: 55,
      bearing: -20,
      maxPitch: 80,
      attributionControl: { compact: true }
    });
    state.map = map;
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
    map.on('load', function () {
      map.addSource('dem', {
        type: 'raster-dem',
        tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'],
        encoding: 'terrarium', tileSize: 256, maxzoom: 14,
        attribution: '地形：Mapzen/AWS Terrain Tiles'
      });
      map.setTerrain({ source: 'dem', exaggeration: 3 });
      map.addLayer({ id: 'hillshade', type: 'hillshade', source: 'dem', paint: { 'hillshade-exaggeration': 0.4 } });

      map.addSource('route', { type: 'geojson', data: buildChunks() });
      map.addLayer({ id: 'route-casing', type: 'line', source: 'route', layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': '#fff', 'line-width': 9 } });
      map.addLayer({ id: 'route-line', type: 'line', source: 'route', layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': colorExpr(state.colorMode), 'line-width': 5 } });

      map.addSource('stops', { type: 'geojson', data: stopsGeoJSON() });
      map.addLayer({
        id: 'stops-circle', type: 'circle', source: 'stops',
        paint: {
          'circle-radius': ['match', ['get', 'type'], 'official', 9, 6],
          'circle-color': ['match', ['get', 'type'], 'official', '#111', C.stop],
          'circle-stroke-color': '#fff', 'circle-stroke-width': 2
        }
      });
      map.addLayer({
        id: 'stops-label', type: 'symbol', source: 'stops',
        layout: { 'text-field': ['concat', ['get', 'name'], ' · ', ['to-string', ['round', ['get', 'km']]], ' km'], 'text-size': 12, 'text-offset': [0, 1.3], 'text-anchor': 'top', 'text-font': ['Noto Sans Regular'] },
        paint: { 'text-color': '#111', 'text-halo-color': '#fff', 'text-halo-width': 1.5 }
      });
      map.addSource('me', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
      map.addLayer({
        id: 'next-stop', type: 'circle', source: 'stops', filter: ['==', ['get', 'id'], ''],
        paint: { 'circle-radius': 16, 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-color': '#f59e0b', 'circle-stroke-width': 4 }
      }, 'stops-circle');
      map.addLayer({ id: 'me-halo', type: 'circle', source: 'me', paint: { 'circle-radius': 18, 'circle-color': '#1f6feb', 'circle-opacity': 0.25 } });
      map.addLayer({ id: 'me-dot', type: 'circle', source: 'me', paint: { 'circle-radius': 8, 'circle-color': '#1f6feb', 'circle-stroke-color': '#fff', 'circle-stroke-width': 3 } });
      if (state.me) drawMe(false);
      map.on('click', 'stops-circle', function (e) {
        var p = e.features[0].properties;
        var row = state.schedule.rows.filter(function (r) { return r.stop.id === p.id; })[0];
        var html = '<b>' + esc(p.name) + '</b><br><span class="hint">' + esc(p.zh) + '</span>' + '<br>km ' + (+p.km).toFixed(1) +
          (row ? '<br>預計抵達 ' + fmt(row.arrive) : '') + (p.cutoff ? '<br>關門 ' + esc(p.cutoff) : '');
        new maplibregl.Popup().setLngLat(e.lngLat).setHTML(html).addTo(map);
      });
      map.on('mouseenter', 'stops-circle', function () { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', 'stops-circle', function () { map.getCanvas().style.cursor = ''; });
      state.mapReady = true;
    });
  }

  function refreshMap() {
    if (!state.mapReady) return;
    state.map.getSource('route').setData(buildChunks());
    state.map.setPaintProperty('route-line', 'line-color', colorExpr(state.colorMode));
  }

  function focusSegment(idx) {
    var seg = segmentsFromStops()[idx];
    document.querySelectorAll('.seg').forEach(function (el) { el.classList.toggle('active', +el.dataset.seg === idx); });
    if (!state.map) return;
    var b = new maplibregl.LngLatBounds([seg.a.lon, seg.a.lat], [seg.a.lon, seg.a.lat]);
    state.route.points.forEach(function (p) { if (p[3] >= seg.a.km && p[3] <= seg.b.km) b.extend([p[0], p[1]]); });
    state.map.fitBounds(b, { padding: 60, pitch: 60, duration: 1200 });
    if (window.innerWidth < 900) document.getElementById('map').scrollIntoView({ behavior: 'smooth' });
  }

  // ---------- wind (Open-Meteo, no key) ----------
  function windFor(idx) {
    if (!state.wind) return '<span class="hint">' + (state.windMsg || '載入中…') + '</span>';
    var seg = segmentsFromStops()[idx];
    var w = state.wind[idx];
    if (!w) return '<span class="hint">無資料</span>';
    var mid = (seg.a.km + seg.b.km) / 2;
    var hour = Math.floor(etaAtKm(mid) / 60);
    var i = Math.max(0, Math.min(23, hour));
    var ws = w.speed[i], from = w.dir[i];
    var travel = bearing([seg.a.lon, seg.a.lat], [seg.b.lon, seg.b.lat]);
    var rad = (from - travel) * Math.PI / 180;
    var head = ws * Math.cos(rad);
    var cross = Math.abs(ws * Math.sin(rad));
    var label;
    if (head <= -6) label = '<b style="color:' + C.easy + '">順風</b>';
    else if (head >= 6) label = '<b style="color:' + C.critical + '">逆風：壓低身體，預期掉 2–3 km/h</b>';
    else if (cross >= 15) label = '<b style="color:' + C.steady + '">強側風：握緊把手</b>';
    else label = '微風／側風';
    return label + ' · ' + String(i).padStart(2, '0') + ':00 風速 ' + Math.round(ws) + ' km/h（逆風分量 ' + Math.round(head) + '、側風分量 ' + Math.round(cross) + '）';
  }

  function loadWind() {
    var status = document.getElementById('windStatus');
    var box = document.getElementById('windBox');
    var raceDay = new Date(P.raceDate + 'T00:00:00+08:00');
    var days = Math.ceil((raceDay - new Date()) / 86400000);
    if (days > 15) {
      state.windMsg = (days - 15) + ' 天後開放預報';
      status.textContent = '尚未開放';
      box.innerHTML = 'Open-Meteo 只預報 16 天內的天氣。比賽日的風向會從 <b>' +
        new Date(raceDay - 15 * 86400000).toLocaleDateString('zh-TW') + '</b> 起自動顯示在這裡。10 月底通常吹東北季風，南下多半是順風或斜順風，海岸陣風較強。';
      renderCards();
      return;
    }
    if (days < -1) { status.textContent = '已結束'; state.windMsg = '比賽已結束'; box.textContent = '比賽日已過。'; renderCards(); return; }
    var segs = segmentsFromStops();
    var lats = [], lons = [];
    segs.forEach(function (s) { lats.push(((s.a.lat + s.b.lat) / 2).toFixed(3)); lons.push(((s.a.lon + s.b.lon) / 2).toFixed(3)); });
    var url = 'https://api.open-meteo.com/v1/forecast?latitude=' + lats.join(',') + '&longitude=' + lons.join(',') +
      '&hourly=wind_speed_10m,wind_direction_10m&wind_speed_unit=kmh&timezone=Asia%2FTaipei&start_date=' + P.raceDate + '&end_date=' + P.raceDate;
    fetch(url).then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }).then(function (data) {
      var arr = Array.isArray(data) ? data : [data];
      state.wind = arr.map(function (d) { return { speed: d.hourly.wind_speed_10m, dir: d.hourly.wind_direction_10m }; });
      status.textContent = '即時';
      box.textContent = '每段的風向以模擬的抵達時間計算。更新於 ' + new Date().toLocaleString('zh-TW') + '。';
      renderCards();
    }).catch(function (e) {
      status.textContent = '錯誤';
      state.windMsg = '無法取得預報';
      box.textContent = '預報載入失敗（' + e.message + '）。';
      renderCards();
    });
  }

  // ---------- race-day position + coach report ----------
  function nowMinutes() {
    var t = new URLSearchParams(location.search).get('t');   // test override: ?t=HH:MM
    if (t) return hm(t);
    var d = new Date();
    return d.getHours() * 60 + d.getMinutes() + d.getSeconds() / 60;
  }

  // Snap a GPS fix to the route: nearest segment, projected km and off-route distance.
  function snap(lon, lat) {
    var pts = state.route.points;
    var kx = Math.cos(lat * Math.PI / 180) * 111320, ky = 110540;
    var best = { d2: Infinity, km: 0 };
    for (var i = 0; i < pts.length - 1; i++) {
      var ax = (pts[i][0] - lon) * kx, ay = (pts[i][1] - lat) * ky;
      var bx = (pts[i + 1][0] - lon) * kx, by = (pts[i + 1][1] - lat) * ky;
      var dx = bx - ax, dy = by - ay;
      var len2 = dx * dx + dy * dy;
      var t = len2 > 0 ? Math.max(0, Math.min(1, -(ax * dx + ay * dy) / len2)) : 0;
      var px = ax + t * dx, py = ay + t * dy;
      var d2 = px * px + py * py;
      if (d2 < best.d2) best = { d2: d2, km: pts[i][3] + t * (pts[i + 1][3] - pts[i][3]) };
    }
    return { km: best.km, offM: Math.sqrt(best.d2) };
  }
  function pointAtKm(km) {
    var pts = state.route.points;
    for (var i = 0; i < pts.length - 1; i++) if (pts[i + 1][3] >= km) return [pts[i][0], pts[i][1]];
    return [pts[pts.length - 1][0], pts[pts.length - 1][1]];
  }
  function nextStops(km) {
    return state.stops.filter(function (s) { return s.type !== 'rest' && s.km > km + 0.3; });
  }

  function setPosition(km, lonlat, offM, fly) {
    state.me = { km: km, lonlat: lonlat, offM: offM, at: nowMinutes() };
    renderReport();
    drawMe(fly);
  }
  function drawMe(fly) {
    if (!state.mapReady || !state.me) return;
    var map = state.map;
    map.getSource('me').setData({ type: 'FeatureCollection', features: [{ type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: state.me.lonlat } }] });
    var next = nextStops(state.me.km)[0];
    map.setFilter('next-stop', ['==', ['get', 'id'], next ? next.id : '']);
    map.setPaintProperty('route-line', 'line-color', colorExpr(state.colorMode));
    if (fly) map.flyTo({ center: state.me.lonlat, zoom: 12.5, pitch: 60, duration: 1500 });
    else map.easeTo({ center: state.me.lonlat, duration: 800 });
  }

  function bufCls(min) { return min < 0 ? 'bad' : (min < 30 ? 'warn' : 'ok'); }
  function signed(min) { var m = Math.round(min); return (m < 0 ? '−' : '+') + Math.abs(m) + ' 分'; }

  function buildReport() {
    var me = state.me;
    var now = me.at;
    var rows = state.schedule.rows;
    var planHere = etaAtKm(me.km);
    var delta = now - planHere;               // positive = behind plan
    var elapsedH = (now - state.schedule.start) / 60;
    var avg = elapsedH > 0.05 ? me.km / elapsedH : 0;
    var finish = state.stops[state.stops.length - 1];
    var finishPlan = now + (rows[rows.length - 1].arrive - planHere);
    // Scale the remaining plan by how much slower/faster than plan you have been so far (keeps the planned fade).
    var planElapsed = planHere - state.schedule.start;
    var finishAvg = planElapsed > 5 ? now + (rows[rows.length - 1].arrive - planHere) * ((now - state.schedule.start) / planElapsed) : null;
    var finishCut = hm(finish.cutoff);
    var ns = nextStops(me.km).slice(0, 2).map(function (s) {
      var row = rows.filter(function (r) { return r.stop.id === s.id; })[0];
      var eta = now + (row.arrive - planHere);
      return { stop: s, eta: eta, cut: s.cutoff ? hm(s.cutoff) : null };
    });
    var near = state.stops.filter(function (s) { return s.km <= me.km + 0.3; }).pop();
    var where = near ? nameOf(near) + (me.km - near.km < 1 ? ' 附近' : ' 之後 ' + (me.km - near.km).toFixed(1) + ' km') : '';
    var offTxt = me.offM === null ? '手動輸入 km' : '偏離路線 ' + Math.round(me.offM) + ' m';
    var deltaTxt;
    if (Math.abs(delta) < 1) deltaTxt = '準時';
    else if (delta > 0) deltaTxt = '落後 ' + Math.round(delta) + ' 分';
    else deltaTxt = '超前 ' + Math.round(-delta) + ' 分';

    var lines = [];
    lines.push('【桃南280 回報】' + fmt(now));
    lines.push('位置：km ' + me.km.toFixed(1) + '（' + where + '，' + offTxt + '）');
    lines.push('計畫此處應到：' + fmt(planHere) + ' → ' + deltaTxt);
    lines.push('出發至今均速（含停）：' + avg.toFixed(1) + ' km/h');
    ns.forEach(function (n, i) {
      var t = (i === 0 ? '下一站：' : '再下站：') + nameOf(n.stop) + '（km ' + n.stop.km.toFixed(0) + '，再 ' + (n.stop.km - me.km).toFixed(0) + ' km）預計 ' + fmt(n.eta);
      if (n.cut !== null) t += '｜關門 ' + n.stop.cutoff + '｜餘裕 ' + signed(n.cut - n.eta);
      lines.push(t);
    });
    lines.push('預估完賽（照計畫配速）：' + fmt(finishPlan) + '｜關門 ' + finish.cutoff + '｜' + signed(finishCut - finishPlan));
    if (finishAvg !== null) lines.push('預估完賽（照目前落後比例）：' + fmt(finishAvg));

    var deltaCls = delta > 15 ? 'bad' : (delta > 0 ? 'warn' : 'ok');
    var html = '<div class="lbl">📍 ' + fmt(now) + ' · ' + esc(offTxt) + '</div>' +
      '<div class="big">km ' + me.km.toFixed(1) + '</div>' +
      '<div class="' + deltaCls + '"><b>' + deltaTxt + '</b>（計畫 ' + fmt(planHere) + '）</div>' +
      '<div class="lbl">出發至今均速 ' + avg.toFixed(1) + ' km/h（含停）</div><hr>';
    ns.forEach(function (n, i) {
      html += '<div><span class="lbl">' + (i === 0 ? '下一站' : '再下站') + '</span> <b>' + esc(nameOf(n.stop)) + '</b></div>' +
        '<div>再 <b>' + (n.stop.km - me.km).toFixed(1) + ' km</b> · 預計 <b>' + fmt(n.eta) + '</b>' +
        (n.cut !== null ? ' · 關門 ' + n.stop.cutoff + ' <b class="' + bufCls(n.cut - n.eta) + '">' + signed(n.cut - n.eta) + '</b>' : '') + '</div>';
    });
    html += '<hr><div><span class="lbl">預估完賽</span> <b class="' + bufCls(finishCut - finishPlan) + '">' + fmt(finishPlan) + '</b>（關門 ' + finish.cutoff + '，' + signed(finishCut - finishPlan) + '）</div>';
    if (finishAvg !== null) html += '<div class="lbl">照目前落後比例：' + fmt(finishAvg) + '</div>';
    return { text: lines.join('\n'), html: html };
  }

  function renderReport() {
    if (!state.me || !state.schedule) return;
    var r = buildReport();
    state.reportText = r.text;
    document.getElementById('reportCard').innerHTML = r.html;
    document.getElementById('reportWrap').hidden = false;
  }

  function fixToPosition(pos, fly) {
    var lon = pos.coords.longitude, lat = pos.coords.latitude;
    var s = snap(lon, lat);
    var msg = 'GPS 精度 ±' + Math.round(pos.coords.accuracy) + ' m';
    if (s.offM > 2000) msg += '。⚠️ 距離路線 ' + (s.offM / 1000).toFixed(1) + ' km，km 數可能不準';
    if (state.watchId !== null) msg = '持續追蹤中 · ' + msg;
    document.getElementById('locMsg').textContent = msg;
    setPosition(s.km, [lon, lat], s.offM, fly);
  }
  function onGeoError(e) {
    document.getElementById('locMsg').textContent = '定位失敗（' + e.message + '）。請改用手動輸入碼錶 km。';
  }
  function locateOnce() {
    var test = new URLSearchParams(location.search).get('pos');   // test override: ?pos=lat,lon
    if (test) { var p = test.split(','); fixToPosition({ coords: { latitude: +p[0], longitude: +p[1], accuracy: 5 } }, true); return; }
    if (!navigator.geolocation) { onGeoError({ message: '此瀏覽器不支援定位' }); return; }
    document.getElementById('locMsg').textContent = '定位中…';
    navigator.geolocation.getCurrentPosition(function (pos) { fixToPosition(pos, true); }, onGeoError,
      { enableHighAccuracy: true, timeout: 20000, maximumAge: 30000 });
  }
  function setTracking(on) {
    var msg = document.getElementById('locMsg');
    if (on) {
      if (!navigator.geolocation) { onGeoError({ message: '此瀏覽器不支援定位' }); return; }
      var first = true;
      state.watchId = navigator.geolocation.watchPosition(function (pos) {
        fixToPosition(pos, first);   // fly on the first fix, then just follow
        first = false;
      }, onGeoError, { enableHighAccuracy: true, maximumAge: 10000 });
      try {
        if (navigator.wakeLock) navigator.wakeLock.request('screen').then(function (l) { state.wakeLock = l; }).catch(function () {});
      } catch (e) { /* wake lock not supported */ }
      msg.textContent = '持續追蹤中（螢幕保持亮著，較耗電）';
    } else {
      if (state.watchId !== null) navigator.geolocation.clearWatch(state.watchId);
      state.watchId = null;
      if (state.wakeLock) { state.wakeLock.release(); state.wakeLock = null; }
      msg.textContent = '已停止持續追蹤';
    }
  }
  function copyReport() {
    var btn = document.getElementById('copyBtn');
    function done() {
      btn.textContent = '已複製 ✓';
      setTimeout(function () { btn.textContent = '複製文字給教練'; }, 2000);
    }
    function fallback() {
      var ta = document.createElement('textarea');
      ta.value = state.reportText;
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); done(); } catch (e) { btn.textContent = '複製失敗，請截圖'; }
      document.body.removeChild(ta);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(state.reportText).then(done).catch(fallback);
    else fallback();
  }

  // ---------- prep tab ----------
  function renderPrep() {
    var X = window.PREP;
    var saved = {};
    try { saved = JSON.parse(localStorage.getItem('taonan-gear') || '{}'); } catch (e) { saved = {}; }
    function list(items) { return '<ul>' + items.map(function (t) { return '<li>' + esc(t) + '</li>'; }).join('') + '</ul>'; }
    var html = '';
    html += '<div class="card"><h2>接下來 20 天</h2><p class="small hint">沒有時間騎長距離，所以目標是練踏頻、測車燈、養好腿，不是拚體能。</p><table class="cal">' +
      X.calendar.map(function (r) { return '<tr><td>' + esc(r[0]) + '</td><td>' + esc(r[1]) + '</td></tr>'; }).join('') + '</table></div>';
    html += '<div class="card"><h2>踏頻：62 → 85 rpm</h2>' + list(X.cadence) + '</div>';
    html += '<div class="card"><h2>補給計算</h2>' + list(X.fuel) + '</div>';
    html += '<div class="card"><h2>賽前 3 天：飲食與睡眠</h2>' + list(X.lastDays) + '</div>';
    html += '<div class="card check"><h2>裝備清單</h2>' + X.gear.map(function (g, i) {
      return '<label><input type="checkbox" data-i="' + i + '"' + (saved[i] ? ' checked' : '') + '> <span>' + esc(g) + '</span></label>';
    }).join('') + '</div>';
    var root = document.getElementById('prepRoot');
    root.innerHTML = html;
    root.querySelectorAll('.check input').forEach(function (cb) {
      cb.addEventListener('change', function () {
        saved[cb.dataset.i] = cb.checked;
        try { localStorage.setItem('taonan-gear', JSON.stringify(saved)); } catch (e) { /* storage unavailable */ }
      });
    });
  }

  // ---------- wiring ----------
  function update() { computeSchedule(); renderSchedule(); renderCards(); refreshMap(); renderReport(); }

  document.querySelectorAll('.tab').forEach(function (btn) {
    btn.addEventListener('click', function () {
      document.querySelectorAll('.tab').forEach(function (b) { b.classList.toggle('active', b === btn); });
      document.querySelectorAll('.tabpane').forEach(function (p) { p.classList.toggle('active', p.id === 'tab-' + btn.dataset.tab); });
      if (btn.dataset.tab === 'race' && state.map) state.map.resize();
    });
  });
  document.querySelectorAll('.seg-toggle button').forEach(function (btn) {
    btn.addEventListener('click', function () {
      document.querySelectorAll('.seg-toggle button').forEach(function (b) { b.classList.toggle('active', b === btn); });
      state.colorMode = btn.dataset.color;
      renderLegend();
      refreshMap();
    });
  });
  ['pace', 'startTime'].forEach(function (id) { document.getElementById(id).addEventListener('input', update); });
  document.getElementById('locBtn').addEventListener('click', locateOnce);
  document.getElementById('trackToggle').addEventListener('change', function (e) { setTracking(e.target.checked); });
  document.getElementById('copyBtn').addEventListener('click', copyReport);
  document.getElementById('manualBtn').addEventListener('click', function () {
    var km = parseFloat(document.getElementById('manualKm').value);
    if (isNaN(km) || !state.route) return;
    km = Math.max(0, Math.min(state.route.distance_km, km));
    setPosition(km, pointAtKm(km), null, true);
  });

  renderPrep();
  Promise.all([fetch('data/route.json').then(function (r) { return r.json(); }), fetch('data/stops.json').then(function (r) { return r.json(); })])
    .then(function (res) {
      state.route = res[0];
      state.stops = res[1].sort(function (a, b) { return a.km - b.km; });
      computeSchedule();
      renderSchedule();
      renderLegend();
      renderCards();
      initMap();
      loadWind();
    })
    .catch(function (e) {
      document.getElementById('segCards').innerHTML = '<div class="card todo">路線資料載入失敗：' + esc(e.message) + '。請用 HTTP 伺服器開啟（例如 python -m http.server）。</div>';
    });
})();
