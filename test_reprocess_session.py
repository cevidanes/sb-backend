#!/usr/bin/env python3
"""
Script para reprocessar uma sessão específica e monitorar o processamento.
"""
import asyncio
import sys
import os
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from celery import chain

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.config import settings
from app.models.session import Session, SessionStatus
from app.models.ai_job import AIJob, AIJobStatus
from app.tasks.transcribe_audio import transcribe_audio_task
from app.tasks.process_images import process_images_task
from app.tasks.generate_summary import generate_summary_task

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database setup
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
)
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

SESSION_ID = "13255b67-cc3d-4a4d-acce-9c20da732dfd"


async def reprocess_session():
    """Reprocessa a sessão especificada."""
    async with AsyncSessionLocal() as db:
        try:
            # Fetch session
            result = await db.execute(
                select(Session).where(Session.id == SESSION_ID)
            )
            session = result.scalar_one_or_none()
            
            if not session:
                logger.error(f"Sessão {SESSION_ID} não encontrada")
                return False
            
            logger.info(f"✅ Sessão encontrada: {SESSION_ID}")
            logger.info(f"   Status atual: {session.status.value}")
            logger.info(f"   User ID: {session.user_id}")
            
            # Create new AIJob
            ai_job = AIJob(
                user_id=session.user_id,
                session_id=session.id,
                job_type="session_reprocessing",
                credits_used=0,
                status=AIJobStatus.PENDING
            )
            db.add(ai_job)
            await db.commit()
            await db.refresh(ai_job)
            
            logger.info(f"✅ AIJob criado: {ai_job.id}")
            
            # Reset session status
            session.status = SessionStatus.PENDING_PROCESSING
            session.ai_summary = None
            session.suggested_title = None
            session.processed_at = None
            await db.commit()
            
            logger.info(f"✅ Sessão resetada para PENDING_PROCESSING")
            
            # Enqueue Celery pipeline
            logger.info("🚀 Enfileirando pipeline de processamento...")
            logger.info("   Pipeline: transcribe_audio -> process_images -> generate_summary")
            
            pipeline = chain(
                transcribe_audio_task.s(SESSION_ID, str(ai_job.id)),
                process_images_task.s(),
                generate_summary_task.s()
            )
            result = pipeline.delay()
            
            logger.info(f"✅ Pipeline enfileirado!")
            logger.info(f"   Task ID: {result.id}")
            logger.info(f"\n📊 Acompanhe os logs com:")
            logger.info(f"   docker logs sb-worker -f | grep -E '(13255b67|transcribe|process_images|generate_summary|Groq|Vision|ERROR)'")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao reprocessar sessão: {e}", exc_info=True)
            return False
        finally:
            await engine.dispose()


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("TESTE DE REPROCESSAMENTO DE SESSÃO")
    logger.info("=" * 60)
    logger.info(f"Sessão: {SESSION_ID}")
    logger.info("")
    
    success = asyncio.run(reprocess_session())
    
    if success:
        logger.info("")
        logger.info("=" * 60)
        logger.info("✅ Reprocessamento iniciado com sucesso!")
        logger.info("=" * 60)
    else:
        logger.error("")
        logger.error("=" * 60)
        logger.error("❌ Falha ao iniciar reprocessamento")
        logger.error("=" * 60)
        sys.exit(1)

