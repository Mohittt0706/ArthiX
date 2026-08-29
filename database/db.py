from datetime import datetime, timezone
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean, Text,
    DateTime, ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session, relationship

Base = declarative_base()

engine = None
SessionLocal = None
_sessionScoped = None


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(150), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)

    settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    analyses = relationship("Analysis", back_populates="user", cascade="all, delete-orphan")
    watchlist_items = relationship("WatchlistItem", back_populates="user", cascade="all, delete-orphan")


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    telegram_chat_id = Column(String(100), nullable=True)
    confidence_threshold = Column(Integer, default=7)
    notifications_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="settings")


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    mode = Column(String(10), nullable=False, default="demo")
    verdict = Column(String(10), nullable=False)
    confidence = Column(Float, nullable=False)
    bull_score = Column(Float, nullable=False)
    bear_score = Column(Float, nullable=False)
    net_score = Column(Float, nullable=False)
    rationale = Column(Text, nullable=True)
    key_catalyst = Column(Text, nullable=True)
    evidence_bundle = Column(Text, nullable=True)
    agent_outputs = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="analyses")

    __table_args__ = (
        Index("idx_analyses_user_created", "user_id", "created_at"),
    )


class WatchlistItem(Base):
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String(20), nullable=False)
    name = Column(String(255), nullable=True)
    added_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="watchlist_items")

    __table_args__ = (
        UniqueConstraint("user_id", "symbol", name="uq_watchlist_user_symbol"),
    )


def get_engine():
    return engine


def get_session():
    if _sessionScoped:
        return _sessionScoped()
    return None


def init_db(database_url=None):
    global engine, SessionLocal, _sessionScoped

    from config import config
    url = database_url or config.DATABASE_URL

    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False,
    )

    SessionLocal = sessionmaker(bind=engine)
    _sessionScoped = scoped_session(SessionLocal)

    Base.metadata.create_all(bind=engine)


def close_session(session):
    if session:
        try:
            session.close()
        except Exception:
            pass


def reset_db():
    global engine, SessionLocal, _sessionScoped
    if _sessionScoped:
        _sessionScoped.remove()
    if engine:
        engine.dispose()
    engine = None
    SessionLocal = None
    _sessionScoped = None
