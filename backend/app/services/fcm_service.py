"""
Firebase Cloud Messaging (FCM) service for sending push notifications.
Uses Firebase Admin SDK to send notifications to user devices.
"""
import logging
from typing import Optional
from firebase_admin import messaging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.auth.firebase import get_firebase_app

logger = logging.getLogger(__name__)


class FCMService:
    """Service for sending FCM push notifications."""
    
    @staticmethod
    async def send_session_ready_notification(
        db: AsyncSession,
        user_id: str,
        session_id: str,
        session_title: Optional[str] = None
    ) -> bool:
        """
        Send FCM notification when a session analysis is ready.
        
        Args:
            db: Database session
            user_id: User ID to send notification to
            session_id: Session ID that was processed
            session_title: Optional session title to include in notification
            
        Returns:
            True if notification was sent successfully, False otherwise
        """
        user = None
        try:
            # Fetch user to get FCM token
            result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                logger.warning(f"User {user_id} not found for FCM notification")
                return False
            
            if not user.fcm_token:
                logger.debug(f"User {user_id} has no FCM token, skipping notification")
                return False
            
            # Check if Firebase is initialized
            firebase_app = get_firebase_app()
            if not firebase_app:
                logger.warning("Firebase Admin SDK not initialized, cannot send FCM notification")
                return False
            
            # Prepare notification message
            title = "Análise pronta!"
            body = f"Sua sessão está pronta para visualização."
            if session_title:
                body = f"'{session_title}' está pronta para visualização."
            
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data={
                    "type": "session_ready",
                    "session_id": session_id,
                },
                token=user.fcm_token,
            )
            
            # Send notification
            response = messaging.send(message, app=firebase_app)
            logger.info(
                f"FCM notification sent successfully to user {user_id} "
                f"for session {session_id}: {response}"
            )
            return True
            
        except messaging.UnregisteredError:
            logger.warning(
                f"FCM token for user {user_id} is invalid or unregistered. "
                f"Token should be removed from database."
            )
            # Remove invalid token from database
            if user:
                user.fcm_token = None
                await db.commit()
            return False
        except Exception as e:
            logger.error(
                f"Failed to send FCM notification to user {user_id} "
                f"for session {session_id}: {str(e)}",
                exc_info=True
            )
            return False
    
    @staticmethod
    async def send_low_credits_notification(
        db: AsyncSession,
        user_id: str,
        credits_balance: int
    ) -> bool:
        """
        Send FCM notification when user credits are running low (<= 5).
        
        Args:
            db: Database session
            user_id: User ID to send notification to
            credits_balance: Current credit balance
            
        Returns:
            True if notification was sent successfully, False otherwise
        """
        user = None
        try:
            # Fetch user to get FCM token
            result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                logger.warning(f"User {user_id} not found for FCM notification")
                return False
            
            if not user.fcm_token:
                logger.debug(f"User {user_id} has no FCM token, skipping notification")
                return False
            
            # Check if Firebase is initialized
            firebase_app = get_firebase_app()
            if not firebase_app:
                logger.warning("Firebase Admin SDK not initialized, cannot send FCM notification")
                return False
            
            # Prepare notification message
            title = "Créditos acabando!"
            if credits_balance == 0:
                body = "Você não tem mais créditos. Recarregue para continuar usando a IA."
            elif credits_balance == 1:
                body = f"Você tem apenas {credits_balance} crédito restante. Recarregue agora!"
            else:
                body = f"Você tem apenas {credits_balance} créditos restantes. Recarregue agora!"
            
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data={
                    "type": "low_credits",
                    "credits_balance": str(credits_balance),
                },
                token=user.fcm_token,
            )
            
            # Send notification
            response = messaging.send(message, app=firebase_app)
            logger.info(
                f"FCM low credits notification sent successfully to user {user_id} "
                f"(balance: {credits_balance}): {response}"
            )
            return True
            
        except messaging.UnregisteredError:
            logger.warning(
                f"FCM token for user {user_id} is invalid or unregistered. "
                f"Token should be removed from database."
            )
            # Remove invalid token from database
            if user:
                user.fcm_token = None
                await db.commit()
            return False
        except Exception as e:
            logger.error(
                f"Failed to send FCM low credits notification to user {user_id} "
                f"(balance: {credits_balance}): {str(e)}",
                exc_info=True
            )
            return False

