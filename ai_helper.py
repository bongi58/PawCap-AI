import json
import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
import streamlit as st

# --- AKILLI ŞİFRE YÜKLEME ---
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
else:
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError(
        "⚠️ GEMINI_API_KEY bulunamadı! Lütfen Streamlit Secrets veya .env ayarlarınızı kontrol edin."
    )

client = genai.Client(api_key=api_key)
MODEL_NAME = "gemini-2.5-flash"


# --- PYDANTIC ŞEMALARI ---
class QuestionSchema(BaseModel):
    question_text: str = Field(description="Sorunun kök metni")
    options: list[str] = Field(description="4 adet şıkkın listesi")
    correct_answer: str = Field(description="Doğru olan şık")
    explanation: str = Field(description="Açıklama")


class QuizSchema(BaseModel):
    questions: list[QuestionSchema]


class Flashcard(BaseModel):
    front: str = Field(description="Kartın ön yüzü (Kavram/Soru)")
    back: str = Field(description="Kartın arka yüzü (Cevap/Açıklama)")


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
        contents.append(uploaded_file)

    if text_content:
        contents.append(f"Ders İçeriği:\n{text_content}")

    contents.append(prompt_text)

    response = client.models.generate_content(
        model=MODEL_NAME, contents=contents, config=config
    )

    if uploaded_file:
        client.files.delete(name=uploaded_file.name)

    return response.text


def generate_summary(text_content=None, file_path=None):
    prompt = """
    Sen zeki bir yapay zeka ders asistanı olan PawCap'sin.
    Eklenen ders içeriğini öğrenci dostu ve akılda kalıcı bir şekilde özetle.
    Önemli yerleri madde işaretleri ve emojilerle vurgula.
    """
    return process_content(prompt, text_content, file_path)


def generate_structured_quiz(text_content=None, file_path=None):
    prompt = """
    Sen PawCap'sin. Eklenen ders içeriğini analiz et ve öğrenciyi test etmek için 3 soruluk harika bir quiz hazırla.
    Tüm sorular doğrudan sağlanan içeriğe dayanmalıdır.
    """
    quiz_config = types.GenerateContentConfig(
        response_mime_type="application/json", response_schema=QuizSchema
    )
    raw_json = process_content(
        prompt, text_content, file_path, config=quiz_config
    )
    return json.loads(raw_json)


def generate_flashcards(text_content=None, file_path=None):
    prompt = """
    Sen PawCap'sin. Eklenen ders içeriğini analiz et ve öğrencinin konuyu hızlıca tekrar edip ezberleyebilmesi için en önemli 5 kavram/soru üzerinden önlü arkalı çalışma kartları (flashcards) hazırla.
    """
    flashcard_config = types.GenerateContentConfig(
        response_mime_type="application/json", response_schema=FlashcardSchema
    )
    raw_json = process_content(
        prompt, text_content, file_path, config=flashcard_config
    )
    return json.loads(raw_json)