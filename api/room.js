'use strict';
/* BARREL BLAST Online — satu Vercel Function untuk PENSINYALAN (bukan untuk gameplay).
   Gameplay berjalan langsung antar-perangkat lewat WebRTC (tanpa server di tengah → latensi serendah mungkin).
   Server ini hanya dipakai untuk: membuat/gabung ruangan dengan kode 5 karakter, saling bertukar SDP/ICE,
   dan sebagai RELAY cadangan bila koneksi langsung gagal (mis. jaringan seluler dengan NAT ketat dan tanpa TURN).

     GET  /api/room?action=ice                       -> daftar ICE server (STUN/TURN)
     GET  /api/room?code=&token=&since=N&peer=1|2    -> polling kotak surat: {peer, msgs, n}  (peer hanya dipakai Room Master)
     POST /api/room {action: create|join|send|leave, ...}

   Topologi BINTANG: Room Master (pembuat ruangan, jaringan cepat) menjalankan SATU dunia permainan; Pemain 1 dan Pemain 2
   masing-masing tersambung ke Room Master (bukan satu sama lain).
   Peran: h = Room Master (host) · 1 = Pemain 1 (merah) · 2 = Pemain 2 (biru). Pemain yang masuk lebih dulu mendapat kursi 1.
   Redis:  room:KODE (host) · p1:KODE / p2:KODE (SET NX → hanya satu pemain per kursi) · mb:KODE:<dari><ke> (kotak surat per pasangan: h1, 1h, h2, 2h) */
const crypto = require('crypto');
const { getStore } = require('../lib/store.js');

const TTL = 2 * 3600;
const MAX_MB = 15000;          // batas panjang kotak surat (relay ±15 menit)
const MAX_BATCH = 60, MAX_MSG = 12000;
const ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
const DEFAULT_ICE = [
  { urls: ['stun:stun.l.google.com:19302', 'stun:stun1.l.google.com:19302'] },
  { urls: 'stun:stun.cloudflare.com:3478' }
];

const fail = (status, msg, extra) => { const e = new Error(msg); e.status = status; if (extra) Object.assign(e, extra); return e; };
const rid = n => crypto.randomBytes(n).toString('hex');
const cleanName = (s, fb) => {
  s = String(s == null ? '' : s).replace(/[\u0000-\u001f<>&"'`]/g, '').replace(/\s+/g, ' ').trim().slice(0, 14);
  return s || fb;
};
const normCode = c => { c = String(c || '').toUpperCase().replace(/[^A-Z0-9]/g, ''); if (c.length !== 5) throw fail(400, 'Kode ruangan harus 5 karakter.'); return c; };
const parse = s => { try { return s ? JSON.parse(s) : null; } catch (e) { return null; } };
const K = { room: c => 'room:' + c, slot: (c, n) => 'p' + n + ':' + c, mb: (c, link) => 'mb:' + c + ':' + link };

/* ICE server, urutan prioritas:
   1) Metered: env METERED_APP_NAME + METERED_API_KEY (+ METERED_REGION opsional) → kredensial diambil dari REST API Metered di SERVER
      (key tidak pernah dikirim ke browser), di-cache 5 menit.
   2) env ICE_SERVERS (JSON array manual).
   3) STUN publik saja (koneksi langsung tanpa relay TURN). */
let meteredCache = { at: 0, list: null };
async function meteredServers() {
  const app = (process.env.METERED_APP_NAME || '').trim().replace(/\.metered\.live.*$/i, ''), key = (process.env.METERED_API_KEY || '').trim();
  if (!app || !key) return null;
  if (meteredCache.list && Date.now() - meteredCache.at < 5 * 60 * 1000) return meteredCache.list;
  try {
    const region = (process.env.METERED_REGION || '').trim();
    const u = 'https://' + encodeURIComponent(app) + '.metered.live/api/v1/turn/credentials?apiKey=' + encodeURIComponent(key) + (region ? '&region=' + encodeURIComponent(region) : '');
    const ac = new AbortController(), t = setTimeout(() => ac.abort(), 4000);
    const r = await fetch(u, { signal: ac.signal }); clearTimeout(t);
    if (!r.ok) throw new Error('Metered ' + r.status);
    const arr = await r.json();
    if (Array.isArray(arr) && arr.length) { meteredCache = { at: Date.now(), list: arr }; return arr; }
  } catch (e) { console.error('Metered gagal, pakai cadangan:', e.message); }
  return meteredCache.list;       // pakai cache lama bila ada
}
async function iceServers() {
  const m = await meteredServers();
  if (m) return m;
  const raw = process.env.ICE_SERVERS;           // JSON array, mis. [{"urls":"turn:host:3478","username":"u","credential":"p"}]
  if (raw) { try { const a = JSON.parse(raw); if (Array.isArray(a) && a.length) return a; } catch (e) { /* abaikan, pakai bawaan */ } }
  return DEFAULT_ICE;
}

/* Identifikasi pemanggil → 'h' (Room Master) / '1' / '2' (pemain). Mengembalikan {role, room, slots:[p1,p2]}. */
async function auth(code, token) {
  const r = await getStore().pipeline([['GET', K.room(code)], ['GET', K.slot(code, 1)], ['GET', K.slot(code, 2)]]);
  const room = parse(r[0]);
  if (!room) throw fail(404, 'Ruangan tidak ditemukan atau sudah kedaluwarsa.', { gone: true });
  const slots = [parse(r[1]), parse(r[2])];
  let role = null;
  if (token && room.host.token === token) role = 'h';
  else if (token && slots[0] && slots[0].token === token) role = '1';
  else if (token && slots[1] && slots[1].token === token) role = '2';
  if (!role) throw fail(401, 'Sesi tidak valid. Gabung ulang ke ruangan.', { gone: true });
  return { role, room, slots };
}

async function actCreate(b) {
  const store = getStore(), name = cleanName(b.name, 'Room Master'), token = rid(12);
  for (let i = 0; i < 12; i++) {
    let code = ''; for (let k = 0; k < 5; k++) code += ALPHABET[crypto.randomInt(ALPHABET.length)];
    const room = { code, host: { token, name }, createdAt: Date.now() };
    const ok = await store.cmd(['SET', K.room(code), JSON.stringify(room), 'NX', 'EX', TTL]);
    if (ok === 'OK') return { code, token, role: 'h', name };
  }
  throw fail(503, 'Gagal membuat ruangan. Coba lagi.');
}

async function actJoin(b) {
  const code = normCode(b.code), store = getStore();
  const r = await store.pipeline([['GET', K.room(code)], ['GET', K.slot(code, 1)], ['GET', K.slot(code, 2)]]);
  const room = parse(r[0]);
  if (!room) throw fail(404, 'Ruangan tidak ditemukan atau sudah kedaluwarsa.');
  const cur = [parse(r[1]), parse(r[2])];
  for (let i = 0; i < 2; i++) {                                                             // sambung ulang dengan token lama
    if (b.token && cur[i] && cur[i].token === b.token) return { code, token: cur[i].token, role: String(i + 1), name: cur[i].name, hostName: room.host.name, base: await store.cmd(['LLEN', K.mb(code, 'h' + (i + 1))]) || 0 };
  }
  for (let i = 0; i < 2; i++) {                                                             // kursi kosong pertama: Pemain 1 lalu Pemain 2
    if (cur[i]) continue;
    const name = cleanName(b.name, 'Pemain ' + (i + 1)), token = rid(12);
    const ok = await store.cmd(['SET', K.slot(code, i + 1), JSON.stringify({ token, name }), 'NX', 'EX', TTL]);
    if (ok !== 'OK') continue;                                                              // keduluan pemain lain: coba kursi berikutnya
    const base = await store.cmd(['LLEN', K.mb(code, 'h' + (i + 1))]);                      // pesan lama (sesi sebelumnya) dilewati klien baru lewat 'base'
    return { code, token, role: String(i + 1), name, hostName: room.host.name, base: base || 0 };
  }
  throw fail(409, 'Ruangan sudah penuh (2 pemain).');
}

async function actState(q) {
  const code = normCode(q.code), token = String(q.token || '');
  const { role, room, slots } = await auth(code, token);
  const since = Math.max(0, Math.floor(Number(q.since) || 0));
  const peerRole = role === 'h' ? (q.peer === '2' ? '2' : '1') : 'h';                    // Room Master punya dua pasangan; pemain hanya Room Master
  const msgs = await getStore().cmd(['LRANGE', K.mb(code, peerRole + role), since, -1]);
  const who = peerRole === 'h' ? room.host : slots[Number(peerRole) - 1];
  const peer = { joined: !!who, name: who ? (who.name || '') : '' };
  return { peer, msgs: (msgs || []).map(parse).filter(Boolean), n: since + (msgs || []).length };
}

async function actSend(b) {
  const code = normCode(b.code), { role } = await auth(code, String(b.token || ''));
  const list = Array.isArray(b.msgs) ? b.msgs.slice(0, MAX_BATCH) : [];
  if (!list.length) return {};
  const to = role === 'h' ? (b.to === '2' ? '2' : '1') : 'h', key = K.mb(code, role + to), store = getStore();
  const strs = [];
  for (const m of list) {
    const s = typeof m === 'string' ? m : JSON.stringify(m);
    if (s.length > MAX_MSG) throw fail(413, 'Pesan terlalu besar.');
    strs.push(s);
  }
  const res = await store.pipeline([['RPUSH', key].concat(strs), ['EXPIRE', key, TTL]]);
  if (res[0] > MAX_MB) throw fail(409, 'Sesi relay terlalu panjang. Mulai ruangan baru.');
  return {};
}

async function actLeave(b) {
  const code = normCode(b.code), store = getStore();
  let a; try { a = await auth(code, String(b.token || '')); } catch (e) { return {}; }
  const bye = JSON.stringify({ t: 'bye' }), cmds = [];
  if (a.role === 'h') {                                  // Room Master pergi = ruangan ditutup untuk semua
    for (const l of ['h1', 'h2']) cmds.push(['RPUSH', K.mb(code, l), bye], ['EXPIRE', K.mb(code, l), 600]);
    cmds.push(['DEL', K.room(code), K.slot(code, 1), K.slot(code, 2)]);
  } else {                                               // pemain pergi = kursinya kosong lagi; Room Master diberi tahu
    cmds.push(['RPUSH', K.mb(code, a.role + 'h'), bye], ['EXPIRE', K.mb(code, a.role + 'h'), 600], ['DEL', K.slot(code, a.role)]);
  }
  await store.pipeline(cmds);
  return {};
}

function readBody(req) {
  if (req.body && typeof req.body === 'object') return req.body;
  if (typeof req.body === 'string') { try { return JSON.parse(req.body); } catch (e) { throw fail(400, 'Body tidak valid.'); } }
  return {};
}

module.exports = async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  try {
    let out;
    if (req.method === 'GET') {
      const q = req.query || {};
      out = q.action === 'ice' ? { iceServers: await iceServers() } : await actState(q);
    } else if (req.method === 'POST') {
      const b = readBody(req);
      const acts = { create: actCreate, join: actJoin, send: actSend, leave: actLeave };
      if (!acts[b.action]) throw fail(400, 'Aksi tidak dikenal.');
      out = await acts[b.action](b);
    } else throw fail(405, 'Metode tidak didukung.');
    res.status(200).json(Object.assign({ ok: true }, out));
  } catch (e) {
    const status = e.status || 500;
    if (status >= 500) console.error(e);
    res.status(status).json({ ok: false, error: status >= 500 && !e.status ? 'Terjadi kesalahan di server.' : e.message, gone: !!e.gone });
  }
};
