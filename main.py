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

# Veritabanını başlat
init_db()

TEMP_DIR = "temp_uploads"
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

# Logo dosya yolu kontrolü (Görsel varsa onu, yoksa zarif bir varsayılan çizim kullanır)
LOGO_PATH = "logo.png"
HAS_CUSTOM_LOGO = os.path.exists(LOGO_PATH)
ASSISTANT_AVATAR = LOGO_PATH if HAS_CUSTOM_LOGO else None

st.set_page_config(
    page_title="PawCap AI - Premium Asistan", layout="wide"
)

# --- PREMIUM CSS TASARIMI ---
st.markdown(
    """
    <style>
    .stApp { background-color: #fff5f8; font-family: 'Segoe UI', sans-serif; }
    [data-testid="stSidebar"] { background-color: white; border-right: 2px solid #ffeef2; }
    
    /* Premium Butonlar */
    .stButton>button { 
        background: linear-gradient(135deg, #ff85a1 0%, #ff6b8b 100%); 
        color: white; border-radius: 12px; font-weight: bold; border: none;
        box-shadow: 0 4px 10px rgba(255,107,139,0.2); transition: all 0.3s;
    }
    .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 6px 15px rgba(255,107,139,0.3); }
    
    /* Şov Kartları */
    .badge-box { background: #fff; padding: 10px; border-radius: 10px; border: 1px solid #ffeef2; margin-bottom: 5px; text-align: center; font-size: 20px; }
    .flashcard { background: white; padding: 30px; border-radius: 20px; text-align: center; border: 2px solid #ff85a1; box-shadow: 0 10px 20px rgba(255,133,161,0.1); margin: 10px 0; font-size: 18px; }
    
    /* Mesaj Balonları UX */
    [data-testid="stChatMessage"] { border-radius: 15px; padding: 15px; margin-bottom: 15px; border: 1px solid #ffeef2;}
    [data-testid="stChatMessage"]:nth-child(even) { background-color: #ff85a1; color: white; margin-left: 20%; }
    [data-testid="stChatMessage"]:nth-child(even) p { color: white !important; }
    [data-testid="stChatMessage"]:nth-child(odd) { background-color: white; color: #8a606d; margin-right: 20%; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- SIDEBAR: ÖZEL LOGO, ROZETLER VE POMODORO ---
with st.sidebar:
    # 🎨 KURUMSAL LOGO ALANI
    if HAS_CUSTOM_LOGO:
        st.image(LOGO_PATH, use_container_width=True)
    else:
        # Görsel yüklenene kadar modern, emojili olmayan CSS logo placeholder
        st.markdown(
            """
            <div style='text-align:center; padding:10px; background:#ffeef2; border-radius:12px; color:#ff85a1; font-weight:900; font-size:24px; letter-spacing:-1px;'>
                PAWCAP AI
            </div>
            """, 
            unsafe_allow_html=True
        )

    st.write("---")
    
    # Rozet Odası
    st.markdown("### 🏆 Başarı Rozetlerin")
    badges = get_my_badges()
    if not badges:
        st.caption("Henüz rozetin yok. Çalışmaya başla!")
    else:
        cols = st.columns(3)
        for i, b in enumerate(badges):
            cols[i % 3].markdown(
                f"<div class='badge-box' title='{b.badge_name}'>{b.badge_icon}</div>", 
                unsafe_allow_html=True
            )

    st.write("---")
    
    # Pomodoro Sayacı
    st.markdown("### ⏱️ Pomodoro Odak Modu")
    if "pomo_time" not in st.session_state:
        st.session_state.pomo_time = 25 * 60
    if "pomo_running" not in st.session_state:
        st.session_state.pomo_running = False

    mins, secs = divmod(st.session_state.pomo_time, 60)
    st.markdown(
        f"<h1 style='text-align:center; color:#ff6b8b;'>{mins:02d}:{secs:02d}</h1>", 
        unsafe_allow_html=True
    )
    
    col_p1, col_p2 = st.columns(2)
    if col_p1.button("▶️ Başlat"):
        st.session_state.pomo_running = True
    if col_p2.button("⏹️ Sıfırla"): 
        st.session_state.pomo_running = False
        st.session_state.pomo_time = 25 * 60
    
    st.write("---")
    if st.button("➕ Yeni Sohbet Başlat", use_container_width=True):
        st.session_state.current_session_id = create_new_chat_session()
        st.rerun()

# --- ANA EKRAN VE SOHBET ---
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None
if "flashcards" not in st.session_state:
    st.session_state.flashcards = None

if not st.session_state.current_session_id:
    st.markdown(
        """
        <div style='text-align:center; padding-top:80px;'>
            <h1 style='color:#ff85a1; font-size:45px;'>PawCap AI Asistanına Hoş Geldin</h1>
            <p style='color:#8a606d; font-size:18px;'>Sol menüden yeni bir sohbet başlatarak ders notlarını yükleyebilir ve analize başlayabilirsin.</p>
        </div>
        """, 
        unsafe_allow_html=True
    )
else:
    # Veritabanından oturumları çekip güncel başlığı bul
    sessions = get_all_chat_sessions()
    active_session = next((s for s in sessions if s.id == st.session_state.current_session_id), None)
    session_title = active_session.title if active_session else "Sohbet Odası"
    
    st.subheader(f"💬 {session_title}")
    
    # Dosya Yükleme Paneli
    with st.expander("📥 Analiz Edilecek Dosya veya Not Ekle", expanded=True):
        f = st.file_uploader("PDF, Video veya Ses Kaydı", type=["pdf", "mp4", "mp3"])
        t = st.text_area("Veya doğrudan metin yapıştır:")
        active_f = None
        if f:
            active_f = os.path.join(TEMP_DIR, f.name)
            with open(active_f, "wb") as out_file:
                out_file.write(f.getbuffer())

    # Geçmiş Mesajları Çiz (Emoji avatar yerine harici görseli kullanır)
    messages = get_messages_for_session(st.session_state.current_session_id)
    for msg in messages:
        # Kullanıcı için standart profil ikonu, asistan için logo görseli
        avatar_img = ASSISTANT_AVATAR if msg.role == "assistant" else "user"
        with st.chat_message(msg.role, avatar=avatar_img):
            st.markdown(msg.content)

    # Sohbet Akışı
    if prompt := st.chat_input("Ne yapalım? (Özetle / Quiz Yap / Flashcard Hazırla)"):
        # Kullanıcı girdi balonunu çiz
        save_chat_message(st.session_state.current_session_id, "user", prompt)
        with st.chat_message("user", avatar="user"):
            st.write(prompt)
        
        # Asistan yanıt balonunu çiz
        with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
            if "özet" in prompt.lower():
                with st.spinner("İçerik analiz edilip özetleniyor..."):
                    res = generate_summary(text_content=t, file_path=active_f)
                    st.markdown(res)
                    save_chat_message(st.session_state.current_session_id, "assistant", res)
                    earn_badge("Özet Ustası", "📝")
            elif "quiz" in prompt.lower() or "test" in prompt.lower():
                with st.spinner("İnteraktif sorular hazırlanıyor..."):
                    st.session_state.quiz_data = generate_structured_quiz(text_content=t, file_path=active_f)
                    st.write("🎯 Sınav hazırlandı! Hemen aşağıdan şıkları işaretleyebilirsin.")
                    earn_badge("Sınav Avcısı", "🎯")
            elif "flashcard" in prompt.lower() or "kart" in prompt.lower():
                with st.spinner("Ezber kartları derleniyor..."):
                    st.session_state.flashcards = generate_flashcards(text_content=t, file_path=active_f)
                    st.write("🃏 Senin için önemli kavramlardan ezber kartları oluşturdum!")
                    earn_badge("Hafıza Şampiyonu", "🧠")
            else:
                resp = "Merhaba! İçeriğini yükledikten sonra benden 'Özet', 'Quiz' veya 'Flashcard' hazırlamamı isteyebilirsin."
                st.write(resp)
                save_chat_message(st.session_state.current_session_id, "assistant", resp)

    # --- ŞOV ALANI: FLASHCARDLAR ---
    if st.session_state.flashcards:
        st.write("---")
        st.markdown("### 🃏 Flashcard Çalışma Modu")
        cards = st.session_state.flashcards["cards"]
        if "card_idx" not in st.session_state:
            st.session_state.card_idx = 0
        if "flipped" not in st.session_state:
            st.session_state.flipped = False
        
        curr = cards[st.session_state.card_idx]
        card_content = f"<b>CEVAP:</b><br>{curr['back']}" if st.session_state.flipped else f"<b>KAVRAM / SORU:</b><br>{curr['front']}"
        
        st.markdown(f"<div class='flashcard'>{card_content}</div>", unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns(3)
        if c1.button("🔙 Önceki Kart"):
            st.session_state.card_idx = max(0, st.session_state.card_idx - 1)
            st.session_state.flipped = False
            st.rerun()
        if c2.button("🔄 Kartı Çevir"):
            st.session_state.flipped = not st.session_state.flipped
            st.rerun()
        if c3.button("Sonraki Kart 🔜"):
            st.session_state.card_idx = min(len(cards) - 1, st.session_state.card_idx + 1)
            st.session_state.flipped = False
            st.rerun()

# --- ARKA PLAN SAYAÇ MANTIĞI ---
if st.session_state.pomo_running and st.session_state.pomo_time > 0:
    time.sleep(1)
    st.session_state.pomo_time -= 1
    st.rerun()