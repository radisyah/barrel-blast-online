"""E2E Room Master: host (P1) + tamu (P2) + Room Master (penonton) = 3 browser sungguhan lewat WebRTC.

Pakai:  python3 test/e2e_master.py [folder-proyek] [delay_ms_per_arah]
        (pip install playwright && playwright install chromium)

Yang diperiksa:
  - master bergabung lewat tombol lobi, tersambung ke HOST (bukan ke tamu), host melihat statusnya
  - master melihat gerak P1 dan P2 secara langsung (posisi sama dengan di layar pemain)
  - master melihat bayangan P2 terkena tong / sedang menjawab soal, gerbang yang terbuka, dan skor kedua pemain
  - master menjalankan dunia acuan dari seed yang sama (tong & boss sama dengan pemain)
  - master tidak bisa mengendalikan siapa pun (tombol di master tidak sampai ke host)
  - master keluar di tengah pertandingan -> pertandingan jalan terus; master BARU bisa masuk di tengah pertandingan dan langsung menonton
  - hasil pertandingan juga tampil di master; master tidak punya "MAIN LAGI"
  - kursi master hanya satu (master kedua ditolak)
"""
import subprocess, time, sys, os
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(HERE)
DELAY = int(sys.argv[2]) if len(sys.argv) > 2 else 40
PORT = 3990 + (sum(map(ord, ROOT)) % 40)
srv = subprocess.Popen(['node', '-e', "require('./dev-server.js').start(%d).then(()=>console.log('up'))" % PORT], cwd=ROOT, stdout=subprocess.PIPE)
srv.stdout.readline()
ARGS = ["--disable-features=WebRtcHideLocalIpsWithMdns", "--allow-loopback-in-peer-connection", "--autoplay-policy=no-user-gesture-required"]
INIT = """(()=>{const D=%d;if(D>0){const o=RTCDataChannel.prototype.send;
  RTCDataChannel.prototype.send=function(x){const t=this;setTimeout(()=>{try{o.call(t,x)}catch(e){}},D);};}})();""" % DELAY
ok = True


def check(name, cond, extra=''):
    global ok
    print(('  ✔ ' if cond else '  ✘ ') + name + (' ' + str(extra) if extra != '' else ''))
    if not cond:
        ok = False


def near(src, dst, expr, tol=4, tries=12):
    """Bandingkan nilai di layar sumber (pemain/host) dan layar master. Pemain bisa sedang bergeser (arena miring), jadi sampel
    master diapit dua pembacaan sumber; lolos bila ada satu percobaan di mana nilainya di antara keduanya (± tol)."""
    last = None
    for _ in range(tries):
        a = src.evaluate(expr); v = dst.evaluate(expr); c = src.evaluate(expr); last = (round(a, 1), round(v, 1), round(c, 1))
        if min(a, c) - tol <= v <= max(a, c) + tol: return True, last
        time.sleep(0.25)
    return False, last


try:
    with sync_playwright() as p:
        b = p.chromium.launch(args=ARGS)

        def page(name):
            c = b.new_context(viewport={'width': 960, 'height': 540}); c.add_init_script(INIT)
            pg = c.new_page(); pg.on('pageerror', lambda e, n=name: (print('  PAGEERROR', n, e), globals().__setitem__('ok', False)))
            return pg
        h, g, m = page('H'), page('G'), page('M')
        base = 'http://localhost:%d/' % PORT
        h.goto(base); h.wait_for_function("typeof Online!=='undefined' && Game.getState()==='menu'")
        h.evaluate('Online.openLobby()'); h.fill('#l-name', 'Andi'); h.click('#l-create')
        h.wait_for_selector('#l-room:not(.hidden)')
        code = h.inner_text('#l-codebig')
        check('host melihat "belum ada" Room Master', 'BELUM ADA' in h.inner_text('#l-mstatus'), h.inner_text('#l-mstatus'))

        g.goto(base + '?kode=' + code); g.wait_for_function("typeof Online!=='undefined'")
        g.fill('#l-name', 'Budi'); g.click('#l-join')
        h.wait_for_function('Online.ready', timeout=40000); g.wait_for_function('Online.ready', timeout=40000)

        # --- master bergabung lewat tombol lobi ---
        m.goto(base + '?kode=' + code); m.wait_for_function("typeof Online!=='undefined'")
        m.fill('#l-name', 'Wasit'); m.click('#l-watch')
        m.wait_for_function('Online.ready', timeout=40000); h.wait_for_function('Online.mReady', timeout=40000)
        check('master tersambung ke host (langsung)', m.evaluate('Online.master && Online.net.mode') == 'p2p', m.evaluate('Online.net.mode'))
        check('host menampilkan Room Master di lobi', 'WASIT' in h.inner_text('#l-mstatus') and 'MENONTON' in h.inner_text('#l-mstatus'), h.inner_text('#l-mstatus'))
        check('lobi master tanpa tombol mulai', m.evaluate("document.getElementById('l-start').classList.contains('hidden')"))
        check('tamu & host tetap terhubung', g.evaluate('Online.ready') and h.evaluate('Online.ready'))

        # --- kursi master hanya satu ---
        x = b.new_context(viewport={'width': 960, 'height': 540}).new_page()
        x.goto(base + '?kode=' + code); x.wait_for_function("typeof Online!=='undefined'")
        x.click('#l-watch'); time.sleep(0.8)
        check('master kedua ditolak', x.evaluate('!Online.on'))
        x.context.close()

        # --- mulai pertandingan ---
        h.click('#l-start')
        for pg in (h, g, m):
            pg.wait_for_function("Game.getState()==='playing'", timeout=30000)
        check('host, tamu, dan master sama-sama PLAYING', True)
        check('badge master tampil, tombol sentuh tersembunyi', m.evaluate("document.body.classList.contains('master')"))
        time.sleep(1.5)

        # --- gerak P2 (tamu) dan P1 (host) terlihat di master ---
        g.evaluate("window.focus()"); g.keyboard.down('ArrowLeft'); time.sleep(0.9); g.keyboard.up('ArrowLeft'); time.sleep(0.9)
        r, d = near(g, m, 'players[1].x'); check('gerak P2 tampil di master (selisih < 4 px)', r, d)
        x0 = m.evaluate('players[0].x'); h.keyboard.down('KeyD'); time.sleep(0.8); h.keyboard.up('KeyD'); time.sleep(0.9)
        r, d = near(h, m, 'players[0].x'); check('gerak P1 tampil di master (selisih < 4 px)', r and h.evaluate('players[0].x') > x0 + 20, (round(x0),) + d)

        # --- tabrakan tong pada P2: master ikut melihat P2 terpental ---
        g.evaluate("""()=>{const q=players[1], b=Barrels.pool[23]; q.invuln=0;
          Object.assign(b,{active:true,x:q.x+q.w/2,y:q.y+q.h-CONFIG.BARREL_R,vx:0,vy:0,dir:1,grounded:true,kind:'normal',onLadder:null,cd:0.3,descents:0,rolled:null});}""")
        try:
            m.wait_for_function('players[1].hitTimer>0 || players[1].hits>0', timeout=4000); hit = True
        except Exception:
            hit = False
        check('master melihat P2 terkena tong', hit, m.evaluate('[players[1].hitTimer, players[1].hits]'))
        time.sleep(2.2)

        # --- panel soal P2 (tamu membuka gerbang) tampil di master ---
        for _ in range(4):                            # arena bisa sedang miring (pemain meluncur) → ulangi bila belum terbuka
            g.evaluate("""()=>{const gt=Level.gates[0], q=players[1]; q.x=gt.cx-q.w/2; q.y=gt.y-q.h; q.vx=0; q.vy=0; q.onGround=true; q.invuln=3;}""")
            time.sleep(0.12); g.keyboard.press('Enter'); time.sleep(0.25)
            if g.evaluate('players[1].panel!==null'): break
        g.wait_for_function('players[1].panel!==null', timeout=3000)
        m.wait_for_function('!!players[1].ghostAns', timeout=4000)
        check('master melihat P2 sedang menjawab soal (penanda "MENJAWAB")', True)
        target = g.evaluate('players[1].panel.q.correct'); sel = g.evaluate('players[1].panel.sel')
        if (target & 1) != (sel & 1): g.keyboard.press('ArrowLeft' if sel & 1 else 'ArrowRight')
        if (target >> 1) != (sel >> 1): g.keyboard.press('ArrowUp' if sel >> 1 else 'ArrowDown')
        time.sleep(0.6); g.keyboard.press('Enter')
        m.wait_for_function('Level.gates[0].open[1]===true && players[1].score>0', timeout=6000)
        check('master melihat gerbang P2 terbuka & skor naik', m.evaluate('players[1].score') > 0 and m.evaluate('players[1].solved') >= 1, m.evaluate('players[1].score'))

        # --- master tidak bisa mengendalikan siapa pun ---
        before = (h.evaluate('players[1].x'), g.evaluate('players[1].x'))
        m.focus('#game'); m.keyboard.down('ArrowLeft'); m.keyboard.down('KeyA'); m.keyboard.press('Enter'); time.sleep(0.6); m.keyboard.up('ArrowLeft'); m.keyboard.up('KeyA')
        check('tombol di master tidak mengendalikan siapa pun', m.evaluate('ACT.length') == 0 and m.evaluate('Online.held.size') == 0)
        after = (h.evaluate('players[1].x'), g.evaluate('players[1].x'))
        check('P2 tidak bergerak karena master', abs(after[0] - before[0]) < 3 and abs(after[1] - before[1]) < 3, (before, after))

        # --- master keluar: pertandingan jalan terus ---
        m.evaluate('Online.leave()')
        try: h.wait_for_function('Online.mReady===false', timeout=10000); gone = True
        except Exception: gone = False
        check('host menandai master tidak ada', gone)
        check('pertandingan tetap jalan setelah master keluar', h.evaluate("Game.getState()") == 'playing' and g.evaluate("Game.getState()") == 'playing')

        # --- master BARU masuk di tengah pertandingan ---
        m2 = page('M2'); m2.goto(base + '?kode=' + code); m2.wait_for_function("typeof Online!=='undefined'")
        m2.fill('#l-name', 'Wasit2'); m2.click('#l-watch')
        m2.wait_for_function("Online.ready && Game.getState()==='playing'", timeout=40000)
        h.wait_for_function('Online.mReady', timeout=20000)
        check('master baru langsung menonton pertandingan yang sedang berjalan', True)
        time.sleep(1.5)
        r2, d2 = near(g, m2, 'players[1].x', tol=30); r1, d1 = near(h, m2, 'players[0].x', tol=30)    # arena miring: pemain meluncur → master tertinggal ±latensi
        check('posisi P1 & P2 di master baru cocok', r1 and r2, (d1, d2))
        time.sleep(0.6)
        check('skor P2 sama dengan host', m2.evaluate('players[1].score') == h.evaluate('players[1].score'), m2.evaluate('players[1].score'))
        hs, ms_ = h.evaluate('Online.seed'), m2.evaluate('Online.seed')
        check('master baru memakai seed yang sama', hs and hs == ms_, (hs, ms_))
        check('jam pertandingan master baru ≈ host (selisih < 1 dtk)', abs(m2.evaluate('Game.getElapsed()') - h.evaluate('Game.getElapsed()')) < 1.0, (round(m2.evaluate('Game.getElapsed()'), 2), round(h.evaluate('Game.getElapsed()'), 2)))
        check('master baru: jumlah tong dunia acuan = host (±1)', abs(m2.evaluate('Barrels.spawned()') - h.evaluate('Barrels.spawned()')) <= 1, (m2.evaluate('Barrels.spawned()'), h.evaluate('Barrels.spawned()')))
        check('nama pemain tampil di master', m2.evaluate('players[0].name') == 'ANDI' and m2.evaluate('players[1].name') == 'BUDI', m2.evaluate('[players[0].name, players[1].name]'))

        # --- hasil pertandingan ---
        h.evaluate("(()=>{const f=Level.finish, q=players[0]; f.gate.open[0]=true; q.climbing=false; q.ladder=null; q.x=(f.x0+f.x1)/2-q.w/2; q.y=f.y-q.h; q.vx=0; q.vy=0; q.onGround=true; q.invuln=3;})()")
        for pg in (h, g, m2):
            pg.wait_for_function("Game.getState()==='result'", timeout=10000)
        check('hasil pertandingan tampil di host, tamu, dan master', True)
        check('layar hasil master tanpa MAIN LAGI', m2.evaluate("Online.master") is True)

        # --- host mulai lagi: master ikut ---
        time.sleep(2.5)
        h.keyboard.press('Enter')
        for pg in (h, g, m2):
            pg.wait_for_function("Game.getState()==='countdown' || Game.getState()==='playing'", timeout=15000)
        check('main lagi: master otomatis ikut menonton ronde baru', True)

        # --- host keluar: master kembali ke menu ---
        h.evaluate('Online.leave()')
        m2.wait_for_function("Game.getState()==='menu' && !Online.on", timeout=20000)
        check('host keluar -> master kembali ke menu', True)
        b.close()
finally:
    srv.terminate()
print('SEMUA LULUS' if ok else 'ADA YANG GAGAL')
sys.exit(0 if ok else 1)
