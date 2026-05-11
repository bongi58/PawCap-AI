import json
import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# API anahtarını yükle
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError(
        "⚠️ GEMINI_API_KEY bulunamadı! Lütfen .env dosyanızı kontrol edin."
    )

# --- BİTİRME PROJESİ: YENİ NESİL CLIENT BAĞLANTISI ---
client = genai.Client(api_key=api_key)

# Terminal çıktından en kararlı, hızlı ve güçlü olan yeni modeli seçtik
MODEL_NAME = "gemini-2.5-flash"


# --- PYDANTIC JSON ŞEMALARI (Halüsinasyon Engelleyici) ---
class QuestionSchema(BaseModel):
    question_text: str = Field(description="Sorunun kök metni")
    options: list[str] = Field(
        description="A, B, C, D şeklinde 4 adet şıkkın tam listesi"
    )
    correct_answer: str = Field(description="Doğru olan şıkkın tam metni")
    explanation: str = Field(
        description="Bu cevabın neden doğru olduğunun detaylı ve öğretici açıklaması"
    )


class QuizSchema(BaseModel):
    questions: list[QuestionSchema] = Field(
        description="Hazırlanan soruların listesi"
    )


def process_content(prompt_text, text_content=None, file_path=None, config=None):
    """Yeni nesil google.genai kütüphanesi ile içerik işleme."""
    contents = []
    uploaded_file = None

    # 1. Video veya Ses dosyası varsa yeni File API ile yükle
    if file_path and os.path.exists(file_path):
        uploaded_file = client.files.upload(file=file_path)

        # Google sunucularında video/ses analizinin bitmesini bekle
        while uploaded_file.state.name == "PROCESSING":
            time.sleep(2)
            uploaded_file = client.files.get(name=uploaded_file.name)

        contents.append(uploaded_file)

    # 2. Metin notu varsa içeriğe ekle
    if text_content:
        contents.append(f"Ders İçeriği:\n{text_content}")

    # 3. Asıl komutu (prompt) ekle
    contents.append(prompt_text)

    # Yeni SDK ile yapay zekayı tetikle
    response = client.models.generate_content(
        model=MODEL_NAME, contents=contents, config=config
    )

    # Analiz bittikten sonra sunucudaki geçici dosyayı güvenle sil
    if uploaded_file:
        client.files.delete(name=uploaded_file.name)

    return response.text


def generate_summary(text_content=None, file_path=None):
    """Ders içeriğinden markdown formatında akıllı özet çıkarır."""
    prompt = """
    Sen zeki bir yapay zeka ders asistanı olan PawCap'sin.
    Eklenen ders içeriğini öğrenci dostu ve akılda kalıcı bir şekilde özetle.
    Önemli yerleri madde işaretleri ve emojilerle vurgula.
    """
    return process_content(prompt, text_content, file_path)


def generate_structured_quiz(text_content=None, file_path=None):
    """Ders içeriğine göre JSON formatında 3 soruluk interaktif quiz üretir."""
    prompt = """
    Sen PawCap'sin. Eklenen ders içeriğini analiz et ve öğrenciyi test etmek için 3 soruluk harika bir quiz hazırla.
    Tüm sorular doğrudan sağlanan içeriğe dayanmalıdır.
    """

    # Yeni nesil SDK'da Pydantic şemasını JSON olarak zorlayan konfigürasyon
    quiz_config = types.GenerateContentConfig(
        response_mime_type="application/json", response_schema=QuizSchema
    )

    raw_json = process_content(
        prompt, text_content, file_path, config=quiz_config
    )

    # Gelen string formatındaki JSON'ı Python sözlüğüne dönüştür
    return json.loads(raw_json)