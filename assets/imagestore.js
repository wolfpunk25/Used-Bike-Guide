/* Image store for the Used Bike Guide.
 *
 * The site is static — served straight from a GitHub Pages branch with no
 * backend — so uploaded images cannot be posted anywhere. They are held in
 * IndexedDB in the browser instead: enough room for hundreds of photos
 * (localStorage would blow its ~5MB quota on a handful), and they survive a
 * reload. They do NOT sync between people or machines; the ZIP export is how
 * they leave this browser.
 *
 * Also contains a minimal ZIP writer. Photos are already compressed, so the
 * archive uses STORE (no deflate), which keeps this to a few dozen lines and
 * avoids taking a dependency on a CDN that a strict network could block.
 */
window.ImageStore = (function () {
  'use strict';

  var DB = 'ubg-images', STORE = 'images', VERSION = 1;
  var dbp = null;

  function open() {
    if (dbp) return dbp;
    dbp = new Promise(function (resolve, reject) {
      var req = indexedDB.open(DB, VERSION);
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

  function put(id, blob, ext) {
    return tx('readwrite', function (s) {
      return s.put({ blob: blob, ext: ext, added: new Date().toISOString() }, id);
    });
  }
  function get(id) { return tx('readonly', function (s) { return s.get(id); }); }
  function del(id) { return tx('readwrite', function (s) { return s.delete(id); }); }
  function keys() { return tx('readonly', function (s) { return s.getAllKeys(); }); }

  function all() {
    return open().then(function (db) {
      return new Promise(function (resolve, reject) {
        var out = {};
        var t = db.transaction(STORE, 'readonly');
        var cur = t.objectStore(STORE).openCursor();
        cur.onsuccess = function (e) {
          var c = e.target.result;
          if (!c) { resolve(out); return; }
          out[c.key] = c.value;
          c.continue();
        };
        cur.onerror = function () { reject(cur.error); };
      });
    });
  }

  /* ---------------- minimal ZIP (STORE) ---------------- */

  var CRC_TABLE = (function () {
    var t = new Uint32Array(256);
    for (var n = 0; n < 256; n++) {
      var c = n;
      for (var k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
      t[n] = c >>> 0;
    }
    return t;
  })();

  function crc32(bytes) {
    var c = 0xFFFFFFFF;
    for (var i = 0; i < bytes.length; i++) c = CRC_TABLE[(c ^ bytes[i]) & 0xFF] ^ (c >>> 8);
    return (c ^ 0xFFFFFFFF) >>> 0;
  }

  function dosTime(d) {
    return ((d.getHours() << 11) | (d.getMinutes() << 5) | (d.getSeconds() / 2)) & 0xFFFF;
  }
  function dosDate(d) {
    return (((d.getFullYear() - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate()) & 0xFFFF;
  }

  function bytesOf(str) {
    var out = [];
    for (var i = 0; i < str.length; i++) {
      var c = str.charCodeAt(i);
      if (c < 128) out.push(c);
      else out.push(63);                      // '?' — filenames here are ASCII ids
    }
    return new Uint8Array(out);
  }

  function zip(files) {
    // files: [{name, bytes}]
    var chunks = [], central = [], offset = 0, now = new Date();
    var tm = dosTime(now), dt = dosDate(now);

    files.forEach(function (f) {
      var nameB = bytesOf(f.name), crc = crc32(f.bytes), size = f.bytes.length;
      var lh = new DataView(new ArrayBuffer(30));
      lh.setUint32(0, 0x04034b50, true); lh.setUint16(4, 20, true); lh.setUint16(6, 0, true);
      lh.setUint16(8, 0, true);            // STORE
      lh.setUint16(10, tm, true); lh.setUint16(12, dt, true);
      lh.setUint32(14, crc, true); lh.setUint32(18, size, true); lh.setUint32(22, size, true);
      lh.setUint16(26, nameB.length, true); lh.setUint16(28, 0, true);
      chunks.push(new Uint8Array(lh.buffer), nameB, f.bytes);

      var cd = new DataView(new ArrayBuffer(46));
      cd.setUint32(0, 0x02014b50, true); cd.setUint16(4, 20, true); cd.setUint16(6, 20, true);
      cd.setUint16(8, 0, true); cd.setUint16(10, 0, true);
      cd.setUint16(12, tm, true); cd.setUint16(14, dt, true);
      cd.setUint32(16, crc, true); cd.setUint32(20, size, true); cd.setUint32(24, size, true);
      cd.setUint16(28, nameB.length, true); cd.setUint16(30, 0, true); cd.setUint16(32, 0, true);
      cd.setUint16(34, 0, true); cd.setUint16(36, 0, true); cd.setUint32(38, 0, true);
      cd.setUint32(42, offset, true);
      central.push(new Uint8Array(cd.buffer), nameB);

      offset += 30 + nameB.length + size;
    });

    var centralSize = central.reduce(function (n, c) { return n + c.length; }, 0);
    var eocd = new DataView(new ArrayBuffer(22));
    eocd.setUint32(0, 0x06054b50, true);
    eocd.setUint16(8, files.length, true); eocd.setUint16(10, files.length, true);
    eocd.setUint32(12, centralSize, true); eocd.setUint32(16, offset, true);
    eocd.setUint16(20, 0, true);

    return new Blob(chunks.concat(central, [new Uint8Array(eocd.buffer)]),
                    { type: 'application/zip' });
  }

  function blobToBytes(blob) {
    return blob.arrayBuffer().then(function (buf) { return new Uint8Array(buf); });
  }

  return { put: put, get: get, del: del, keys: keys, all: all, zip: zip, blobToBytes: blobToBytes };
})();
