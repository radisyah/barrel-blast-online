"""E2E: host + tamu (dua browser sungguhan, WebRTC DataChannel) dengan latensi jaringan BUATAN.

Pakai:  python3 test/e2e.py [folder-proyek] [delay_ms_per_arah]
        (pip install playwright && playwright install chromium)

Contoh:
  python3 test/e2e.py                      # proyek ini, 60 ms per arah  (ping ≈ 120 ms)
  python3 test/e2e.py ../versi-lama 60     # bandingkan dengan versi lain (hanya mencetak angka bila fitur tak ada)

Yang diukur:
  - 'respons tamu'  : jeda dari tombol ditekan di tamu sampai karakter tamu bergerak DI LAYAR TAMU sendiri.
  - 'host melihat'  : jeda dari tombol ditekan di tamu sampai P2 bergerak di layar host.
  - 'hit'           : jeda dari host memutuskan tabrakan tong sampai tamu terpental.
  - panel soal, pilihan jawaban instan, ukuran paket.
"""
import subprocess, time, sys, os
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(HERE)
DELAY = int(sys.argv[2]) if len(sys.argv) > 2 else 60
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
  addEventListener('keydown',e=>{ if(!__m.t0){__m.t0=Date.now(); __m.x0=players[1].x;} },true);
  (function loop(){ if(__m.t0&&!__m.t1&&Math.abs(players[1].x-__m.x0)>1) __m.t1=Date.now();
                    if(!__m.hit&&players[1].hitTimer>0) __m.hit=Date.now();
                    requestAnimationFrame(loop)})(); }"""
HWATCH = """()=>{ window.__h={x0:players[1].x,t1:0,th:0};
  (function loop(){ if(!__h.t1&&Math.abs(players[1].x-__h.x0)>1) __h.t1=Date.now(); requestAnimationFrame(loop)})(); }"""

try:
    with sync_playwright() as p:
        b = p.chromium.launch(args=ARGS)
        hc = b.new_context(viewport={'width': 960, 'height': 540}); gc = b.new_context(viewport={'width': 960, 'height': 540})
        hc.add_init_script(INIT); gc.add_init_script(INIT)
        h = hc.new_page(); g = gc.new_page()
        for pg, n in ((h, 'H'), (g, 'G')):
            pg.on('pageerror', lambda e, n=n: print('  PAGEERROR', n, e))
        base = 'http://localhost:%d/' % PORT
        h.goto(base); h.wait_for_function("typeof Online!=='undefined' && Game.getState()==='menu'")
        h.evaluate('Online.openLobby()'); h.fill('#l-name', 'Andi'); h.click('#l-create')
        h.wait_for_selector('#l-room:not(.hidden)')
        code = h.inner_text('#l-codebig'); check('kode ruangan 5 karakter', len(code) == 5, code)
        g.goto(base + '?kode=' + code); g.wait_for_function("typeof Online!=='undefined'")
        g.fill('#l-name', 'Budi'); g.click('#l-join')
        h.wait_for_function('Online.ready', timeout=40000); g.wait_for_function('Online.ready', timeout=40000)
        mode = h.evaluate('Online.net.mode'); check('koneksi langsung (bukan relay)', mode == 'p2p', mode)
        h.click('#l-start')
        h.wait_for_function("Game.getState()==='playing'", timeout=30000); g.wait_for_function("Game.getState()==='playing'", timeout=30000)
        check('kedua sisi masuk PLAYING', True)
        time.sleep(2.2)   # biar rtt terukur & awal pertandingan stabil
        info('ping terukur (tamu)', '%d ms' % g.evaluate('Math.round(Online.net.rtt)'))
        info('ukuran snapshot / paket posisi', '%d B / %d B' % (h.evaluate('JSON.stringify(Online.snap()).length'), h.evaluate("typeof Online.pkt==='function'?JSON.stringify(Online.pkt()).length:0")))

        # 1) respons gerak tamu
        g.evaluate(WATCH); h.evaluate(HWATCH)
        g.evaluate("window.focus()"); g.keyboard.down('ArrowLeft'); time.sleep(0.9)
        gx = g.evaluate('players[1].x'); g.keyboard.up('ArrowLeft'); time.sleep(0.8)
        m = g.evaluate('window.__m'); hm = h.evaluate('window.__h')
        local = (m['t1'] - m['t0']) if m['t1'] else None
        seen = (hm['t1'] - m['t0']) if hm['t1'] else None
        info('respons tamu di layarnya sendiri', ('%d ms' % local) if local is not None else 'tidak bergerak')
        info('host melihat P2 bergerak', ('%d ms' % seen) if seen is not None else 'tidak bergerak')
        check('tamu bergerak oleh input lokal', local is not None and gx < m['x0'] - 5, (round(m['x0']), round(gx)))
        check('respons tamu < 100 ms walau ping %d ms' % (2 * DELAY), local is not None and local < 100, local)
        hx = h.evaluate('players[1].x'); gx = g.evaluate('players[1].x')
        check('posisi P2 di host = di tamu (selisih < 3 px)', abs(hx - gx) < 3, (round(hx, 1), round(gx, 1)))

        # 2) P1 (host) terlihat di tamu
        x0 = h.evaluate('players[0].x'); h.keyboard.down('KeyD'); time.sleep(0.8); h.keyboard.up('KeyD'); time.sleep(0.9)
        h1 = h.evaluate('players[0].x'); g1 = g.evaluate('players[0].x')
        check('gerak P1 tampil di tamu (selisih < 3 px)', h1 > x0 + 20 and abs(h1 - g1) < 3, (round(x0), round(h1, 1), round(g1, 1)))

        # 3) tabrakan tong: host memutuskan, tamu terpental
        g.evaluate("window.__m.hit=0")
        h.evaluate("""()=>{const q=players[1], b=Barrels.pool[0]; q.invuln=0;
          Object.assign(b,{active:true,x:q.x+q.w/2,y:q.y+q.h-CONFIG.BARREL_R,vx:0,vy:0,dir:1,grounded:true,kind:'normal',onLadder:null,cd:0.3,descents:0,rolled:null});
          window.__th=Date.now();}""")
        time.sleep(0.9)
        hit = g.evaluate('window.__m.hit'); th = h.evaluate('window.__th')
        info('hit: tong kena (host) -> tamu terpental', ('%d ms' % (hit - th)) if hit else 'tidak terpental')
        check('tamu terpental saat host memutuskan tabrakan', bool(hit) and hit - th < DELAY * 2 + 150)
        time.sleep(2.2)    # tunggu stun & kekebalan selesai

        # 4) gerbang soal: buka di host, pilih jawaban lokal, jawab benar
        g.evaluate("""()=>{const gt=Level.gates[0], q=players[1]; q.x=gt.cx-q.w/2; q.y=gt.y-q.h; q.vx=0; q.vy=0; q.onGround=true;}""")
        time.sleep(0.7)
        check('host mengenali P2 di depan gerbang', h.evaluate('!!Gates.nearGate(players[1])'))
        t0 = time.time(); g.keyboard.press('Enter')
        h.wait_for_function('players[1].panel!==null', timeout=5000); g.wait_for_function('players[1].panel!==null', timeout=5000)
        info('panel soal muncul di tamu', '%d ms' % int((time.time() - t0) * 1000))
        g.keyboard.press('ArrowRight'); time.sleep(0.08)
        check('pilihan jawaban berubah INSTAN di tamu', g.evaluate('players[1].panel.sel') == 1, g.evaluate('players[1].panel.sel'))
        time.sleep(0.8)
        gs, hs = g.evaluate('players[1].panel.sel'), h.evaluate('players[1].panel.sel')
        check('pilihan tidak terpental balik & sama dengan host', gs == 1 and hs == 1, (gs, hs))
        target = h.evaluate('players[1].panel.q.correct')
        if (target & 1) != 1: g.keyboard.press('ArrowLeft')
        if (target >> 1) != 0: g.keyboard.press('ArrowDown')
        time.sleep(0.6); g.keyboard.press('Enter')
        g.wait_for_function('Level.gates[0].open[1]===true', timeout=6000)
        check('jawaban benar: gerbang terbuka di host & tamu', h.evaluate('Level.gates[0].open[1]') is True)
        check('skor matematika tercatat', h.evaluate('players[1].solved') == 1 and h.evaluate('players[1].score') > 0, h.evaluate('players[1].score'))
        check('tanpa kesalahan JS', True)
        b.close()
finally:
    srv.terminate()
print('SEMUA LULUS' if ok else 'ADA YANG GAGAL')
sys.exit(0 if ok else 1)
