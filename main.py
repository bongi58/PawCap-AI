import os
import pandas as pd
import streamlit as st
from ai_helper import generate_structured_quiz, generate_summary
from database import SessionLocal, QuizScore, init_db, save_quiz_score

# Veritabanını başlat
init_db()

TEMP_DIR = "temp_uploads"
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)


def save_uploaded_file(uploaded_file):
    file_path = os.path.join(TEMP_DIR, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path


def clean_temp_file(file_path):
    if file_path and os.path.exists(file_path):
        os.remove(file_path)


def get_all_scores():
    """Veritabanından tüm geçmiş sınav skorlarını çeker."""
    db = SessionLocal()
    try:
        return db.query(QuizScore).all()
    finally:
        db.close()


# --- SESSION STATE (DURUM YÖNETİMİ) ---
if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = None
if "selected_answers" not in st.session_state:
    st.session_state.selected_answers = {}
if "quiz_submitted" not in st.session_state:
    st.session_state.quiz_submitted = False
if "current_topic" not in st.session_state:
    st.session_state.current_topic = "Genel Ders İçeriği"

# Sayfa Ayarları (Geniş ve Profesyonel Görünüm)
st.set_page_config(
    page_title="PawCap - AI Study Buddy", page_icon="🐾", layout="wide"
)

# Soft Pastel & Premium CSS Tasarımı
st.markdown(
    """
    <style>
    .stApp { background-color: #fff5f8; }
    h1, h2, h3, h4 { color: #ff85a1; font-family: 'sans-serif'; font-weight: bold; }
    .stButton>button {
        background-color: #ff85a1; color: white;
        border-radius: 12px; border: none; width: 100%;
        font-weight: bold; transition: all 0.3s;
    }
    .stButton>button:hover { background-color: #ff6b8b; transform: translateY(-2px); }
    div[role="radiogroup"] { padding: 15px; background: white; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.03); }
    .metric-card { background: white; padding: 15px; border-radius: 12px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
    </style>
    """,
    unsafe_allow_html=True,
)

# ÜST BAŞLIK VE ANA SEKMELER
st.title("🐾 PawCap AI")
st.subheader("İnteraktif Yapay Zeka Ders Asistanı & Gelişim Takip Platformu")
st.write("---")

# Jürinin gözünü dolduracak Ana Uygulama Sekmeleri
app_tab1, app_tab2 = st.tabs(
    ["📚 Çalışma Odası (Özet & Quiz)", "📊 Öğrenci İlerleme Paneli (Dashboard)"]
)

# ==========================================
# SEKTÖR 1: ÇALIŞMA ODASI
# ==========================================
with app_tab1:
    st.markdown("### 📥 1. Adım: Ders İçeriğini Yükle")
    media_tab1, media_tab2, media_tab3 = st.tabs(
        ["🎥 Video", "🎙️ Ses Kaydı", "📄 Ders Notu (Metin)"]
    )

    active_file_path = None
    active_text = None

    with media_tab1:
        video_file = st.file_uploader(
            "Ders videosunu yükle", type=["mp4", "mov", "avi"]
        )
        if video_file:
            st.video(video_file)
            active_file_path = save_uploaded_file(video_file)
            st.session_state.current_topic = video_file.name

    with media_tab2:
        audio_file = st.file_uploader(
            "Ders ses kaydını yükle", type=["mp3", "wav"]
        )
        if audio_file:
            st.audio(audio_file)
            active_file_path = save_uploaded_file(audio_file)
            st.session_state.current_topic = audio_file.name

    with media_tab3:
        text_note = st.text_area(
            "Doğrudan ders notlarını buraya yapıştır:", height=150
        )
        if text_note.strip():
            active_text = text_note
            st.session_state.current_topic = text_note[:40] + "..."

    st.write("---")
    st.markdown("### 🧠 2. Adım: PawCap Ne Yapsın?")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("📝 Akıllı Özet Çıkar"):
            if active_file_path or active_text:
                with st.spinner("🐱 PawCap içeriği analiz edip özetliyor..."):
                    try:
                        ozet = generate_summary(
                            text_content=active_text, file_path=active_file_path
                        )
                        st.success("✨ İşte Dersin Özeti!")
                        st.markdown(ozet)
                    except Exception as e:
                        st.error(f"⚠️ Hata oluştu: {e}")
                    finally:
                        clean_temp_file(active_file_path)
            else:
                st.warning("⚠️ Lütfen önce bir içerik yükleyin.")

    with col2:
        if st.button("🎯 İnteraktif Quiz Başlat"):
            if active_file_path or active_text:
                with st.spinner(
                    "🐱 PawCap yapılandırılmış (JSON) test hazırlıyor..."
                ):
                    try:
                        st.session_state.selected_answers = {}
                        st.session_state.quiz_submitted = False
                        st.session_state.quiz_data = generate_structured_quiz(
                            text_content=active_text, file_path=active_file_path
                        )
                    except Exception as e:
                        st.error(f"⚠️ Hata oluştu: {e}")
                    finally:
                        clean_temp_file(active_file_path)
            else:
                st.warning("⚠️ Lütfen önce bir içerik yükleyin.")

    # --- 🎯 İNTERAKTİF QUİZ RENDER ALANI ---
    if st.session_state.quiz_data:
        st.write("---")
        st.markdown("### 📝 Kendini Test Et")

        questions = st.session_state.quiz_data.get("questions", [])

        for idx, q_data in enumerate(questions):
            st.markdown(f"#### Soru {idx + 1}: {q_data['question_text']}")
            cevap = st.radio(
                "Şıklar:",
                q_data["options"],
                key=f"q_{idx}",
                index=None,
                disabled=st.session_state.quiz_submitted,
            )
            if cevap:
                st.session_state.selected_answers[idx] = cevap

        st.write("")

        if not st.session_state.quiz_submitted:
            if st.button("✅ Quizi Bitir ve Puanımı Hesapla"):
                st.session_state.quiz_submitted = True
                st.rerun()

        if st.session_state.quiz_submitted:
            st.write("---")
            st.markdown("### 🏆 Sınav Sonucu ve Analiz")

            dogru_sayisi = 0
            toplam_soru = len(questions)
            yanlis_sorular = []  # Hata koçu için yanlışları biriktiriyoruz

            for idx, q_data in enumerate(questions):
                kullanici_cevabi = st.session_state.selected_answers.get(
                    idx, ""
                )
                dogru_cevap = q_data["correct_answer"]

                with st.expander(f"Soru {idx + 1} Analizi", expanded=True):
                    st.write(f"**Soru:** {q_data['question_text']}")
                    st.write(f"**Senin Cevabın:** `{kullanici_cevabi}`")

                    if kullanici_cevabi == dogru_cevap:
                        st.success("✅ Doğru!")
                        dogru_sayisi += 1
                    else:
                        st.error(f"❌ Yanlış. Doğru Cevap: `{dogru_cevap}`")
                        yanlis_sorular.append(q_data["question_text"])

                    st.info(f"💡 **Açıklama:** {q_data['explanation']}")

            # Puan Metriği
            basari_yuzdesi = int((dogru_sayisi / toplam_soru) * 100)
            st.metric(
                label="Başarı Puanın",
                value=f"{dogru_sayisi} / {toplam_soru}",
                delta=f"%{basari_yuzdesi}",
            )

            # Veritabanına Skoru Kaydet
            save_quiz_score(
                st.session_state.current_topic, dogru_sayisi, toplam_soru
            )

            # --- 🧠 YAPAY ZEKA HATA KOÇU (AI MISTAKE ROUTER) ---
            if yanlis_sorular:
                st.write("---")
                st.markdown("### 🧠 PawCap Hata Koçu Tavsiyesi")
                st.warning(
                    "Görünüşe göre bazı konularda eksiklerimiz var. Pati asistanın şu konuları tekrar etmeni öneriyor:"
                )
                for hata in yanlis_sorular:
                    st.markdown(f"- 📌 **Gözden Geçir:** {hata}")
            else:
                st.balloons()
                st.success(
                    "🎉 Muhteşem! Tüm soruları doğru bildin, konuya tamamen hakimsin."
                )


# ==========================================
# SEKTÖR 2: ÖĞRENCİ İLERLEME PANELİ (DASHBOARD)
# ==========================================
with app_tab2:
    st.markdown("### 📊 Akademik Başarı ve Gelişim İzleme Paneli")
    scores = get_all_scores()

    if not scores:
        st.info(
            "Henüz kayıtlı bir sınav verisi yok. Çalışma odasında birkaç quiz çözdükçe grafikler burada otomatik oluşacaktır."
        )
    else:
        # Veritabanı verisini Pandas DataFrame'e dönüştür
        df = pd.DataFrame(
            [
                {
                    "Konu": s.topic,
                    "Doğru": s.score,
                    "Toplam