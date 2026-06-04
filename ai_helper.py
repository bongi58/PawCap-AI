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

def clean_json(raw_str):
    if not raw_str: return ""
    raw_str = raw_str.strip()
    if raw_str.startswith("```json"):
        raw_str = raw_str[7:]
    elif raw_str.startswith("```"):
        raw_str = raw_str[3:]
    if raw_str.endswith("```"):
        raw_str = raw_str[:-3]
    return raw_str.strip()

def process_content(prompt_text, text_content=None, file_path=None, config=None, chat_history=None):
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

    context_str = ""
    if chat_history and len(chat_history) > 0:
        context_str += "--- ÖNCEKİ SOHBET GEÇMİŞİ ---\n"
        for msg in chat_history[-6:]: 
            role = "Sen (PawCap)" if msg.role == "assistant" else "Öğrenci"
            safe_content = str(msg.content) if msg.content else ""
            context_str += f"{role}: {safe_content}\n"
        context_str += "-------------------------------\n\n"

    if text_content:
        context_str += f"--- İNCELENECEK DERS MATERYALİ ---\n{text_content}\n----------------------------------\n\n"

    final_prompt = f"{context_str}Öğrencinin Yeni Sorusu/Talebi: {prompt_text}"
    contents.append(final_prompt)

    if not config:
        config = types.GenerateContentConfig(
            system_instruction=(
                "Sen PawCap'sin, zeki ve motive edici bir yapay zeka ders asistanısın. "
                "Öğrenciyle sohbette konuyu detaylandır, farklı/ilginç örnekler ver. "
                "Öğrenci eğer senden quiz, test, soru, flashcard veya ezber kartı hazırlamanı isterse, "
                "BUNLARI KESİNLİKLE METİN OLARAK UZUN UZUN YAZMA. Bunun yerine ona sadece şu mesajı ver: "
                "'Sana özel interaktif arayüzü açabilmem için lütfen mesajında **quiz**, **test** veya **kart** kelimelerinden birini kullan.' "
                "KESİNLİKLE VE SADECE TÜRKÇE CEVAP VER."
            ),
            temperature=0.7 
        )

    max_retries = 5
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
            if attempt < max_retries - 1:
                time.sleep(4) 
                continue
            
            if uploaded_file:
                try: 
                    client.files.delete(name=uploaded_file.name)
                except: 
                    pass
            raise e

def generate_summary(text_content=None, file_path=None, chat_history=None):
    prompt = "Eklenen ders içeriğini veya sohbet geçmişini öğrenci dostu ve akılda kalıcı bir şekilde özetle. LÜTFEN ÖZETİ KESİNLİKLE TÜRKÇE (TURKISH) OLARAK YAZ."
    try:
        res = process_content(prompt, text_content, file_path, chat_history=chat_history)
        return res if res.strip() else "⚠️ İçerik okunamadı. Lütfen içeriği küçültüp tekrar deneyin."
    except Exception as e:
        return "⚠️ Google sunucuları aşırı yoğun. Lütfen 1 dakika sonra tekrar dene."

def generate_structured_quiz(text_content=None, file_path=None, chat_history=None):
    prompt = "Eklenen ders içeriğini veya sohbet geçmişini analiz et ve öğrenciyi test etmek için 5 soruluk quiz hazırla. Tüm içerik KESİNLİKLE TÜRKÇE olmalıdır."
    quiz_config = types.GenerateContentConfig(
        system_instruction="Sen PawCap'sin. Görevin, verilen metinden veya geçmiş sohbetten bilgiye dayalı zorlayıcı akademik sorular hazırlamaktır. YANITLARIN TAMAMI TÜRKÇE OLMALIDIR.",
        temperature=0.2, 
        response_mime_type="application/json",
        response_schema=QuizSchema,
    )
    try:
        raw_json = process_content(prompt, text_content, file_path, config=quiz_config, chat_history=chat_history)
        cleaned = clean_json(raw_json)
        return json.loads(cleaned) if cleaned else None
    except Exception as e:
        st.error("⚠️ Sunucular yoğun veya içerik okunamadı.")
        return None

def generate_flashcards(text_content=None, file_path=None, chat_history=None):
    prompt = "Eklenen ders içeriğini veya sohbet geçmişini analiz et ve konuyu hızlıca tekrar edip ezberleyebilmesi için en önemli 5 kavram/soru üzerinden önlü arkalı çalışma kartları hazırla. KARTLARIN ÖN VE ARKA YÜZLERİ KESİNLİKLE TÜRKÇE OLMALIDIR."
    flashcard_config = types.GenerateContentConfig(
        system_instruction="Sen PawCap'sin. Verilen metinden veya sohbet geçmişinden en kritik kavramları seç ve kısa, net ezber kartları oluştur. YANITLARIN TAMAMI TÜRKÇE OLMALIDIR.",
        temperature=0.2, 
        response_mime_type="application/json",
        response_schema=FlashcardSchema,
    )
    try:
        raw_json = process_content(prompt, text_content, file_path, config=flashcard_config, chat_history=chat_history)
        cleaned = clean_json(raw_json)
        return json.loads(cleaned) if cleaned else None
    except Exception as e:
        st.error("⚠️ Sunucular yoğun veya içerik okunamadı.")
        return None