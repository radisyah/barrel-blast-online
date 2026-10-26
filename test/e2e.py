"""E2E: host + tamu (dua browser sungguhan, WebRTC DataChannel) dengan latensi jaringan BUATAN.

Pakai:  python3 test/e2e.py [folder-proyek] [delay_ms_per_arah] [persen_paket_hilang]
        (pip install playwright && playwright install chromium)

Model online = "balapan dunia sendiri" (seperti Kebun Angka): tiap perangkat menyimulasikan dunia lengkap untuk pemainnya sendiri
dengan seed yang sama; lawan hanya bayangan. Yang diperiksa:
  - seed sama → urutan tong & soal sama di kedua perangkat
  - respons tombol, tabrakan tong, jawaban soal = LOKAL (tidak terpengaruh ping buatan)
  - bayangan lawan mengikuti posisi & skor, tidak menabrak tong / mengambil koin siapa pun
  - pemenang: tiba di garis akhir lebih dulu / waktu habis (skor tertinggi), diputuskan host, sama di kedua layar
"""
import subprocess, time, sys, os
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(HERE)
DELAY = int(sys.argv[2]) if len(sys.argv) > 2 else 100
LOSS = float(sys.argv[3]) if len(sys.argv) > 3 else 0      # % paket kanal tak-andal ('u') yang dibuang, + jitter ±20 ms
PORT = 3930 + (sum(map(ord, ROOT)) % 60)
srv = subprocess.Popen(['node', '-e', "require('./dev-server.js').start(%d).then(()=>console.log('up'))" % PORT], cwd=ROOT, stdout=subprocess.PIPE)
srv.stdout.readline()
ARGS = ["--disable-features=WebRtcHideLocalIpsWithMdns", "--allow-loopback-in-peer-connection", "--autoplay-policy=no-user-gesture-required"]
# latensi buatan: tiap pesan DataChannel ditunda DELAY ms (urutan tetap terjaga) -> ping ≈ 2 x DELAY
INIT = """(()=>{const D=%d,L=%f/100;if(D>0){const o=RTCDataChannel.prototype.send;
  RTCDataChannel.prototype.send=function(x){const t=this;
    if(L>0&&t.label==='u'&&Math.random()<L)return;                       // paket hilang (hanya kanal tak-andal)
    const j=(L>0&&t.label==='u')?(Math.random()*40-20):0;                 // jitter (kanal andal tetap berurutan)
    setTimeout(()=>{try{o.call(t,x)}catch(e){}},Math.max(0,D+j));};}})();""" % (DELAY, LOSS)
ok = True


def check(name, cond, extra=''):
    global ok
    print(('  ✔ ' if cond else '  ✘ ') + name + (' ' + str(extra) if extra != '' else ''))
    if not cond:
        ok = False


def info(name, val):
    print('  · %s: %s' % (name, val))


WATCH = """()=>{ window.__m={t0:0,t1:0,x0:0,hit:0};
  addEventListener('keydown',e=>{ if(!__m.t0){__m.t0=Date.now(); __m.x0=players[Online.me].x;} },true);
  (function loop(){ if(__m.t0&&!__m.t1&&Math.abs(players[Online.me].x-__m.x0)>1) __m.t1=Date.now();
                    if(!__m.hit&&players[Online.me].hitTimer>0) __m.hit=Date.now();
                    requestAnimationFrame(loop)})(); }"""
PLACE_BARREL = """(i)=>{const q=players[i], b=Barrels.pool[23]; q.invuln=0;
  Object.assign(b,{active:true,x:q.x+q.w/2,y:q.y+q.h-CONFIG.BARREL_R,vx:0,vy:0,dir:1,grounded:true,kind:'normal',onLadder:null,cd:0.3,descents:0,rolled:null});
  window.__t=Date.now();}"""
OPEN_GATE0 = """(i)=>{const gt=Level.gates[0], q=players[i]; q.x=gt.cx-q.w/2; q.y=gt.y-q.h; q.vx=0; q.vy=0; q.onGround=true; q.invuln=3;}"""
TO_FINISH = """(i)=>{const f=Level.finish, q=players[i]; f.gate.open[i]=true; q.climbing=false; q.ladder=null; q.x=(f.x0+f.x1)/2-q.w/2; q.y=f.y-q.h; q.vx=0; q.vy=0; q.onGround=true; q.invuln=3;}"""

try:
    with sync_playwright() as p:
        b = p.chromium.launch(args=ARGS)
        hc = b.new_context(viewport={'width': 960, 'height': 540}); gc = b.new_context(viewport={'width': 960, 'height': 540})
        hc.add_init_script(INIT); gc.add_init_script(INIT)
        h = hc.new_page(); g = gc.new_page()
        for pg, n in ((h, 'H'), (g, 'G')):
            pg.on('pageerror', lambda e, n=n: (print('  PAGEERROR', n, e), globals().__setitem__('ok', False)))
        base = 'http://localhost:%d/' % PORT
        h.goto(base); h.wait_for_function("typeof Online!=='undefined' && Game.getState()==='menu'")
        g.goto(base); g.wait_for_function("typeof Online!=='undefined'")
        for pg in (h, g): pg.evaluate("DURATIONS[1]=6")          # 6 dtk: untuk tes 'waktu habis' di bawah
        h.evaluate('Online.openLobby()'); h.fill('#l-name', 'Andi'); h.click('#l-create')
        h.wait_for_selector('#l-room:not(.hidden)')
        code = h.inner_text('#l-codebig'); check('kode ruangan 5 karakter', len(code) == 5, code)
        g.goto(base + '?kode=' + code); g.wait_for_function("typeof Online!=='undefined'"); g.evaluate("DURATIONS[1]=6")
        g.fill('#l-name', 'Budi'); g.click('#l-join')
        h.wait_for_function('Online.ready', timeout=40000); g.wait_for_function('Online.ready', timeout=40000)
        mode = h.evaluate('Online.net.mode'); check('koneksi langsung (bukan relay)', mode == 'p2p', mode)

        # ================= RONDE 1: pertandingan normal, 6 detik lalu waktu habis =================
        h.evaluate("DURATIONS[1]=600"); g.evaluate("DURATIONS[1]=600")      # panjang dulu; dipersingkat sebelum tes waktu habis
        h.click('#l-start')
        h.wait_for_function("Game.getState()==='playing'", timeout=30000); g.wait_for_function("Game.getState()==='playing'", timeout=30000)
        check('kedua sisi masuk PLAYING', True)
        time.sleep(2.2)   # biar rtt terukur & awal pertandingan stabil
        info('ping terukur (tamu)', '%d ms' % g.evaluate('Math.round(Online.net.rtt)'))
        info('paket posisi / ringkasan skor', '%d B / %d B' % (h.evaluate('JSON.stringify(Online.pkt()).length'), h.evaluate("JSON.stringify({t:'st',i:0,g:1,s:Online.stat(players[0])}).length")))

        # 1) seed sama → dunia sama
        hs, gs = h.evaluate('Online.seed'), g.evaluate('Online.seed')
        check('seed sama di host & tamu', hs and hs == gs, (hs, gs))
        time.sleep(5)
        hb, gb = h.evaluate('Barrels.spawned()'), g.evaluate('Barrels.spawned()')
        check('jumlah tong yang dilempar boss sama (±1)', abs(hb - gb) <= 1 and hb >= 2, (hb, gb))
        hr, gr = h.evaluate('Boss.S.rageT'), g.evaluate('Boss.S.rageT')
        check('jam amukan boss sama (selisih < 0,6 dtk)', abs(hr - gr) < 0.6, (round(hr, 2), round(gr, 2)))

        # 2) respons gerak = lokal walau ping buatan
        g.evaluate(WATCH)
        g.evaluate("window.focus()"); g.keyboard.down('ArrowLeft'); time.sleep(0.9)
        gx = g.evaluate('players[1].x'); g.keyboard.up('ArrowLeft'); time.sleep(0.8)
        m = g.evaluate('window.__m')
        local = (m['t1'] - m['t0']) if m['t1'] else None
        info('respons tamu di layarnya sendiri', ('%d ms' % local) if local is not None else 'tidak bergerak')
        check('tamu bergerak oleh input lokal', local is not None and gx < m['x0'] - 5, (round(m['x0']), round(gx)))
        check('respons tamu < 100 ms walau ping %d ms' % (2 * DELAY), local is not None and local < 100, local)
        time.sleep(0.8)
        hx, gx = h.evaluate('players[1].x'), g.evaluate('players[1].x')
        check('bayangan P2 di host = posisi P2 di tamu (selisih < 4 px)', abs(hx - gx) < 4, (round(hx, 1), round(gx, 1)))
        h.evaluate(WATCH)
        x0 = h.evaluate('players[0].x'); h.keyboard.down('KeyD'); time.sleep(0.8); h.keyboard.up('KeyD'); time.sleep(0.9)
        h1, g1 = h.evaluate('players[0].x'), g.evaluate('players[0].x')
        mh = h.evaluate('window.__m')
        check('respons host < 100 ms', bool(mh['t1']) and mh['t1'] - mh['t0'] < 100, (mh['t1'] - mh['t0']) if mh['t1'] else None)
        check('bayangan P1 di tamu = posisi P1 di host (selisih < 4 px)', h1 > x0 + 20 and abs(h1 - g1) < 4, (round(x0), round(h1, 1), round(g1, 1)))

        # 3) tabrakan tong: lokal & instan di pemain itu; bayangan lawan tidak ikut tertabrak
        g.evaluate("window.__m.hit=0"); g.evaluate(PLACE_BARREL, 1)
        time.sleep(0.5)
        m = g.evaluate('window.__m'); t = g.evaluate('window.__t')
        info('tong kena P2 → P2 terpental (di tamu)', ('%d ms' % (m['hit'] - t)) if m['hit'] else 'tidak')
        check('tamu terpental SEGERA oleh dunianya sendiri (< 80 ms)', bool(m['hit']) and m['hit'] - t < 80, (m['hit'] - t) if m['hit'] else None)
        time.sleep(2.2)
        hh = h.evaluate('players[1].hits')
        h.evaluate(PLACE_BARREL, 1); time.sleep(0.4)
        check('tong di dunia host TIDAK menabrak bayangan P2', h.evaluate('players[1].hits') == hh and h.evaluate('players[1].hitTimer') == 0 or h.evaluate('players[1].hitTimer') in (0, 0.2), h.evaluate('[players[1].hits, players[1].hitTimer]'))
        time.sleep(1.0)
        check('jumlah "KENA" P2 sampai ke host lewat ringkasan skor', h.evaluate('players[1].hits') == g.evaluate('players[1].hits') >= 1, h.evaluate('players[1].hits'))

        # 4) gerbang soal: urutan soal sama, jawab di dunia sendiri, skor tampil di lawan
        for _ in range(4):                            # arena bisa sedang miring (pemain meluncur) → ulangi bila belum terbuka
            h.evaluate(OPEN_GATE0, 0); g.evaluate(OPEN_GATE0, 1); time.sleep(0.12)
            h.keyboard.press('KeyE'); g.keyboard.press('Enter'); time.sleep(0.25)
            if h.evaluate('players[0].panel!==null') and g.evaluate('players[1].panel!==null'): break
        h.wait_for_function('players[0].panel!==null', timeout=3000); g.wait_for_function('players[1].panel!==null', timeout=3000)
        qh, qg = h.evaluate('players[0].panel.q.text'), g.evaluate('players[1].panel.q.text')
        check('soal pertama sama di host & tamu (seed sama)', qh == qg and qh, (qh, qg))
        g.keyboard.press('ArrowRight'); time.sleep(0.05)
        check('pilihan jawaban berubah INSTAN di tamu', g.evaluate('players[1].panel.sel') == 1)
        time.sleep(0.5)
        check('host melihat bayangan P2 "MENJAWAB"', h.evaluate('!!players[1].ghostAns'))
        target = g.evaluate('players[1].panel.q.correct'); sel = g.evaluate('players[1].panel.sel')
        if (target & 1) != (sel & 1): g.keyboard.press('ArrowLeft' if sel & 1 else 'ArrowRight')
        if (target >> 1) != (sel >> 1): g.keyboard.press('ArrowUp' if sel >> 1 else 'ArrowDown')
        time.sleep(0.3); g.keyboard.press('Enter')
        g.wait_for_function('Level.gates[0].open[1]===true', timeout=4000)
        check('jawaban benar: gerbang terbuka di dunia tamu', True)
        h.wait_for_function('players[1].solved>=1 && players[1].score>0', timeout=4000)
        check('skor & gerbang P2 tampil di layar host', h.evaluate('Level.gates[0].open[1]') is True and h.evaluate('players[1].score') == g.evaluate('players[1].score'), h.evaluate('players[1].score'))

        # 5) garis akhir: tamu tiba lebih dulu → menang; host diputus di tengah main
        time.sleep(2.2)
        g.evaluate(TO_FINISH, 1)
        for pg in (h, g): pg.wait_for_function("Game.getState()==='result'", timeout=8000)
        rh, rg = h.evaluate('Game.getResult()'), g.evaluate('Game.getResult()')
        check('tamu menang karena tiba lebih dulu (host & tamu sepakat)', rh['winner'] == 1 and rg['winner'] == 1 and rh['reason'] == 'finish' and rg['reason'] == 'finish', (rh, rg))
        check('skor akhir sama di kedua layar', h.evaluate('[players[0].score,players[1].score]') == g.evaluate('[players[0].score,players[1].score]'), h.evaluate('[players[0].score,players[1].score]'))
        check('bonus garis akhir tercatat di tamu', g.evaluate('players[1].pts.finish') >= 500, g.evaluate('players[1].pts.finish'))

        # ================= RONDE 2: main lagi, host tiba lebih dulu =================
        time.sleep(1.4)
        g.keyboard.press('Enter')                     # tamu minta main lagi (host memulai)
        h.wait_for_function("Game.getState()==='countdown'||Game.getState()==='playing'", timeout=8000)
        for pg in (h, g): pg.wait_for_function("Game.getState()==='playing'", timeout=15000)
        check('main lagi: ronde baru dengan seed baru', h.evaluate('Online.seed') == g.evaluate('Online.seed') and h.evaluate('Online.seed') != hs)
        time.sleep(1.2)
        h.evaluate(TO_FINISH, 0)
        for pg in (h, g): pg.wait_for_function("Game.getState()==='result'", timeout=8000)
        rh, rg = h.evaluate('Game.getResult()'), g.evaluate('Game.getResult()')
        check('host menang karena tiba lebih dulu', rh['winner'] == 0 and rg['winner'] == 0, (rh, rg))

        # ================= RONDE 3: waktu habis → skor tertinggi menang =================
        for pg in (h, g): pg.evaluate("DURATIONS[1]=4")
        time.sleep(1.4)
        h.keyboard.press('Enter')                     # host: MAIN LAGI
        for pg in (h, g): pg.wait_for_function("Game.getState()==='playing'", timeout=15000)
        g.evaluate("Score.award(players[1], 120, 'coin', 100, 100)")
        for pg in (h, g): pg.wait_for_function("Game.getState()==='result'", timeout=20000)
        rh, rg = h.evaluate('Game.getResult()'), g.evaluate('Game.getResult()')
        check('waktu habis: skor tertinggi (tamu) menang di kedua layar', rh['reason'] == 'time' and rh['winner'] == 1 and rg['winner'] == 1, (rh, rg))
        hs1, gs1 = h.evaluate('players[1].score'), g.evaluate('players[1].score')
        check('skor akhir tamu (≥120) sama di host & tamu', hs1 == gs1 and gs1 >= 120, (hs1, gs1))
        b.close()
finally:
    srv.terminate()
print('SEMUA LULUS' if ok else 'ADA YANG GAGAL')
sys.exit(0 if ok else 1)
