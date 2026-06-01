from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.sql import func
from contextlib import contextmanager

SQLALCHEMY_DATABASE_URL = "sqlite:///./pawcap.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    created_at = Column(DateTime, server_default=func.now())
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"))
    role = Column(String) 
    content = Column(Text)
    timestamp = Column(DateTime, server_default=func.now())
    session = relationship("ChatSession", back_populates="messages")

class UserBadge(Base):
    __tablename__ = "user_badges"
    id = Column(Integer, primary_key=True, index=True)
    badge_name = Column(String)
    badge_icon = Column(String)
    earned_at = Column(DateTime, server_default=func.now())

class QuizScore(Base):
    __tablename__ = "quiz_scores"
    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String)
    score = Column(Integer)
    total_questions = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())

def init_db():
    Base.metadata.create_all(bind=engine)

@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_new_chat_session(title="Yeni Sohbet"):
    with get_db() as db:
        new_session = ChatSession(title=title[:50])
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        return new_session.id

def get_all_chat_sessions():
    with get_db() as db:
        return db.query(ChatSession).order_by(ChatSession.created_at.desc()).all()

def get_messages_for_session(session_id):
    with get_db() as db:
        return db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.timestamp.asc()).all()

def save_chat_message(session_id, role, content):
    with get_db() as db:
        new_message = ChatMessage(session_id=session_id, role=role, content=content)
        db.add(new_message)
        db.commit()

def earn_badge(name, icon):
    with get_db() as db:
        exists = db.query(UserBadge).filter(UserBadge.badge_name == name).first()
        if not exists:
            new_badge = UserBadge(badge_name=name, badge_icon=icon)
            db.add(new_badge)
            db.commit()
            return True
    return False

def get_my_badges():
    with get_db() as db:
        return db.query(UserBadge).all()

def save_quiz_score(topic, score, total_questions):
    with get_db() as db:
        new_score = QuizScore(topic=topic[:50], score=score, total_questions=total_questions)
        db.add(new_score)
        db.commit()

def get_all_quiz_scores():
    with get_db() as db:
        return db.query(QuizScore).order_by(QuizScore.created_at.asc()).all()
   
def update_chat_session_title(session_id, new_title):
    with get_db() as db:
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        # Sadece başlık "Yeni Sohbet" ise güncelle (yani ilk mesajda)
        if session and session.title == "Yeni Sohbet":
            # Başlık çok uzun olmasın diye ilk 30 karakterini alıp sonuna ... koyuyoruz
            session.title = (new_title[:30] + "...") if len(new_title) > 30 else new_title
            db.commit()