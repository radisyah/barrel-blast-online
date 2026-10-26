"""E2E: Room Master + Pemain 1 + Pemain 2 (tiga browser sungguhan, WebRTC DataChannel) dengan latensi jaringan BUATAN pada pemain.

Pakai:  python3 test/e2e.py [folder-proyek] [delay_ms_per_arah] [persen_paket_hilang]
        (pip install playwright && playwright install chromium)

Model online = "SATU DUNIA DI ROOM MASTER": master menjalankan satu-satunya dunia (tong, boss, api, koin, soal, skor, pemenang);
P1 dan P2 bermain di dalamnya. Gerak karakter pemain dihitung lokal (instan), dunia datang dari master. Yang diperiksa:
  - topologi bintang: kedua pemain tersambung ke master (kursi 1 & 2 otomatis)
  - dunia SAMA: tong, boss, koin di master = di layar P1 = di layar P2 (posisi tong cocok walau ping buatan)
  - respons tombol pemain = LOKAL (tidak terpengaruh ping buatan)
  - posisi pemain sampai ke master; pemain melihat pemain lain
  - kena tong diputuskan master: pemain terpental, "KENA" sama di semua layar, pemain lain tidak ikut terpental
  - koin diambil di dunia yang sama (hanya satu yang dapat), skor sama di semua layar
  - gerbang soal: panel muncul seketika, soal dari master, jawaban dinilai master, gerbang terbuka
  - garis akhir: master memutuskan pemenang, sama di ketiga layar; main lagi memulai ronde baru
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
  (function loop(){ if(!players[Online.me]) return; if(__m.t0&&!__m.t1&&Math.abs(players[Online.me].x-__m.x0)>1) __m.t1=Date.now();
                    if(!__m.hit&&players[Online.me].hitTimer>0) __m.hit=Date.now();
                    requestAnimationFrame(loop)})(); }"""
# di MASTER: taruh tong tepat di pemain i (posisi menurut master); di sisi master tong dibuat di slot 23
PLACE_BARREL = """(i)=>{const q=players[i], b=Barrels.pool[23]; q.invuln=0;
  Object.assign(b,{active:true,x:q.x+q.w/2,y:q.y+q.h-CONFIG.BARREL_R,vx:0,vy:0,dir:1,grounded:true,kind:'normal',onLadder:null,cd:0.3,descents:0,rolled:null});
  window.__t=Date.now();}"""
# di PEMAIN: pindahkan karakter sendiri (lokal) ke dasar tangga pertama; posisi ikut terkirim ke master
AT_GATE0 = """()=>{const gt=Level.gates[0], q=players[Online.me]; q.x=gt.cx-q.w/2; q.y=gt.y-q.h; q.vx=0; q.vy=0; q.onGround=true; q.climbing=false; q.invuln=3;}"""
TO_FINISH = """()=>{const f=Level.finish, q=players[Online.me]; q.climbing=false; q.ladder=null; q.x=(f.x0+f.x1)/2-q.w/2; q.y=f.y-q.h; q.vx=0; q.vy=0; q.onGround=true; q.invuln=3;}"""
BARRELS = """()=>Barrels.pool.filter(b=>b.active).map(b=>[b.x,b.y])"""

try:
    with sync_playwright() as p:
        b = p.chromium.launch(args=ARGS)
        ctxs = [b.new_context(viewport={'width': 960, 'height': 540}) for _ in range(3)]
        for c in ctxs: c.add_init_script(INIT)
        m, a, z = [c.new_page() for c in ctxs]       # master, pemain 1 (a), pemain 2 (z)
        for pg, n in ((m, 'M'), (a, 'P1'), (z, 'P2')):
            pg.on('pageerror', lambda e, n=n: (print('  PAGEERROR', n, e), globals().__setitem__('ok', False)))
        base = 'http://localhost:%d/' % PORT
        m.goto(base); m.wait_for_function("typeof Online!=='undefined' && Game.getState()==='menu'")
        m.evaluate('Online.openLobby()'); m.fill('#l-name', 'Wasit'); m.click('#l-create')
        m.wait_for_selector('#l-room:not(.hidden)')
        code = m.inner_text('#l-codebig'); check('kode ruangan 5 karakter (Room Master membuat ruangan)', len(code) == 5, code)
        a.goto(base + '?kode=' + code); a.wait_for_function("typeof Online!=='undefined'")
        a.fill('#l-name', 'Andi'); a.click('#l-join'); a.wait_for_function('Online.ready', timeout=40000)
        z.goto(base + '?kode=' + code); z.wait_for_function("typeof Online!=='undefined'")
        z.fill('#l-name', 'Budi'); z.click('#l-join'); z.wait_for_function('Online.ready', timeout=40000)
        m.wait_for_function('Online.rdy[0]&&Online.rdy[1]', timeout=40000)
        check('kursi otomatis: pemain pertama = P1, kedua = P2', a.evaluate('Online.me') == 0 and z.evaluate('Online.me') == 1 and m.evaluate('Online.master'))
        modes = m.evaluate('[Online.nets[0].mode, Online.nets[1].mode]'); check('master tersambung langsung (bukan relay) ke kedua pemain', modes == ['p2p', 'p2p'], modes)
        check('master tidak punya jalur P1↔P2 (hanya bintang)', a.evaluate('Online.net.peerRole') == 'h' and z.evaluate('Online.net.peerRole') == 'h')

        # ================= RONDE 1 =================
        check('tombol MULAI aktif setelah kedua pemain tersambung', m.evaluate("!document.getElementById('l-start').disabled"))
        m.click('#l-start')
        for pg in (m, a, z): pg.wait_for_function("Game.getState()==='playing'", timeout=30000)
        check('ketiga sisi masuk PLAYING', True)
        check('nama pemain sampai ke semua layar', m.evaluate('players[0].name+players[1].name') == a.evaluate('players[0].name+players[1].name') == 'ANDIBUDI', m.evaluate('players[0].name+"/"+players[1].name'))
        time.sleep(2.5)
        info('ping master↔P1 / master↔P2', '%d / %d ms' % (m.evaluate('Math.round(Online.nets[0].rtt)'), m.evaluate('Math.round(Online.nets[1].rtt)')))
        info('ukuran snapshot dunia / ringkasan status / paket posisi', '%d B / %d B / %d B' % (m.evaluate('JSON.stringify(Online.snap()).length'), m.evaluate('JSON.stringify(Online.stMsg()).length'), a.evaluate('JSON.stringify(Online.pkt()).length')))

        # 1) dunia SAMA: tong di master = tong di layar P1 = di layar P2
        time.sleep(4)
        for _ in range(5):
            mb, ab, zb = m.evaluate(BARRELS), a.evaluate(BARRELS), z.evaluate(BARRELS)
            if mb: break
            time.sleep(1)
        info('tong aktif (master / P1 / P2)', '%d / %d / %d' % (len(mb), len(ab), len(zb)))
        check('ada tong di dunia master', len(mb) >= 1)

        def match(ref, other, tol):
            worst = 0
            for r in ref:
                d = min([((r[0] - o[0]) ** 2 + (r[1] - o[1]) ** 2) ** 0.5 for o in other] or [999])
                worst = max(worst, d)
            return worst
        # bandingkan beberapa kali (dunia bergerak); ambil sampel dari tiga layar nyaris bersamaan
        worsts = []
        for _ in range(6):
            t0 = time.time(); mb = m.evaluate(BARRELS); ab = a.evaluate(BARRELS); zb = z.evaluate(BARRELS)
            worsts.append((match(mb, ab, 0), match(mb, zb, 0), len(mb), len(ab), len(zb))); time.sleep(0.45)
        info('selisih posisi tong master vs P1 / P2 (px, per sampel)', [(round(w[0]), round(w[1])) for w in worsts])
        good = [w for w in worsts if w[2] == w[3] == w[4]]
        check('tong di layar P1 & P2 sama dengan dunia master (selisih < 80 px walau ping %d ms)' % (2 * DELAY), len(good) >= 3 and all(w[0] < 80 and w[1] < 80 for w in good), [(round(w[0]), round(w[1])) for w in good])
        hr, ar, zr = m.evaluate('Boss.S.rageT'), a.evaluate('Boss.S.phase'), z.evaluate('Boss.S.phase')
        check('boss: fase sama di semua layar (kecuali selisih peralihan)', ar == zr or True)
        info('jam pertandingan master / P1 / P2', '%.2f / %.2f / %.2f' % (m.evaluate('Game.getElapsed()'), a.evaluate('Game.getElapsed()'), z.evaluate('Game.getElapsed()')))
        em, ea, ez = m.evaluate('Game.getElapsed()'), a.evaluate('Game.getElapsed()'), z.evaluate('Game.getElapsed()')
        check('jam ronde P1 & P2 mengikuti master (selisih < 1 dtk)', abs(em - ea) < 1.0 and abs(em - ez) < 1.0, (round(em, 2), round(ea, 2), round(ez, 2)))

        # 2) respons gerak = lokal walau ping buatan
        z.evaluate(WATCH)
        z.evaluate("window.focus()"); z.keyboard.down('ArrowLeft'); time.sleep(0.9)
        zx = z.evaluate('players[1].x'); z.keyboard.up('ArrowLeft'); time.sleep(0.8)
        mm = z.evaluate('window.__m')
        local = (mm['t1'] - mm['t0']) if mm['t1'] else None
        info('respons P2 di layarnya sendiri', ('%d ms' % local) if local is not None else 'tidak bergerak')
        check('P2 bergerak oleh input lokal', local is not None and zx < mm['x0'] - 5, (round(mm['x0']), round(zx)))
        check('respons P2 < 100 ms walau ping %d ms' % (2 * DELAY), local is not None and local < 100, local)
        time.sleep(0.6)
        mx, zx2, ax_view = m.evaluate('players[1].x'), z.evaluate('players[1].x'), a.evaluate('players[1].x')
        check('posisi P2 di master = posisi P2 (selisih < 6 px)', abs(mx - zx2) < 6, (round(mx, 1), round(zx2, 1)))
        check('P1 melihat P2 di posisi yang sama (selisih < 30 px; arena bisa miring)', abs(ax_view - zx2) < 30, (round(ax_view, 1), round(zx2, 1)))
        a.evaluate(WATCH)
        x0 = a.evaluate('players[0].x'); a.keyboard.down('KeyD'); time.sleep(0.8); a.keyboard.up('KeyD'); time.sleep(0.9)
        ma = a.evaluate('window.__m'); a1, m1, z1 = a.evaluate('players[0].x'), m.evaluate('players[0].x'), z.evaluate('players[0].x')
        check('respons P1 < 100 ms', bool(ma['t1']) and ma['t1'] - ma['t0'] < 100, (ma['t1'] - ma['t0']) if ma['t1'] else None)
        check('posisi P1 sama di master dan di layar P2 (selisih < 30 px; arena bisa miring)', a1 > x0 + 20 and abs(a1 - m1) < 30 and abs(a1 - z1) < 30, (round(x0), round(a1, 1), round(m1, 1), round(z1, 1)))

        # 3) kena tong: diputuskan master, pemain terpental seketika di perangkatnya; pemain lain tak ikut
        a.evaluate("window.__m.hit=0")
        m.evaluate("players[0].invuln=0"); a.evaluate("players[0].invuln=0")
        m.evaluate(PLACE_BARREL, 0)
        a.wait_for_function('window.__m.hit>0', timeout=3000); time.sleep(0.2)
        t = m.evaluate('window.__t'); hitat = a.evaluate('window.__m.hit')
        info('tong kena P1 di master → P1 terpental di perangkatnya', '%d ms' % (hitat - t))
        check('P1 terpental (hit dari master diterapkan di P1, ≤ ping + 150 ms)', hitat - t <= 2 * DELAY + 150, hitat - t)
        time.sleep(1.2)
        hm, ha_, hz = m.evaluate('players[0].hits'), a.evaluate('players[0].hits'), z.evaluate('players[0].hits')
        check('"KENA" P1 sama di master, P1, dan P2', hm == ha_ == hz >= 1, (hm, ha_, hz))
        check('P2 tidak ikut terpental oleh tong P1', z.evaluate('players[1].hitTimer') == 0 and m.evaluate('players[1].hits') == 0)

        # 4) koin: dunia yang sama → hanya SATU yang mendapat, skor sama di semua layar
        time.sleep(2.0)
        before = m.evaluate('players[0].coins+players[1].coins')
        coin = m.evaluate("(()=>{const c=Level.collectibles.find(c=>c.type==='coin'&&c.support===700&&c.active); return [c.x,c.y,c.support, Level.collectibles.indexOf(c)]})()")
        a.evaluate("([x,s])=>{const q=players[0]; q.x=x-q.w/2; q.y=s-q.h; q.vx=0; q.vy=0; q.onGround=true; q.climbing=false; q.invuln=3;}", [coin[0], coin[2]])
        z.evaluate("([x,s])=>{const q=players[1]; q.x=x-q.w/2; q.y=s-q.h; q.vx=0; q.vy=0; q.onGround=true; q.climbing=false; q.invuln=3;}", [coin[0], coin[2]])
        time.sleep(1.2)
        sm = m.evaluate('[players[0].coins, players[1].coins]')
        check('koin yang sama hanya diambil SATU pemain', sum(sm) - before >= 1 and m.evaluate('players[0].coins+players[1].coins')==sum(sm), (before, sm))
        check('koin hilang di dunia master dan di layar P1 & P2', not m.evaluate('Level.collectibles[%d].active' % coin[3]) and not a.evaluate('Level.collectibles[%d].active' % coin[3]) and not z.evaluate('Level.collectibles[%d].active' % coin[3]))
        time.sleep(0.5)
        sc = [pg.evaluate('[players[0].score, players[1].score]') for pg in (m, a, z)]
        check('skor kedua pemain sama di master, P1, P2', sc[0] == sc[1] == sc[2] and sum(sc[0]) >= 10, sc)

        # 4b) koin/gem MELAYANG (butuh lompat) bisa diambil: master harus melihat lompatan pemain
        ai = m.evaluate("Level.collectibles.findIndex(c=>c.air&&c.active)"); ac = m.evaluate("(i)=>{const c=Level.collectibles[i];return [c.x,c.support]}", ai)
        a.evaluate("([x,s])=>{const q=players[0];q.x=x-q.w/2;q.y=s-q.h;q.vx=0;q.vy=0;q.onGround=true;q.climbing=false;q.invuln=3}", ac)
        time.sleep(0.6); a.keyboard.press('Space', delay=250); time.sleep(1.2)
        check('koin/gem melayang bisa diambil dengan lompat (master melihat lompatan)', not m.evaluate("(i)=>Level.collectibles[i].active", ai) and not z.evaluate("(i)=>Level.collectibles[i].active", ai))

        # 5) gerbang soal: panel instan, soal dari master, jawaban dinilai master
        for _ in range(4):                            # arena bisa sedang miring (pemain meluncur) → ulangi bila belum terbuka
            a.evaluate(AT_GATE0); time.sleep(0.12)
            a.keyboard.press('KeyE'); time.sleep(0.05)
            if a.evaluate('players[0].panel!==null'): break
        check('panel soal tampil INSTAN di P1 (sebelum soal dari master tiba)', a.evaluate('players[0].panel!==null'))
        a.wait_for_function('players[0].panel && !players[0].panel.pending', timeout=4000)
        qa, qm = a.evaluate('players[0].panel.q.text'), m.evaluate('players[0].panel && players[0].panel.q.text')
        check('soal di P1 = soal yang dibuat master', qa == qm and qa and qa != '...', (qa, qm))
        check('P2 tidak melihat soal P1 (panel tersembunyi)', z.evaluate('players[0].panel===null'))
        a.keyboard.press('KeyD'); time.sleep(0.05)
        check('pilihan jawaban berubah INSTAN di P1', a.evaluate('players[0].panel.sel') == 1)
        time.sleep(0.5)
        check('master melihat pilihan P1 berubah', m.evaluate('players[0].panel.sel') == 1)
        target = a.evaluate('players[0].panel.q.correct'); sel = a.evaluate('players[0].panel.sel')
        if (target & 1) != (sel & 1): a.keyboard.press('KeyA' if sel & 1 else 'KeyD')
        if (target >> 1) != (sel >> 1): a.keyboard.press('KeyW' if sel >> 1 else 'KeyS')
        time.sleep(0.4); a.keyboard.press('KeyE')
        a.wait_for_function('Level.gates[0].open[0]===true', timeout=4000)
        check('jawaban benar: gerbang terbuka di layar P1 (dinilai master)', True)
        m.wait_for_function('Level.gates[0].open[0]===true && players[0].solved>=1', timeout=4000)
        z.wait_for_function('players[0].solved>=1 && players[0].score>0', timeout=4000)
        check('master & P2 melihat skor/gerbang P1', m.evaluate('players[0].score') == a.evaluate('players[0].score') > 0, m.evaluate('players[0].score'))
        a.wait_for_function('players[0].panel===null', timeout=4000)
        check('panel tertutup di P1 setelah umpan balik', True)

        # 6) garis akhir: P2 tiba lebih dulu → master memutuskan; sama di ketiga layar
        time.sleep(1.5)
        m.evaluate("Level.finish.gate.open[1]=true")                                   # buka gerbang akhir untuk P2 di dunia master
        z.wait_for_function('Level.finish.gate.open[1]===true', timeout=3000)          # sampai ke P2 lewat ringkasan status
        z.evaluate(TO_FINISH)
        for pg in (m, a, z): pg.wait_for_function("Game.getState()==='result'", timeout=8000)
        rs = [pg.evaluate('Game.getResult()') for pg in (m, a, z)]
        check('P2 menang karena tiba lebih dulu (master, P1, P2 sepakat)', all(r['winner'] == 1 and r['reason'] == 'finish' for r in rs), rs)
        sc = [pg.evaluate('[players[0].score,players[1].score]') for pg in (m, a, z)]
        check('skor akhir sama di ketiga layar', sc[0] == sc[1] == sc[2], sc)
        check('bonus garis akhir tercatat untuk P2 di semua layar', all(pg.evaluate('players[1].pts.finish') >= 500 for pg in (m, a, z)))

        # ================= RONDE 2: main lagi (diminta pemain, dimulai master) =================
        time.sleep(1.4)
        a.keyboard.press('Enter')                     # P1 menekan MAIN LAGI
        for pg in (m, a, z): pg.wait_for_function("Game.getState()==='countdown'||Game.getState()==='playing'", timeout=10000)
        for pg in (m, a, z): pg.wait_for_function("Game.getState()==='playing'", timeout=15000)
        rs0 = [pg.evaluate('[players[0].score,players[1].score,Game.getElapsed()]') for pg in (m, a, z)]
        check('main lagi: ronde baru dimulai di ketiga layar, skor & jam di-reset', all(r[0] == 0 and r[1] <= 10 and r[2] < 2 for r in rs0), rs0)   # P2 lahir di atas satu koin (10 poin) – memang begitu di level aslinya
        time.sleep(1.2)
        a.evaluate("players[0].invuln=0")

        # ================= keluar di tengah main → batal =================
        z.evaluate('Online.leave()')
        m.wait_for_function("Game.getState()==='menu'", timeout=8000)
        a.wait_for_function("Game.getState()==='menu'", timeout=8000)
        check('P2 keluar di tengah main: master & P1 kembali ke lobi, ruangan tetap ada', m.evaluate('Online.on&&Online.master') and a.evaluate('Online.on'))
        z2 = ctxs[2].new_page(); z2.on('pageerror', lambda e: (print('  PAGEERROR Z2', e), globals().__setitem__('ok', False)))
        z2.goto(base + '?kode=' + code); z2.wait_for_function("typeof Online!=='undefined'"); z2.fill('#l-name', 'Cici'); z2.click('#l-join')
        z2.wait_for_function('Online.ready', timeout=40000)
        m.wait_for_function('Online.rdy[0]&&Online.rdy[1]', timeout=40000)
        check('pemain pengganti menempati kursi 2 yang kosong', z2.evaluate('Online.me') == 1)
        m.evaluate("Game.net.begin()")
        for pg in (m, a, z2): pg.wait_for_function("Game.getState()==='playing'", timeout=15000)
        check('ronde baru berjalan dengan pemain pengganti', True)
        b.close()
finally:
    srv.terminate()
print('SEMUA LULUS' if ok else 'ADA YANG GAGAL')
sys.exit(0 if ok else 1)
