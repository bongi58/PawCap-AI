from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

SQLALCHEMY_DATABASE_URL = "sqlite:///./pawcap.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# --- BİTİRME PROJESİ: SOHBET HAFIZA MODELLERİ ---

class ChatSession(Base):
    """Sohbet oturumlarını tutar (Örn: 'Matematik Dersi Özetleme')"""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)  # Sohbetin başlığı
    created_at = Column(DateTime, default=datetime.now)
    
    # Mesajlarla ilişki
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    """Bir oturumdaki tekil mesajları tutar"""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"))
    role = Column(String)  # 'user' veya 'assistant'
    content = Column(Text)  # Mesajın metni (veya formatted JSON string)
    timestamp = Column(DateTime, default=datetime.now)
    
    session = relationship("ChatSession", back_populates="messages")


class QuizScore(Base):
    """Öğrenci Quiz Skorları (Değişmedi)"""
    __tablename__ = "quiz_scores"

    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String)
    score = Column(Integer)
    total_questions = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)


def init_db():
    """Veritabanını ve tabloları oluşturur."""
    Base.metadata.create_all(bind=engine)


# --- SOHBET YÖNETİM FONKSİYONLARI ---

def create_new_chat_session(title="Yeni Sohbet"):
    db = SessionLocal()
    try:
        new_session = ChatSession(title=title[:50])
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        return new_session.id
    finally:
        db.close()

def get_all_chat_sessions():
    db = SessionLocal()
    try:
        return db.query(ChatSession).order_by(ChatSession.created_at.desc()).all()
    finally:
        db.close()

def get_messages_for_session(session_id):
    db = SessionLocal()
    try:
        return db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.timestamp.asc()).all()
    finally:
        db.close()

def save_chat_message(session_id, role, content):
    db = SessionLocal()
    try:
        new_message = ChatMessage(session_id=session_id, role=role, content=content)
        db.add(new_message)
        db.commit()
    finally:
        db.close()

# --- SKOR YÖNETİM FONKSİYONLARI ---
def save_quiz_score(topic, score, total_questions):
    db = SessionLocal()
    try:
        new_score = QuizScore(
            topic=topic[:50],
            score=score,
            total_questions=total_questions,
        )
        db.add(new_score)
        db.commit()
    finally:
        db.close()