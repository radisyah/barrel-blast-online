# BARREL BLAST · Online

Versi online dari *BARREL BLAST* (Donkey Kong + soal matematika), 1 vs 1 dengan **kode ruangan**.
Satu perangkat = satu pemain. Host = P1 (merah), tamu = P2 (biru). Mode lokal 2 pemain satu perangkat tetap ada.

## Cara kerja (latensi rendah)
Model sinkronisasinya sama dengan *Number Bomber Online*: **gerak dihitung di perangkat pemain sendiri**, dunia bersama diputuskan host.
- **Gerak pemain = lokal.** Tamu menjalankan fisika P2-nya sendiri (lompat, tangga, tilt), jadi tombol/joystick langsung terasa tanpa menunggu ping.
  Posisi dikirim **30×/dtk** (paket ±70 B, tak andal) dan lawan digambar dengan interpolasi + ekstrapolasi singkat.
- **Host memutuskan dunia bersama**: tong, api, boss, tabrakan, gerbang & soal, skor, garis akhir. Disiarkan sebagai snapshot **20×/dtk**
  (tong/api diekstrapolasi dari kecepatannya di sisi tamu) + kejadian andal `hit` saat P2 tertabrak (tamu menerapkan lentingan di simulasi lokalnya).
- **Soal tamu** dibuat di host; jawaban benar tidak dikirim ke tamu selama soal terbuka. Pilihan jawaban (panah / ketuk) tampil **instan** di tamu,
  host tetap yang memutuskan benar/salah. Jam & hitung mundur dikoreksi dengan setengah ping.
- Koneksi **langsung antar-perangkat** (WebRTC DataChannel, kanal `u` tak andal untuk posisi/snapshot, kanal `r` andal untuk kejadian). Server Vercel + Upstash Redis
  hanya untuk membuat/gabung ruangan, bertukar SDP/ICE, dan **relay cadangan** bila koneksi langsung gagal. Badge di bawah layar: `LANGSUNG · xx MS` atau `RELAY`.

## Sinkronisasi dunia: snapshot kecil (<2 KB penuh, biasanya 200–900 B)
Snapshot host → tamu dibuat kecil agar tidak terfragmentasi di jaringan seluler dan tidak membuat antrean kirim yang menaikkan ping:
pemain dikirim sebagai **delta** (hanya field yang berubah; snapshot penuh tiap ±1 dtk), tong/api sebagai larik angka bulat (hanya yang aktif),
gerbang/collectible/palu/skor hanya saat berubah, dan teks soal + pilihan jawaban sekali lewat kanal andal (`pq`). Laju snapshot 15×/dtk.
Terukur (loopback, 2 browser): bandwidth host→tamu 41–69 KB/s → 8–12 KB/s.

## Kontrol
- **HP (landscape, online)**: joystick di **kiri**; **LOMPAT** dan **SOAL** di **kanan** (SOAL = buka gerbang soal / jawab). Ketuk pilihan jawaban di panel soal juga bisa.
- **PC online**: WASD atau panah · Spasi/Shift = lompat · E/Enter = soal/jawab.
- Online tidak punya jeda; tombol **II** = keluar ruangan.

## Main online
1. Menu → **MAIN ONLINE** → **Buat Ruangan** (atur KESULITAN / DURASI / WAKTU SOAL di menu dulu; host yang menentukan).
2. Kirim kode atau **Salin Tautan Undangan** (`?kode=XXXXX`) ke teman → ia memilih **Gabung**.
3. Setelah status "Terhubung", host menekan **Mulai Pertandingan**. Di layar hasil: **Main Lagi** (tamu meminta, host memulai) / **Menu Utama**.

## Deploy ke Vercel
1. Taruh folder ini di GitHub → **Add New → Project** di Vercel (preset "Other", tanpa build command).
2. **Storage / Marketplace → Upstash Redis** → hubungkan ke proyek, lalu **Redeploy**.
3. *(Disarankan)* server **TURN** lewat env `METERED_*` atau `ICE_SERVERS` (lihat `.env.example`) agar jaringan seluler/NAT ketat tetap P2P.

## Lokal & tes
```bash
node dev-server.js     # http://localhost:3000 (penyimpanan memori)
npm test               # tes API pensinyalan
python3 test/e2e.py    # 2 browser sungguhan lewat WebRTC dengan ping buatan (default 60 ms/arah ≈ 120 ms);
                       # args: [folder] [delay_ms] [persen_paket_hilang]  (pip install playwright && playwright install chromium)
```

## Batasan
- Host dipercaya untuk tabrakan/skor; posisi tiap pemain dipercaya dari perangkatnya (cukup untuk duel antar-teman, bukan anti-cheat).
- Karena gerak tamu lokal, tabrakan tong/api dinilai host dengan posisi tamu yang tertunda ±setengah ping: lentingan tiba beberapa puluh ms setelah tong terlihat mengenai.
- Tidak ada sambung-ulang di tengah pertandingan: bila koneksi putus, kedua pemain kembali ke menu.
