// Rest points along the route: brand-logo markers on the map, a "next 30 km" strip,
// and opening-hours evaluation at the rider's ETA.
// Data: data/pois.json  [{ id, name, brand, cat, km, off, lon, lat, oh }]
//   brand: key into BRANDS (or null), cat: convenience|food|fuel|police|bicycle, off: metres from route,
//   oh: OSM opening_hours string or null.
(function () {
  'use strict';

  var CAT = {
    convenience: { label: '超商', emoji: '🏪' },
    food: { label: '餐飲', emoji: '🍔' },
    fuel: { label: '加油站', emoji: '⛽' },
    police: { label: '警察局', emoji: '👮' },
    bicycle: { label: '單車店', emoji: '🚲' }
  };

  // ---------- opening hours (subset of the OSM syntax) ----------
  var DAYS = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];

  function dayIndex(d) { return DAYS.indexOf(d); }
  function parseDays(spec) {
    var set = {};
    spec.split(',').forEach(function (part) {
      var r = part.split('-');
      var a = dayIndex(r[0]), b = dayIndex(r[1] || r[0]);
      if (a < 0 || b < 0) throw new Error('day');
      for (var i = a; ; i = (i + 1) % 7) { set[i] = true; if (i === b) break; }
    });
    return set;
  }
  function toMin(t) { var p = t.split(':'); return (+p[0]) * 60 + (+p[1]); }

  // Returns [{days:{0..6:true}, spans:[[from,to],...]}] or null when unknown/unparseable.
  function parseOH(oh) {
    if (!oh) return null;
    var s = oh.trim();
    if (s === '24/7') return [{ days: parseDays('Mo-Su'), spans: [[0, 1440]] }];
    try {
      var rules = [];
      s.split(';').forEach(function (raw) {
        var r = raw.trim();
        if (!r) return;
        if (/^PH\b/.test(r)) return;                    // public-holiday rules: ignore
        var m = r.match(/^((?:Mo|Tu|We|Th|Fr|Sa|Su)(?:[-,](?:Mo|Tu|We|Th|Fr|Sa|Su))*)?\s*(.*)$/);
        var days = parseDays(m[1] || 'Mo-Su');
        var rest = m[2].trim();
        if (rest === 'off' || rest === 'closed') { rules.push({ days: days, spans: [] }); return; }
        var spans = rest.split(',').map(function (t) {
          var x = t.trim().match(/^(\d{1,2}:\d{2})-(\d{1,2}:\d{2})$/);
          if (!x) throw new Error('time');
          return [toMin(x[1]), toMin(x[2])];
        });
        rules.push({ days: days, spans: spans });
      });
      return rules.length ? rules : null;
    } catch (e) { return null; }
  }

  function spansFor(rules, day) {
    var spans = null;
    rules.forEach(function (r) { if (r.days[day]) spans = r.spans; });   // later rules override
    return spans || [];
  }

  // Status at minute-of-day `min` on weekday `day` (0=Mo). Spans past midnight (e.g. 22:00-02:00) are handled.
  function statusAt(oh, day, min) {
    var rules = parseOH(oh);
    if (!rules) return { known: false };
    if (oh.trim() === '24/7') return { known: true, open: true, h24: true };
    var today = spansFor(rules, day), yday = spansFor(rules, (day + 6) % 7);
    var open = today.some(function (s) { return s[1] > s[0] ? (min >= s[0] && min < s[1]) : (min >= s[0]); }) ||
      yday.some(function (s) { return s[1] <= s[0] && min < s[1]; });
    var h24 = today.length === 1 && today[0][0] === 0 && today[0][1] >= 1440;
    if (open) return { known: true, open: true, h24: h24 };
    var later = today.map(function (s) { return s[0]; }).filter(function (t) { return t > min; }).sort(function (a, b) { return a - b; });
    if (later.length) return { known: true, open: false, opensAt: later[0], tomorrow: false };
    var tmr = spansFor(rules, (day + 1) % 7).map(function (s) { return s[0]; }).sort(function (a, b) { return a - b; });
    return { known: true, open: false, opensAt: tmr.length ? tmr[0] : null, tomorrow: true };
  }

  // ---------- logo badges drawn on a canvas (works for map icons and HTML <img>) ----------
  var SIZE = 56;
  var badgeCache = {};

  function drawBadge(img, emoji, grey, text) {
    var c = document.createElement('canvas');
    c.width = c.height = SIZE;
    var g = c.getContext('2d');
    g.beginPath();
    g.arc(SIZE / 2, SIZE / 2, SIZE / 2 - 2, 0, Math.PI * 2);
    g.fillStyle = '#fff';
    g.fill();
    if (text) { g.fillStyle = text.bg; g.fill(); }
    g.lineWidth = 3;
    g.strokeStyle = grey ? '#9aa0a6' : (text ? '#fff' : '#1d1f22');
    g.stroke();
    g.save();
    g.beginPath();
    g.arc(SIZE / 2, SIZE / 2, SIZE / 2 - 5, 0, Math.PI * 2);
    g.clip();
    if (grey) g.filter = 'grayscale(1) opacity(0.45)';
    if (img) {
      var pad = 9, box = SIZE - pad * 2;
      var r = Math.min(box / img.width, box / img.height);
      var w = img.width * r, h = img.height * r;
      g.drawImage(img, (SIZE - w) / 2, (SIZE - h) / 2, w, h);
    } else if (text) {
      var fs = text.short.length <= 1 ? 30 : (text.short.length === 2 ? 22 : 16);
      g.font = 'bold ' + fs + 'px sans-serif';
      g.fillStyle = text.fg;
      g.textAlign = 'center';
      g.textBaseline = 'middle';
      g.fillText(text.short, SIZE / 2, SIZE / 2 + 1);
    } else {
      g.font = '28px sans-serif';
      g.textAlign = 'center';
      g.textBaseline = 'middle';
      g.fillText(emoji, SIZE / 2, SIZE / 2 + 2);
    }
    g.restore();
    return c;
  }

  function loadImg(src) {
    return new Promise(function (resolve) {
      var im = new Image();
      im.onload = function () { resolve(im); };
      im.onerror = function () { resolve(null); };
      im.src = src;
    });
  }

  // Build both normal and closed (grey) badges for every brand + category fallback.
  function buildBadges(brands) {
    var jobs = [];
    Object.keys(CAT).forEach(function (cat) {
      badgeCache['cat-' + cat] = drawBadge(null, CAT[cat].emoji, false);
      badgeCache['cat-' + cat + '-off'] = drawBadge(null, CAT[cat].emoji, true);
    });
    Object.keys(brands).forEach(function (key) {
      var b = brands[key];
      if (!b.logo && b.short) {      // no logo file: brand-colour text badge
        var t = { short: b.short, bg: b.bg, fg: b.fg };
        badgeCache['b-' + key] = drawBadge(null, '', false, t);
        badgeCache['b-' + key + '-off'] = drawBadge(null, '', true, t);
        return;
      }
      if (!b.logo) return;
      jobs.push(loadImg(b.logo).then(function (im) {
        if (!im) return;
        badgeCache['b-' + key] = drawBadge(im, '', false);
        badgeCache['b-' + key + '-off'] = drawBadge(im, '', true);
      }));
    });
    return Promise.all(jobs);
  }

  function iconKey(p, closed) {
    var base = (p.brand && badgeCache['b-' + p.brand]) ? 'b-' + p.brand : 'cat-' + p.cat;
    return base + (closed ? '-off' : '');
  }

  window.POI = { drawBadge: drawBadge, CAT: CAT, statusAt: statusAt, buildBadges: buildBadges, badges: badgeCache, iconKey: iconKey, SIZE: SIZE };
})();
