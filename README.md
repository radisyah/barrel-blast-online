# BARREL BLAST · Online

Versi online dari *BARREL BLAST* (Donkey Kong + soal matematika), 1 vs 1 dengan **kode ruangan**.
Satu perangkat = satu pemain. Host = P1 (merah), tamu = P2 (biru). Mode lokal 2 pemain satu perangkat tetap ada.

## Cara kerja
- **Host menjalankan seluruh simulasi** (fisika, tong, boss, api, gerbang, soal, skor). Tamu mengirim inputnya (joystick/lompat/soal/jawaban) ke host dan
  menggambar snapshot dunia 25×/dtk dengan interpolasi. Suara & efek dari host diteruskan ke tamu.
- Koneksi **langsung antar-perangkat** (WebRTC DataChannel). Server Vercel + Upstash Redis hanya untuk membuat/gabung ruangan, bertukar SDP/ICE,
  dan **relay cadangan** bila koneksi langsung gagal. Badge di bawah layar menampilkan `LANGSUNG · xx MS` atau `RELAY`.
- Soal tamu dibuat di host; jawaban benar tidak dikirim ke tamu selama soal masih terbuka.

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
```

## Batasan
- Tamu merasakan latensi ≈ ping (tanpa prediksi gerak lokal); host responsif penuh. Cocok untuk duel antar-teman, bukan anti-cheat.
- Tidak ada sambung-ulang di tengah pertandingan: bila koneksi putus, kedua pemain kembali ke menu.
