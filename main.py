import os
import pandas as pd
import streamlit as st
from ai_helper import generate_structured_quiz, generate_summary
from database import QuizScore, SessionLocal, init_db, save_quiz_score

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

# Sayfa Ayarları
st.set_page_config(
    page_title="PawCap AI - Zeki Ders Asistanın", page_icon="🐾", layout="wide"
)

# ==========================================
# 🎨 PAWCAP PREMIUM LOGO & UI CSS TASARIMI
# ==========================================
st.markdown(
    """
    <style>
    /* 1. Global Sayfa Temeli */
    .stApp { background-color: #fff5f8; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    
    /* 2. LOGO BÖLÜMÜ (CSS ile Çizim) */
    .logo-container {
        display: flex; align-items: center; justify-content: center;
        gap: 20px; padding: 20px 0; margin-bottom: 20px;
    }
    .logo-icon {
        position: relative; width: 70px; height: 70px;
        background-color: #ff85a1; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        box-shadow: 0 6px 15px rgba(255,133,161,0.3);
    }
    /* Kep Kısmı */
    .logo-icon::before {
        content: ''; position: absolute; top: -10px; width: 45px; height: 10px;
        background-color: #ff6b8b; border-radius: 4px;
    }
    /* Pati Kısmı (Basit Çizim) */
    .logo-paw {
        width: 30px; height: 25px; background-color: white;
        border-radius: 50% 50% 40% 40%; position: relative;
    }
    .logo-paw::after {
        content: ''; position: absolute; top: -12px; left: 5px;
        width: 10px; height: 10px; background-color: white; border-radius: 50%;
        box-shadow: 10px 0 0 white;
    }

    .logo-text {
        color: #ff85a1; font-size: 50px; font-weight: 900;
        letter-spacing: -1.5px; text-shadow: 0 2px 4px rgba(0,0,0,0.03);
    }

    /* 3. Genel Başlıklar ve Metinler */
    h1, h2, h3, h4 { color: #ff6b8b !important; font-weight: 800 !important; }
    .subheader-text { color: #8a606d; font-size: 18px; text-align: center; margin-bottom: 30px; }

    /* 4. PREMIUM BUTON TASARIMI (.stButton) */
    .stButton>button {
        background: linear-gradient(135deg, #ff85a1 0%, #ff6b8b 100%);
        color: white; border-radius: 15px; border: none !important;
        width: 100%; height: 55px; font-weight: 800; font-size: 17px;
        letter-spacing: 0.5px; text-transform: uppercase;
        box-shadow: 0 6px 12px rgba(255,107,139,0.25);
        transition: all 0.3s ease-in-out;
    }
    .stButton>button:hover {
        box-shadow: 0 8px 20px rgba(255,107,139,0.4);
        transform: translateY(-3px) scale(1.02);
    }
    .stButton>button:active { transform: translateY(1px); }

    /* 5. GİRDİ ALANLARI VE ŞIKLAR (UX Güncellemesi) */
    div[role="radiogroup"] {
        padding: 20px; background: white; border-radius: 15px;
        border: 2px solid #ffeef2;
        box-shadow: 0 8px 25px rgba(0,0,0,0.03);
        transition: border-color 0.3s;
    }
    div[role="radiogroup"]:hover { border-color: #ffb3c6; }

    /* 6. SONUÇ VE ÖZET KARTLARI ( premium card feel ) */
    .premium-card {
        background: white; padding: 25px; border-radius: 18px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.04);
        border: 1px solid #ffeef2; margin-bottom: 25px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ==========================================
# 🐾 PAWCAP UI RENDER BAŞLIYOR
# ==========================================

# 1. LOGO VE BAŞLIK ALANI
st.markdown(
    """
    <div class="logo-container">
        <div class="logo-icon">
            <div class="logo-paw"></div>
        </div>
        <div class="logo-text">PawCap</div>
    </div>
    <div class="subheader-text">Akademik Pati: Yapay Zeka Destekli İnteraktif Çalışma Asistanın</div>
    """,
    unsafe_allow_html=True,
)
st.write("---")

app_tab1, app_tab2 = st.tabs(
    ["📚 Çalışma Odası (Özet & Quiz)", "📊 Gelişim Paneli (Dashboard)"]
)

with app_tab1:
    st.markdown("### 📥 1. Adım: Ders İçeriğini Yükle")
    
    media_tab1, media_tab2, media_tab3, media_tab4 = st.tabs(
        ["📕 PDF / Slayt", "🎥 Video", "🎙️ Ses Kaydı", "📄 Ders Notu (Metin)"]
    )

    active_file_path = None
    active_text = None

    with media_tab1:
        pdf_file = st.file_uploader(
            "Ders kitapçığı veya slayt PDF'i yükle", type=["pdf"]
        )
        if pdf_file:
            active_file_path = save_uploaded_file(pdf_file)
            st.session_state.current_topic = pdf_file.name
            st.success(f"📄 {pdf_file.name} analize hazır.")

    with media_tab2:
        video_file = st.file_uploader(
            "Ders videosunu yükle", type=["mp4", "mov", "avi"]
        )
        if video_file:
            st.video(video_file)
            active_file_path = save_uploaded_file(video_file)
            st.session_state.current_topic = video_file.name

    with media_tab3:
        audio_file = st.file_uploader(
            "Ders ses kaydını yükle", type=["mp3", "wav"]
        )
        if audio_file:
            st.audio(audio_file)
            active_file_path = save_uploaded_file(audio_file)
            st.session_state.current_topic = audio_file.name

    with media_tab4:
        text_note = st.text_area(
            "Ders notlarını yapıştır:", height=150
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
                with st.spinner("🐱 Özetleniyor..."):
                    try:
                        ozet = generate_summary(
                            text_content=active_text, file_path=active_file_path
                        )
                        st.markdown("### ✨ Dersin Özeti")
                        st.markdown(f'<div class="premium-card">{ozet}</div>', unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"⚠️ Hata: {e}")
                    finally:
                        clean_temp_file(active_file_path)
            else:
                st.warning("⚠️ Lütfen önce içerik yükleyin.")

    with col2:
        if st.button("🎯 İnteraktif Quiz Başlat"):
            if active_file_path or active_text:
                with st.spinner("🐱 Quiz hazırlanıyor..."):
                    try:
                        st.session_state.selected_answers = {}
                        st.session_state.quiz_submitted = False
                        st.session_state.quiz_data = generate_structured_quiz(
                            text_content=active_text, file_path=active_file_path
                        )
                    except Exception as e:
                        st.error(f"⚠️ Hata: {e}")
                    finally:
                        clean_temp_file(active_file_path)
            else:
                st.warning("⚠️ Lütfen önce içerik yükleyin.")

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
            if st.button("✅ Quizi Bitir ve Puanla"):
                st.session_state.quiz_submitted = True
                st.rerun()

        if st.session_state.quiz_submitted:
            st.markdown(f'<div class="premium-card">', unsafe_allow_html=True)
            st.markdown("### 🏆 Sunucu ve Analiz")

            dogru_sayisi = 0
            toplam_soru = len(questions)
            yanlis_sorular = []

            for idx, q_data in enumerate(questions):
                kullanici_cevabi = st.session_state.selected_answers.get(idx, "")
                dogru_cevap = q_data["correct_answer"]

                with st.expander(f"Soru {idx + 1} Analizi", expanded=True):
                    if kullanici_cevabi == dogru_cevap:
                        st.success(f"✅ Doğru! Senin Cevabın: `{kullanici_cevabi}`")
                        dogru_sayisi += 1
                    else:
                        st.error(f"❌ Yanlış. Senin Cevabın: `{kullanici_cevabi}`. Doğru Cevap: `{dogru_cevap}`")
                        yanlis_sorular.append(q_data["question_text"])
                    st.info(f"💡 **Açıklama:** {q_data['explanation']}")

            basari_yuzdesi = int((dogru_sayisi / toplam_soru) * 100)
            st.metric(label="Başarı Puanın", value=f"{dogru_sayisi} / {toplam_soru}", delta=f"%{basari_yuzdesi}")
            save_quiz_score(st.session_state.current_topic, dogru_sayisi, toplam_soru)
            st.markdown('</div>', unsafe_allow_html=True) # Premium card sonu

            if yanlis_sorular:
                st.write("---")
                st.markdown("### 🧠 PawCap Hata Koçu Tavsiyesi")
                tavsiye_html = '<div class="premium-card" style="border-left: 5px solid #ffb3c6;">'
                tavsiye_html += '<p style="color: #8a606d;">Pati asistanın şu konuları gözden geçirmeni öneriyor:</p><ul>'
                for hata in yanlis_sorular:
                    tavsiye_html += f"<li>📌 <b>{hata}</b></li>"
                tavsiye_html += "</ul></div>"
                st.markdown(tavsiye_html, unsafe_allow_html=True)
            else:
                st.balloons()
                st.success("🎉 Muhteşem! Konuya tamamen hakimsin.")


with app_tab2:
    st.markdown("### 📊 Gelişim İzleme Paneli")
    scores = get_all_scores()

    if not scores:
        st.info("Henüz sınav verisi yok. Çalışma odasında quiz çözdükçe burası güncellenecektir.")
    else:
        df = pd.DataFrame([
            {
                "Konu": s.topic,
                "Doğru": s.score,
                "Toplam": s.total_questions,
                "Yüzde": int((s.score / s.total_questions) * 100),
                "Tarih": s.created_at.strftime("%d-%m-%Y %H:%M"),
            }
            for s in scores
        ])

        dash_col1, dash_col2, dash_col3 = st.columns(3)
        with dash_col1:
            st.metric("Çözülen Quiz", len(df))
        with dash_col2:
            st.metric("Ortalama Başarı", f"%{int(df['Yüzde'].mean())}")
        with dash_col3:
            st.metric("Çözülen Soru", int(df["Toplam"].sum()))

        st.write("---")
        st.markdown(f'<div class="premium-card">', unsafe_allow_html=True)
        st.markdown("#### 📈 Sınav Başarı Eğrisi (%)")
        st.line_chart(df.set_index("Tarih")["Yüzde"])
        st.markdown('</div>', unsafe_allow_html=True)

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.markdown(f'<div class="premium-card">', unsafe_allow_html=True)
            st.markdown("#### 🎯 Doğru/Yanlış Dağılımı")
            df["Yanlış"] = df["Toplam"] - df["Doğru"]
            st.bar_chart(df[["Konu", "Doğru", "Yanlış"]].set_index("Konu"))
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col_g2:
            st.markdown(f'<div class="premium-card">', unsafe_allow_html=True)
            st.markdown("#### 🗄️ Son Sınav Kayıtları")
            st.dataframe(df[["Tarih", "Konu", "Doğru", "Toplam", "Yüzde"]].tail(5), use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)