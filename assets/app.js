/* Used Bike Guide - internal listings browser.
   Reads data/bikes.json, filters/sorts in the browser, exports CSV for page design. */
(function () {
  'use strict';

  var DATA_URL = 'data/bikes.json';
  var state = { bikes: [], meta: {}, sort: { key: 'make', dir: 1 }, open: {}, images: {}, uploading: {} };

  var $ = function (sel) { return document.querySelector(sel); };
  var els = {};

  /* ---------- formatting ---------- */

  function money(n) {
    if (n === null || n === undefined || isNaN(n)) return '';
    return '£' + Number(n).toLocaleString('en-GB');
  }

  function priceRange(b) {
    if (b.price_private == null && b.price_dealer == null) return 'TBC';
    return money(b.price_private) + ' - ' + money(b.price_dealer);
  }

  function years(b) {
    if (!b.year_from) return '';
    if (!b.year_to || b.year_to === b.year_from) return String(b.year_from);
    return b.year_from + '-' + b.year_to;
  }

  function fullModel(b) {
    return (b.model + ' ' + (b.variant || '')).trim();
  }

  // Google Images link so editorial can cross-check archive photos against the
  // web. Includes the year span, because several models here span generations
  // that look nothing alike (Daytona 675 vs 955i vs 660).
  function imageSearchUrl(b) {
    // Most variants help the search (Slabside, EXUP, Bol d'Or, DBD34 are all how
    // people describe these bikes). Strip only our own bookkeeping labels — "Gen 1"
    // and years duplicated from the span — which would just muddy the results.
    var variant = (b.variant || '')
      .replace(/\bgen\s*\d+\b/gi, '')
      .replace(/\b(19|20)\d{2}\b/g, '')
      .replace(/\s+/g, ' ').trim();
    var terms = [b.make, b.model, variant, years(b)].filter(Boolean).join(' ');
    return 'https://www.google.com/search?tbm=isch&q=' + encodeURIComponent(terms);
  }

  // Uploaded photos are keyed by bike id and named on export as <id>.<ext>,
  // so a designer receives bimota-db1-1985.jpg rather than IMG_0421.jpg.
  function imageName(b) {
    var rec = state.images[b.id];
    return rec ? rec.name : '';
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
    var nowMid = midpoint(bike.price && bike.price.private, bike.price && bike.price.dealer);
    var prevMid = midpoint(prev.private, prev.dealer);
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
        price_private: p.private != null ? p.private : null,
        price_dealer: p.dealer != null ? p.dealer : null,
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
      if (pmin !== null && b.price_dealer != null && b.price_dealer < pmin) return false;
      if (pmax !== null && b.price_private != null && b.price_private > pmax) return false;
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

    tr.appendChild(imageCell(b));

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

    tr.appendChild(cell(money(b.price_private), 'num'));
    tr.appendChild(cell(money(b.price_dealer), 'num'));

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

  function imageCell(b) {
    var td = document.createElement('td');
    td.className = 'img-cell';
    // The row toggles open on click, so keep the image controls to themselves.
    td.addEventListener('click', function (e) { e.stopPropagation(); });

    if (state.uploading[b.id]) {
      var busy = document.createElement('div');
      busy.className = 'img-drop';
      busy.textContent = '\u2026';
      busy.title = 'Uploading\u2026';
      td.appendChild(busy);
      return td;
    }

    var rec = state.images[b.id];
    if (rec) {
      var wrap = document.createElement('div');
      wrap.className = 'img-wrap';
      var img = document.createElement('img');
      img.className = 'img-thumb';
      img.src = rec.url;
      img.alt = b.make + ' ' + b.model;
      img.title = imageName(b) + (rec.remote ? ' — shared' : ' — in this browser only, not shared')
                  + '. Click to replace.';
      if (!rec.remote) img.classList.add('img-local');
      img.addEventListener('click', function () { pickFor(b); });
      wrap.appendChild(img);

      var rm = document.createElement('button');
      rm.className = 'img-remove';
      rm.type = 'button';
      rm.textContent = '\u00d7';
      rm.title = 'Remove image';
      rm.addEventListener('click', function () {
        ImageStore.del(b.id, rec.ext).then(function () {
          if (!rec.remote) URL.revokeObjectURL(rec.url);
          delete state.images[b.id];
          render();
        }).catch(function (err) {
          showStatus('<strong>Could not remove that image</strong> — ' + err.message);
        });
      });
      wrap.appendChild(rm);
      td.appendChild(wrap);
    } else {
      var label = document.createElement('label');
      label.className = 'img-drop';
      label.title = 'Upload a photo for ' + b.make + ' ' + b.model;
      label.textContent = '\uff0b';
      var inp = document.createElement('input');
      inp.type = 'file';
      inp.accept = 'image/*';
      inp.addEventListener('change', function () {
        if (inp.files && inp.files[0]) storeImage(b, inp.files[0]);
      });
      label.appendChild(inp);
      td.appendChild(label);
    }
    return td;
  }

  function pickFor(b) {
    var inp = document.createElement('input');
    inp.type = 'file';
    inp.accept = 'image/*';
    inp.addEventListener('change', function () {
      if (inp.files && inp.files[0]) storeImage(b, inp.files[0]);
    });
    inp.click();
  }

  function storeImage(b, file) {
    state.uploading[b.id] = true;
    render();
    ImageStore.put(b.id, file).then(function (rec) {
      delete state.uploading[b.id];
      state.images[b.id] = rec;
      render();
    }).catch(function (err) {
      delete state.uploading[b.id];
      render();
      showStatus('<strong>Could not save that image</strong> — ' + err.message +
                 (ImageStore.shared()
                   ? '. Check the sharing token is still valid.'
                   : '. Browser storage may be full.'));
    });
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
    td.colSpan = 12;

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

    var look = document.createElement('p');
    look.className = 'provenance';
    var a = document.createElement('a');
    a.className = 'image-search';
    a.href = imageSearchUrl(b);
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    a.textContent = 'Image search \u2197';
    a.title = 'Google Images — for checking archive photos, not for publication';
    look.appendChild(a);
    td.appendChild(look);

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
      ['Private', function (b) { return b.price_private; }],
      ['Dealer', function (b) { return b.price_dealer; }],
      ['Category', function (b) { return b.category; }],
      ['Change vs last check', function (b) { return b.change == null ? '' : (Math.round(b.change * 10) / 10) + '%'; }],
      ['Price checked', function (b) { return b.as_of || ''; }],
      ['Price source', function (b) { return b.source; }],
      ['Sample size', function (b) { return b.sample_size || ''; }],
      ['Confidence', function (b) { return b.confidence; }],
      ['ID', function (b) { return b.id; }],
      ['Image search', function (b) { return imageSearchUrl(b); }],
      ['Image file', function (b) { return imageName(b); }]
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

  function exportImages() {
    var view = currentView();
    var wanted = view.filter(function (b) { return state.images[b.id]; });
    if (!wanted.length) {
      showStatus('<strong>No images to download.</strong> Upload photos with the ' +
                 '\uff0b button on each row first — the ZIP includes only the rows ' +
                 'currently shown, so it matches the CSV export.');
      return;
    }
    Promise.all(wanted.map(function (b) {
      return ImageStore.bytesFor(state.images[b.id]).then(function (bytes) {
        return { name: imageName(b), bytes: bytes };
      });
    })).then(function (files) {
      var blob = ImageStore.zip(files);
      var stamp = new Date().toISOString().slice(0, 10);
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url; a.download = 'used-bike-guide-images-' + stamp + '.zip';
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    });
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

  function loadImages() {
    Object.keys(state.images).forEach(function (id) {
      var r = state.images[id];
      if (r && !r.remote && r.url) URL.revokeObjectURL(r.url);
    });
    state.images = {};
    return ImageStore.list().then(function (stored) {
      state.images = stored || {};
      render();
      updateShareLabel();
    }).catch(function () { updateShareLabel(); });
  }

  function updateShareLabel() {
    var btn = $('#sharing');
    if (!btn) return;
    var on = ImageStore.shared();
    btn.textContent = on ? 'Sharing: on' : 'Sharing: off';
    btn.className = 'btn' + (on ? ' btn-primary' : '');
    btn.title = on
      ? 'Images upload to the ' + ImageStore.branch + ' branch and are visible to everyone'
      : 'Images are saved in this browser only — click to turn on sharing';
  }

  function toggleSharing() {
    var panel = $('#share-panel');
    panel.hidden = !panel.hidden;
    if (!panel.hidden) $('#share-token').value = ImageStore.token();
  }

  function saveSharing() {
    ImageStore.setToken($('#share-token').value.trim());
    $('#share-panel').hidden = true;
    loadImages();
    showStatus(ImageStore.shared()
      ? '<strong>Sharing on.</strong> Uploads now go to the <code>' + ImageStore.branch +
        '</code> branch of ' + ImageStore.repo.owner + '/' + ImageStore.repo.repo +
        ' and everyone sees them.'
      : '<strong>Sharing off.</strong> Images are saved in this browser only.');
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
    $('#export-images').addEventListener('click', exportImages);
    $('#sharing').addEventListener('click', toggleSharing);
    $('#share-save').addEventListener('click', saveSharing);
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

    // Pull any previously uploaded photos out of IndexedDB and re-render once.
    loadImages();
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
