from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./pawcap.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# Yüklenen içeriklerin kaydı
class VideoRecord(Base):
    __tablename__ = "video_records"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    file_path = Column(String)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


# BİTİRME PROJESİ EKLEMESİ: Öğrenci Quiz Skorları Tablosu
class QuizScore(Base):
    __tablename__ = "quiz_scores"

    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String)  # Quiz Konusu/İçeriği
    score = Column(Integer)  # Doğru Sayısı
    total_questions = Column(Integer)  # Toplam Soru Sayısı
    created_at = Column(DateTime, default=datetime.now)


def init_db():
    Base.metadata.create_all(bind=engine)


def save_quiz_score(topic, score, total_questions):
    """Çözülen quizin sonucunu veritabanına kaydeder."""
    db = SessionLocal()
    try:
        new_score = QuizScore(
            topic=topic[:50],  # İlk 50 karakteri başlık olarak al
            score=score,
            total_questions=total_questions,
        )
        db.add(new_score)
        db.commit()
    finally:
        db.close()