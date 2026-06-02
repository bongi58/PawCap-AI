import os
import json
import pandas as pd
import streamlit as st
from ai_helper import generate_structured_quiz, generate_summary, generate_flashcards, process_content
from database import (
    init_db, save_quiz_score, create_new_chat_session,
    get_all_chat_sessions, get_messages_for_session, save_chat_message,
    earn_badge, get_my_badges, get_all_quiz_scores, update_chat_session_title,
    save_setting, get_setting, register_user, login_user
)

init_db()

TEMP_DIR = "temp_uploads"
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

LOGO_PATH = "logo.png"
HAS_CUSTOM_LOGO = os.path.exists(LOGO_PATH)
ASSISTANT_AVATAR = LOGO_PATH if HAS_CUSTOM_LOGO else None

st.set_page_config(page_title="PawCap AI", layout="wide")

st.markdown(
    """
    <style>
    .stApp { background-color: #fff5f8; font-family: 'Segoe UI', sans-serif; }
    [data-testid="stSidebar"] { background-color: white; border-right: 2px solid #ffeef2; }
    .stButton>button { background: linear-gradient(135deg, #ff85a1 0%, #ff6b8b 100%); color: white; border-radius: 12px; font-weight: bold; border: none; box-shadow: 0 4px 10px rgba(255,107,139,0.2); transition: all 0.3s; }
    .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 6px 15px rgba(255,107,139,0.3); }
    .premium-card { background: white; padding: 20px; border-radius: 15px; border: 1px solid #ffeef2; box-shadow: 0 4px 10px rgba(0,0,0,0.03); margin-top: 15px; margin-bottom: 15px; }
    [data-testid="stChatMessage"] { border-radius: 15px; padding: 15px; margin-bottom: 15px; border: 1px solid #ffeef2;}
    [data-testid="stChatMessage"]:nth-child(even) { background-color: #ff85a1; color: white; margin-left: 20%; }
    [data-testid="stChatMessage"]:nth-child(even) p { color: white !important; }
    [data-testid="stChatMessage"]:nth-child(odd) { background-color: white; color: #8a606d; margin-right: 20%; }
    .todo-row { display: flex; align-items: center; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #ffeef2;}
    </style>
    """, unsafe_allow_html=True,
)

# --- OTURUM YÖNETİMİ ---
if "logged_in_user_id" not in st.session_state:
    st.session_state.logged_in_user_id = None
if "username" not in st.session_state:
    st.session_state.username = None

# --- GİRİŞ / KAYIT EKRANI ---
if st.session_state.logged_in_user_id is None:
    st.markdown("<div style='text-align:center; padding-top:40px;'><h1 style='color:#ff85a1;'>PawCap AI'ye Hoş Geldin</h1><p>Kişisel asistanına erişmek için giriş yap.</p></div>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab_login, tab_register = st.tabs(["🔑 Giriş Yap", "📝 Kayıt Ol"])
        
        with tab_login:
            log_user = st.text_input("Kullanıcı Adı", key="log_u")
            log_pass = st.text_input("Şifre", type="password", key="log_p")
            if st.button("Giriş Yap", use_container_width=True):
                user_id = login_user(log_user, log_pass)
                if user_id:
                    st.session_state.logged_in_user_id = user_id
                    st.session_state.username = log_user
                    st.rerun()
                else:
                    st.error("Kullanıcı adı veya şifre hatalı!")

        with tab_register:
            reg_user = st.text_input("Yeni Kullanıcı Adı", key="reg_u")
            reg_pass = st.text_input("Yeni Şifre", type="password", key="reg_p")
            if st.button("Kayıt Ol", use_container_width=True):
                if reg_user and len(reg_pass) >= 4:
                    success, msg = register_user(reg_user, reg_pass)
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
                else:
                    st.warning("Lütfen bilgileri eksiksiz doldurun (Şifre min. 4 karakter).")
    st.stop() # Kullanıcı giriş yapmadıysa kodun geri kalanını çalıştırma

# ==========================================
# ANA UYGULAMA (Sadece Giriş Yapanlar İçin)
# ==========================================
user_id = st.session_state.logged_in_user_id

# Verileri Yükle
if "planner_loaded" not in st.session_state:
    # Modern To-Do Listesi formatı
    todo_json = get_setting(user_id, "todo_list")
    st.session_state.todos = json.loads(todo_json) if todo_json else [{"id": 1, "task": "DGS Denemesi Çöz", "done": False}]
    st.session_state.planner_loaded = True

defaults = {
    "current_session_id": None, "flashcards": None, "quiz_data": None,
    "selected_answers": {}, "quiz_submitted": False, "active_content_name": "Genel İçerik",
    "temp_text_input": "", "temp_file_path": None
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

def save_todos():
    save_setting(user_id, "todo_list", json.dumps(st.session_state.todos))

# --- SOL MENÜ (SIDEBAR) ---
with st.sidebar:
    st.markdown(f"<div style='text-align:center; padding:10px; background:#ffeef2; border-radius:12px; color:#ff85a1; font-weight:bold; font-size:18px;'>👤 Hoş geldin, {st.session_state.username}</div>", unsafe_allow_html=True)
    if st.button("🚪 Çıkış Yap"):
        st.session_state.clear()
        st.rerun()

    st.write("---")
    
    # YENİ TASARIM MODERN TO-DO LİSTESİ
    st.markdown("### ✅ Günlük Görevler")
    
    # Mevcut görevleri listele
    for i, todo in enumerate(st.session_state.todos):
        col1, col2, col3 = st.columns([1, 6, 1])
        # Checkbox değeri değiştiğinde anında kaydet
        is_done = col1.checkbox("", value=todo["done"], key=f"chk_{todo['id']}")
        if is_done != todo["done"]:
            st.session_state.todos[i]["done"] = is_done
            save_todos()
            st.rerun()
            
        task_text = f"~~{todo['task']}~~" if is_done else todo['task']
        col2.markdown(task_text)
        
        # Silme Butonu
        if col3.button("🗑️", key=f"del_{todo['id']}", help="Sil"):
            st.session_state.todos.pop(i)
            save_todos()
            st.rerun()
            
    # Yeni görev ekleme
    new_task = st.text_input("Yeni Görev", placeholder="Ne yapacaksın?", label_visibility="collapsed")
    if st.button("➕ Ekle", use_container_width=True) and new_task:
        new_id = max([t["id"] for t in st.session_state.todos] + [0]) + 1
        st.session_state.todos.append({"id": new_id, "task": new_task, "done": False})
        save_todos()
        st.rerun()

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
        scores = get_all_quiz_scores(user_id)
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
        st.session_state.current_session_id = create_new_chat_session(user_id)
        for key in ["flashcards", "quiz_data"]: st.session_state[key] = None
        st.session_state.selected_answers = {}
        st.session_state.quiz_submitted = False
        st.rerun()

    st.markdown("### 🗄️ Geçmiş Sohbetlerin")
    sessions = get_all_chat_sessions(user_id)
    for s in sessions:
        if st.button(f"📄 {s.title}", key=f"sess_{s.id}", use_container_width=True):
            st.session_state.current_session_id = s.id
            for key in ["flashcards", "quiz_data"]: st.session_state[key] = None
            st.session_state.selected_answers = {}
            st.session_state.quiz_submitted = False
            st.rerun()

# --- ANA EKRAN (SOHBET) ---
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

    messages = get_messages_for_session(st.session_state.current_session_id)
    for msg in messages:
        avatar_img = ASSISTANT_AVATAR if msg.role == "assistant" else "user"
        with st.chat_message(msg.role, avatar=avatar_img):
            st.markdown(msg.content)

    if prompt := st.chat_input("Bana bir görev ver veya sohbet et..."):
        save_chat_message(st.session_state.current_session_id, "user", prompt)
        update_chat_session_title(st.session_state.current_session_id, prompt)

        with st.chat_message("user", avatar="user"):
            st.write(prompt)

        safe_text = st.session_state.temp_text_input
        active_f = st.session_state.temp_file_path

        with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
            p_lower = prompt.lower()
            try:
                if "özet" in p_lower or "kısaca" in p_lower:
                    if not active_f and not safe_text:
                        st.write("⚠️ Özet çıkarmam için sol menüden bir dosya yüklemelisin!")
                    else:
                        with st.spinner("İçerik analiz edilip özetleniyor..."):
                            res = generate_summary(text_content=safe_text, file_path=active_f)
                            st.markdown(res)
                            save_chat_message(st.session_state.current_session_id, "assistant", res)
                            earn_badge(user_id, "Özet Ustası", "📝")
                            st.download_button("📥 Bu Özeti İndir", data=res, file_name="PawCap_Ozet.txt")
                            st.session_state.flashcards, st.session_state.quiz_data = None, None

                elif "quiz" in p_lower or "test" in p_lower or "soru" in p_lower:
                    if not active_f and not safe_text:
                        st.write("⚠️ Soru hazırlayabilmem için not eklemelisin!")
                    else:
                        with st.spinner("İnteraktif sorular hazırlanıyor..."):
                            st.session_state.quiz_data = generate_structured_quiz(text_content=safe_text, file_path=active_f)
                            st.session_state.selected_answers, st.session_state.quiz_submitted, st.session_state.flashcards = {}, False, None
                            st.write("🎯 Sınav hazırlandı! Hemen aşağıdan işaretleyebilirsin.")
                            save_chat_message(st.session_state.current_session_id, "assistant", "🎯 Sınav hazırlandı!")
                            earn_badge(user_id, "Sınav Avcısı", "🎯")

                elif "flashcard" in p_lower or "kart" in p_lower:
                    if not active_f and not safe_text:
                        st.write("⚠️ Kart hazırlayabilmem için içeriği eklemelisin!")
                    else:
                        with st.spinner("Ezber kartları derleniyor..."):
                            st.session_state.flashcards = generate_flashcards(text_content=safe_text, file_path=active_f)
                            st.session_state.quiz_data = None
                            st.write("🃏 Senin için önemli kavramlardan ezber kartları oluşturdum!")
                            save_chat_message(st.session_state.current_session_id, "assistant", "🃏 Kartlar hazır!")
                            earn_badge(user_id, "Hafıza Şampiyonu", "🧠")
                else:
                    with st.spinner("PawCap düşünüyor..."):
                        res = process_content(prompt_text=prompt, text_content=safe_text, file_path=active_f)
                        st.markdown(res)
                        save_chat_message(st.session_state.current_session_id, "assistant", res)
            except Exception as e:
                st.error(f"Hata: {str(e)}")
            finally:
                if active_f and os.path.exists(active_f):
                    os.remove(active_f)
                    st.session_state.temp_file_path = None

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
            if c1.button("🔙 Önceki"): st.session_state.card_idx = max(0, st.session_state.card_idx - 1); st.session_state.flipped = False; st.rerun()
            if c2.button("🔄 Çevir"): st.session_state.flipped = not st.session_state.flipped; st.rerun()
            if c3.button("Sonraki 🔜"): st.session_state.card_idx = min(len(cards) - 1, st.session_state.card_idx + 1); st.session_state.flipped = False; st.rerun()
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
                if st.button("✅ Quizi Bitir ve Puanla", key="btn_finish_main"): st.session_state.quiz_submitted = True; st.rerun()

            if st.session_state.quiz_submitted:
                st.write("---")
                dogru_sayisi, toplam_soru = 0, len(questions)
                for idx, q_data in enumerate(questions):
                    kullanici_cevabi = st.session_state.selected_answers.get(idx, "")
                    dogru_cevap = q_data["correct_answer"]
                    with st.expander(f"Soru {idx + 1} Analizi", expanded=True):
                        st.write(f"**Senin Cevabın:** `{kullanici_cevabi}`")
                        if kullanici_cevabi == dogru_cevap: st.success("✅ Doğru!"); dogru_sayisi += 1
                        else: st.error(f"❌ Yanlış. Doğru Cevap: `{dogru_cevap}`")
                        st.info(f"💡 **Açıklama:** {q_data['explanation']}")

                st.metric(label="Başarı Puanın", value=f"{dogru_sayisi} / {toplam_soru}", delta=f"%{int((dogru_sayisi/toplam_soru)*100) if toplam_soru > 0 else 0}")
                save_quiz_score(user_id, st.session_state.active_content_name, dogru_sayisi, toplam_soru)

                if st.button("Kapat"): st.session_state.quiz_data, st.session_state.selected_answers, st.session_state.quiz_submitted = None, {}, False; st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)