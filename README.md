# BARREL BLAST · Online

Versi online dari *BARREL BLAST* (Donkey Kong + soal matematika), 1 vs 1 dengan **kode ruangan** dan **Room Master**.

## Cara kerja: "satu dunia di Room Master"
Sistem online berbentuk **bintang**, mengikuti Kebun Angka (Room Master = pembuat ruangan & pusat), tetapi P1 dan P2 bermain di **dunia yang sama** yang berjalan di Room Master (perangkat dengan jaringan cepat).

```
 P1 ──WebRTC──┐
              ├── Room Master (satu-satunya dunia: tong, boss, api, miring, koin, palu, soal, skor, pemenang)
 P2 ──WebRTC──┘        └── Vercel + Upstash hanya untuk kode ruangan, SDP/ICE, dan relay cadangan
```
- **Room Master** membuat ruangan, menjalankan seluruh simulasi, dan menjadi wasit/penonton (tidak bermain). P1 dan P2 tidak tersambung satu sama lain.
- **Tanpa lag terasa di P1/P2:** gerak karakter sendiri (lari, lompat, tangga, pilih jawaban) dihitung **lokal**, jadi tombol instan (terukur ±20 ms walau ping buatan 200 ms). Posisi dikirim ke master 40×/dtk.
- **Dunia sama:** master mengirim snapshot tong/api/boss/arena miring 30×/dtk; layar pemain menggambarnya dengan prediksi maju (umur snapshot + setengah ping), jadi tong di layar pemain ≈ tong di master "sekarang". Koin & palu satu dunia (siapa cepat dia dapat).
- **Master memutuskan interaksi:** kena tong/api, koin/palu, lompati tong, soal & jawaban, skor, garis akhir/pemenang. Hasil kembali lewat pesan andal (`hit` pemain terpental seketika, `pn` panel soal, `ev` efek/suara, `ps` efek TURBO/PERISAI/PALU) + ringkasan status 10×/dtk.
- Kursi otomatis: masuk pertama = P1 (merah), kedua = P2 (biru). Pemain keluar saat main = ronde batal, kembali ke lobi, kursi bisa diisi pengganti.
- `api/room.js`: peran `h` (Room Master), `1`, `2`; kotak surat `h1`,`1h`,`h2`,`2h`.

## Kontrol
- **HP (landscape, online)**: joystick di **kiri**; **LOMPAT** dan **SOAL** di **kanan** (SOAL = buka gerbang soal / jawab). Ketuk pilihan jawaban di panel soal juga bisa.
- **PC online**: WASD atau panah · Spasi/Shift = lompat · E/Enter = soal/jawab.
- Online tidak punya jeda; tombol **II** = keluar ruangan.

## Main online
1. **Room Master** (jaringan tercepat): Menu → **MAIN ONLINE** → **Buat Ruangan (Jadi Room Master)**; atur KESULITAN / DURASI / WAKTU SOAL di menu dulu.
2. Kirim kode atau **Salin Tautan Undangan** (`?kode=XXXXX`) ke dua pemain → masing-masing **Gabung**.
3. Setelah keduanya "TERHUBUNG", master menekan **Mulai Pertandingan**. Layar hasil: **Main Lagi** (pemain meminta, master memulai) / **Menu Utama**.

## Deploy ke Vercel
1. Taruh folder ini di GitHub → **Add New → Project** di Vercel (preset "Other", tanpa build command).
2. **Storage / Marketplace → Upstash Redis** → hubungkan ke proyek, lalu **Redeploy**.
3. *(Disarankan)* server **TURN** lewat env `METERED_*` atau `ICE_SERVERS` (lihat `.env.example`) agar jaringan seluler/NAT ketat tetap P2P.

## Lokal & tes
```bash
node dev-server.js     # http://localhost:3000 (penyimpanan memori)
npm test               # tes API pensinyalan (master + kursi 1 & 2)
python3 test/e2e.py    # 3 browser: master + P1 + P2 via WebRTC dengan ping buatan (default 100 ms/arah); args: [folder] [delay_ms] [persen_paket_hilang]
```

## Batasan
- Tidak anti-curang (posisi/skor dipercaya dari perangkat): untuk duel teman/kelas.
- Tiba di garis akhir nyaris bersamaan: pesan yang lebih dulu sampai ke master menang (selisih ping bisa menentukan bila < ±100 ms).
- Master harus menjaga tabnya terbuka; kualitas jaringan master menentukan kualitas kedua pemain. Tidak ada sambung-ulang di tengah ronde.
