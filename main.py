import os
import streamlit as st
from ai_helper import generate_structured_quiz, generate_summary
from database import (
    init_db, save_quiz_score, create_new_chat_session,
    get_all_chat_sessions, get_messages_for_session, save_chat_message
)

# Veritabanını başlat
init_db()

TEMP_DIR = "temp_uploads"
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

# Sayfa Ayarları (Chat için daraltılmış layout daha iyi durur)
st.set_page_config(
    page_title="PawCap AI - Senin Ders Partnerin", page_icon="🐾", layout="wide"
)

# ==========================================
# 🎨 PAWCAP CHAT UI CSS TASARIMI (BANA BENZEYEN PEMBE VERSİYON)
# ==========================================
st.markdown(
    """
    <style>
    /* Global Temel */
    .stApp { background-color: #fff5f8; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    
    /* SIDEBAR (GEÇMİŞ SOHBETLER) */
    [data-testid="stSidebar"] { background-color: white; border-right: 1px solid #ffeef2; }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2 { color: #ff85a1; font-weight: 800; text-align: center;}
    
    /* Sidebar Logo */
    .sidebar-logo {
        text-align: center; color: #ff85a1; font-size: 28px; font-weight: 900;
        margin-bottom: 20px; text-shadow: 0 2px 4px rgba(0,0,0,0.03);
    }
    
    /* Sidebar Geçmiş Linkleri */
    .sidebar-history-link {
        color: #8a606d; text-decoration: none; padding: 8px 12px;
        display: block; border-radius: 8px; transition: background 0.2s;
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    .sidebar-history-link:hover { background-color: #ffeef2; color: #ff6b8b; }
    
    /* ANA CHAT ALANI */
    .chat-container { max-width: 800px; margin: 0 auto; padding-bottom: 100px; }
    
    /* Mesaj Balonları UX */
    [data-testid="stChatMessage"] { border-radius: 15px; padding: 15px; margin-bottom: 15px; border: 1px solid #ffeef2;}
    
    /* User (Sağda, Pembe) */
    [data-testid="stChatMessage"]:nth-child(even) {
        background-color: #ff85a1; color: white; margin-left: 20%;
        box-shadow: 0 4px 10px rgba(255,133,161,0.15);
    }
    [data-testid="stChatMessage"]:nth-child(even) h1, [data-testid="stChatMessage"]:nth-child(even) h2, [data-testid="stChatMessage"]:nth-child(even) h3 { color: white !important; }
    [data-testid="stChatMessage"]:nth-child(even) p { color: white !important; }
    
    /* Assistant (Solda, Beyaz) */
    [data-testid="stChatMessage"]:nth-child(odd) {
        background-color: white; color: #8a606d; margin-right: 20%;
        box-shadow: 0 4px 10px rgba(0,0,0,0.03);
    }

    /* PREMIUM BUTON VE KARTLAR */
    .stButton>button {
        background: linear-gradient(135deg, #ff85a1 0%, #ff6b8b 100%);
        color: white; border-radius: 15px; border: none !important;
        font-weight: 800; transition: all 0.3s;
    }
    .stButton>button:hover { box-shadow: 0 6px 15px rgba(255,107,139,0.3); transform: translateY(-2px); }
    
    .premium-card { background: white; padding: 20px; border-radius: 15px; border: 1px solid #ffeef2; box-shadow: 0 4px 10px rgba(0,0,0,0.03); }
    </style>
    """,
    unsafe_allow_html=True,
)


def save_uploaded_file(uploaded_file):
    file_path = os.path.join(TEMP_DIR, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path


def clean_temp_file(file_path):
    if file_path and os.path.exists(file_path):
        os.remove(file_path)


# ==========================================
# 🐾 SESSION STATE YÖNETİMİ (CHAT ODAKLI)
# ==========================================

# 1. Aktif Sohbet Oturumu
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None

# 2. Aktif Quiz Verisi (Özet/Quiz butonları için geçici hafıza)
if "temp_quiz_data" not in st.session_state:
    st.session_state.temp_quiz_data = None
if "temp_selected_answers" not in st.session_state:
    st.session_state.temp_selected_answers = {}
if "temp_quiz_submitted" not in st.session_state:
    st.session_state.temp_quiz_submitted = False

# ==========================================
# 📂 SIDEBAR (GEÇMİŞ SOHBETLER BÖLÜMÜ)
# ==========================================
with st.sidebar:
    st.markdown('<div class="sidebar-logo">🐾 PawCap AI</div>', unsafe_allow_html=True)
    st.write("---")
    
    # YENİ SOHBET BUTONU
    if st.button("➕ Yeni Sohbet Başlat", use_container_width=True):
        st.session_state.current_session_id = create_new_chat_session()
        st.session_state.temp_quiz_data = None # Eski quiz verilerini temizle
        st.rerun()

    st.write("---")
    st.markdown("### 🗄️ Geçmiş Sohbetlerin")
    
    # Veritabanından geçmiş sohbetleri çek ve listele
    sessions = get_all_chat_sessions()
    if not sessions:
        st.caption("Henüz sohbet kaydı yok.")
    else:
        for s in sessions:
            # Sohbet başlığına tıklayınca aktif oturumu değiştir
            if st.button(f"📄 {s.title}", key=f"sess_{s.id}", use_container_width=True):
                st.session_state.current_session_id = s.id
                st.session_state.temp_quiz_data = None # Eski quiz verilerini temizle
                st.rerun()

# ==========================================
# 💬 ANA CHAT PENCERESİ RENDER
# ==========================================

# Eğer aktif bir oturum yoksa, ana ekranı göster
if st.session_state.current_session_id is None:
    st.markdown(
        """
        <div style="text-align: center; padding: 100px 20px;">
            <h1 style="font-size: 60px; color: #ff85a1;">🐾 Merhaba! Ben PawCap</h1>
            <p style="font-size: 20px; color: #8a606d; max-width: 600px; margin: 20px auto;">
                Sana benziyorum, değil mi? Senin için ders videolarını, ses kayıtlarını ve uzun PDF'leri analiz edebilirim.
            </p>
            <p style="font-size: 18px; color: #ff6b8b;">
                Başlamak için sol taraftaki <b>"+ Yeni Sohbet Başlat"</b> butonuna tıkla.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    # Aktif sohbetin başlığını al
    active_session = next((s for s in sessions if s.id == st.session_state.current_session_id), None)
    st.title(f"🐾 PawCap Chat: {active_session.title}")
    st.write("---")
    
    # 📥 İÇERİK YÜKLME ARACI (Chat'in üstüne sabitlendi)
    with st.expander("📥 Neyin özetini/quizini istiyorsun? Buradan dosya ekle:", expanded=True):
        up_col1, up_col2 = st.columns([2, 1])
        
        active_file_path = None
        active_text = None
        
        with up_col1:
            uploaded_file = st.file_uploader(
                "PDF, Video, Ses veya Ders Notu ekle", 
                type=["pdf", "mp4", "mp3", "wav", "txt"]
            )
            if uploaded_file:
                active_file_path = save_uploaded_file(uploaded_file)
                st.session_state.active_content_name = uploaded_file.name
        
        with up_col2:
            text_note = st.text_area("Veya not yapıştır:", height=70)
            if text_note.strip():
                active_text = text_note
                st.session_state.active_content_name = text_note[:20] + "..."

    # 📜 GEÇMİŞ MESAJLARI VERİTABANINDAN ÇEK VE RENDER ET
    messages = get_messages_for_session(st.session_state.current_session_id)
    for msg in messages:
        with st.chat_message(msg.role, avatar="🐾" if msg.role == "assistant" else "🧑‍🎓"):
            st.markdown(msg.content)

    # 🎯 ÖZET/QUIZ SONUÇLARI (Butona basınca buraya çizilir)
    # Eğer geçmişte bir quiz çözüldüyse veya yeni bir quiz başlatıldıysa onu göster
    # (Not: Bu kısım, chat akışını bozmamak için expander veya chat bubble içinde olmalıdır.)

    # 🧑‍🎓 KULLANICI CHAT GİRDİSİ
    if prompt := st.chat_input("Ders içeriği hakkında ne yapmamı istersin? (Örn: Özetle, Quiz yap)"):
        
        # 1. Kullanıcının mesajını kaydet ve ekrana çiz
        save_chat_message(st.session_state.current_session_id, "user", prompt)
        with st.chat_message("user", avatar="🧑‍🎓"):
            st.markdown(prompt)
            
        # 2. PawCap'in analiz ve yanıt süreci
        with st.chat_message("assistant", avatar="🐾"):
            
            # --- SENARYO A: İçerik Yüklenmiş ve ANALİZ İSTENİYOR ---
            if active_file_path or active_text:
                with st.spinner("🐱 PawCap içeriği analiz edip yanıtlıyor..."):
                    
                    response_text = ""
                    
                    # Kullanıcı "Özet" istiyorsa
                    if "özet" in prompt.lower():
                        ozet = generate_summary(text_content=active_text, file_path=active_file_path)
                        response_text = f"### ✨ İşte Dersin Özeti!\n\n{ozet}"
                        clean_temp_file(active_file_path)
                    
                    # Kullanıcı "Quiz" istiyorsa
                    elif "quiz" in prompt.lower() or "test" in prompt.lower():
                        # Yeni bir quiz başlat
                        st.session_state.temp_selected_answers = {}
                        st.session_state.temp_quiz_submitted = False
                        quiz_json = generate_structured_quiz(text_content=active_text, file_path=active_file_path)
                        
                        # JSON'ı chat'e kaydetmek içinFormatted text'e çevir
                        # (Not: Chat geçmişinde interaktif quiz göstermek zordur, 
                        # bu yüzden geçmişe sadece 'Quiz oluşturuldu' yazıp widget'ı geçici hafızada tutuyoruz.)
                        st.session_state.temp_quiz_data = quiz_json
                        response_text = f"### 🎯 Quiz Hazır!\n\nSenin için {len(quiz_json.get('questions', []))} soruluk harika bir test hazırladım. **Hemen aşağıdan çözmeye başlayabilirsin!** 👇"
                        clean_temp_file(active_file_path)
                        
                    # Sadece içerik hakkında soru soruyorsa
                    else:
                        response_text = "🐱 İçeriği yükledin, harika! Ama ne yapmamı istediğini tam anlayamadım. Lütfen 'Bunu özetle' veya 'Bu içerikten quiz yap' gibi bir komut verir misin?"

                    # Yanıtı kaydet ve ekrana çiz
                    st.markdown(response_text)
                    save_chat_message(st.session_state.current_session_id, "assistant", response_text)

            # --- SENARYO B: İçerik Yüklenmemiş (Genel Sohbet) ---
            else:
                response_text = "🐱 Selam! Ders asistanın PawCap burada. Analiz etmem için yukarıdaki araçla bir video, PDF veya ders notu eklemelisin. Ondan sonra bana 'Özetle' veya 'Quiz yap' demen yeterli!"
                st.markdown(response_text)
                save_chat_message(st.session_state.current_session_id, "assistant", response_text)

    # 🎯 İNTERAKTİF QUİZ WIDGET (Chat akışının en altına, geçici olarak çizilir)
    if st.session_state.temp_quiz_data:
        st.write("---")
        with st.markdown('<div class="premium-card">', unsafe_allow_html=True):
            st.markdown("### 📝 Kendini Test Et")

            questions = st.session_state.temp_quiz_data.get("questions", [])

            for idx, q_data in enumerate(questions):
                st.markdown(f"#### Soru {idx + 1}: {q_data['question_text']}")
                cevap = st.radio(
                    "Şıklar:",
                    q_data["options"],
                    key=f"q_temp_{idx}",
                    index=None,
                    disabled=st.session_state.temp_quiz_submitted,
                )
                if cevap:
                    st.session_state.temp_selected_answers[idx] = cevap

            st.write("")

            # QUİZİ BİTİR BUTONU
            if not st.session_state.temp_quiz_submitted:
                if st.button("✅ Quizi Bitir ve Puanla", key="btn_finish_temp"):
                    st.session_state.temp_quiz_submitted = True
                    st.rerun()

            # SONUÇ ANALİZİ
            if st.session_state.temp_quiz_submitted:
                st.write("---")
                st.markdown("### 🏆 Sınav Sonucu ve Analiz")
                
                dogru_sayisi = 0
                toplam_soru = len(questions)
                
                for idx, q_data in enumerate(questions):
                    kullanici_cevabi = st.session_state.temp_selected_answers.get(idx, "")
                    dogru_cevap = q_data["correct_answer"]
                    
                    with st.expander(f"Soru {idx + 1} Analizi", expanded=True):
                        st.write(f"**Senin Cevabın:** `{kullanici_cevabi}`")
                        if kullanici_cevabi == dogru_cevap:
                            st.success(f"✅ Doğru!")
                            dogru_sayisi += 1
                        else:
                            st.error(f"❌ Yanlış. Doğru Cevap: `{dogru_cevap}`")
                        st.info(f"💡 **Açıklama:** {q_data['explanation']}")
                
                basari_yuzdesi = int((dogru_sayisi / toplam_soru) * 100)
                st.metric(label="Başarı Puanın", value=f"{dogru_sayisi} / {toplam_soru}", delta=f"%{basari_yuzdesi}")
                
                # Skoru ana veritabanına kaydet (Gelişim Dashboard'u için)
                save_quiz_score(st.session_state.active_content_name, dogru_sayisi, toplam_soru)
                st.caption("📌 *Bu sonuç gelişim takibin için veritabanına kaydedildi.*")

                # Quiz bitti, geçici hafızayı temizlemek için bir buton veya mesaj ekle
                if st.button("Sohbete Geri Dön (Quiz'i Kapat)", key="btn_close_quiz"):
                    st.session_state.temp_quiz_data = None
                    st.session_state.temp_selected_answers = {}
                    st.session_state.temp_quiz_submitted = False
                    st.rerun()

        st.markdown('</div>', unsafe_allow_html=True) # premium card sonu