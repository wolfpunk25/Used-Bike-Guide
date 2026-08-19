/* Image store for the Used Bike Guide.
 *
 * Two backends behind one interface, so the page does not care where photos live
 * and the choice can change later without touching the UI:
 *
 *   GitHub  — shared. Reads straight from raw.githubusercontent.com (public, no
 *             auth, updates the instant a commit lands) and writes through the
 *             contents API with a token the user supplies. Photos go on the
 *             `images` branch, NOT main, because Pages builds from main and
 *             throttles at roughly ten builds an hour; a busy afternoon of
 *             uploads would otherwise exhaust that.
 *
 *   Local   — IndexedDB, per-browser. Used when no token is set, so someone can
 *             still work offline or without GitHub access.
 *
 * Photos are resized to 1600px on the long edge before upload. They are for
 * identification and cross-reference, not reproduction — print originals belong
 * in the picture library. GitHub recommends keeping files near 1MB, and 733
 * untouched archive JPEGs would be several gigabytes.
 */
window.ImageStore = (function () {
  'use strict';

  var BRANCH = 'images';
  var MAX_EDGE = 1600;
  var JPEG_Q = 0.82;
  var TOKEN_KEY = 'ubg-github-token';

  // Derive the repo from the Pages URL; fall back for local testing.
  function repoInfo() {
    var m = /^([^.]+)\.github\.io$/.exec(location.hostname);
    if (m) {
      var seg = location.pathname.split('/').filter(Boolean)[0];
      if (seg) return { owner: m[1], repo: seg };
    }
    return { owner: 'wolfpunk25', repo: 'Used-Bike-Guide' };
  }
  var REPO = repoInfo();

  function token() { try { return localStorage.getItem(TOKEN_KEY) || ''; } catch (e) { return ''; } }
  function setToken(t) {
    try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); }
    catch (e) { /* private browsing */ }
  }
  function shared() { return !!token(); }

  function rawUrl(name) {
    return 'https://raw.githubusercontent.com/' + REPO.owner + '/' + REPO.repo +
           '/' + BRANCH + '/' + encodeURIComponent(name) + '?t=' + Date.now();
  }

  function api(path, opts) {
    opts = opts || {};
    var headers = { 'Accept': 'application/vnd.github+json' };
    if (token()) headers.Authorization = 'Bearer ' + token();
    if (opts.body) headers['Content-Type'] = 'application/json';
    var url = 'https://api.github.com/repos/' + REPO.owner + '/' + REPO.repo + path;
    if ((opts.method || 'GET') === 'GET') {
      url += (url.indexOf('?') === -1 ? '?' : '&') + '_=' + Date.now();
    }
    return fetch(url, {
      method: opts.method || 'GET',
      cache: 'no-store',
      headers: headers,
      body: opts.body ? JSON.stringify(opts.body) : undefined
    }).then(function (r) {
      if (r.status === 404) return null;
      return r.json().then(function (j) {
        if (!r.ok) throw new Error(j.message || ('HTTP ' + r.status));
        return j;
      });
    });
  }

  /* ---------------- resizing ---------------- */

  function resize(file) {
    return new Promise(function (resolve, reject) {
      var url = URL.createObjectURL(file);
      var img = new Image();
      img.onload = function () {
        URL.revokeObjectURL(url);
        var w = img.naturalWidth, h = img.naturalHeight;
        var scale = Math.min(1, MAX_EDGE / Math.max(w, h));
        // Always re-encode, even when no resizing is needed. Passing the original
        // through kept its extension, which let .avif and .heic onto the branch
        // where the listing pattern did not match them — the file existed but was
        // invisible, so it looked permanently unshared.
        var c = document.createElement('canvas');
        c.width = Math.round(w * scale); c.height = Math.round(h * scale);
        c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
        c.toBlob(function (b) {
          resolve({ blob: b || file, ext: 'jpg' });
        }, 'image/jpeg', JPEG_Q);
      };
      img.onerror = function () { URL.revokeObjectURL(url); reject(new Error('not a readable image')); };
      img.src = url;
    });
  }

  function extOf(file) {
    var m = /\.([a-z0-9]+)$/i.exec(file.name || '');
    if (m) return m[1].toLowerCase().replace('jpeg', 'jpg');
    if (/png/.test(file.type)) return 'png';
    if (/webp/.test(file.type)) return 'webp';
    return 'jpg';
  }

  function toBase64(blob) {
    return new Promise(function (resolve, reject) {
      var fr = new FileReader();
      fr.onload = function () { resolve(String(fr.result).split(',')[1]); };
      fr.onerror = function () { reject(fr.error); };
      fr.readAsDataURL(blob);
    });
  }

  /* ---------------- GitHub backend ---------------- */

  var shaCache = {};

  function ghList() {
    return api('/contents?ref=' + BRANCH).then(function (items) {
      var out = {};
      (items || []).forEach(function (it) {
        if (it.type !== 'file') return;
        var m = /^(.+)\.(jpg|jpeg|png|webp|avif|heic|gif)$/i.exec(it.name);
        if (!m) return;
        shaCache[it.name] = it.sha;
        out[m[1]] = { ext: m[2].toLowerCase(), name: it.name, url: rawUrl(it.name), remote: true };
      });
      return out;
    }).catch(function () { return {}; });
  }

  function ghPut(id, blob, ext) {
    var name = id + '.' + ext;
    return toBase64(blob).then(function (b64) {
      var body = { message: 'Add image for ' + id, content: b64, branch: BRANCH };
      if (shaCache[name]) body.sha = shaCache[name];
      return api('/contents/' + encodeURIComponent(name), { method: 'PUT', body: body });
    }).then(function (res) {
      if (res && res.content) shaCache[name] = res.content.sha;
      return { ext: ext, name: name, url: rawUrl(name), remote: true };
    }).catch(function (err) {
      // Someone else wrote the same file first — re-read the sha and retry once.
      if (/sha|conflict|409/i.test(err.message)) {
        return api('/contents/' + encodeURIComponent(name) + '?ref=' + BRANCH).then(function (cur) {
          if (cur && cur.sha) shaCache[name] = cur.sha;
          return ghPut(id, blob, ext);
        });
      }
      throw err;
    });
  }

  // A bike must end up with exactly one file. Uploads are always JPEG now, but a
  // .avif or .png from before that could otherwise sit alongside the new .jpg.
  function dropOtherExtensions(id, keepName) {
    var stale = Object.keys(shaCache).filter(function (n) {
      return n !== keepName && n.replace(/\.[a-z0-9]+$/i, '') === id;
    });
    return stale.reduce(function (chain, name) {
      return chain.then(function () {
        return api('/contents/' + encodeURIComponent(name), {
          method: 'DELETE',
          body: { message: 'Replace image for ' + id, sha: shaCache[name], branch: BRANCH }
        }).then(function () { delete shaCache[name]; })
          .catch(function () { /* already gone, or someone beat us to it */ });
      });
    }, Promise.resolve());
  }

  function ghDel(id, ext) {
    var name = id + '.' + ext;
    if (!shaCache[name]) return Promise.resolve();
    return api('/contents/' + encodeURIComponent(name), {
      method: 'DELETE',
      body: { message: 'Remove image for ' + id, sha: shaCache[name], branch: BRANCH }
    }).then(function () { delete shaCache[name]; });
  }

  /* ---------------- local backend ---------------- */

  var DB = 'ubg-images', STORE = 'images', dbp = null;

  function open() {
    if (dbp) return dbp;
    dbp = new Promise(function (resolve, reject) {
      var req = indexedDB.open(DB, 1);
      req.onupgradeneeded = function () {
        var db = req.result;
        if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE);
      };
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error); };
    });
    return dbp;
  }

  function tx(mode, fn) {
    return open().then(function (db) {
      return new Promise(function (resolve, reject) {
        var t = db.transaction(STORE, mode);
        var req = fn(t.objectStore(STORE));
        t.oncomplete = function () { resolve(req && req.result); };
        t.onerror = function () { reject(t.error); };
      });
    });
  }

  function localList() {
    return open().then(function (db) {
      return new Promise(function (resolve, reject) {
        var out = {};
        var t = db.transaction(STORE, 'readonly');
        var cur = t.objectStore(STORE).openCursor();
        cur.onsuccess = function (e) {
          var c = e.target.result;
          if (!c) { resolve(out); return; }
          out[c.key] = { ext: c.value.ext, name: c.key + '.' + c.value.ext,
                         url: URL.createObjectURL(c.value.blob), blob: c.value.blob, remote: false };
          c.continue();
        };
        cur.onerror = function () { reject(cur.error); };
      });
    }).catch(function () { return {}; });
  }

  function localPut(id, blob, ext) {
    return tx('readwrite', function (s) { return s.put({ blob: blob, ext: ext }, id); })
      .then(function () {
        return { ext: ext, name: id + '.' + ext, url: URL.createObjectURL(blob), blob: blob, remote: false };
      });
  }
  function localDel(id) { return tx('readwrite', function (s) { return s.delete(id); }); }

  /* ---------------- public interface ---------------- */

  // Always read the shared set, token or not. The repo is public, so the listing
  // and the images themselves need no auth — a token is only ever needed to WRITE.
  // (This was previously gated on shared(), which meant a colleague opening the
  // page without a token saw nothing at all.)
  function list() {
    return Promise.all([ghList(), localList()]).then(function (r) {
      var remote = r[0] || {}, local = r[1] || {}, out = {};
      // Anything only in this browser still shows, flagged as not yet shared.
      Object.keys(local).forEach(function (k) { out[k] = local[k]; });
      // The branch is the shared truth, so it wins where both exist.
      var settled = [];
      Object.keys(remote).forEach(function (k) {
        var was = out[k];
        if (was && !was.remote) {
          if (was.url) URL.revokeObjectURL(was.url);
          settled.push(k);          // confirmed on the branch; the local copy is dead weight
        }
        out[k] = remote[k];
      });
      // Tidy up in the background — it must not hold up the first render.
      settled.forEach(function (k) { localDel(k).catch(function () {}); });
      return out;
    });
  }

  // Uploading REQUIRES a token. Storing photos in one browser only was a trap:
  // someone could add a hundred images, connect sharing afterwards, and find none
  // of them had ever left their machine. The UI asks for a token first instead.
  function put(id, file) {
    if (!shared()) return Promise.reject(new Error('NO_TOKEN'));
    return resize(file).then(function (r) {
      // Keep a local copy too, so the thumbnail appears instantly rather than
      // waiting for the commit to reach raw.githubusercontent.com.
      return localPut(id, r.blob, r.ext).then(function () {
        return ghPut(id, r.blob, r.ext);
      }).then(function (rec) {
        // Shared now — the local copy would otherwise linger for ever and keep
        // showing up as "saved in this browser but not shared yet".
        return localDel(id)
          .then(function () { return dropOtherExtensions(id, rec.name); })
          .then(function () {
            // Show the bytes we just uploaded rather than fetching them back.
            // raw.githubusercontent sits behind a CDN that strips the query
            // string from its cache key, so the ?t= on rawUrl() is not the
            // cache-buster it looks like: for up to five minutes after a
            // REPLACE the CDN keeps serving the previous image, which made a
            // successful replace look as though it had silently failed.
            // The file really is on the branch, so this stays flagged remote —
            // only the display source is local, and the next page load (by
            // which time the CDN has caught up) goes back to the raw URL.
            rec.url = URL.createObjectURL(r.blob);
            return rec;
          });
      });
    });
  }

  // Check a token really works before we rely on it — a typo'd or expired token
  // would otherwise fail silently at the moment someone tries to upload.
  function validateToken(t) {
    return fetch('https://api.github.com/repos/' + REPO.owner + '/' + REPO.repo, {
      headers: { Accept: 'application/vnd.github+json', Authorization: 'Bearer ' + t }
    }).then(function (r) {
      if (r.status === 401) throw new Error('That token was not accepted — check it was copied in full.');
      if (!r.ok) throw new Error('GitHub returned HTTP ' + r.status + '.');
      return r.json();
    }).then(function (j) {
      if (!j.permissions || !j.permissions.push) {
        throw new Error('That token can read the repository but not write to it. ' +
                        'Set Repository permissions \u2192 Contents: Read and write.');
      }
      return true;
    });
  }

  // Push anything stranded in this browser up to the shared branch.
  function pushLocal(onProgress) {
    if (!shared()) return Promise.reject(new Error('NO_TOKEN'));
    return localList().then(function (local) {
      var ids = Object.keys(local).filter(function (k) { return !local[k].remote; });
      var done = 0;
      return ids.reduce(function (chain, id) {
        return chain.then(function () {
          return ghPut(id, local[id].blob, local[id].ext)
            .then(function () { return localDel(id); })
            .then(function () {
              done++; if (onProgress) onProgress(done, ids.length);
            });
        });
      }, Promise.resolve()).then(function () { return done; });
    });
  }

  function del(id, ext) {
    return localDel(id).then(function () { return shared() ? ghDel(id, ext) : null; });
  }

  function bytesFor(rec) {
    if (rec.blob) return rec.blob.arrayBuffer().then(function (b) { return new Uint8Array(b); });
    return fetch(rec.url).then(function (r) { return r.arrayBuffer(); })
      .then(function (b) { return new Uint8Array(b); });
  }

  /* ---------------- minimal ZIP (STORE) ---------------- */

  var CRC = (function () {
    var t = new Uint32Array(256);
    for (var n = 0; n < 256; n++) {
      var c = n;
      for (var k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
      t[n] = c >>> 0;
    }
    return t;
  })();
  function crc32(b) {
    var c = 0xFFFFFFFF;
    for (var i = 0; i < b.length; i++) c = CRC[(c ^ b[i]) & 0xFF] ^ (c >>> 8);
    return (c ^ 0xFFFFFFFF) >>> 0;
  }
  function bytesOf(s) {
    var o = [];
    for (var i = 0; i < s.length; i++) { var c = s.charCodeAt(i); o.push(c < 128 ? c : 63); }
    return new Uint8Array(o);
  }
  function zip(files) {
    var chunks = [], central = [], offset = 0, d = new Date();
    var tm = ((d.getHours() << 11) | (d.getMinutes() << 5) | (d.getSeconds() / 2)) & 0xFFFF;
    var dt = (((d.getFullYear() - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate()) & 0xFFFF;
    files.forEach(function (f) {
      var nb = bytesOf(f.name), crc = crc32(f.bytes), size = f.bytes.length;
      var lh = new DataView(new ArrayBuffer(30));
      lh.setUint32(0, 0x04034b50, true); lh.setUint16(4, 20, true);
      lh.setUint16(10, tm, true); lh.setUint16(12, dt, true);
      lh.setUint32(14, crc, true); lh.setUint32(18, size, true); lh.setUint32(22, size, true);
      lh.setUint16(26, nb.length, true);
      chunks.push(new Uint8Array(lh.buffer), nb, f.bytes);
      var cd = new DataView(new ArrayBuffer(46));
      cd.setUint32(0, 0x02014b50, true); cd.setUint16(4, 20, true); cd.setUint16(6, 20, true);
      cd.setUint16(12, tm, true); cd.setUint16(14, dt, true);
      cd.setUint32(16, crc, true); cd.setUint32(20, size, true); cd.setUint32(24, size, true);
      cd.setUint16(28, nb.length, true); cd.setUint32(42, offset, true);
      central.push(new Uint8Array(cd.buffer), nb);
      offset += 30 + nb.length + size;
    });
    var cs = central.reduce(function (n, c) { return n + c.length; }, 0);
    var e = new DataView(new ArrayBuffer(22));
    e.setUint32(0, 0x06054b50, true);
    e.setUint16(8, files.length, true); e.setUint16(10, files.length, true);
    e.setUint32(12, cs, true); e.setUint32(16, offset, true);
    return new Blob(chunks.concat(central, [new Uint8Array(e.buffer)]), { type: 'application/zip' });
  }

  return {
    list: list, put: put, del: del, bytesFor: bytesFor, zip: zip,
    token: token, setToken: setToken, shared: shared, repo: REPO, branch: BRANCH,
    validateToken: validateToken, pushLocal: pushLocal, localList: localList
  };
})();
