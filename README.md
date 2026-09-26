# 💼 Kerin - Asisten Karir AI

Final Project: **LLM-Based Tools and Gemini API Integration for Data Scientists** (Hacktiv8)

Kerin adalah chatbot AI berbasis **Gemini API** yang berperan sebagai asisten karir.
Kerin membantu pengguna mencari lowongan kerja terbaru, memberi tips CV/interview,
dan memberi rekomendasi karir yang dipersonalisasi berdasarkan skill pengguna.

## ✨ Use Case & Fitur

| Aspek | Implementasi |
|---|---|
| **Use Case** | Job-search / career assistant bot |
| **Gaya bahasa** | Bisa dipilih: Santai atau Formal (toggle di sidebar) |
| **Domain pengetahuan** | Karir, lowongan kerja, tips CV & wawancara |
| **Integrasi API eksternal** | [Arbeitnow Job Board API](https://www.arbeitnow.com/api/job-board-api) — dipanggil otomatis lewat *function calling* Gemini saat pengguna minta dicarikan lowongan |
| **Memory** | Profil pengguna (skill, level pengalaman, preferensi lokasi) disimpan di `user_memory.json` dan otomatis dimuat kembali saat pengguna membuka sesi baru dengan nama yang sama |
| **Rekomendasi** | Tombol "Rekomendasikan Lowongan Untukku" mencari lowongan otomatis berdasarkan profil tersimpan |

## 🧠 Bagaimana LLM Tools / Function Calling Bekerja

Fungsi Python `search_jobs(keyword, location)` didaftarkan langsung sebagai **tool**
ke Gemini (`google-genai` SDK mendukung *automatic function calling*: cukup daftarkan
fungsi Python dengan type hint + docstring, dan model akan otomatis memanggilnya
saat relevan dengan permintaan pengguna).

Alur singkatnya:
1. Pengguna menulis, misalnya: *"carikan lowongan data analyst remote"*.
2. Gemini mendeteksi perlu memanggil tool `search_jobs`, lalu mengeksekusinya
   dengan argumen `keyword="data analyst"`, `location="remote"`.
3. Hasil JSON dari Arbeitnow API dikirim balik ke Gemini.
4. Gemini merangkum hasilnya menjadi jawaban natural language yang rapi.

## 🗂️ Struktur Project

```
kerin-karir-ai/
├── app.py              # Aplikasi utama Streamlit
├── requirements.txt     # Dependencies
├── .gitignore
└── README.md
```

## 🚀 Cara Menjalankan

### 1. Clone & masuk ke folder project
```bash
git clone <URL_REPO_KAMU>
cd kerin-karir-ai
```

### 2. Buat virtual environment (opsional tapi disarankan)
```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Siapkan Gemini API Key

> ⚠️ **Setiap orang yang menjalankan aplikasi ini butuh API key Gemini miliknya
> sendiri.** Key tidak disertakan di repo ini (dan memang tidak boleh) karena
> terikat ke akun Google & kuota pemakaian masing-masing.

1. Buka [Google AI Studio](https://aistudio.google.com/apikey), login dengan
   akun Google kamu, lalu buat API key gratis.
2. Simpan key itu — nanti ditempel langsung di kotak **"Gemini API Key"**
   di sidebar aplikasi saat sudah berjalan (lihat langkah 5).

Key **tidak pernah** ditulis di kode maupun disimpan ke file apa pun (tidak
perlu file `.env`) — hanya tersimpan sementara di memori sesi browser selama
aplikasi berjalan, sehingga aman untuk repo publik.

### 5. Jalankan aplikasi
```bash
streamlit run app.py
```
Aplikasi akan terbuka di `http://localhost:8501`.

## ⚠️ Catatan

- API pencarian lowongan (Arbeitnow) adalah API publik gratis tanpa API key,
  namun data listing-nya sebagian besar berfokus pada lowongan remote/tech
  Eropa — cocok untuk keperluan demo, bukan sumber data lowongan Indonesia resmi.
- Model default: `gemini-3.5-flash-lite` — dipilih karena kuota gratis
  hariannya jauh lebih besar (~500 request/hari) dibanding Flash biasa
  (~20 request/hari per September 2026), sementara *function calling* tetap
  didukung penuh. Bisa diganti model Gemini lain lewat variabel `MODEL_NAME`
  di `app.py`, tapi perhatikan kuota gratis masing-masing model bisa berbeda
  jauh dan berubah sewaktu-waktu — cek dashboard Google AI Studio kamu untuk
  angka yang berlaku saat ini.
- Kalau muncul error `429 RESOURCE_EXHAUSTED`, itu artinya kuota gratis harian
  API key kamu sudah habis. Kuota reset tiap tengah malam waktu Pacific Time
  (siang/sore hari berikutnya di WIB). Solusi cepat: tunggu reset, pakai API
  key/project lain, atau aktifkan billing di Google Cloud Console untuk
  limit yang jauh lebih tinggi.