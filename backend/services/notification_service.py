import logging
from backend.models import Notification
from backend.database import db

logger = logging.getLogger(__name__)

class NotificationService:
    @classmethod
    def create_notification(cls, user_id, title, message, order_id=None):
        try:
            notification = Notification(
                user_id=user_id,
                title=title,
                message=message,
                order_id=order_id,
                is_read=False
            )
            db.session.add(notification)
            db.session.commit()
            return notification
        except Exception as e:
            db.session.rollback()
            logger.exception("Failed to create notification for user %s: %s", user_id, e)
            raise

    @classmethod
    def get_user_notifications(cls, user_id, unread_only=False):
        query = Notification.query.filter_by(user_id=user_id)
        if unread_only:
            query = query.filter_by(is_read=False)
        return [n.to_dict() for n in query.order_by(Notification.created_at.desc()).all()]

    @classmethod
    def mark_as_read(cls, notification_id, user_id):
        notification = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
        if notification:
            try:
                notification.is_read = True
                db.session.commit()
                return True
            except Exception as e:
                db.session.rollback()
                logger.exception("Failed to mark notification %s as read: %s", notification_id, e)
                raise
        return False
