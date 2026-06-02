from datetime import datetime
import hashlib
from sqlalchemy import Column, DateTime, Integer, String, Text, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.sql import func
from contextlib import contextmanager

SQLALCHEMY_DATABASE_URL = "sqlite:///./pawcap.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- ŞİFRELEME FONKSİYONU ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# --- MODELLER ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
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
    user_id = Column(Integer, ForeignKey("users.id"))
    badge_name = Column(String)
    badge_icon = Column(String)
    earned_at = Column(DateTime, server_default=func.now())

class QuizScore(Base):
    __tablename__ = "quiz_scores"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    topic = Column(String)
    score = Column(Integer)
    total_questions = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())

class UserSetting(Base):
    __tablename__ = "user_settings"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    setting_key = Column(String, index=True)
    setting_value = Column(Text)

def init_db():
    Base.metadata.create_all(bind=engine)

@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- KULLANICI FONKSİYONLARI ---
def register_user(username, password):
    with get_db() as db:
        if db.query(User).filter(User.username == username).first():
            return False, "Bu kullanıcı adı zaten alınmış."
        new_user = User(username=username, password_hash=hash_password(password))
        db.add(new_user)
        db.commit()
        return True, "Kayıt başarılı! Giriş yapabilirsiniz."

def login_user(username, password):
    with get_db() as db:
        user = db.query(User).filter(User.username == username).first()
        if user and user.password_hash == hash_password(password):
            return user.id
        return None

# --- DİĞER VERİTABANI FONKSİYONLARI (Kişiselleştirilmiş) ---
def save_setting(user_id, key, value):
    with get_db() as db:
        setting = db.query(UserSetting).filter(UserSetting.user_id == user_id, UserSetting.setting_key == key).first()
        if setting:
            setting.setting_value = value
        else:
            new_setting = UserSetting(user_id=user_id, setting_key=key, setting_value=value)
            db.add(new_setting)
        db.commit()

def get_setting(user_id, key):
    with get_db() as db:
        setting = db.query(UserSetting).filter(UserSetting.user_id == user_id, UserSetting.setting_key == key).first()
        return setting.setting_value if setting else None

def create_new_chat_session(user_id, title="Yeni Sohbet"):
    with get_db() as db:
        new_session = ChatSession(user_id=user_id, title=title[:50])
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        return new_session.id

def get_all_chat_sessions(user_id):
    with get_db() as db:
        return db.query(ChatSession).filter(ChatSession.user_id == user_id).order_by(ChatSession.created_at.desc()).all()

def get_messages_for_session(session_id):
    with get_db() as db:
        return db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.timestamp.asc()).all()

def save_chat_message(session_id, role, content):
    with get_db() as db:
        new_message = ChatMessage(session_id=session_id, role=role, content=content)
        db.add(new_message)
        db.commit()

def earn_badge(user_id, name, icon):
    with get_db() as db:
        exists = db.query(UserBadge).filter(UserBadge.user_id == user_id, UserBadge.badge_name == name).first()
        if not exists:
            new_badge = UserBadge(user_id=user_id, badge_name=name, badge_icon=icon)
            db.add(new_badge)
            db.commit()
            return True
    return False

def get_my_badges(user_id):
    with get_db() as db:
        return db.query(UserBadge).filter(UserBadge.user_id == user_id).all()

def save_quiz_score(user_id, topic, score, total_questions):
    with get_db() as db:
        new_score = QuizScore(user_id=user_id, topic=topic[:50], score=score, total_questions=total_questions)
        db.add(new_score)
        db.commit()

def update_chat_session_title(session_id, new_title):
    with get_db() as db:
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if session and session.title == "Yeni Sohbet":
            session.title = (new_title[:30] + "...") if len(new_title) > 30 else new_title
            db.commit()

def get_all_quiz_scores(user_id):
    with get_db() as db:
        return db.query(QuizScore).filter(QuizScore.user_id == user_id).order_by(QuizScore.created_at.asc()).all()