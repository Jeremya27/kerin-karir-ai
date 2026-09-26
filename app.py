"""
Kerin - Asisten Karir AI
========================
Chatbot berbasis Gemini API yang membantu pengguna mencari lowongan kerja,
memberi tips CV & interview, serta merekomendasikan lowongan sesuai skill
dan preferensi pengguna.

Fitur:
- Percakapan natural language dengan Gemini (function calling / tools)
- Integrasi API eksternal: pencarian lowongan kerja real-time (Arbeitnow API)
- Memory: profil pengguna (skill, level, preferensi lokasi) disimpan lintas sesi
- Rekomendasi lowongan berdasarkan profil
"""

import os
import json
import requests
import streamlit as st
from datetime import datetime
from google import genai
from google.genai import types

# Catatan: API key Gemini SENGAJA tidak dibaca otomatis dari file/env di sini.
# Pengguna wajib menempelkannya sendiri lewat kotak input di sidebar (lihat
# bagian UI - SIDEBAR di bawah), supaya key tidak pernah tertulis di kode
# maupun ter-commit ke repository.

# --------------------------------------------------------------------------
# KONFIGURASI DASAR
# --------------------------------------------------------------------------
st.set_page_config(page_title="Kerin - Asisten Karir AI", page_icon="💼", layout="wide")

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "user_memory.json")
MODEL_NAME = "gemini-3.5-flash"

STYLE_PROMPTS = {
    "Santai": (
        "Gunakan gaya bahasa santai, hangat, dan seperti teman ngobrol. "
        "Boleh pakai emoji secukupnya, hindari istilah yang terlalu kaku."
    ),
    "Formal": (
        "Gunakan gaya bahasa formal, sopan, dan profesional layaknya konsultan karir. "
        "Hindari emoji dan singkatan tidak baku."
    ),
}

BASE_SYSTEM_PROMPT = """
Kamu adalah "Kerin", asisten karir AI berbahasa Indonesia yang membantu pengguna
dalam hal-hal berikut:
1. Mencari lowongan kerja terbaru sesuai posisi/skill dan lokasi yang diminta
   (gunakan tools 'search_jobs' setiap kali pengguna minta dicarikan lowongan,
   minta rekomendasi kerja, atau bertanya lowongan apa saja yang tersedia).
2. Memberi tips menulis CV/resume dan mempersiapkan wawancara kerja.
3. Memberi saran pengembangan karir (skill yang perlu dipelajari, jalur karir, dst).
4. Melakukan follow-up ramah berdasarkan profil pengguna (skill, pengalaman,
   preferensi lokasi/remote) yang sudah tersimpan, tanpa perlu bertanya ulang
   informasi yang sama.

Aturan penting:
- Saat menampilkan hasil pencarian lowongan dari tools, rangkum dalam format
  markdown list yang rapi: **Judul Posisi** - Perusahaan - Lokasi, lalu
  sertakan link lamarannya. Jangan mengarang lowongan yang tidak ada di hasil tools.
- Jika hasil pencarian kosong, sampaikan dengan jujur dan sarankan kata kunci lain.
- Selalu jawab dalam Bahasa Indonesia kecuali diminta lain.
- Jangan mengarang informasi lowongan atau data yang tidak berasal dari tools.
"""


# --------------------------------------------------------------------------
# MEMORY: profil pengguna disimpan di file JSON lokal (persist antar sesi)
# --------------------------------------------------------------------------
def load_all_profiles() -> dict:
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_profile(username: str, profile: dict) -> None:
    all_profiles = load_all_profiles()
    profile["last_updated"] = datetime.now().isoformat(timespec="seconds")
    all_profiles[username] = profile
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(all_profiles, f, ensure_ascii=False, indent=2)


def get_profile(username: str) -> dict:
    all_profiles = load_all_profiles()
    return all_profiles.get(
        username,
        {"skills": "", "experience_level": "Fresh Graduate", "preferred_location": "Remote"},
    )


# --------------------------------------------------------------------------
# TOOL / FUNCTION CALLING: pencarian lowongan kerja via Arbeitnow API
# --------------------------------------------------------------------------
def search_jobs(keyword: str, location: str = "") -> dict:
    """Mencari lowongan kerja terbaru berdasarkan kata kunci posisi atau skill.

    Gunakan fungsi ini setiap kali pengguna ingin mencari lowongan kerja,
    minta rekomendasi pekerjaan, atau bertanya lowongan apa saja yang tersedia
    untuk suatu posisi/skill tertentu.

    Args:
      keyword: Kata kunci posisi atau skill, misalnya 'data scientist',
        'frontend developer', 'digital marketing'.
      location: Preferensi lokasi kerja, misalnya 'remote', 'jakarta'.
        Boleh dikosongkan jika pengguna tidak menyebutkan lokasi.

    Returns:
      Dictionary berisi daftar lowongan (jobs) dan jumlah hasil (count).
    """
    try:
        resp = requests.get("https://www.arbeitnow.com/api/job-board-api", timeout=10)
        resp.raise_for_status()
        data = resp.json().get("data", [])
    except requests.RequestException as e:
        return {"error": f"Gagal mengambil data lowongan: {e}", "jobs": [], "count": 0}

    keyword_lower = keyword.lower().strip()
    location_lower = location.lower().strip()
    results = []

    for job in data:
        title = job.get("title", "")
        tags = " ".join(job.get("tags", []) or [])
        haystack = f"{title} {tags}".lower()

        if keyword_lower and keyword_lower not in haystack:
            continue

        job_location = (job.get("location") or "").lower()
        is_remote = bool(job.get("remote"))
        if location_lower and location_lower not in ("remote",) and not is_remote:
            if location_lower not in job_location:
                continue

        results.append(
            {
                "title": job.get("title"),
                "company": job.get("company_name"),
                "location": job.get("location") or ("Remote" if is_remote else "-"),
                "remote": is_remote,
                "tags": job.get("tags"),
                "url": job.get("url"),
            }
        )
        if len(results) >= 6:
            break

    return {"jobs": results, "count": len(results)}


# --------------------------------------------------------------------------
# GEMINI CLIENT & CHAT SESSION
# --------------------------------------------------------------------------
def get_client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)


def build_system_instruction(style: str, profile: dict) -> str:
    profile_note = (
        f"\nProfil pengguna yang sudah diketahui (memory): "
        f"skill/keahlian = '{profile.get('skills', '-')}', "
        f"level pengalaman = '{profile.get('experience_level', '-')}', "
        f"preferensi lokasi kerja = '{profile.get('preferred_location', '-')}'. "
        f"Gunakan informasi ini secara natural tanpa menanyakannya ulang."
    )
    return BASE_SYSTEM_PROMPT + "\n" + STYLE_PROMPTS[style] + profile_note


def init_chat(api_key: str, style: str, profile: dict):
    client = get_client(api_key)
    config = types.GenerateContentConfig(
        system_instruction=build_system_instruction(style, profile),
        tools=[search_jobs],
        temperature=0.6,
    )
    chat = client.chats.create(model=MODEL_NAME, config=config)
    # PENTING: kembalikan `client` juga dan simpan di session_state.
    # Jika hanya `chat` yang disimpan, `client` akan di-garbage-collect Python
    # karena tidak ada referensi lain ke sana -> genai.Client.__del__() otomatis
    # menutup koneksi HTTP yang sebenarnya masih dipakai bersama oleh `chat`,
    # sehingga permintaan berikutnya gagal dengan error
    # "Cannot send a request, as the client has been closed."
    return client, chat


# --------------------------------------------------------------------------
# UI - SIDEBAR (identitas, profil/memory, konfigurasi)
# --------------------------------------------------------------------------
st.sidebar.title("💼 Kerin - Asisten Karir AI")
st.sidebar.caption("Chatbot pencari kerja & konsultan karir berbasis Gemini API")

api_key = st.sidebar.text_input(
    "Gemini API Key",
    type="password",
    help="Dapatkan API key gratis di https://aistudio.google.com/apikey. "
    "Key ini hanya disimpan sementara di sesi browser kamu, tidak ditulis ke file mana pun.",
)

st.sidebar.divider()
st.sidebar.subheader("👤 Profil Kamu (tersimpan otomatis)")

username = st.sidebar.text_input("Nama / username", value=st.session_state.get("username", ""))

if username:
    if "loaded_username" not in st.session_state or st.session_state.loaded_username != username:
        loaded_profile = get_profile(username)
        st.session_state.profile_skills = loaded_profile.get("skills", "")
        st.session_state.profile_level = loaded_profile.get("experience_level", "Fresh Graduate")
        st.session_state.profile_location = loaded_profile.get("preferred_location", "Remote")
        st.session_state.loaded_username = username

    skills = st.sidebar.text_input(
        "Skill / keahlian (pisahkan koma)",
        value=st.session_state.get("profile_skills", ""),
        placeholder="mis. Python, SQL, Data Visualization",
    )
    level = st.sidebar.selectbox(
        "Level pengalaman",
        ["Fresh Graduate", "Junior (1-2 tahun)", "Mid (3-5 tahun)", "Senior (5+ tahun)"],
        index=["Fresh Graduate", "Junior (1-2 tahun)", "Mid (3-5 tahun)", "Senior (5+ tahun)"].index(
            st.session_state.get("profile_level", "Fresh Graduate")
        ),
    )
    location_pref = st.sidebar.text_input(
        "Preferensi lokasi kerja", value=st.session_state.get("profile_location", "Remote")
    )

    if st.sidebar.button("💾 Simpan Profil", use_container_width=True):
        save_profile(
            username,
            {"skills": skills, "experience_level": level, "preferred_location": location_pref},
        )
        st.session_state.profile_skills = skills
        st.session_state.profile_level = level
        st.session_state.profile_location = location_pref
        st.session_state.pop("chat", None)  # rebuild chat supaya system prompt ter-update
        st.sidebar.success("Profil disimpan! Kerin akan mengingat ini di sesi berikutnya.")

    if st.sidebar.button("🔍 Rekomendasikan Lowongan Untukku", use_container_width=True):
        st.session_state.trigger_recommendation = True
else:
    st.sidebar.info("Isi nama untuk menyimpan & memuat profil kamu (memory lintas sesi).")

st.sidebar.divider()
style_choice = st.sidebar.radio("Gaya bahasa chatbot", ["Santai", "Formal"], horizontal=True)

if st.sidebar.button("🗑️ Reset Percakapan", use_container_width=True):
    st.session_state.pop("chat", None)
    st.session_state.pop("messages", None)

# --------------------------------------------------------------------------
# UI - MAIN CHAT AREA
# --------------------------------------------------------------------------
st.title("💼 Kerin - Asisten Karir AI")
st.caption(
    "Tanya seputar lowongan kerja, tips CV & interview, atau minta rekomendasi "
    "pekerjaan sesuai skill kamu."
)

if not api_key:
    st.warning("Masukkan Gemini API key di sidebar untuk mulai chat dengan Kerin.")
    st.stop()

current_profile = {
    "skills": st.session_state.get("profile_skills", ""),
    "experience_level": st.session_state.get("profile_level", "Fresh Graduate"),
    "preferred_location": st.session_state.get("profile_location", "Remote"),
}

if "chat" not in st.session_state or st.session_state.get("chat_style") != style_choice:
    try:
        client, chat = init_chat(api_key, style_choice, current_profile)
        st.session_state.gemini_client = client  # simpan agar tidak di-garbage-collect
        st.session_state.chat = chat
        st.session_state.chat_style = style_choice
    except Exception as e:
        st.error(f"Gagal menginisialisasi Gemini client: {e}")
        st.stop()

if "messages" not in st.session_state:
    intro = (
        f"Halo{', ' + username if username else ''}! 👋 Aku Kerin, asisten karir kamu. "
        "Aku bisa bantu cariin lowongan kerja terbaru, kasih tips CV & interview, "
        "atau rekomendasi karir sesuai skill kamu. Yuk mulai ngobrol!"
    )
    st.session_state.messages = [{"role": "assistant", "content": intro}]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


def send_and_render(user_text: str):
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.chat_message("user"):
        st.markdown(user_text)

    with st.chat_message("assistant"):
        with st.spinner("Kerin sedang mengetik..."):
            try:
                response = st.session_state.chat.send_message(user_text)
                reply = response.text
            except Exception as e:
                reply = f"Maaf, terjadi kendala saat menghubungi Gemini API: {e}"
        st.markdown(reply)
    st.session_state.messages.append({"role": "assistant", "content": reply})


# Trigger otomatis dari tombol "Rekomendasikan Lowongan Untukku"
if st.session_state.pop("trigger_recommendation", False):
    skill_query = current_profile["skills"] or "entry level"
    auto_prompt = (
        f"Tolong carikan dan rekomendasikan lowongan kerja yang cocok untuk skill "
        f"'{skill_query}' dengan preferensi lokasi '{current_profile['preferred_location']}'."
    )
    send_and_render(auto_prompt)

user_input = st.chat_input("Tulis pesan untuk Kerin...")
if user_input:
    send_and_render(user_input)