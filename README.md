# BARREL BLAST · Online

Versi online dari *BARREL BLAST* (Donkey Kong + soal matematika), 1 vs 1 (balapan) dengan **kode ruangan**.
Satu perangkat = satu pemain. Host = P1 (merah), tamu = P2 (biru). Mode lokal 2 pemain satu perangkat tetap ada.
Ruangan juga punya satu kursi **Room Master**: penonton yang melihat P1 dan P2 bermain secara langsung (tanpa ikut bermain / mengontrol).

## Cara kerja: "balapan dunia sendiri" (tanpa lag untuk P1 maupun P2)
Sistem online-nya sama dengan *Kebun Angka / FloraBite*: **tiap perangkat menjalankan seluruh dunia permainan untuk pemainnya sendiri**,
dengan **seed yang sama** dari host. Tidak ada satu pun aksi pemain yang menunggu jaringan.

- **Dunia lokal.** Tong, boss, api, gerbang, soal, koin, palu, tabrakan, kombo, dan skor dihitung di perangkat pemain itu sendiri.
  Tombol, lompat, terkena tong, dan jawab soal terasa **instan** (terukur ±20 ms walau ping buatan 200 ms), baik untuk P1 (host) maupun P2 (tamu).
  Sebelumnya P2 harus menunggu host untuk tong/tabrakan/soal; itu sumber lag yang dirasakan P2 dan sudah dihapus.
- **Seed sama = gelombang sama.** Host membuat satu seed tiap ronde dan mengirimnya di pesan `go`. Dari seed itu: rangkaian acak tong tangga & api (`Rnd`),
  dan urutan soal matematika (`Quiz.setRng`). Soal ke-N yang dibuka kedua pemain identik; jam boss/tong sama. Hitung mundur dikoreksi setengah ping agar "GO!" bersamaan.
- **Lawan = bayangan.** Posisi lawan dikirim 30×/dtk (paket ±85 B, tak andal) lalu digambar dengan interpolasi + ekstrapolasi singkat; ringkasan skor/kombo/efek/gerbang
  terbuka 8×/dtk (±140 B). Bayangan digambar sedikit tembus pandang, **tidak menabrak tong, tidak mengambil koin/palu, dan tidak mengganggu** dunia siapa pun.
  Penanda "MENJAWAB..." muncul di atas bayangan yang sedang membuka soal. Soal lawan tidak ditampilkan.
- **Pemenang diputuskan host (sekali, di akhir).** Tiap pemain yang selesai (garis akhir / waktu habis) mengirim `done` (andal) berisi waktu & statistiknya, dunianya dibekukan
  dengan tulisan "MENUNGGU LAWAN...", lalu host mengirim `end`:
  - tiba di garis akhir lebih dulu menang (waktu tiba dibandingkan; selisih <20 ms = tiba bersamaan → skor tertinggi);
  - waktu habis = skor tertinggi menang, seri bila sama;
  - host menunggu ±setengah ping untuk pesan tiba lawan yang mungkin lebih awal; bila lawan tak kunjung selesai (>6 dtk setelah host selesai) dipakai skor terakhirnya.
- Koneksi **langsung antar-perangkat** (WebRTC DataChannel, kanal `u` tak andal untuk posisi/skor, kanal `r` andal untuk `go`/`done`/`end`). Server Vercel + Upstash Redis
  hanya untuk membuat/gabung ruangan, bertukar SDP/ICE, dan **relay cadangan**. Badge di bawah layar: `LANGSUNG · xx MS` atau `RELAY`.
  `api/room.js` tidak berubah: perubahan sistem online ada seluruhnya di `public/index.html` (`Online`, `Rnd`, `ACT`).

Akibat desain ini (sama seperti Kebun Angka): kedua pemain **berlomba**, bukan saling mengganggu: tong dan koin masing-masing terpisah, dan tidak ada ketergantungan
antar-pemain di tengah ronde. Bila satu pemain koneksinya buruk, yang terdampak hanya gerak bayangannya di layar lawan, bukan permainan siapa pun.

## Room Master (penonton)
- **Hanya satu** master per ruangan (kursi terpisah dari P2; master kedua ditolak 409). Master tersambung **hanya ke host** (WebRTC kedua, relay cadangan sama seperti tamu);
  tamu tidak tahu ada master dan tidak ada beban tambahan untuk P1↔P2.
- Host meneruskan ke master: `go` (seed + pengaturan), posisi P1 (milik host) dan P2 (diteruskan dari tamu), ringkasan skor kedua pemain, dan `end`.
- Karena dunia tiap pemain terpisah, master menjalankan **dunia acuan** dari seed yang sama (tanpa pemain): tong & boss yang ia lihat sama jamnya dengan yang dihadapi pemain,
  hanya efek yang bergantung pada tindakan pemain (palu menghancurkan tong, hukuman tong tangga karena jawaban salah, api yang mengejar pemain) yang tidak identik. Layar menampilkan catatan
  "TONG & BOSS = SEED SAMA DENGAN PEMAIN". Master melihat kedua bayangan, skor, kombo, gerbang terbuka, dan penanda "MENJAWAB..." (bukan teks soal).
- Master yang masuk di tengah pertandingan menerima seed + jam berjalan lalu memajukan dunia acuannya secepatnya (tanpa suara), jadi langsung sinkron.
- Master tidak mengirim input; tidak ada "Main Lagi" (host yang memulai ronde baru; master ikut otomatis).
- Host keluar atau koneksi host–tamu putus = ruangan ditutup, master kembali ke menu.

## Kontrol
- **HP (landscape, online)**: joystick di **kiri**; **LOMPAT** dan **SOAL** di **kanan** (SOAL = buka gerbang soal / jawab). Ketuk pilihan jawaban di panel soal juga bisa.
- **PC online**: WASD atau panah · Spasi/Shift = lompat · E/Enter = soal/jawab.
- Online tidak punya jeda; tombol **II** = keluar ruangan.

## Main online
1. Menu → **MAIN ONLINE** → **Buat Ruangan** (atur KESULITAN / DURASI / WAKTU SOAL di menu dulu; host yang menentukan).
2. Kirim kode atau **Salin Tautan Undangan** (`?kode=XXXXX`) ke teman → ia memilih **Gabung**.
3. *(Opsional)* Orang ketiga memasukkan kode yang sama lalu menekan **Gabung sebagai Room Master (Nonton)**. Lobi host menampilkan nama master.
   Master boleh masuk kapan saja, termasuk di tengah pertandingan, dan boleh keluar/diganti tanpa mengganggu pemain.
4. Setelah status "Terhubung", host menekan **Mulai Pertandingan**. Di layar hasil: **Main Lagi** (tamu meminta, host memulai) / **Menu Utama**.

## Deploy ke Vercel
1. Taruh folder ini di GitHub → **Add New → Project** di Vercel (preset "Other", tanpa build command).
2. **Storage / Marketplace → Upstash Redis** → hubungkan ke proyek, lalu **Redeploy**.
3. *(Disarankan)* server **TURN** lewat env `METERED_*` atau `ICE_SERVERS` (lihat `.env.example`) agar jaringan seluler/NAT ketat tetap P2P.

## Lokal & tes
```bash
node dev-server.js     # http://localhost:3000 (penyimpanan memori)
npm test               # tes API pensinyalan
python3 test/e2e_master.py   # 3-4 browser: host + tamu + Room Master (nonton bayangan P1/P2, skor, masuk/keluar di tengah main, hasil)
python3 test/e2e.py    # 2 browser sungguhan lewat WebRTC dengan ping buatan (default 100 ms/arah ≈ 200 ms): seed sama, respons lokal, bayangan, pemenang;
                       # args: [folder] [delay_ms] [persen_paket_hilang]  (pip install playwright && playwright install chromium)
```

## Batasan
- Skor dihitung di perangkat pemain masing-masing (seperti Kebun Angka): cocok untuk duel antar-teman/kelas, bukan turnamen berhadiah (tidak anti-curang).
- Tidak ada interaksi antar-pemain di dalam ronde (tidak saling menabrak, tidak berebut koin): ini justru yang menghilangkan lag.
- Jam tiap pemain berjalan di perangkatnya; tab yang disembunyikan menghentikan permainan pemain itu (host menunggu ≤6 dtk setelah ia sendiri selesai, lalu memakai skor terakhir lawan).
- Tidak ada sambung-ulang di tengah pertandingan: bila koneksi putus, kedua pemain kembali ke menu.
