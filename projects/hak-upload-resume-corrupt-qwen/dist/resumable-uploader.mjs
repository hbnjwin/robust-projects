import { ref as K, computed as G, readonly as ot, defineComponent as ut, resolveComponent as J, openBlock as O, createElementBlock as P, createVNode as m, withCtx as B, unref as A, createElementVNode as D, createTextVNode as T, toDisplayString as X, createCommentVNode as j, createBlock as it, Fragment as Z } from "vue";
import { ElMessage as V } from "element-plus";
import { UploadFilled as lt, Document as ft, VideoPause as ct, Close as Q, VideoPlay as ht, RefreshRight as dt, Check as pt } from "@element-plus/icons-vue";
import gt from "axios";
const W = gt.create({
  baseURL: "/api",
  timeout: 6e4
});
async function yt(h) {
  const { data: u } = await W.post("/file/init", h);
  return u.data;
}
async function mt(h, u, c, l, p) {
  const g = new FormData();
  g.append("file", c), g.append("uploadId", h), g.append("chunkIndex", String(u)), g.append("chunkMd5", l);
  const { data: v } = await W.post(
    "/file/upload-chunk",
    g,
    { signal: p, timeout: 12e4 }
  );
  return v.data;
}
async function rt(h) {
  const { data: u } = await W.get("/file/status", {
    params: { uploadId: h }
  });
  return u.data;
}
async function nt(h) {
  const { data: u } = await W.post("/file/merge", h);
  return u.data;
}
function _t(h) {
  return h && h.__esModule && Object.prototype.hasOwnProperty.call(h, "default") ? h.default : h;
}
var at = { exports: {} };
(function(h, u) {
  (function(c) {
    h.exports = c();
  })(function(c) {
    var l = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "a", "b", "c", "d", "e", "f"];
    function p(s, a) {
      var e = s[0], t = s[1], n = s[2], r = s[3];
      e += (t & n | ~t & r) + a[0] - 680876936 | 0, e = (e << 7 | e >>> 25) + t | 0, r += (e & t | ~e & n) + a[1] - 389564586 | 0, r = (r << 12 | r >>> 20) + e | 0, n += (r & e | ~r & t) + a[2] + 606105819 | 0, n = (n << 17 | n >>> 15) + r | 0, t += (n & r | ~n & e) + a[3] - 1044525330 | 0, t = (t << 22 | t >>> 10) + n | 0, e += (t & n | ~t & r) + a[4] - 176418897 | 0, e = (e << 7 | e >>> 25) + t | 0, r += (e & t | ~e & n) + a[5] + 1200080426 | 0, r = (r << 12 | r >>> 20) + e | 0, n += (r & e | ~r & t) + a[6] - 1473231341 | 0, n = (n << 17 | n >>> 15) + r | 0, t += (n & r | ~n & e) + a[7] - 45705983 | 0, t = (t << 22 | t >>> 10) + n | 0, e += (t & n | ~t & r) + a[8] + 1770035416 | 0, e = (e << 7 | e >>> 25) + t | 0, r += (e & t | ~e & n) + a[9] - 1958414417 | 0, r = (r << 12 | r >>> 20) + e | 0, n += (r & e | ~r & t) + a[10] - 42063 | 0, n = (n << 17 | n >>> 15) + r | 0, t += (n & r | ~n & e) + a[11] - 1990404162 | 0, t = (t << 22 | t >>> 10) + n | 0, e += (t & n | ~t & r) + a[12] + 1804603682 | 0, e = (e << 7 | e >>> 25) + t | 0, r += (e & t | ~e & n) + a[13] - 40341101 | 0, r = (r << 12 | r >>> 20) + e | 0, n += (r & e | ~r & t) + a[14] - 1502002290 | 0, n = (n << 17 | n >>> 15) + r | 0, t += (n & r | ~n & e) + a[15] + 1236535329 | 0, t = (t << 22 | t >>> 10) + n | 0, e += (t & r | n & ~r) + a[1] - 165796510 | 0, e = (e << 5 | e >>> 27) + t | 0, r += (e & n | t & ~n) + a[6] - 1069501632 | 0, r = (r << 9 | r >>> 23) + e | 0, n += (r & t | e & ~t) + a[11] + 643717713 | 0, n = (n << 14 | n >>> 18) + r | 0, t += (n & e | r & ~e) + a[0] - 373897302 | 0, t = (t << 20 | t >>> 12) + n | 0, e += (t & r | n & ~r) + a[5] - 701558691 | 0, e = (e << 5 | e >>> 27) + t | 0, r += (e & n | t & ~n) + a[10] + 38016083 | 0, r = (r << 9 | r >>> 23) + e | 0, n += (r & t | e & ~t) + a[15] - 660478335 | 0, n = (n << 14 | n >>> 18) + r | 0, t += (n & e | r & ~e) + a[4] - 405537848 | 0, t = (t << 20 | t >>> 12) + n | 0, e += (t & r | n & ~r) + a[9] + 568446438 | 0, e = (e << 5 | e >>> 27) + t | 0, r += (e & n | t & ~n) + a[14] - 1019803690 | 0, r = (r << 9 | r >>> 23) + e | 0, n += (r & t | e & ~t) + a[3] - 187363961 | 0, n = (n << 14 | n >>> 18) + r | 0, t += (n & e | r & ~e) + a[8] + 1163531501 | 0, t = (t << 20 | t >>> 12) + n | 0, e += (t & r | n & ~r) + a[13] - 1444681467 | 0, e = (e << 5 | e >>> 27) + t | 0, r += (e & n | t & ~n) + a[2] - 51403784 | 0, r = (r << 9 | r >>> 23) + e | 0, n += (r & t | e & ~t) + a[7] + 1735328473 | 0, n = (n << 14 | n >>> 18) + r | 0, t += (n & e | r & ~e) + a[12] - 1926607734 | 0, t = (t << 20 | t >>> 12) + n | 0, e += (t ^ n ^ r) + a[5] - 378558 | 0, e = (e << 4 | e >>> 28) + t | 0, r += (e ^ t ^ n) + a[8] - 2022574463 | 0, r = (r << 11 | r >>> 21) + e | 0, n += (r ^ e ^ t) + a[11] + 1839030562 | 0, n = (n << 16 | n >>> 16) + r | 0, t += (n ^ r ^ e) + a[14] - 35309556 | 0, t = (t << 23 | t >>> 9) + n | 0, e += (t ^ n ^ r) + a[1] - 1530992060 | 0, e = (e << 4 | e >>> 28) + t | 0, r += (e ^ t ^ n) + a[4] + 1272893353 | 0, r = (r << 11 | r >>> 21) + e | 0, n += (r ^ e ^ t) + a[7] - 155497632 | 0, n = (n << 16 | n >>> 16) + r | 0, t += (n ^ r ^ e) + a[10] - 1094730640 | 0, t = (t << 23 | t >>> 9) + n | 0, e += (t ^ n ^ r) + a[13] + 681279174 | 0, e = (e << 4 | e >>> 28) + t | 0, r += (e ^ t ^ n) + a[0] - 358537222 | 0, r = (r << 11 | r >>> 21) + e | 0, n += (r ^ e ^ t) + a[3] - 722521979 | 0, n = (n << 16 | n >>> 16) + r | 0, t += (n ^ r ^ e) + a[6] + 76029189 | 0, t = (t << 23 | t >>> 9) + n | 0, e += (t ^ n ^ r) + a[9] - 640364487 | 0, e = (e << 4 | e >>> 28) + t | 0, r += (e ^ t ^ n) + a[12] - 421815835 | 0, r = (r << 11 | r >>> 21) + e | 0, n += (r ^ e ^ t) + a[15] + 530742520 | 0, n = (n << 16 | n >>> 16) + r | 0, t += (n ^ r ^ e) + a[2] - 995338651 | 0, t = (t << 23 | t >>> 9) + n | 0, e += (n ^ (t | ~r)) + a[0] - 198630844 | 0, e = (e << 6 | e >>> 26) + t | 0, r += (t ^ (e | ~n)) + a[7] + 1126891415 | 0, r = (r << 10 | r >>> 22) + e | 0, n += (e ^ (r | ~t)) + a[14] - 1416354905 | 0, n = (n << 15 | n >>> 17) + r | 0, t += (r ^ (n | ~e)) + a[5] - 57434055 | 0, t = (t << 21 | t >>> 11) + n | 0, e += (n ^ (t | ~r)) + a[12] + 1700485571 | 0, e = (e << 6 | e >>> 26) + t | 0, r += (t ^ (e | ~n)) + a[3] - 1894986606 | 0, r = (r << 10 | r >>> 22) + e | 0, n += (e ^ (r | ~t)) + a[10] - 1051523 | 0, n = (n << 15 | n >>> 17) + r | 0, t += (r ^ (n | ~e)) + a[1] - 2054922799 | 0, t = (t << 21 | t >>> 11) + n | 0, e += (n ^ (t | ~r)) + a[8] + 1873313359 | 0, e = (e << 6 | e >>> 26) + t | 0, r += (t ^ (e | ~n)) + a[15] - 30611744 | 0, r = (r << 10 | r >>> 22) + e | 0, n += (e ^ (r | ~t)) + a[6] - 1560198380 | 0, n = (n << 15 | n >>> 17) + r | 0, t += (r ^ (n | ~e)) + a[13] + 1309151649 | 0, t = (t << 21 | t >>> 11) + n | 0, e += (n ^ (t | ~r)) + a[4] - 145523070 | 0, e = (e << 6 | e >>> 26) + t | 0, r += (t ^ (e | ~n)) + a[11] - 1120210379 | 0, r = (r << 10 | r >>> 22) + e | 0, n += (e ^ (r | ~t)) + a[2] + 718787259 | 0, n = (n << 15 | n >>> 17) + r | 0, t += (r ^ (n | ~e)) + a[9] - 343485551 | 0, t = (t << 21 | t >>> 11) + n | 0, s[0] = e + s[0] | 0, s[1] = t + s[1] | 0, s[2] = n + s[2] | 0, s[3] = r + s[3] | 0;
    }
    function g(s) {
      var a = [], e;
      for (e = 0; e < 64; e += 4)
        a[e >> 2] = s.charCodeAt(e) + (s.charCodeAt(e + 1) << 8) + (s.charCodeAt(e + 2) << 16) + (s.charCodeAt(e + 3) << 24);
      return a;
    }
    function v(s) {
      var a = [], e;
      for (e = 0; e < 64; e += 4)
        a[e >> 2] = s[e] + (s[e + 1] << 8) + (s[e + 2] << 16) + (s[e + 3] << 24);
      return a;
    }
    function U(s) {
      var a = s.length, e = [1732584193, -271733879, -1732584194, 271733878], t, n, r, i, I, N;
      for (t = 64; t <= a; t += 64)
        p(e, g(s.substring(t - 64, t)));
      for (s = s.substring(t - 64), n = s.length, r = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], t = 0; t < n; t += 1)
        r[t >> 2] |= s.charCodeAt(t) << (t % 4 << 3);
      if (r[t >> 2] |= 128 << (t % 4 << 3), t > 55)
        for (p(e, r), t = 0; t < 16; t += 1)
          r[t] = 0;
      return i = a * 8, i = i.toString(16).match(/(.*?)(.{0,8})$/), I = parseInt(i[2], 16), N = parseInt(i[1], 16) || 0, r[14] = I, r[15] = N, p(e, r), e;
    }
    function C(s) {
      var a = s.length, e = [1732584193, -271733879, -1732584194, 271733878], t, n, r, i, I, N;
      for (t = 64; t <= a; t += 64)
        p(e, v(s.subarray(t - 64, t)));
      for (s = t - 64 < a ? s.subarray(t - 64) : new Uint8Array(0), n = s.length, r = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], t = 0; t < n; t += 1)
        r[t >> 2] |= s[t] << (t % 4 << 3);
      if (r[t >> 2] |= 128 << (t % 4 << 3), t > 55)
        for (p(e, r), t = 0; t < 16; t += 1)
          r[t] = 0;
      return i = a * 8, i = i.toString(16).match(/(.*?)(.{0,8})$/), I = parseInt(i[2], 16), N = parseInt(i[1], 16) || 0, r[14] = I, r[15] = N, p(e, r), e;
    }
    function F(s) {
      var a = "", e;
      for (e = 0; e < 4; e += 1)
        a += l[s >> e * 8 + 4 & 15] + l[s >> e * 8 & 15];
      return a;
    }
    function _(s) {
      var a;
      for (a = 0; a < s.length; a += 1)
        s[a] = F(s[a]);
      return s.join("");
    }
    _(U("hello")), typeof ArrayBuffer < "u" && !ArrayBuffer.prototype.slice && function() {
      function s(a, e) {
        return a = a | 0 || 0, a < 0 ? Math.max(a + e, 0) : Math.min(a, e);
      }
      ArrayBuffer.prototype.slice = function(a, e) {
        var t = this.byteLength, n = s(a, t), r = t, i, I, N, Y;
        return e !== c && (r = s(e, t)), n > r ? new ArrayBuffer(0) : (i = r - n, I = new ArrayBuffer(i), N = new Uint8Array(I), Y = new Uint8Array(this, n, i), N.set(Y), I);
      };
    }();
    function w(s) {
      return /[\u0080-\uFFFF]/.test(s) && (s = unescape(encodeURIComponent(s))), s;
    }
    function b(s, a) {
      var e = s.length, t = new ArrayBuffer(e), n = new Uint8Array(t), r;
      for (r = 0; r < e; r += 1)
        n[r] = s.charCodeAt(r);
      return a ? n : t;
    }
    function L(s) {
      return String.fromCharCode.apply(null, new Uint8Array(s));
    }
    function z(s, a, e) {
      var t = new Uint8Array(s.byteLength + a.byteLength);
      return t.set(new Uint8Array(s)), t.set(new Uint8Array(a), s.byteLength), t;
    }
    function $(s) {
      var a = [], e = s.length, t;
      for (t = 0; t < e - 1; t += 2)
        a.push(parseInt(s.substr(t, 2), 16));
      return String.fromCharCode.apply(String, a);
    }
    function y() {
      this.reset();
    }
    return y.prototype.append = function(s) {
      return this.appendBinary(w(s)), this;
    }, y.prototype.appendBinary = function(s) {
      this._buff += s, this._length += s.length;
      var a = this._buff.length, e;
      for (e = 64; e <= a; e += 64)
        p(this._hash, g(this._buff.substring(e - 64, e)));
      return this._buff = this._buff.substring(e - 64), this;
    }, y.prototype.end = function(s) {
      var a = this._buff, e = a.length, t, n = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], r;
      for (t = 0; t < e; t += 1)
        n[t >> 2] |= a.charCodeAt(t) << (t % 4 << 3);
      return this._finish(n, e), r = _(this._hash), s && (r = $(r)), this.reset(), r;
    }, y.prototype.reset = function() {
      return this._buff = "", this._length = 0, this._hash = [1732584193, -271733879, -1732584194, 271733878], this;
    }, y.prototype.getState = function() {
      return {
        buff: this._buff,
        length: this._length,
        hash: this._hash.slice()
      };
    }, y.prototype.setState = function(s) {
      return this._buff = s.buff, this._length = s.length, this._hash = s.hash, this;
    }, y.prototype.destroy = function() {
      delete this._hash, delete this._buff, delete this._length;
    }, y.prototype._finish = function(s, a) {
      var e = a, t, n, r;
      if (s[e >> 2] |= 128 << (e % 4 << 3), e > 55)
        for (p(this._hash, s), e = 0; e < 16; e += 1)
          s[e] = 0;
      t = this._length * 8, t = t.toString(16).match(/(.*?)(.{0,8})$/), n = parseInt(t[2], 16), r = parseInt(t[1], 16) || 0, s[14] = n, s[15] = r, p(this._hash, s);
    }, y.hash = function(s, a) {
      return y.hashBinary(w(s), a);
    }, y.hashBinary = function(s, a) {
      var e = U(s), t = _(e);
      return a ? $(t) : t;
    }, y.ArrayBuffer = function() {
      this.reset();
    }, y.ArrayBuffer.prototype.append = function(s) {
      var a = z(this._buff.buffer, s), e = a.length, t;
      for (this._length += s.byteLength, t = 64; t <= e; t += 64)
        p(this._hash, v(a.subarray(t - 64, t)));
      return this._buff = t - 64 < e ? new Uint8Array(a.buffer.slice(t - 64)) : new Uint8Array(0), this;
    }, y.ArrayBuffer.prototype.end = function(s) {
      var a = this._buff, e = a.length, t = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], n, r;
      for (n = 0; n < e; n += 1)
        t[n >> 2] |= a[n] << (n % 4 << 3);
      return this._finish(t, e), r = _(this._hash), s && (r = $(r)), this.reset(), r;
    }, y.ArrayBuffer.prototype.reset = function() {
      return this._buff = new Uint8Array(0), this._length = 0, this._hash = [1732584193, -271733879, -1732584194, 271733878], this;
    }, y.ArrayBuffer.prototype.getState = function() {
      var s = y.prototype.getState.call(this);
      return s.buff = L(s.buff), s;
    }, y.ArrayBuffer.prototype.setState = function(s) {
      return s.buff = b(s.buff, !0), y.prototype.setState.call(this, s);
    }, y.ArrayBuffer.prototype.destroy = y.prototype.destroy, y.ArrayBuffer.prototype._finish = y.prototype._finish, y.ArrayBuffer.hash = function(s, a) {
      var e = C(new Uint8Array(s)), t = _(e);
      return a ? $(t) : t;
    }, y;
  });
})(at);
var vt = at.exports;
const st = /* @__PURE__ */ _t(vt), k = 2 * 1024 * 1024;
function wt(h, u) {
  return new Promise((c, l) => {
    const p = Math.ceil(h.size / k);
    let g = 0;
    const v = new st.ArrayBuffer(), U = () => {
      const C = g * k, F = Math.min(C + k, h.size), _ = h.slice(C, F), w = new FileReader();
      w.onload = (b) => {
        v.append(b.target.result), g++, u == null || u(Math.round(g / p * 100)), g < p ? setTimeout(U, 0) : c(v.end());
      }, w.onerror = () => l(new Error("文件读取失败")), w.readAsArrayBuffer(_);
    };
    U();
  });
}
function bt(h) {
  return new Promise((u, c) => {
    const l = new FileReader();
    l.onload = (p) => {
      const g = st.ArrayBuffer.hash(p.target.result);
      u(g);
    }, l.onerror = () => c(new Error("分片读取失败")), l.readAsArrayBuffer(h);
  });
}
async function At(h, u, c) {
  const l = Math.ceil(h.size / u), p = {};
  for (let g = 0; g < l; g++) {
    const v = g * u, U = Math.min(v + u, h.size), C = h.slice(v, U);
    p[g] = await bt(C), c == null || c(Math.round((g + 1) / l * 100));
  }
  return p;
}
const q = 5 * 1024 * 1024, Ct = 3, tt = 3, Mt = 1e3, et = "upload_meta_";
function St(h = Ct) {
  const u = K("idle"), c = K(0), l = K(0), p = K(0), g = K("");
  let v = null, U = "", C = "", F = {}, _ = 0, w = !1, b = !1, L = [], z = /* @__PURE__ */ new Set();
  const $ = G(() => ({
    status: u.value,
    progress: c.value,
    uploadedCount: l.value,
    totalCount: p.value,
    errorMsg: g.value
  }));
  function y(o) {
    try {
      const f = et + o.name + "_" + o.size, M = localStorage.getItem(f);
      if (!M) return null;
      const S = JSON.parse(M);
      if (S.fileName === o.name && S.fileSize === o.size)
        return S;
    } catch {
    }
    return null;
  }
  function s(o) {
    try {
      const f = et + o.fileName + "_" + o.fileSize;
      localStorage.setItem(f, JSON.stringify(o));
    } catch {
    }
  }
  function a(o, f) {
    try {
      const M = et + o + "_" + f;
      localStorage.removeItem(M);
    } catch {
    }
  }
  function e() {
    l.value = z.size, p.value = _, _ > 0 && (c.value = Math.round(z.size / _ * 100));
  }
  function t(o) {
    return new Promise((f) => setTimeout(f, o));
  }
  async function n(o) {
    if (!v) throw new Error("文件未设置");
    const f = o * q, M = Math.min(f + q, v.size), S = v.slice(f, M), d = F[o];
    for (let R = 0; R < tt; R++) {
      if (w || b) return;
      const E = new AbortController();
      L.push(E);
      try {
        if ((await mt(
          U,
          o,
          S,
          d,
          E.signal
        )).success) {
          z.add(o), e();
          return;
        }
      } catch (H) {
        if ((H == null ? void 0 : H.name) === "AbortError" || b) return;
        R < tt - 1 && await t(Mt * Math.pow(2, R));
      }
    }
    throw new Error(`分片 ${o} 上传失败（已重试 ${tt} 次）`);
  }
  async function r(o) {
    const f = [];
    let M = 0;
    async function S() {
      for (; M < o.length; ) {
        if (w || b) return;
        const R = M++, E = o[R];
        if (!z.has(E))
          try {
            await n(E);
          } catch (H) {
            f.push(H);
            return;
          }
      }
    }
    const d = Array.from(
      { length: Math.min(h, o.length) },
      () => S()
    );
    if (await Promise.all(d), f.length > 0 && !w && !b)
      throw f[0];
  }
  async function i() {
    const f = (await rt(U)).uploadedChunks;
    z = new Set(f.map((d) => d.index));
    const M = [];
    for (let d = 0; d < _; d++)
      z.has(d) || M.push(d);
    const S = [];
    for (const d of f)
      F[d.index] && F[d.index] !== d.md5 && S.push(d.index);
    if (S.length > 0) {
      for (const d of S)
        z.delete(d);
      M.push(...S);
    }
    return e(), M.sort((d, R) => d - R);
  }
  async function I(o) {
    v = o, w = !1, b = !1, g.value = "", L = [], z = /* @__PURE__ */ new Set();
    try {
      u.value = "hashing", c.value = 0;
      const f = y(o);
      if (f ? (C = f.fileHash, F = f.chunkMd5Map, U = f.uploadId, _ = f.totalChunks) : (C = await wt(o, (E) => {
        c.value = Math.round(E * 0.2);
      }), _ = Math.ceil(o.size / q), F = await At(o, q, (E) => {
        c.value = 20 + Math.round(E * 0.1);
      })), p.value = _, b) return;
      if (w) {
        u.value = "paused";
        return;
      }
      const M = await yt({
        fileName: o.name,
        fileSize: o.size,
        totalChunks: _,
        chunkSize: q,
        fileHash: C
      });
      U = M.uploadId, s({
        uploadId: U,
        fileName: o.name,
        fileSize: o.size,
        totalChunks: _,
        chunkSize: q,
        fileHash: C,
        chunkMd5Map: F
      }), z = new Set(M.uploadedChunks.map((E) => E.index)), e(), u.value = "uploading";
      const S = Array.from({ length: _ }, (E, H) => H).filter(
        (E) => !z.has(E)
      );
      if (S.length > 0 && await r(S), b) return;
      if (w) {
        u.value = "paused";
        return;
      }
      u.value = "merging";
      const d = await i();
      if (d.length > 0) {
        if (u.value = "uploading", await r(d), b || w) return;
        u.value = "merging";
        const E = await i();
        if (E.length > 0)
          throw new Error(`合并校验失败：仍有 ${E.length} 个分片缺失`);
      }
      const R = await nt({
        uploadId: U,
        fileName: o.name,
        fileHash: C
      });
      if (!R.success)
        throw new Error(R.errorMsg || "文件合并失败");
      return a(o.name, o.size), u.value = "done", c.value = 100, l.value = _, R.fileUrl;
    } catch (f) {
      if ((f == null ? void 0 : f.name) === "AbortError" || b) {
        u.value = "idle";
        return;
      }
      throw u.value = "error", g.value = (f == null ? void 0 : f.message) || "上传失败", f;
    }
  }
  function N() {
    u.value === "uploading" && (w = !0, u.value = "paused");
  }
  async function Y() {
    if (!(u.value !== "paused" || !v)) {
      w = !1, b = !1, L = [];
      try {
        const o = await rt(U);
        z = new Set(o.uploadedChunks.map((d) => d.index)), e(), u.value = "uploading";
        const f = Array.from({ length: _ }, (d, R) => R).filter(
          (d) => !z.has(d)
        );
        if (f.length > 0 && await r(f), b) return;
        if (w) {
          u.value = "paused";
          return;
        }
        u.value = "merging";
        const M = await i();
        if (M.length > 0) {
          if (u.value = "uploading", await r(M), b || w) return;
          u.value = "merging";
          const d = await i();
          if (d.length > 0)
            throw new Error(`合并校验失败：仍有 ${d.length} 个分片缺失`);
        }
        const S = await nt({
          uploadId: U,
          fileName: v.name,
          fileHash: C
        });
        if (!S.success)
          throw new Error(S.errorMsg || "文件合并失败");
        return a(v.name, v.size), u.value = "done", c.value = 100, l.value = _, S.fileUrl;
      } catch (o) {
        if ((o == null ? void 0 : o.name) === "AbortError" || b) {
          u.value = "idle";
          return;
        }
        throw u.value = "error", g.value = (o == null ? void 0 : o.message) || "上传失败", o;
      }
    }
  }
  function x() {
    b = !0, w = !1;
    for (const o of L)
      o.abort();
    L = [], u.value = "idle", c.value = 0, l.value = 0, g.value = "";
  }
  return {
    state: ot($),
    start: I,
    pause: N,
    resume: Y,
    cancel: x
  };
}
const Bt = { class: "resumable-uploader" }, Ut = {
  key: 0,
  class: "upload-info"
}, Et = { class: "file-name" }, zt = { class: "file-size" }, Ft = { class: "progress-area" }, Rt = { class: "progress-detail" }, It = { key: 0 }, Nt = { class: "action-buttons" }, xt = /* @__PURE__ */ ut({
  __name: "ResumableUploader",
  emits: ["success", "error"],
  setup(h, { emit: u }) {
    const c = u, { state: l, start: p, pause: g, resume: v, cancel: U } = St(3), C = K(""), F = K(0);
    let _ = null;
    const w = G(
      () => ["hashing", "uploading", "merging"].includes(l.value.status)
    ), b = G(() => {
      switch (l.value.status) {
        case "idle":
          return "准备上传";
        case "hashing":
          return "计算文件指纹...";
        case "uploading":
          return `上传中 ${l.value.progress}%`;
        case "paused":
          return "已暂停";
        case "merging":
          return "合并文件中...";
        case "done":
          return "上传完成";
        case "error":
          return "上传出错";
        default:
          return "";
      }
    }), L = G(() => {
      switch (l.value.status) {
        case "done":
          return "success";
        case "error":
          return "exception";
        default:
          return;
      }
    });
    function z(n) {
      if (n === 0) return "0 B";
      const r = ["B", "KB", "MB", "GB"], i = Math.floor(Math.log(n) / Math.log(1024));
      return (n / Math.pow(1024, i)).toFixed(1) + " " + r[i];
    }
    async function $(n) {
      const r = n.raw;
      if (r) {
        _ = r, C.value = r.name, F.value = r.size;
        try {
          const i = await p(r);
          i && (V.success("文件上传成功"), c("success", i));
        } catch (i) {
          V.error((i == null ? void 0 : i.message) || "上传失败"), c("error", (i == null ? void 0 : i.message) || "上传失败");
        }
      }
    }
    async function y() {
      g(), V.info("上传已暂停");
    }
    async function s() {
      try {
        const n = await v();
        n && (V.success("文件上传成功"), c("success", n));
      } catch (n) {
        V.error((n == null ? void 0 : n.message) || "续传失败"), c("error", (n == null ? void 0 : n.message) || "续传失败");
      }
    }
    function a() {
      U(), C.value = "", F.value = 0, _ = null, V.info("上传已取消");
    }
    async function e() {
      if (_)
        try {
          const n = await p(_);
          n && (V.success("文件上传成功"), c("success", n));
        } catch (n) {
          V.error((n == null ? void 0 : n.message) || "重试失败"), c("error", (n == null ? void 0 : n.message) || "重试失败");
        }
    }
    function t() {
      C.value = "", F.value = 0, _ = null;
    }
    return (n, r) => {
      const i = J("el-icon"), I = J("el-upload"), N = J("el-progress"), Y = J("el-alert"), x = J("el-button");
      return O(), P("div", Bt, [
        m(I, {
          "auto-upload": !1,
          "show-file-list": !1,
          "on-change": $,
          disabled: w.value,
          drag: "",
          class: "upload-dragger"
        }, {
          tip: B(() => [...r[0] || (r[0] = [
            D("div", { class: "el-upload__tip" }, "支持 PDF 等格式，单文件最大 500MB", -1)
          ])]),
          default: B(() => [
            m(i, { size: 40 }, {
              default: B(() => [
                m(A(lt))
              ]),
              _: 1
            }),
            r[1] || (r[1] = D("div", { class: "el-upload__text" }, [
              T(" 将文件拖拽到此处，或"),
              D("em", null, "点击选择文件")
            ], -1))
          ]),
          _: 1
        }, 8, ["disabled"]),
        C.value ? (O(), P("div", Ut, [
          D("div", Et, [
            m(i, null, {
              default: B(() => [
                m(A(ft))
              ]),
              _: 1
            }),
            D("span", null, X(C.value), 1),
            D("span", zt, X(z(F.value)), 1)
          ]),
          D("div", Ft, [
            m(N, {
              percentage: A(l).progress,
              status: L.value,
              "stroke-width": 12,
              striped: "",
              "striped-flow": ""
            }, null, 8, ["percentage", "status"]),
            D("div", Rt, [
              D("span", null, X(b.value), 1),
              A(l).status === "uploading" || A(l).status === "paused" ? (O(), P("span", It, X(A(l).uploadedCount) + " / " + X(A(l).totalCount) + " 分片 ", 1)) : j("", !0)
            ])
          ]),
          A(l).status === "error" ? (O(), it(Y, {
            key: 0,
            title: A(l).errorMsg,
            type: "error",
            "show-icon": "",
            closable: !1,
            class: "error-alert"
          }, null, 8, ["title"])) : j("", !0),
          D("div", Nt, [
            A(l).status === "uploading" ? (O(), P(Z, { key: 0 }, [
              m(x, {
                type: "warning",
                onClick: y
              }, {
                default: B(() => [
                  m(i, null, {
                    default: B(() => [
                      m(A(ct))
                    ]),
                    _: 1
                  }),
                  r[2] || (r[2] = T("暂停 ", -1))
                ]),
                _: 1
              }),
              m(x, {
                type: "danger",
                onClick: a
              }, {
                default: B(() => [
                  m(i, null, {
                    default: B(() => [
                      m(A(Q))
                    ]),
                    _: 1
                  }),
                  r[3] || (r[3] = T("取消 ", -1))
                ]),
                _: 1
              })
            ], 64)) : j("", !0),
            A(l).status === "paused" ? (O(), P(Z, { key: 1 }, [
              m(x, {
                type: "primary",
                onClick: s
              }, {
                default: B(() => [
                  m(i, null, {
                    default: B(() => [
                      m(A(ht))
                    ]),
                    _: 1
                  }),
                  r[4] || (r[4] = T("继续上传 ", -1))
                ]),
                _: 1
              }),
              m(x, {
                type: "danger",
                onClick: a
              }, {
                default: B(() => [
                  m(i, null, {
                    default: B(() => [
                      m(A(Q))
                    ]),
                    _: 1
                  }),
                  r[5] || (r[5] = T("取消 ", -1))
                ]),
                _: 1
              })
            ], 64)) : j("", !0),
            A(l).status === "error" ? (O(), P(Z, { key: 2 }, [
              m(x, {
                type: "primary",
                onClick: e
              }, {
                default: B(() => [
                  m(i, null, {
                    default: B(() => [
                      m(A(dt))
                    ]),
                    _: 1
                  }),
                  r[6] || (r[6] = T("重试 ", -1))
                ]),
                _: 1
              }),
              m(x, { onClick: a }, {
                default: B(() => [
                  m(i, null, {
                    default: B(() => [
                      m(A(Q))
                    ]),
                    _: 1
                  }),
                  r[7] || (r[7] = T("取消 ", -1))
                ]),
                _: 1
              })
            ], 64)) : j("", !0),
            A(l).status === "done" ? (O(), P(Z, { key: 3 }, [
              m(x, {
                type: "success",
                disabled: ""
              }, {
                default: B(() => [
                  m(i, null, {
                    default: B(() => [
                      m(A(pt))
                    ]),
                    _: 1
                  }),
                  r[8] || (r[8] = T("上传完成 ", -1))
                ]),
                _: 1
              }),
              m(x, { onClick: t }, {
                default: B(() => [...r[9] || (r[9] = [
                  T("上传其他文件", -1)
                ])]),
                _: 1
              })
            ], 64)) : j("", !0)
          ])
        ])) : j("", !0)
      ]);
    };
  }
}), Dt = (h, u) => {
  const c = h.__vccOpts || h;
  for (const [l, p] of u)
    c[l] = p;
  return c;
}, Ot = /* @__PURE__ */ Dt(xt, [["__scopeId", "data-v-02fc39dc"]]);
export {
  Ot as default
};
