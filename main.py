import os
import time
import pandas as pd
import streamlit as st
from ai_helper import generate_structured_quiz, generate_summary, generate_flashcards, process_content
from database import (
    init_db, save_quiz_score, create_new_chat_session,
    get_all_chat_sessions, get_messages_for_session, save_chat_message,
    earn_badge, get_my_badges, get_all_quiz_scores, update_chat_session_title
)

# Veritabanını başlat
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
    .premium-card { background: white; padding: 20px; border-radius: 15px; border: 1px solid #ffeef2; box-shadow: 0 4px 10px rgba(0,0,0,0.03); margin-top: 15px; margin-bottom: 15px; }
    [data-testid="stChatMessage"] { border-radius: 15px; padding: 15px; margin-bottom: 15px; border: 1px solid #ffeef2;}
    [data-testid="stChatMessage"]:nth-child(even) { background-color: #ff85a1; color: white; margin-left: 20%; }
    [data-testid="stChatMessage"]:nth-child(even) p { color: white !important; }
    [data-testid="stChatMessage"]:nth-child(odd) { background-color: white; color: #8a606d; margin-right: 20%; }
    </style>
    """, unsafe_allow_html=True,
)

# State Başlatma (Planlayıcı verileri eklendi)
defaults = {
    "current_session_id": None, "flashcards": None, "quiz_data": None,
    "selected_answers": {}, "quiz_submitted": False, "active_content_name": "Genel İçerik",
    "temp_text_input": "", "temp_file_path": None,
    "todo_list": pd.DataFrame([{"Durum": False, "Görev": "DGS Denemesi Çöz"}]),
    "time_blocks": pd.DataFrame([{"Saat": "09:00-11:00", "Aktivite": "Python Çalış"}])
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- SOL MENÜ (SIDEBAR) ---
with st.sidebar:
    if HAS_CUSTOM_LOGO:
        st.image(LOGO_PATH, use_container_width=True)
    else:
        st.markdown("<div style='text-align:center; padding:10px; background:#ffeef2; border-radius:12px; color:#ff85a1; font-weight:900; font-size:24px;'>PAWCAP AI</div>", unsafe_allow_html=True)

    st.write("---")
    
    # YENİ ÖZELLİK: GÜNLÜK PLANLAYICI
    st.markdown("### 📅 Günlük Planlayıcı")
    tab_todo, tab_time = st.tabs(["✅ To-Do", "⏳ Çizelge"])
    
    with tab_todo:
        st.caption("Görev eklemek için alt satıra tıkla:")
        st.session_state.todo_list = st.data_editor(
            st.session_state.todo_list, 
            num_rows="dynamic", 
            use_container_width=True, 
            hide_index=True
        )
        
    with tab_time:
        st.caption("Saat aralıklarını ve planını yaz:")
        st.session_state.time_blocks = st.data_editor(
            st.session_state.time_blocks, 
            num_rows="dynamic", 
            use_container_width=True, 
            hide_index=True
        )

    st.write("---")
    
    st.markdown("### 📥 Ders Materyali Ekle")
    f = st.file_uploader("PDF veya Ses Yükle", type=["pdf", "mp4", "mp3"], label_visibility="collapsed")
    t = st.text_area("Veya metin yapıştır:", height=100)
    
    if f:
        active_f = os.path.join(TEMP_DIR, f.name)
        with open(active_f, "wb") as out_file:
            out_file.write(f.getbuffer())
        st.session_state.temp_file_path = active_f
        st.session_state.active_content_name = f.name
    else:
        st.session_state.temp_file_path = None

    if t.strip():
        st.session_state.temp_text_input = t
        st.session_state.active_content_name = t[:20] + "..."
    else:
        st.session_state.temp_text_input = ""

    st.write("---")
    
    with st.expander("📊 Gelişim İstatistiklerim"):
        scores = get_all_quiz_scores()
        if scores:
            df = pd.DataFrame([{
                "Tarih": s.created_at, 
                "Başarı (%)": (s.score / s.total_questions) * 100 if s.total_questions > 0 else 0
            } for s in scores])
            df.set_index("Tarih", inplace=True)
            st.line_chart(df, y="Başarı (%)", color="#ff6b8b")
        else:
            st.caption("Henüz quiz çözmedin. Grafiğin burada belirecek!")

    st.write("---")
    if st.button("➕ Yeni Sohbet Başlat", use_container_width=True):
        st.session_state.current_session_id = create_new_chat_session()
        for key in ["flashcards", "quiz_data"]: st.session_state[key] = None
        st.session_state.selected_answers = {}
        st.session_state.quiz_submitted = False
        st.rerun()

    st.markdown("### 🗄️ Geçmiş Sohbetlerin")
    sessions = get_all_chat_sessions()
    for s in sessions:
        if st.button(f"📄 {s.title}", key=f"sess_{s.id}", use_container_width=True):
            st.session_state.current_session_id = s.id
            for key in ["flashcards", "quiz_data"]: st.session_state[key] = None
            st.session_state.selected_answers = {}
            st.session_state.quiz_submitted = False
            st.rerun()

# --- ANA EKRAN (SADECE SOHBET) ---
if not st.session_state.current_session_id:
    st.markdown(
        """<div style='text-align:center; padding-top:80px;'>
        <h1 style='color:#ff85a1; font-size:45px;'>PawCap AI Asistanına Hoş Geldin</h1>
        <p style='color:#8a606d; font-size:18px;'>Sol menüden planını yap, materyalini ekle ve sohbete başla.</p>
        </div>""", unsafe_allow_html=True,
    )
else:
    active_session = next((s for s in sessions if s.id == st.session_state.current_session_id), None)
    session_title = active_session.title if active_session else "Sohbet Odası"

    st.subheader(f"💬 {session_title}")

    # Sohbet Geçmişini Render Et
    messages = get_messages_for_session(st.session_state.current_session_id)
    for msg in messages:
        avatar_img = ASSISTANT_AVATAR if msg.role == "assistant" else "user"
        with st.chat_message(msg.role, avatar=avatar_img):
            st.markdown(msg.content)

    # Sohbet Girdisi (Prompt)
    if prompt := st.chat_input("Bana bir görev ver veya sohbet et..."):
        save_chat_message(st.session_state.current_session_id, "user", prompt)
        
        # Sohbet başlığını kullanıcının ilk mesajıyla güncelle
        update_chat_session_title(st.session_state.current_session_id, prompt)

        with st.chat_message("user", avatar="user"):
            st.write(prompt)

        safe_text = st.session_state.temp_text_input
        active_f = st.session_state.temp_file_path

        with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
            p_lower = prompt.lower()
            
            try:
                # 1. ÖZET İSTEĞİ
                if "özet" in p_lower or "kısaca" in p_lower:
                    if not active_f and not safe_text:
                        warning_msg = "⚠️ Özet çıkarmam için sol menüden bir dosya yüklemeli veya metin yapıştırmalısın!"
                        st.write(warning_msg)
                        save_chat_message(st.session_state.current_session_id, "assistant", warning_msg)
                    else:
                        with st.spinner("İçerik analiz edilip özetleniyor..."):
                            res = generate_summary(text_content=safe_text, file_path=active_f)
                            st.markdown(res)
                            save_chat_message(st.session_state.current_session_id, "assistant", res)
                            earn_badge("Özet Ustası", "📝")
                            
                            st.download_button(
                                label="📥 Bu Özeti İndir",
                                data=res,
                                file_name="PawCap_Ozet.txt",
                                mime="text/plain"
                            )
                            st.session_state.flashcards, st.session_state.quiz_data = None, None

                # 2. QUİZ İSTEĞİ
                elif "quiz" in p_lower or "test" in p_lower or "soru" in p_lower:
                    if not active_f and not safe_text:
                        warning_msg = "⚠️ Soru hazırlayabilmem için sol menüden bir not veya dosya eklemelisin!"
                        st.write(warning_msg)
                        save_chat_message(st.session_state.current_session_id, "assistant", warning_msg)
                    else:
                        with st.spinner("İnteraktif sorular hazırlanıyor..."):
                            st.session_state.quiz_data = generate_structured_quiz(text_content=safe_text, file_path=active_f)
                            st.session_state.selected_answers, st.session_state.quiz_submitted, st.session_state.flashcards = {}, False, None
                            resp_msg = "🎯 Sınav hazırlandı! Hemen aşağıdan şıkları işaretleyebilirsin."
                            st.write(resp_msg)
                            save_chat_message(st.session_state.current_session_id, "assistant", resp_msg)
                            earn_badge("Sınav Avcısı", "🎯")

                # 3. FLASHCARD İSTEĞİ
                elif "flashcard" in p_lower or "kart" in p_lower:
                    if not active_f and not safe_text:
                        warning_msg = "⚠️ Kart hazırlayabilmem için sol menüden içeriği eklemelisin!"
                        st.write(warning_msg)
                        save_chat_message(st.session_state.current_session_id, "assistant", warning_msg)
                    else:
                        with st.spinner("Ezber kartları derleniyor..."):
                            st.session_state.flashcards = generate_flashcards(text_content=safe_text, file_path=active_f)
                            st.session_state.quiz_data = None
                            resp_msg = "🃏 Senin için önemli kavramlardan ezber kartları oluşturdum! Aşağıdan çalışabilirsin."
                            st.write(resp_msg)
                            save_chat_message(st.session_state.current_session_id, "assistant", resp_msg)
                            earn_badge("Hafıza Şampiyonu", "🧠")
                            
                # 4. NORMAL SOHBET (Yapay Zeka Devrede!)
                else:
                    with st.spinner("PawCap düşünüyor..."):
                        res = process_content(prompt_text=prompt, text_content=safe_text, file_path=active_f)
                        st.markdown(res)
                        save_chat_message(st.session_state.current_session_id, "assistant", res)
                        
            except Exception as e:
                st.error(f"İşlem sırasında bir hata oluştu: {str(e)}")
            
            finally:
                if active_f and os.path.exists(active_f):
                    os.remove(active_f)
                    st.session_state.temp_file_path = None

    # --- Flashcard & Quiz Modülleri ---
    if st.session_state.flashcards:
        with st.markdown('<div class="premium-card">', unsafe_allow_html=True):
            st.markdown("### 🃏 Flashcard Çalışma Modu")
            cards = st.session_state.flashcards["cards"]
            if "card_idx" not in st.session_state: st.session_state.card_idx = 0
            if "flipped" not in st.session_state: st.session_state.flipped = False

            curr = cards[st.session_state.card_idx]
            card_content = f"<b>CEVAP:</b><br>{curr['back']}" if st.session_state.flipped else f"<b>KAVRAM / SORU:</b><br>{curr['front']}"
            st.markdown(f"<div class='flashcard'>{card_content}</div>", unsafe_allow_html=True)

            c1, c2, c3 = st.columns(3)
            if c1.button("🔙 Önceki"):
                st.session_state.card_idx = max(0, st.session_state.card_idx - 1)
                st.session_state.flipped = False
                st.rerun()
            if c2.button("🔄 Çevir"):
                st.session_state.flipped = not st.session_state.flipped
                st.rerun()
            if c3.button("Sonraki 🔜"):
                st.session_state.card_idx = min(len(cards) - 1, st.session_state.card_idx + 1)
                st.session_state.flipped = False
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.quiz_data:
        with st.markdown('<div class="premium-card">', unsafe_allow_html=True):
            st.markdown("### 📝 Kendini Test Et")
            questions = st.session_state.quiz_data.get("questions", [])

            for idx, q_data in enumerate(questions):
                st.markdown(f"#### Soru {idx + 1}: {q_data['question_text']}")
                cevap = st.radio("Şıklar:", q_data["options"], key=f"q_main_{idx}", index=None, disabled=st.session_state.quiz_submitted)
                if cevap: st.session_state.selected_answers[idx] = cevap
            
            if not st.session_state.quiz_submitted:
                st.write("")
                if st.button("✅ Quizi Bitir ve Puanla", key="btn_finish_main"):
                    st.session_state.quiz_submitted = True
                    st.rerun()

            if st.session_state.quiz_submitted:
                st.write("---")
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

                if st.button("Kapat", key="btn_close_main"):
                    st.session_state.quiz_data, st.session_state.selected_answers, st.session_state.quiz_submitted = None, {}, False
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)