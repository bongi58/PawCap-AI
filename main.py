import os
import json
import datetime
import pandas as pd
import streamlit as st
import extra_streamlit_components as stx
from ai_helper import generate_structured_quiz, generate_summary, generate_flashcards, process_content
from database import (
    init_db, save_quiz_score, create_new_chat_session,
    get_all_chat_sessions, get_messages_for_session, save_chat_message,
    earn_badge, get_my_badges, get_all_quiz_scores, update_chat_session_title,
    save_setting, get_setting, register_user, login_user
)

# Veritabanını başlat
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
    .stApp { background-color: #f8fafc; font-family: 'Segoe UI', sans-serif; }
    [data-testid="stSidebar"] { background-color: white; border-right: 2px solid #e2e8f0; }
    .stButton>button { background: linear-gradient(135deg, #4f46e5 0%, #0ea5e9 100%); color: white; border-radius: 12px; font-weight: bold; border: none; box-shadow: 0 4px 10px rgba(79,70,229,0.15); transition: all 0.3s; }
    .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 6px 15px rgba(79,70,229,0.3); }
    .premium-card { background: white; padding: 20px; border-radius: 15px; border: 1px solid #e2e8f0; box-shadow: 0 4px 10px rgba(0,0,0,0.02); margin-top: 15px; margin-bottom: 15px; }
    [data-testid="stChatMessage"] { border-radius: 15px; padding: 15px; margin-bottom: 15px; border: 1px solid #e2e8f0;}
    [data-testid="stChatMessage"]:nth-child(even) { background-color: #4f46e5; color: white; margin-left: 20%; }
    [data-testid="stChatMessage"]:nth-child(even) p { color: white !important; }
    [data-testid="stChatMessage"]:nth-child(odd) { background-color: white; color: #1e293b; margin-right: 20%; }
    .todo-row { display: flex; align-items: center; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #e2e8f0;}
    </style>
    """, unsafe_allow_html=True,
)

# --- ÇEREZ (COOKIE) YÖNETİCİSİ ---
cookie_manager = stx.CookieManager(key="pawcap_cookie_manager")

# --- OTURUM YÖNETİMİ ---
if "logged_in_user_id" not in st.session_state:
    st.session_state.logged_in_user_id = None
if "username" not in st.session_state:
    st.session_state.username = None

# Tarayıcıdan otomatik giriş kontrolü (Beni Hatırla)
cached_user_id = cookie_manager.get(cookie="pawcap_user_id")
cached_username = cookie_manager.get(cookie="pawcap_username")

if cached_user_id and cached_username and st.session_state.logged_in_user_id is None:
    st.session_state.logged_in_user_id = int(cached_user_id)
    st.session_state.username = cached_username

# --- GİRİŞ / KAYIT EKRANI ---
if st.session_state.logged_in_user_id is None:
    st.markdown("<div style='text-align:center; padding-top:40px;'><h1 style='color:#4f46e5;'>PawCap AI'ye Hoş Geldin</h1><p style='color:#64748b;'>Kişisel asistanına erişmek için giriş yap.</p></div>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab_login, tab_register = st.tabs(["🔑 Giriş Yap", "📝 Kayıt Ol"])
        
        with tab_login:
            log_user = st.text_input("Kullanıcı Adı", key="log_u")
            log_pass = st.text_input("Şifre", type="password", key="log_p")
            beni_hatirla = st.checkbox("Beni Hatırla", value=True)
            
            if st.button("Giriş Yap", use_container_width=True):
                user_id = login_user(log_user, log_pass)
                if user_id:
                    st.session_state.logged_in_user_id = user_id
                    st.session_state.username = log_user
                    
                    if beni_hatirla:
                        # 30 günlük süre tanımla
                        expire_date = datetime.datetime.now() + datetime.timedelta(days=30)
                        cookie_manager.set("pawcap_user_id", str(user_id), expires_at=expire_date)
                        cookie_manager.set("pawcap_username", log_user, expires_at=expire_date)
                        
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
    st.stop() 

# ==========================================
# ANA UYGULAMA (Sadece Giriş Yapanlar İçin)
# ==========================================
user_id = st.session_state.logged_in_user_id

# Verileri Yükle
if "planner_loaded" not in st.session_state:
    todo_json = get_setting(user_id, "todo_list")
    st.session_state.todos = json.loads(todo_json) if todo_json else [{"id": 1, "task": "Hedeflerini belirle!", "done": False}]
    st.session_state.planner_loaded = True

# --- SOHBET BAZLI AKTİF HAFIZA TANIMLAMALARI ---
defaults = {
    "current_session_id": None,
    "flashcards_by_session": {},    
    "quiz_by_session": {},          
    "selected_answers_by_session": {}, 
    "quiz_submitted_by_session": {},   
    "active_content_name": "Genel İçerik",
    "temp_text_input": "", "temp_file_path": None
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

def save_todos():
    save_setting(user_id, "todo_list", json.dumps(st.session_state.todos))

# --- SOL MENÜ (SIDEBAR) ---
with st.sidebar:
    st.markdown(f"<div style='text-align:center; padding:10px; background:#f0f4f8; border-radius:12px; color:#4f46e5; font-weight:bold; font-size:18px;'>👤 {st.session_state.username}</div>", unsafe_allow_html=True)
    
    if st.button("🚪 Çıkış Yap"):
        # Çıkış yapıldığında çerezleri de temizle
        cookie_manager.delete("pawcap_user_id")
        cookie_manager.delete("pawcap_username")
        st.session_state.clear()
        st.rerun()

    st.write("---")
    
    st.markdown("### ✅ Günlük Görevler")
    
    for i, todo in enumerate(st.session_state.todos):
        col1, col2, col3 = st.columns([1, 6, 1])
        is_done = col1.checkbox("", value=todo["done"], key=f"chk_{todo['id']}")
        if is_done != todo["done"]:
            st.session_state.todos[i]["done"] = is_done
            save_todos()
            st.rerun()
            
        task_text = f"~~{todo['task']}~~" if is_done else todo['task']
        col2.markdown(task_text)
        
        if col3.button("🗑️", key=f"del_{todo['id']}", help="Sil"):
            st.session_state.todos.pop(i)
            save_todos()
            st.rerun()
            
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
            st.line_chart(df, y="Başarı (%)", color="#4f46e5")
        else:
            st.caption("Henüz quiz çözmedin. Grafiğin burada belirecek!")

    st.write("---")
    if st.button("➕ Yeni Sohbet Başlat", use_container_width=True):
        st.session_state.current_session_id = create_new_chat_session(user_id)
        st.rerun()

    st.markdown("### 🗄️ Geçmiş Sohbetlerin")
    sessions = get_all_chat_sessions(user_id)
    for s in sessions:
        if st.button(f"📄 {s.title}", key=f"sess_{s.id}", use_container_width=True):
            st.session_state.current_session_id = s.id
            st.rerun()

# --- ANA EKRAN (SOHBET) ---
if not st.session_state.current_session_id:
    st.markdown(
        """<div style='text-align:center; padding-top:80px;'>
        <h1 style='color:#4f46e5; font-size:45px;'>PawCap AI Asistanı</h1>
        <p style='color:#64748b; font-size:18px;'>Sol menüden planını yap, materyalini ekle ve odaklanarak çalışmaya başla.</p>
        </div>""", unsafe_allow_html=True,
    )
else:
    sess_id = st.session_state.current_session_id
    active_session = next((s for s in sessions if s.id == sess_id), None)
    session_title = active_session.title if active_session else "Sohbet Odası"

    st.subheader(f"💬 {session_title}")

    messages = get_messages_for_session(sess_id)
    for msg in messages:
        avatar_img = ASSISTANT_AVATAR if msg.role == "assistant" else "user"
        with st.chat_message(msg.role, avatar=avatar_img):
            st.markdown(msg.content)

    if prompt := st.chat_input("Bana bir görev ver veya sohbet et..."):
        save_chat_message(sess_id, "user", prompt)
        update_chat_session_title(sess_id, prompt)

        with st.chat_message("user", avatar="user"):
            st.write(prompt)

        safe_text = st.session_state.temp_text_input
        active_f = st.session_state.temp_file_path

        with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
            p_lower = prompt.lower()
            try:
                if "özet" in p_lower or "kısaca" in p_lower:
                    if not active_f and not safe_text:
                        st.write("⚠️ Özet çıkarmam için sol menüden bir dosya yüklemeli veya metin yapıştırmalısın!")
                    else:
                        with st.spinner("İçerik analiz edilip özetleniyor..."):
                            res = generate_summary(text_content=safe_text, file_path=active_f)
                            st.markdown(res)
                            save_chat_message(sess_id, "assistant", res)
                            earn_badge(user_id, "Özet Ustası", "📝")
                            st.download_button("📥 Bu Özeti İndir", data=res, file_name="PawCap_Ozet.txt")
                            # ARTIK DİĞER ARAÇLARI SİLMİYORUZ

                elif "quiz" in p_lower or "test" in p_lower or "soru" in p_lower:
                    if not active_f and not safe_text:
                        st.write("⚠️ Soru hazırlayabilmem için not eklemelisin!")
                    else:
                        with st.spinner("İnteraktif sorular hazırlanıyor..."):
                            st.session_state.quiz_by_session[sess_id] = generate_structured_quiz(text_content=safe_text, file_path=active_f)
                            st.session_state.selected_answers_by_session[sess_id] = {}
                            st.session_state.quiz_submitted_by_session[sess_id] = False
                            # ARTIK DİĞER ARAÇLARI SİLMİYORUZ
                            st.write("🎯 Sınav hazırlandı! Hemen aşağıdan işaretleyebilirsin.")
                            save_chat_message(sess_id, "assistant", "🎯 Sınav hazırlandı!")
                            earn_badge(user_id, "Sınav Avcısı", "🎯")

                elif "flashcard" in p_lower or "kart" in p_lower:
                    if not active_f and not safe_text:
                        st.write("⚠️ Kart hazırlayabilmem için içeriği eklemelisin!")
                    else:
                        with st.spinner("Ezber kartları derleniyor..."):
                            st.session_state.flashcards_by_session[sess_id] = generate_flashcards(text_content=safe_text, file_path=active_f)
                            # ARTIK DİĞER ARAÇLARI SİLMİYORUZ
                            st.write("🃏 Senin için önemli kavramlardan ezber kartları oluşturdum!")
                            save_chat_message(sess_id, "assistant", "🃏 Kartlar hazır!")
                            earn_badge(user_id, "Hafıza Şampiyonu", "🧠")
                else:
                    with st.spinner("PawCap düşünüyor..."):
                        res = process_content(prompt_text=prompt, text_content=safe_text, file_path=active_f, chat_history=messages)
                        st.markdown(res)
                        save_chat_message(sess_id, "assistant", res)
            except Exception as e:
                st.error(f"Hata: {str(e)}")
            finally:
                if active_f and os.path.exists(active_f):
                    os.remove(active_f)
                    st.session_state.temp_file_path = None

    if st.session_state.flashcards_by_session.get(sess_id):
        with st.container(border=True):
            st.markdown("### 🃏 Flashcard Çalışma Modu")
            cards = st.session_state.flashcards_by_session[sess_id]["cards"]
            
            if f"card_idx_{sess_id}" not in st.session_state: st.session_state[f"card_idx_{sess_id}"] = 0
            if f"flipped_{sess_id}" not in st.session_state: st.session_state[f"flipped_{sess_id}"] = False

            curr = cards[st.session_state[f"card_idx_{sess_id}"]]
            
            if st.session_state[f"flipped_{sess_id}"]:
                st.success(f"**CEVAP:**\n\n{curr['back']}", icon="💡")
            else:
                st.info(f"**KAVRAM / SORU:**\n\n{curr['front']}", icon="❓")

            c1, c2, c3, c4 = st.columns(4) # Kapatma butonu için 4 kolona ayırdık
            if c1.button("🔙 Önceki", use_container_width=True, key=f"prev_{sess_id}"):
                st.session_state[f"card_idx_{sess_id}"] = max(0, st.session_state[f"card_idx_{sess_id}"] - 1)
                st.session_state[f"flipped_{sess_id}"] = False
                st.rerun()
            if c2.button("🔄 Çevir", use_container_width=True, key=f"flip_{sess_id}"):
                st.session_state[f"flipped_{sess_id}"] = not st.session_state[f"flipped_{sess_id}"]
                st.rerun()
            if c3.button("Sonraki 🔜", use_container_width=True, key=f"next_{sess_id}"):
                st.session_state[f"card_idx_{sess_id}"] = min(len(cards) - 1, st.session_state[f"card_idx_{sess_id}"] + 1)
                st.session_state[f"flipped_{sess_id}"] = False
                st.rerun()
            if c4.button("❌ Kapat", use_container_width=True, key=f"close_flash_{sess_id}"):
                st.session_state.flashcards_by_session[sess_id] = None
                st.rerun()

    if st.session_state.quiz_by_session.get(sess_id):
        with st.container(border=True):
            st.markdown("### 📝 Kendini Test Et")
            questions = st.session_state.quiz_by_session[sess_id].get("questions", [])

            if sess_id not in st.session_state.selected_answers_by_session:
                st.session_state.selected_answers_by_session[sess_id] = {}
            if sess_id not in st.session_state.quiz_submitted_by_session:
                st.session_state.quiz_submitted_by_session[sess_id] = False

            for idx, q_data in enumerate(questions):
                st.markdown(f"#### Soru {idx + 1}: {q_data['question_text']}")
                cevap = st.radio("Şıklar:", q_data["options"], key=f"q_{sess_id}_{idx}", index=None, disabled=st.session_state.quiz_submitted_by_session[sess_id])
                if cevap: st.session_state.selected_answers_by_session[sess_id][idx] = cevap
            
            if not st.session_state.quiz_submitted_by_session[sess_id]:
                st.write("")
                if st.button("✅ Quizi Bitir ve Puanla", key=f"btn_finish_{sess_id}"):
                    st.session_state.quiz_submitted_by_session[sess_id] = True
                    st.rerun()

            if st.session_state.quiz_submitted_by_session[sess_id]:
                st.write("---")
                dogru_sayisi, toplam_soru = 0, len(questions)

                for idx, q_data in enumerate(questions):
                    kullanici_cevabi = st.session_state.selected_answers_by_session[sess_id].get(idx, "")
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
                save_quiz_score(user_id, st.session_state.active_content_name, dogru_sayisi, toplam_soru)

                if st.button("Kapat", key=f"btn_close_{sess_id}"):
                    st.session_state.quiz_by_session[sess_id] = None
                    st.session_state.selected_answers_by_session[sess_id] = {}
                    st.session_state.quiz_submitted_by_session[sess_id] = False
                    st.rerun()