'use strict';
/* Tes API pensinyalan: node test/api.test.js  (memori lokal)
   Topologi bintang: Room Master (h) <-> Pemain 1 ('1') dan Room Master <-> Pemain 2 ('2'). Pemain tidak berkirim pesan satu sama lain. */
const assert = require('assert');
const { start } = require('../dev-server.js');
let base, pass = 0;
const api = async (method, body, q) => {
  const r = await fetch(base + '/api/room' + (q ? '?' + new URLSearchParams(q) : ''), { method, headers: { 'Content-Type': 'application/json' }, body: method === 'POST' ? JSON.stringify(body) : undefined });
  return Object.assign({ http: r.status }, await r.json());
};
const post = (action, o) => api('POST', Object.assign({ action }, o));
const T = async (name, fn) => { try { await fn(); pass++; console.log('  ✔', name); } catch (e) { console.log('  ✘', name, '\n     ', e.stack.split('\n').slice(0, 3).join('\n      ')); process.exitCode = 1; } };

(async () => {
  const srv = await start(0); base = 'http://localhost:' + srv.address().port;
  let M, P1, P2;
  await T('ice mengembalikan daftar STUN', async () => { const j = await api('GET', null, { action: 'ice' }); assert(j.ok && j.iceServers.length >= 1); });
  await T('create (Room Master) membuat kode 5 karakter', async () => { M = await post('create', { name: 'Wasit' }); assert(M.ok && /^[A-Z2-9]{5}$/.test(M.code) && M.role === 'h' && M.name === 'Wasit'); });
  await T('Room Master melihat kedua kursi pemain masih kosong', async () => {
    for (const peer of ['1', '2']) { const j = await api('GET', null, { code: M.code, token: M.token, since: 0, peer }); assert(j.ok && j.peer.joined === false && j.msgs.length === 0); }
  });
  await T('pemain pertama otomatis = Pemain 1; nama dibersihkan; kode kecil/besar sama', async () => {
    P1 = await post('join', { code: M.code.toLowerCase(), name: '<b>Andi</b>' });
    assert(P1.ok && P1.role === '1' && P1.hostName === 'Wasit' && !/[<>]/.test(P1.name) && /Andi/.test(P1.name));
  });
  await T('pemain kedua otomatis = Pemain 2', async () => { P2 = await post('join', { code: M.code, name: 'Budi' }); assert(P2.ok && P2.role === '2' && P2.name === 'Budi'); });
  await T('pemain ketiga ditolak (409)', async () => { const j = await post('join', { code: M.code, name: 'X' }); assert(j.http === 409 && !j.ok); });
  await T('pemain yang sama bisa sambung ulang dengan token (kursi tetap)', async () => {
    const a = await post('join', { code: M.code, token: P1.token }); assert(a.ok && a.token === P1.token && a.role === '1');
    const b = await post('join', { code: M.code, token: P2.token }); assert(b.ok && b.token === P2.token && b.role === '2');
  });
  await T('kode salah → 404, format salah → 400', async () => { assert((await post('join', { code: 'ZZZZZ' })).http === 404); assert((await post('join', { code: 'AB' })).http === 400); });
  await T('Room Master melihat presence tiap pemain', async () => {
    const a = await api('GET', null, { code: M.code, token: M.token, since: 0, peer: '1' }); assert(a.peer.joined && /Andi/.test(a.peer.name));
    const b = await api('GET', null, { code: M.code, token: M.token, since: 0, peer: '2' }); assert(b.peer.joined && b.peer.name === 'Budi');
  });
  await T('pemain melihat Room Master hadir', async () => { const j = await api('GET', null, { code: P1.code, token: P1.token, since: 0 }); assert(j.peer.joined && j.peer.name === 'Wasit'); });
  let n1 = 0, n2 = 0;
  await T('sinyal Master → P1 (berurutan, since bekerja)', async () => {
    assert((await post('send', { code: M.code, token: M.token, to: '1', msgs: [{ t: 'sig', d: { sdp: 'offer1' } }, { t: 'sig', d: { c: 1 } }] })).ok);
    let j = await api('GET', null, { code: P1.code, token: P1.token, since: n1 }); n1 = j.n;
    assert(j.msgs.length === 2 && j.msgs[0].d.sdp === 'offer1' && j.msgs[1].d.c === 1 && n1 === 2);
    j = await api('GET', null, { code: P1.code, token: P1.token, since: n1 }); assert(j.msgs.length === 0 && j.n === 2);
  });
  await T('pesan Master → P1 TIDAK sampai ke P2 (jalur terpisah)', async () => {
    const j = await api('GET', null, { code: P2.code, token: P2.token, since: n2 }); assert(j.msgs.length === 0);
  });
  await T('sinyal Master → P2 terpisah dari jalur P1', async () => {
    assert((await post('send', { code: M.code, token: M.token, to: '2', msgs: [{ t: 'sig', d: { sdp: 'offer2' } }] })).ok);
    let j = await api('GET', null, { code: P2.code, token: P2.token, since: n2 }); n2 = j.n; assert(j.msgs.length === 1 && j.msgs[0].d.sdp === 'offer2');
    j = await api('GET', null, { code: P1.code, token: P1.token, since: n1 }); assert(j.msgs.length === 0, 'P1 tidak boleh menerima pesan untuk P2');
  });
  let m1 = 0, m2 = 0;
  await T('pemain → Room Master (tiap pemain di kotak surat sendiri)', async () => {
    assert((await post('send', { code: P1.code, token: P1.token, msgs: [{ t: 'rl', d: ['{"t":"p"}', '{"t":"s"}'] }] })).ok);
    assert((await post('send', { code: P2.code, token: P2.token, to: '1', msgs: [{ t: 'sig', d: { c: 9 } }] })).ok);     // 'to' diabaikan untuk pemain: selalu ke Room Master
    let j = await api('GET', null, { code: M.code, token: M.token, since: m1, peer: '1' }); m1 = j.n; assert(j.msgs.length === 1 && j.msgs[0].t === 'rl' && j.msgs[0].d.length === 2);
    j = await api('GET', null, { code: M.code, token: M.token, since: m2, peer: '2' }); m2 = j.n; assert(j.msgs.length === 1 && j.msgs[0].d.c === 9);
  });
  await T('token salah ditolak (401) & pesan terlalu besar ditolak (413)', async () => {
    assert((await api('GET', null, { code: M.code, token: 'x', since: 0 })).http === 401);
    assert((await post('send', { code: M.code, token: M.token, msgs: ['x'.repeat(13000)] })).http === 413);
  });
  await T('P1 keluar → Room Master dapat bye, kursi 1 kosong lagi (P2 tak terganggu)', async () => {
    assert((await post('leave', { code: P1.code, token: P1.token })).ok);
    const j = await api('GET', null, { code: M.code, token: M.token, since: m1, peer: '1' }); assert(j.msgs.some(m => m.t === 'bye') && j.peer.joined === false);
    assert((await api('GET', null, { code: M.code, token: M.token, since: m2, peer: '2' })).peer.joined === true);
    const p1b = await post('join', { code: M.code, name: 'Cici' }); assert(p1b.ok && p1b.role === '1' && p1b.name === 'Cici');
    P1 = p1b;
  });
  await T('P2 keluar → Room Master dapat bye, kursi 2 kosong lagi', async () => {
    assert((await post('leave', { code: P2.code, token: P2.token })).ok);
    const j = await api('GET', null, { code: M.code, token: M.token, since: m2, peer: '2' }); assert(j.msgs.some(m => m.t === 'bye') && j.peer.joined === false);
    const p2b = await post('join', { code: M.code, name: 'Dodi' }); assert(p2b.ok && p2b.role === '2'); P2 = p2b;
  });
  await T('Room Master keluar → kedua pemain dapat bye & ruangan ditutup', async () => {
    assert((await post('leave', { code: M.code, token: M.token })).ok);
    for (const P of [P1, P2]) {
      const j = await api('GET', null, { code: M.code, token: P.token, since: 0 });
      assert(j.http === 404 && j.gone === true);
    }
    const j = await api('GET', null, { code: M.code, token: M.token, since: 0 }); assert(j.http === 404 && j.gone === true);
  });
  console.log(pass + ' tes lulus'); srv.close();
})();
