/* Used Bike Guide - internal listings browser.
   Reads data/bikes.json, filters/sorts in the browser, exports CSV for page design. */
(function () {
  'use strict';

  var DATA_URL = 'data/bikes.json';
  var state = { bikes: [], meta: {}, sort: { key: 'make', dir: 1 }, open: {} };

  var $ = function (sel) { return document.querySelector(sel); };
  var els = {};

  /* ---------- formatting ---------- */

  function money(n) {
    if (n === null || n === undefined || isNaN(n)) return '';
    return '£' + Number(n).toLocaleString('en-GB');
  }

  function priceRange(b) {
    if (b.price_low == null && b.price_high == null) return 'TBC';
    return money(b.price_low) + ' - ' + money(b.price_high);
  }

  function years(b) {
    if (!b.year_from) return '';
    if (!b.year_to || b.year_to === b.year_from) return String(b.year_from);
    return b.year_from + '-' + b.year_to;
  }

  function fullModel(b) {
    return (b.model + ' ' + (b.variant || '')).trim();
  }

  function shortDate(iso) {
    if (!iso) return '';
    var d = new Date(iso);
    if (isNaN(d)) return iso;
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: '2-digit' });
  }

  /* ---------- data prep ---------- */

  // Percentage change in the midpoint of the range versus the previous recorded check.
  function computeChange(bike) {
    var hist = bike.price_history || [];
    if (!hist.length) return null;
    var prev = hist[hist.length - 1];
    var nowMid = midpoint(bike.price && bike.price.low, bike.price && bike.price.high);
    var prevMid = midpoint(prev.low, prev.high);
    if (nowMid == null || prevMid == null || prevMid === 0) return null;
    return ((nowMid - prevMid) / prevMid) * 100;
  }

  // A price is "solid" if it came from a real sample or a published guide.
  function isSolid(b) {
    return b.confidence === 'verified' || b.confidence === 'researched';
  }

  function midpoint(lo, hi) {
    if (lo == null && hi == null) return null;
    if (lo == null) return hi;
    if (hi == null) return lo;
    return (lo + hi) / 2;
  }

  function normalise(raw) {
    return raw.map(function (b) {
      var p = b.price || {};
      return Object.assign({}, b, {
        price_low: p.low != null ? p.low : null,
        price_high: p.high != null ? p.high : null,
        as_of: p.as_of || null,
        source: p.source || '',
        confidence: p.confidence || 'unverified',
        sample_size: p.sample_size || 0,
        change: computeChange(b),
        _haystack: [b.make, b.model, b.variant, b.category, b.description]
          .concat(b.pros || []).concat(b.cons || []).join(' ').toLowerCase()
      });
    });
  }

  /* ---------- filtering & sorting ---------- */

  function currentView() {
    var q = els.q.value.trim().toLowerCase();
    var make = els.make.value, cat = els.category.value;
    var minV = els.verdict.value ? Number(els.verdict.value) : null;
    var yfrom = els.yfrom.value !== '' ? Number(els.yfrom.value) : null;
    var yto = els.yto.value !== '' ? Number(els.yto.value) : null;
    var pmin = els.pmin.value !== '' ? Number(els.pmin.value) : null;
    var pmax = els.pmax.value !== '' ? Number(els.pmax.value) : null;
    var conf = els.conf.value;

    var out = state.bikes.filter(function (b) {
      if (q && b._haystack.indexOf(q) === -1) return false;
      if (make && b.make !== make) return false;
      if (cat && b.category !== cat) return false;
      if (minV !== null && !(b.verdict >= minV)) return false;
      // Keep a bike whose production run overlaps the requested window, so a
      // 1998-2003 model still shows up when you ask for the 1990s.
      if (yfrom !== null && (b.year_to || b.year_from) < yfrom) return false;
      if (yto !== null && b.year_from > yto) return false;
      // Overlap test: keep a bike whose range intersects the requested window.
      if (pmin !== null && b.price_high != null && b.price_high < pmin) return false;
      if (pmax !== null && b.price_low != null && b.price_low > pmax) return false;
      if (conf === 'verified' && !isSolid(b)) return false;
      if (conf === 'unverified' && isSolid(b)) return false;
      return true;
    });

    var key = state.sort.key, dir = state.sort.dir;
    out.sort(function (a, b) {
      var av = a[key], bv = b[key];
      if (key === 'model') { av = fullModel(a); bv = fullModel(b); }
      var an = av == null, bn = bv == null;
      if (an && bn) return 0;
      if (an) return 1;          // nulls always sort last
      if (bn) return -1;
      if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * dir;
      return String(av).localeCompare(String(bv), 'en-GB') * dir;
    });
    return out;
  }

  /* ---------- rendering ---------- */

  function render() {
    var view = currentView();
    var tbody = els.rows;
    tbody.textContent = '';

    view.forEach(function (b) {
      tbody.appendChild(buildRow(b));
      if (state.open[b.id]) tbody.appendChild(buildDetail(b));
    });

    els.empty.hidden = view.length !== 0;
    var unver = view.filter(function (b) { return !isSolid(b); }).length;
    els.summary.textContent = view.length + ' of ' + state.bikes.length + ' bikes' +
      (unver ? ' — ' + unver + ' need a price check' : ' — all prices researched or verified');

    Array.prototype.forEach.call(document.querySelectorAll('th[data-sort]'), function (th) {
      var on = th.dataset.sort === state.sort.key;
      th.classList.toggle('sorted', on);
      th.classList.toggle('desc', on && state.sort.dir === -1);
    });
  }

  function cell(text, cls) {
    var td = document.createElement('td');
    if (cls) td.className = cls;
    td.textContent = text;
    return td;
  }

  function buildRow(b) {
    var tr = document.createElement('tr');
    tr.className = 'row' + (state.open[b.id] ? ' open' : '');
    tr.dataset.id = b.id;

    var tw = document.createElement('td');
    tw.innerHTML = '<span class="twist">▶</span>';
    tr.appendChild(tw);

    tr.appendChild(cell(b.make));

    var md = document.createElement('td');
    md.className = 'model-cell';
    md.textContent = b.model;
    if (b.variant) {
      var v = document.createElement('span');
      v.className = 'variant';
      v.textContent = ' ' + b.variant;
      md.appendChild(v);
    }
    tr.appendChild(md);

    tr.appendChild(cell(years(b)));
    tr.appendChild(cell(b.engine_cc ? b.engine_cc + 'cc' : '', 'num'));
    tr.appendChild(cell(b.category || ''));

    var vd = document.createElement('td');
    vd.className = 'num';
    var pill = document.createElement('span');
    pill.className = 'verdict v' + b.verdict;
    pill.textContent = b.verdict + '/10';
    vd.appendChild(pill);
    tr.appendChild(vd);

    tr.appendChild(cell(money(b.price_low), 'num'));
    tr.appendChild(cell(money(b.price_high), 'num'));

    var ch = document.createElement('td');
    ch.className = 'num';
    if (b.change == null) {
      ch.innerHTML = '<span class="chg-flat">&mdash;</span>';
    } else {
      var rounded = Math.round(b.change * 10) / 10;
      var cls = rounded > 0.05 ? 'chg-up' : (rounded < -0.05 ? 'chg-down' : 'chg-flat');
      var sign = rounded > 0 ? '+' : '';
      ch.innerHTML = '<span class="' + cls + '">' + sign + rounded.toFixed(1) + '%</span>';
    }
    tr.appendChild(ch);

    var ck = document.createElement('td');
    if (isSolid(b)) {
      ck.textContent = shortDate(b.as_of);
      if (b.confidence === 'researched') ck.title = 'From a published UK price guide';
    } else {
      var badge = document.createElement('span');
      badge.className = 'badge-unverified';
      badge.textContent = b.confidence === 'thin' ? 'thin' : 'check';
      badge.title = b.confidence === 'thin'
        ? 'Derived from only a handful of listings — worth a second look'
        : 'Not yet researched';
      ck.appendChild(badge);
    }
    tr.appendChild(ck);

    tr.addEventListener('click', function () {
      state.open[b.id] = !state.open[b.id];
      render();
    });
    return tr;
  }

  function listBlock(title, items, cls) {
    var d = document.createElement('div');
    d.className = cls;
    var h = document.createElement('h4');
    h.textContent = title;
    d.appendChild(h);
    var ul = document.createElement('ul');
    (items || []).forEach(function (i) {
      var li = document.createElement('li');
      li.textContent = i;
      ul.appendChild(li);
    });
    d.appendChild(ul);
    return d;
  }

  function buildDetail(b) {
    var tr = document.createElement('tr');
    tr.className = 'detail';
    var td = document.createElement('td');
    td.colSpan = 11;

    var p = document.createElement('p');
    p.className = 'detail-desc';
    p.textContent = b.description || '';
    td.appendChild(p);

    var pc = document.createElement('div');
    pc.className = 'pc';
    pc.appendChild(listBlock('+ Plus points', b.pros, 'pros'));
    pc.appendChild(listBlock('– Minus points', b.cons, 'cons'));
    td.appendChild(pc);

    var prov = document.createElement('p');
    prov.className = 'provenance';
    var bits = ['Price range: ' + priceRange(b)];
    bits.push('source: ' + (b.source || 'unset'));
    if (b.sample_size) bits.push(b.sample_size + ' listings sampled');
    if (b.as_of) bits.push('checked ' + shortDate(b.as_of));
    bits.push((b.price_history || []).length + ' previous check(s) on record');
    prov.textContent = bits.join(' · ');
    td.appendChild(prov);

    tr.appendChild(td);
    return tr;
  }

  /* ---------- export ---------- */

  function csvEscape(v) {
    var s = v == null ? '' : String(v);
    return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }

  function exportCsv() {
    var view = currentView();
    // Column order matches the magazine's page furniture, so design can drop it straight in.
    var cols = [
      ['Make', function (b) { return b.make; }],
      ['Model', function (b) { return fullModel(b); }],
      ['Year', function (b) { return years(b); }],
      ['Engine', function (b) { return b.engine_cc ? b.engine_cc + 'cc' : ''; }],
      ['Verdict', function (b) { return b.verdict + '/10'; }],
      ['Description', function (b) { return b.description; }],
      ['Plus', function (b) { return (b.pros || []).join(', '); }],
      ['Minus', function (b) { return (b.cons || []).join(', '); }],
      ['Price range', function (b) { return priceRange(b); }],
      ['Price from', function (b) { return b.price_low; }],
      ['Price to', function (b) { return b.price_high; }],
      ['Category', function (b) { return b.category; }],
      ['Change vs last check', function (b) { return b.change == null ? '' : (Math.round(b.change * 10) / 10) + '%'; }],
      ['Price checked', function (b) { return b.as_of || ''; }],
      ['Price source', function (b) { return b.source; }],
      ['Sample size', function (b) { return b.sample_size || ''; }],
      ['Confidence', function (b) { return b.confidence; }],
      ['ID', function (b) { return b.id; }]
    ];
    var lines = [cols.map(function (c) { return csvEscape(c[0]); }).join(',')];
    view.forEach(function (b) {
      lines.push(cols.map(function (c) { return csvEscape(c[1](b)); }).join(','));
    });
    // BOM keeps Excel happy with the pound signs.
    download('﻿' + lines.join('\r\n'), 'text/csv;charset=utf-8', 'csv');
  }

  function exportJson() {
    download(JSON.stringify({ meta: state.meta, bikes: currentView() }, null, 2), 'application/json', 'json');
  }

  function download(text, mime, ext) {
    var stamp = new Date().toISOString().slice(0, 10);
    var name = 'used-bike-guide-' + stamp + '.' + ext;
    var url = URL.createObjectURL(new Blob([text], { type: mime }));
    var a = document.createElement('a');
    a.href = url; a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  /* ---------- setup ---------- */

  function fillSelect(sel, values) {
    values.sort(function (a, b) { return a.localeCompare(b, 'en-GB'); }).forEach(function (v) {
      var o = document.createElement('option');
      o.value = v; o.textContent = v;
      sel.appendChild(o);
    });
  }

  function uniq(arr) {
    return Object.keys(arr.reduce(function (acc, v) { if (v) acc[v] = 1; return acc; }, {}));
  }

  function showStatus(html) {
    els.status.innerHTML = html;
    els.status.hidden = false;
  }

  function wire() {
    ['q', 'make', 'category', 'verdict', 'yfrom', 'yto', 'pmin', 'pmax', 'conf'].forEach(function (k) {
      els[k].addEventListener('input', render);
    });
    $('#reset').addEventListener('click', function () {
      ['q', 'yfrom', 'yto', 'pmin', 'pmax'].forEach(function (k) { els[k].value = ''; });
      ['make', 'category', 'verdict', 'conf'].forEach(function (k) { els[k].value = ''; });
      render();
    });
    Array.prototype.forEach.call(document.querySelectorAll('th[data-sort]'), function (th) {
      th.addEventListener('click', function () {
        var key = th.dataset.sort;
        if (state.sort.key === key) state.sort.dir *= -1;
        else { state.sort.key = key; state.sort.dir = 1; }
        render();
      });
    });
    $('#export-csv').addEventListener('click', exportCsv);
    $('#export-json').addEventListener('click', exportJson);
  }

  function init(data) {
    state.meta = data.meta || {};
    state.bikes = normalise(data.bikes || []);

    $('#issue-tag').textContent = state.meta.issue ? '· ' + state.meta.issue : '';
    fillSelect(els.make, uniq(state.bikes.map(function (b) { return b.make; })));
    fillSelect(els.category, uniq(state.bikes.map(function (b) { return b.category; })));

    var unver = state.bikes.filter(function (b) { return !isSolid(b); }).length;
    if (unver) {
      showStatus('<strong>' + unver + ' of ' + state.bikes.length + ' bikes</strong> need a price check. ' +
        'Run a price refresh before this issue goes to press — see <code>README.md</code>.');
    } else if (state.meta.last_refreshed) {
      showStatus('Prices last refreshed <strong>' + shortDate(state.meta.last_refreshed) + '</strong>.');
    }

    wire();
    render();
  }

  document.addEventListener('DOMContentLoaded', function () {
    els = {
      q: $('#q'), make: $('#f-make'), category: $('#f-category'), verdict: $('#f-verdict'),
      yfrom: $('#f-yfrom'), yto: $('#f-yto'),
      pmin: $('#f-pmin'), pmax: $('#f-pmax'), conf: $('#f-conf'),
      rows: $('#rows'), summary: $('#summary'), empty: $('#empty'), status: $('#status-bar')
    };
    fetch(DATA_URL)
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(init)
      .catch(function (err) {
        var local = location.protocol === 'file:';
        showStatus('<strong>Could not load ' + DATA_URL + '</strong> (' + err.message + '). ' +
          (local
            ? 'Browsers block file access from <code>file://</code>. Start a local server with ' +
              '<code>python3 -m http.server 8000</code> in this folder, then open ' +
              '<code>http://localhost:8000</code>.'
            : 'Check that the data file was deployed alongside the page.'));
      });
  });
})();
