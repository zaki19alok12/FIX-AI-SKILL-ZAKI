# Story Video Template

Template video cerita interaktif vertikal 9:16 (animasi malam hari, subtitle kata-per-kata
dengan kata aktif berwarna hijau, HUD jam/episode, dan kartu pilihan "APA PILIHANMU?").

## Cara pakai (singkat)

1. Kirim ke Claude: **judul + tema + narasi** (atau hanya judul/tema, Claude yang menulis narasinya).
2. Claude membuat/ mengisi `stories/<judul>.json`.
3. Push ke GitHub -> GitHub Actions membuat suara narasi (edge-tts) dan merender video.
4. Ambil hasilnya di folder `output/` atau tab **Actions -> videos**.

## Jalankan sendiri

```bash
pip install -r requirements.txt     # + ffmpeg harus terpasang
python tts.py stories/malam-pertama.json     # suara + timing kata (butuh internet)
python render.py stories/malam-pertama.json  # -> output/malam-pertama.mp4
```
Tanpa `tts.py`, video tetap jadi (tanpa suara, timing kata diperkirakan).

## Format cerita (`stories/*.json`)

| Field | Arti |
|---|---|
| `title`, `series`, `episode`, `clock` | teks HUD di pojok kiri atas (3-5 detik pertama) |
| `handle` | watermark kecil di bawah |
| `voice` | suara edge-tts, mis. `id-ID-ArdiNeural` / `id-ID-GadisNeural` |
| `scenes[].bg` | `room`, `street`, `door` |
| `scenes[].camera` | `zoom_in`, `zoom_out`, `pan_left`, `pan_right`, `shake`, `static` |
| `scenes[].characters[]` | `type` (`man`/`woman`/`kid`), `x` (0-1), `color`, `tag`, `speaks` |
| `scenes[].badge` | `{label, text}` lencana info di atas |
| `scenes[].narration` | kalimat narasi (otomatis jadi subtitle kata-per-kata) |
| `choices` | `question`, `options[2]`, `footer`, `narration` (kartu pilihan di akhir) |

Musik latar opsional: taruh `assets/bgm.mp3` (otomatis dicampur pelan).
Latar/karakter baru: tambahkan fungsi `build_...` di `render.py` dan daftarkan di `BUILDERS`.
