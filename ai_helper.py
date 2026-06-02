import json
import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
import streamlit as st

if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
else:
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("⚠️ GEMINI_API_KEY bulunamadı! Lütfen ayarlarınızı kontrol edin.")

client = genai.Client(api_key=api_key)
MODEL_NAME = "gemini-2.5-flash"

class QuestionSchema(BaseModel):
    question_text: str = Field(description="Sorunun TÜRKÇE kök metni")
    options: list[str] = Field(description="4 adet şıkkın TÜRKÇE listesi")
    correct_answer: str = Field(description="Doğru olan şık (TÜRKÇE)")
    explanation: str = Field(description="TÜRKÇE Açıklama")

class QuizSchema(BaseModel):
    questions: list[QuestionSchema]

class Flashcard(BaseModel):
    front: str = Field(description="Kartın ön yüzü - TÜRKÇE (Kavram/Soru)")
    back: str = Field(description="Kartın arka yüzü - TÜRKÇE (Cevap/Açıklama)")

class FlashcardSchema(BaseModel):
    cards: list[Flashcard]

def process_content(prompt_text, text_content=None, file_path=None, config=None):
    contents = []
    uploaded_file = None

    if file_path and os.path.exists(file_path):
        uploaded_file = client.files.upload(file=file_path)
        while uploaded_file.state.name == "PROCESSING":
            time.sleep(2)
            uploaded_file = client.files.get(name=uploaded_file.name)
            
        if uploaded_file.state.name == "FAILED":
            raise ValueError("⚠️ Dosya işlenirken hata oluştu.")
        contents.append(uploaded_file)

    if text_content:
        contents.append(f"Ders İçeriği:\n{text_content}")

    contents.append(prompt_text)

    if not config:
        config = types.GenerateContentConfig(
            system_instruction="Sen zeki ve motive edici bir yapay zeka ders asistanı olan PawCap'sin. Kullanıcının gönderdiği metin hangi dilde olursa olsun, KESİNLİKLE ve SADECE TÜRKÇE yanıt vermelisin.",
            temperature=0.7 
        )

    # --- YENİ: Akıllı Yeniden Deneme (Retry) Mantığı ---
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=contents,
                config=config,
            )
            
            if uploaded_file:
                client.files.delete(name=uploaded_file.name)
                
            return response.text if response.text else ""
            
        except Exception as e:
            error_msg = str(e).lower()
            # Eğer hata sunucu yoğunluğu (503) ise ve henüz 3 deneme hakkımız bitmediyse:
            if "503" in error_msg or "unavailable" in error_msg or "429" in error_msg or "exhausted" in error_msg:
                if attempt < max_retries - 1:
                    time.sleep(3) # 3 saniye bekle ve çaktırmadan tekrar dene
                    continue
            
            # Eğer başka bir hataysa veya 3 deneme de başarısız olduysa dosyayı sil ve hatayı göster
            if uploaded_file:
                try:
                    client.files.delete(name=uploaded_file.name)
                except:
                    pass
            raise e

def generate_summary(text_content=None, file_path=None):
    prompt = "Eklenen ders içeriğini öğrenci dostu ve akılda kalıcı bir şekilde özetle. LÜTFEN ÖZETİ KESİNLİKLE TÜRKÇE (TURKISH) OLARAK YAZ. Kaynak metin İngilizce olsa bile çevirip Türkçe özetle."
    try:
        res = process_content(prompt, text_content, file_path)
        return res if res.strip() else "⚠️ İçerik güvenlik filtrelerine takılmış veya okunamamış olabilir. Lütfen içeriği küçültüp tekrar deneyin."
    except Exception as e:
        if "503" in str(e):
            return "⚠️ Şu an Google sunucuları aşırı yoğun. Lütfen 1-2 dakika sonra tekrar dene."
        raise e

def generate_structured_quiz(text_content=None, file_path=None):
    prompt = "Eklenen ders içeriğini analiz et ve öğrenciyi test etmek için 3 soruluk quiz hazırla. Tüm içerik KESİNLİKLE TÜRKÇE olmalıdır."
    quiz_config = types.GenerateContentConfig(
        system_instruction="Sen PawCap'sin. Görevin, verilen metinden dışarı çıkmadan, tamamen bilgiye dayalı zorlayıcı akademik sorular hazırlamaktır. YANITLARIN TAMAMI TÜRKÇE OLMALIDIR.",
        temperature=0.2, 
        response_mime_type="application/json",
        response_schema=QuizSchema,
    )
    try:
        raw_json = process_content(prompt, text_content, file_path, config=quiz_config)
        return json.loads(raw_json) if raw_json else None
    except Exception as e:
        if "503" in str(e) or "UNAVAILABLE" in str(e):
            st.error("⚠️ Şu an Google sunucuları aşırı yoğun. Quiz hazırlanamadı, lütfen birazdan tekrar dene.")
        return None

def generate_flashcards(text_content=None, file_path=None):
    prompt = "Eklenen ders içeriğini analiz et ve konuyu hızlıca tekrar edip ezberleyebilmesi için en önemli 5 kavram/soru üzerinden önlü arkalı çalışma kartları hazırla. KARTLARIN ÖN VE ARKA YÜZLERİ KESİNLİKLE TÜRKÇE OLMALIDIR."
    flashcard_config = types.GenerateContentConfig(
        system_instruction="Sen PawCap'sin. Sadece verilen metindeki en kritik kavramları seç ve kısa, net ezber kartları oluştur. YANITLARIN TAMAMI TÜRKÇE OLMALIDIR.",
        temperature=0.2, 
        response_mime_type="application/json",
        response_schema=FlashcardSchema,
    )
    try:
        raw_json = process_content(prompt, text_content, file_path, config=flashcard_config)
        return json.loads(raw_json) if raw_json else None
    except Exception as e:
        if "503" in str(e) or "UNAVAILABLE" in str(e):
            st.error("⚠️ Şu an Google sunucuları aşırı yoğun. Kartlar hazırlanamadı, lütfen birazdan tekrar dene.")
        return None