# TTS Bahasa Indonesia, Jawa & Sunda

Aplikasi pengubah teks menjadi suara (text-to-speech) dengan lima pilihan
pembicara. Teknologi yang digunakan meliputi model TTS berbasis VITS dengan
konversi teks ke fonem (G2P). Model ini dilatih khusus untuk bahasa Indonesia,
Jawa, dan Sunda.

## Arsitektur

Aplikasi ini dipisah menjadi dua bagian karena `torch` + `coqui-tts` + checkpoint
330 MB terlalu besar dan terlalu lambat *cold start*-nya untuk Vercel Functions.

```
┌──────────────────────────┐        HTTPS + JSON         ┌──────────────────────────────┐
│  Vercel                  │  ─────────────────────────► │  Modal.com                   │
│  Frontend statis         │   POST /synthesize          │  Backend inferensi           │
│  public/                 │  ◄─────────────────────────  │  modal_app.py                │
│  HTML + CSS + JS murni   │      audio/wav              │  torch CPU + coqui-tts       │
│                          │                             │  checkpoint v1.2 (330 MB)    │
└──────────────────────────┘                             └──────────────────────────────┘
```

| Bagian | Lokasi | Isi |
| --- | --- | --- |
| Frontend | Vercel | `public/` — HTML, CSS, JS statis, tanpa build |
| Backend | Modal | `modal_app.py` — G2P, normalisasi teks, sintesis VITS |
| Paket G2P | keduanya | `g2p_id/` — ikut di-bake ke image Modal saat build |

## Pembicara yang Tersedia

- **Wibowo** — suara jantan berwibawa (Indonesia)
- **Ardi** — suara lembut dan hangat (Indonesia)
- **Gadis** — suara perempuan yang merdu (Indonesia)
- **Juminten** — suara perempuan Jawa (bahasa Jawa)
- **Asep** — suara lelaki Sunda (bahasa Sunda)

Model v1.2 tidak punya *embedding* bahasa, jadi aksen ditentukan oleh pembicara
yang dipilih — bukan oleh pilihan bahasa. Karena itu dropdown **Bahasa** di
frontend berfungsi menyaring daftar pembicara, bukan mengubah pelafalan secara
langsung.

## Contoh Suara

- [Wibowo](public/contoh-suara/wibowo.wav)
- [Gadis](public/contoh-suara/gadis.wav)
- [Juminten (Jawa)](public/contoh-suara/juminten.wav)
- [Asep (Sunda)](public/contoh-suara/asep.wav)

## Cara Menggunakan

1. Masukkan teks yang ingin diubah menjadi suara.
2. Pilih kecepatan bicara yang diinginkan.
3. Pilih bahasa, lalu pilih pembicara.
4. Klik tombol **Lakukan Inferensi Audio**.
5. Audio diputar otomatis; berkas WAV bisa diunduh lewat tautan di bawahnya.

## Deploy Backend ke Modal

1. Pasang CLI dan masuk ke akun Modal Anda:

   ```bash
   pip install modal
   python -m modal token new
   ```

2. Buat kode akses acak, lalu simpan sebagai Secret. Kode ini yang akan diminta
   frontend, supaya endpoint Anda tidak dipakai orang lain secara cuma-cuma:

   ```bash
   python -m modal secret create ttsjawa TTS_ACCESS_TOKEN=<kode-rahasia-anda>
   ```

3. Deploy:

   ```bash
   modal deploy modal_app.py
   ```

   Build pertama memakan waktu beberapa menit karena harus memasang torch dan
   mengunduh checkpoint 330 MB ke dalam image. Build berikutnya pakai cache.

4. Catat URL yang muncul, bentuknya:

   ```
   https://<workspace-anda>--ttsjawa.modal.run
   ```

Endpoint yang tersedia:

| Method | Path | Keterangan |
| --- | --- | --- |
| GET | `/healthz` | Cek backend siap (tanpa kode akses) |
| GET | `/speakers` | Daftar bahasa & pembicara |
| POST | `/synthesize` | Body JSON `{teks, pembicara, kecepatan}`, balas `audio/wav` |

Setiap permintaan selain `/healthz` wajib menyertakan header
`X-Access-Token`. Container Modal tetap hangat selama 10 menit (`scaledown_window=600`);
permintaan pertama setelah idle butuh 20–60 detik untuk memuat model.

## Deploy Frontend ke Vercel

1. Push repo ini ke GitHub.
2. Di [dashboard Vercel](https://vercel.com/new), pilih **Import** repo ini.
3. Biarkan pengaturan apa adanya — `vercel.json` sudah menyetel:
   - `framework: null`, `buildCommand: ""`, `installCommand: ""` (murni statis,
     Vercel tidak akan mencoba memasang dependensi Python)
   - `outputDirectory: "public"`
4. Klik **Deploy**.
5. Buka URL hasilnya, buka bagian **Pengaturan Backend**, lalu isi:
   - **URL Backend Modal** — URL dari langkah deploy Modal
   - **Kode Akses** — nilai `TTS_ACCESS_TOKEN` yang Anda buat

   Keduanya disimpan di `localStorage` peramban Anda, bukan di Vercel. Bisa juga
   diisi sekali lewat query string:

   ```
   https://situs-anda.vercel.app/?api=https://<workspace>--ttsjawa.modal.run&token=<kode>
   ```

> **Catatan:** jangan letakkan berkas Python di `public/`, dan jangan membuat
> folder `api/` berisi `.py` di root — Vercel akan menganggapnya project Python
> dan mencoba memasang `torch`.

## Pengembangan Lokal

```bash
python -m venv venv
venv\Scripts\activate        # Linux/macOS: source venv/bin/activate
pip install -e ".[backend]"
```

Jalankan backend di mesin sendiri (perlu unduh checkpoint 330 MB sekali):

```bash
python modal_app.py --lokal
# Model siap. Sample rate 22050 Hz.
# Uvicorn running on http://127.0.0.1:8000
```

Jalankan frontend di terminal lain:

```bash
npx serve public
```

Buka URL yang ditampilkan `serve`, lalu di **Pengaturan Backend** isi
`http://127.0.0.1:8000`. Saat mode lokal, `TTS_ACCESS_TOKEN` kosong sehingga
kode akses tidak diperiksa.

### Uji cepat tanpa peramban

```bash
curl -X POST http://127.0.0.1:8000/synthesize \
  -H "Content-Type: application/json" \
  -d '{"teks":"Sugeng enjing, kula badhe dhateng pasar.","pembicara":"JV-00264","kecepatan":1.0}' \
  --output hasil.wav
```

## Mode Lama: Antarmuka Gradio

Antarmuka Gradio bawaan repo asli masih ada di `gradio_app.py` dan tetap bisa
dijalankan di mesin lokal. Jalurnya masih memakai binary `tts` hasil instalasi
paket, bukan backend Modal:

```bash
pip install -e ".[web-lokal]"
python gradio_app.py
# buka http://127.0.0.1:7860
```

CLI juga masih tersedia:

```bash
tts_drat --text="Selamat pagi" --speaker=ardi --output-file=pagi.wav
```

## Perubahan dari Versi Asli

- **Backend pindah ke Modal.** Sintesis tidak lagi dijalankan lewat subprocess
  binary `tts`, melainkan memanggil `TTS.utils.synthesizer.Synthesizer` langsung
  di dalam proses — hemat 2–5 detik per permintaan.
- **Frontend Gradio diganti HTML/CSS/JS statis** agar bisa di-deploy ke Vercel
  sebagai situs statis. Tema MetafisikTheme (gradasi kuning-putih, tombol oranye,
  font Quicksand) direplikasi di `public/styles.css`.
- **Slider kecepatan sekarang benar-benar berfungsi.** Di versi asli nilainya
  diterima lalu diabaikan; sekarang dipetakan ke `length_scale` VITS.
- **Dropdown bahasa tidak lagi menyesatkan.** Versi asli menampilkan 17 bahasa
  dari `languages.json` padahal model hanya punya 83 speaker embedding tanpa
  embedding bahasa. Sekarang hanya 3 bahasa yang benar-benar didukung, dan
  pilihannya menyaring daftar pembicara.
- **`tts` (Coqui asli) diganti `coqui-tts` 0.27.5.** Paket lama dikunci
  Python `<3.12` dan sudah tidak dirawat.
- **Normalisasi teks dipindah ke `g2p_id/scripts/normalize.py`** supaya backend
  bisa memakainya tanpa menarik `wget` dan `simpleaudio`.
- **Endpoint dilindungi kode akses** via header `X-Access-Token`.

## Unduh Model TTS

Checkpoint `checkpoint_1260000-inference.pth` (v1.2) diunduh otomatis saat build
image Modal dari [releases Wikidepia/indonesian-tts](https://github.com/Wikidepia/indonesian-tts/releases/).

**DO NOT USE FOR COMMERCIAL PURPOSES!**

### Model changelog

#### v1.2 (Aug 12, 2022)

Finetuned from v1.1 model on:

- 4 hours of Audiobook dataset
- 2000 sample of Azure TTS
- High quality TTS data for Javanese & Sundanese

#### v1.1 (Aug 6, 2022)

Finetuned from LJSpeech model on:

- 4 hours of Audiobook dataset
- 2000 sample of Azure TTS

#### v1.0 (Jun 23, 2022)

Trained from scratch on:

- 4 hours of Audiobook dataset.

## Data

- [Indonesian Azure TTS](https://depia.wiki/files/azure-tts.tar)

## Teknologi yang Digunakan

- [Modal](https://modal.com/) untuk menjalankan inferensi
- [Coqui TTS](https://github.com/coqui-ai/TTS) (fork `coqui-tts`) untuk model VITS
- [ONNX Runtime](https://onnxruntime.ai/) untuk model G2P `bert_pron.onnx`
- [Gradio](https://gradio.app/) untuk antarmuka mode lokal

## Lisensi

Proyek ini dilisensikan di bawah lisensi MIT. Lihat file [LICENSE](LICENSE) untuk
informasi lebih lanjut.

## Kontribusi

Kami menyambut kontribusi dari siapa pun. Untuk berkontribusi, silakan buat
_pull request_ atau buka _issue_ untuk mendiskusikan perubahan yang ingin Anda
lakukan.

## Kontak

Untuk informasi lebih lanjut, silakan hubungi __drat di : http://drat.github.io

---

Energi Semesta Digital © 2024 __drat. | 🇮🇩 Untuk Indonesia Jaya!
