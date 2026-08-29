from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_session, User, UserSettings, close_session


def create_user(username, email, password):
    session = get_session()
    try:
        password_hash = generate_password_hash(password)
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
        )
        session.add(user)
        session.flush()

        settings = UserSettings(user_id=user.id)
        session.add(settings)
        session.commit()
        return user.id
    except Exception:
        session.rollback()
        return None
    finally:
        close_session(session)


def authenticate_user(username, password):
    session = get_session()
    try:
        user = session.query(User).filter(
            User.username == username,
            User.is_active == True,
        ).first()
        if user and check_password_hash(user.password_hash, password):
            return {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "created_at": user.created_at,
                "is_active": user.is_active,
            }
        return None
    finally:
        close_session(session)


def get_user_by_id(user_id):
    session = get_session()
    try:
        user = session.query(User).filter(
            User.id == user_id,
            User.is_active == True,
        ).first()
        if user:
            return {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "created_at": user.created_at,
                "is_active": user.is_active,
            }
        return None
    finally:
        close_session(session)


def get_user_settings(user_id):
    session = get_session()
    try:
        settings = session.query(UserSettings).filter(
            UserSettings.user_id == user_id,
        ).first()
        if settings:
            return {
                "id": settings.id,
                "user_id": settings.user_id,
                "telegram_chat_id": settings.telegram_chat_id,
                "confidence_threshold": settings.confidence_threshold,
                "notifications_enabled": settings.notifications_enabled,
                "created_at": settings.created_at,
                "updated_at": settings.updated_at,
            }
        return None
    finally:
        close_session(session)


def update_user_settings(user_id, telegram_chat_id=None, confidence_threshold=None, notifications_enabled=None):
    session = get_session()
    try:
        settings = session.query(UserSettings).filter(
            UserSettings.user_id == user_id,
        ).first()
        if not settings:
            return False

        if telegram_chat_id is not None:
            settings.telegram_chat_id = telegram_chat_id
        if confidence_threshold is not None:
            settings.confidence_threshold = confidence_threshold
        if notifications_enabled is not None:
            settings.notifications_enabled = notifications_enabled

        from datetime import datetime, timezone
        settings.updated_at = datetime.now(timezone.utc)
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False
    finally:
        close_session(session)
