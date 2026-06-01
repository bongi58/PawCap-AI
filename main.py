import os
import time
import pandas as pd
import streamlit as st
from ai_helper import generate_structured_quiz, generate_summary, generate_flashcards
from database import (
    init_db, save_quiz_score, create_new_chat_session,
    get_all_chat_sessions, get_messages_for_session, save_chat_message,
    earn_badge, get_my_badges
)

init_db()

TEMP_DIR = "temp_uploads"
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

LOGO_PATH = "logo.png"
HAS_CUSTOM_LOGO = os.path.exists(LOGO_PATH)
ASSISTANT_AVATAR = LOGO_PATH if HAS_CUSTOM_LOGO else None

st.set_page_config(page_title="PawCap AI - Premium Asistan", layout="wide")

st.markdown(
    """
    <style>
    .stApp { background-color: #fff5f8; font-family: 'Segoe UI', sans-serif; }
    [data-testid="stSidebar"] { background-color: white; border-right: 2px solid #ffeef2; }
    .stButton>button { background: linear-gradient(135deg, #ff85a1 0%, #ff6b8b 100%); color: white; border-radius: 12px; font-weight: bold; border: none; box-shadow: 0 4px 10px rgba(255,107,139,0.2); transition: all 0.3s; }
    .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 6px 15px rgba(255,107,139,0.3); }
    .badge-box { background: #fff; padding: 10px; border-radius: 10px; border: 1px solid #ffeef2; margin-bottom: 5px; text-align: center; font-size: 20px; }
    .flashcard { background: white; padding: 30px; border-radius: 20px; text-align: center; border: 2px solid #ff85a1; box-shadow: 0 10px 20px rgba(255,133,161,0.1); margin: 10px 0; font-size: 18px; }
    .premium-card { background: white; padding: 20px; border-radius: 15px; border: 1px solid #ffeef2; box-shadow: 0 4px 10px rgba(0,0,0,0.03); margin-top: 15px; }
    [data-testid="stChatMessage"] { border-radius: 15px; padding: 15px; margin-bottom: 15px; border: 1px solid #ffeef2;}
    [data-testid="stChatMessage"]:nth-child(even) { background-color: #ff85a1; color: white; margin-left: 20%; }
    [data-testid="stChatMessage"]:nth-child(even) p { color: white !important; }
    [data-testid="stChatMessage"]:nth-child(odd) { background-color: white; color: #8a606d; margin-right: 20%; }
    </style>
    """, unsafe_allow_html=True,
)

# State Başlatma
defaults = {
    "current_session_id": None, "flashcards": None, "quiz_data": None,
    "selected_answers": {}, "quiz_submitted": False, "active_content_name": "Genel İçerik"
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

with st.sidebar:
    if HAS_CUSTOM_LOGO:
        st.image(LOGO_PATH, use_container_width=True)
    else:
        st.markdown("<div style='text-align:center; padding:10px; background:#ffeef2; border-radius:12px; color:#ff85a1; font-weight:900; font-size:24px;'>PAWCAP AI</div>", unsafe_allow_html=True)

    st.write("---")
    st.markdown("### 🏆 Başarı Rozetlerin")
    badges = get_my_badges()
    if not badges:
        st.caption("Henüz rozetin yok. Çalışmaya başla!")
    else:
        cols = st.columns(3)
        for i, b in enumerate(badges):
            cols[i % 3].markdown(f"<div class='badge-box' title='{b.badge_name}'>{b.badge_icon}</div>", unsafe_allow_html=True)

    st.write("---")
    if st.button("➕ Yeni Sohbet Başlat", use_container_width=True):
        st.session_state.current_session_id = create_new_chat_session()
        for key in ["flashcards", "quiz_data"]: st.session_state[key] = None
        st.session_state.selected_answers = {}
        st.session_state.quiz_submitted = False
        st.rerun()

    st.write("---")
    st.markdown("### 🗄️ Geçmiş Sohbetlerin")
    sessions = get_all_chat_sessions()
    if not sessions:
        st.caption("Henüz sohbet kaydı yok.")
    else:
        for s in sessions:
            if st.button(f"📄 {s.title}", key=f"sess_{s.id}", use_container_width=True):
                st.session_state.current_session_id = s.id
                for key in ["flashcards", "quiz_data"]: st.session_state[key] = None
                st.session_state.selected_answers = {}
                st.session_state.quiz_submitted = False
                st.rerun()

if not st.session_state.current_session_id:
    st.markdown(
        """<div style='text-align:center; padding-top:80px;'>
        <h1 style='color:#ff85a1; font-size:45px;'>PawCap AI Asistanına Hoş Geldin</h1>
        <p style='color:#8a606d; font-size:18px;'>Sol menüden yeni bir sohbet başlatarak ders notlarını yükleyebilir ve analize başlayabilirsin.</p>
        </div>""", unsafe_allow_html=True,
    )
else:
    active_session = next((s for s in sessions if s.id == st.session_state.current_session_id), None)
    session_title = active_session.title if active_session else "Sohbet Odası"

    st.subheader(f"💬 {session_title}")

    with st.expander("📥 Analiz Edilecek Dosya veya Not Ekle", expanded=True):
        f = st.file_uploader("PDF, Video veya Ses Kaydı", type=["pdf", "mp4", "mp3"])
        t = st.text_area("Veya doğrudan metin yapıştır:")
        active_f = None
        if f:
            active_f = os.path.join(TEMP_DIR, f.name)
            with open(active_f, "wb") as out_file:
                out_file.write(f.getbuffer())
            st.session_state.active_content_name = f.name
        elif t.strip():
            st.session_state.active_content_name = t[:20] + "..."

    messages = get_messages_for_session(st.session_state.current_session_id)
    for msg in messages:
        avatar_img = ASSISTANT_AVATAR if msg.role == "assistant" else "user"
        with st.chat_message(msg.role, avatar=avatar_img):
            st.markdown(msg.content)

    if prompt := st.chat_input("Ne yapalım? (Özetle / Quiz Yap / Flashcard Hazırla)"):
        save_chat_message(st.session_state.current_session_id, "user", prompt)
        with st.chat_message("user", avatar="user"):
            st.write(prompt)

        safe_text = t if t.strip() else None

        with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
            if not active_f and not safe_text:
                warning_msg = "⚠️ Analiz yapabilmem için yukarıdaki kutudan bir dosya yüklemeli veya metin yapıştırmalısın!"
                st.write(warning_msg)
                save_chat_message(st.session_state.current_session_id, "assistant", warning_msg)
            else:
                try:
                    if "özet" in prompt.lower():
                        with st.spinner("İçerik analiz edilip özetleniyor..."):
                            res = generate_summary(text_content=safe_text, file_path=active_f)
                            st.markdown(res)
                            save_chat_message(st.session_state.current_session_id, "assistant", res)
                            earn_badge("Özet Ustası", "📝")
                            st.session_state.flashcards, st.session_state.quiz_data = None, None

                    elif "quiz" in prompt.lower() or "test" in prompt.lower():
                        with st.spinner("İnteraktif sorular hazırlanıyor..."):
                            st.session_state.quiz_data = generate_structured_quiz(text_content=safe_text, file_path=active_f)
                            st.session_state.selected_answers, st.session_state.quiz_submitted, st.session_state.flashcards = {}, False, None
                            resp_msg = "🎯 Sınav hazırlandı! Hemen aşağıdan şıkları işaretleyebilirsin."
                            st.write(resp_msg)
                            save_chat_message(st.session_state.current_session_id, "assistant", resp_msg)
                            earn_badge("Sınav Avcısı", "🎯")

                    elif "flashcard" in prompt.lower() or "kart" in prompt.lower():
                        with st.spinner("Ezber kartları derleniyor..."):
                            st.session_state.flashcards = generate_flashcards(text_content=safe_text, file_path=active_f)
                            st.session_state.quiz_data = None
                            resp_msg = "🃏 Senin için önemli kavramlardan ezber kartları oluşturdum! Aşağıdan çalışabilirsin."
                            st.write(resp_msg)
                            save_chat_message(st.session_state.current_session_id, "assistant", resp_msg)
                            earn_badge("Hafıza Şampiyonu", "🧠")
                    else:
                        resp = "Harika! İçeriği aldım. Şimdi benden 'Özet', 'Quiz' veya 'Flashcard' hazırlamamı isteyebilirsin."
                        st.write(resp)
                        save_chat_message(st.session_state.current_session_id, "assistant", resp)
                
                except Exception as e:
                    st.error(f"İşlem sırasında bir hata oluştu: {str(e)}")
                
                finally:
                    # İşlem bitince yüklenen dosyayı klasörden sil (Sunucu şişmesin)
                    if active_f and os.path.exists(active_f):
                        os.remove(active_f)

    # --- Flashcard Render ---
    if st.session_state.flashcards:
        st.write("---")
        st.markdown("### 🃏 Flashcard Çalışma Modu")
        cards = st.session_state.flashcards["cards"]
        if "card_idx" not in st.session_state: st.session_state.card_idx = 0
        if "flipped" not in st.session_state: st.session_state.flipped = False

        curr = cards[st.session_state.card_idx]
        card_content = f"<b>CEVAP:</b><br>{curr['back']}" if st.session_state.flipped else f"<b>KAVRAM / SORU:</b><br>{curr['front']}"
        st.markdown(f"<div class='flashcard'>{card_content}</div>", unsafe_allow_html=True)

        c1, c2, c3 = st.columns(3)
        if c1.button("🔙 Önceki Kart"):
            st.session_state.card_idx = max(0, st.session_state.card_idx - 1)
            st.session_state.flipped, st.session_state.flashcards = False, st.session_state.flashcards 
            st.rerun()
        if c2.button("🔄 Kartı Çevir"):
            st.session_state.flipped = not st.session_state.flipped
            st.rerun()
        if c3.button("Sonraki Kart 🔜"):
            st.session_state.card_idx = min(len(cards) - 1, st.session_state.card_idx + 1)
            st.session_state.flipped = False
            st.rerun()

    if st.session_state.quiz_data:
        st.write("---")
        with st.markdown('<div class="premium-card">', unsafe_allow_html=True):
            st.markdown("### 📝 Kendini Test Et")
            questions = st.session_state.quiz_data.get("questions", [])

            for idx, q_data in enumerate(questions):
                st.markdown(f"#### Soru {idx + 1}: {q_data['question_text']}")
                cevap = st.radio("Şıklar:", q_data["options"], key=f"q_main_{idx}", index=None, disabled=st.session_state.quiz_submitted)
                if cevap: st.session_state.selected_answers[idx] = cevap
            st.write("")

            if not st.session_state.quiz_submitted:
                if st.button("✅ Quizi Bitir ve Puanla", key="btn_finish_main"):
                    st.session_state.quiz_submitted = True
                    st.rerun()

            if st.session_state.quiz_submitted:
                st.write("---")
                st.markdown("### 🏆 Sınav Sonucu ve Analiz")
                dogru_sayisi, toplam_soru = 0, len(questions)

                for idx, q_data in enumerate(questions):
                    kullanici_cevabi = st.session_state.selected_answers.get(idx, "")
                    dogru_cevap = q_data["correct_answer"]
                    with st.expander(f"Soru {idx + 1} Analizi", expanded=True):
                        st.write(f"**Senin Cevabın:** `{kullanici_cevabi}`")
                        if kullanici_cevabi == dogru_cevap:
                            st.success("✅ Doğru!")
                            dogru_sayisi += 1
                        else:
                            st.error(f"❌ Yanlış. Doğru Cevap: `{dogru_cevap}`")
                        st.info(f"💡 **Açıklama:** {q_data['explanation']}")

                basari_yuzdesi = int((dogru_sayisi / toplam_soru) * 100) if toplam_soru > 0 else 0
                st.metric(label="Başarı Puanın", value=f"{dogru_sayisi} / {toplam_soru}", delta=f"%{basari_yuzdesi}")
                save_quiz_score(st.session_state.active_content_name, dogru_sayisi, toplam_soru)
                st.caption("📌 *Bu sonuç gelişim takibin için veritabanına kaydedildi.*")

                if st.button("Sohbete Geri Dön (Quiz'i Kapat)", key="btn_close_main"):
                    st.session_state.quiz_data, st.session_state.selected_answers, st.session_state.quiz_submitted = None, {}, False
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)