#!/usr/bin/env python3
"""
Script de teste para reprocessar uma sessão existente.
Testa o pipeline completo: transcribe_audio -> process_images -> generate_summary
"""
import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

# Adicionar o backend ao path
sys.path.insert(0, './backend')

from app.config import settings
from app.models.session import Session, SessionStatus
from app.models.ai_job import AIJob, AIJobStatus
from celery import chain
from app.tasks.transcribe_audio import transcribe_audio_task
from app.tasks.process_images import process_images_task
from app.tasks.generate_summary import generate_summary_task

# Criar engine
engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def find_session_to_reprocess():
    """Encontra uma sessão com mídia para reprocessar."""
    async with SessionLocal() as db:
        # Buscar sessão com mídia
        from app.models.media_file import MediaFile, MediaStatus
        
        from sqlalchemy import cast, String
        
        result = await db.execute(
            select(Session, MediaFile)
            .join(MediaFile, cast(Session.id, String) == MediaFile.session_id)
            .where(
                Session.status.in_([
                    SessionStatus.PROCESSED,
                    SessionStatus.FAILED,
                    SessionStatus.PENDING_PROCESSING
                ]),
                MediaFile.status == MediaStatus.UPLOADED
            )
            .limit(1)
        )
        
        row = result.first()
        if row:
            session, media_file = row
            return str(session.id)
        return None


async def create_ai_job(session_id: str):
    """Cria um AIJob para reprocessamento."""
    async with SessionLocal() as db:
        # Buscar sessão
        result = await db.execute(
            select(Session).where(Session.id == session_id)
        )
        session = result.scalar_one_or_none()
        
        if not session:
            print(f"Sessão {session_id} não encontrada")
            return None
        
        # Criar AIJob
        ai_job = AIJob(
            user_id=session.user_id,
            session_id=session_id,
            job_type="session_reprocessing",
            credits_used=0,  # Sem débito de créditos para reprocessamento
            status=AIJobStatus.PENDING
        )
        db.add(ai_job)
        
        # Resetar status da sessão
        session.status = SessionStatus.PENDING_PROCESSING
        
        await db.commit()
        await db.refresh(ai_job)
        
        print(f"✅ AIJob criado: {ai_job.id}")
        print(f"✅ Sessão {session_id} resetada para PENDING_PROCESSING")
        
        return str(ai_job.id)


async def main():
    """Função principal."""
    print("🔍 Procurando sessão para reprocessar...")
    
    session_id = await find_session_to_reprocess()
    
    if not session_id:
        print("❌ Nenhuma sessão com mídia encontrada para reprocessar")
        return
    
    print(f"✅ Sessão encontrada: {session_id}")
    
    # Criar AIJob
    ai_job_id = await create_ai_job(session_id)
    
    if not ai_job_id:
        print("❌ Falha ao criar AIJob")
        return
    
    print(f"\n🚀 Iniciando pipeline de reprocessamento...")
    print(f"   Sessão: {session_id}")
    print(f"   AIJob: {ai_job_id}")
    print(f"\n   Pipeline:")
    print(f"   1. transcribe_audio_task")
    print(f"   2. process_images_task")
    print(f"   3. generate_summary_task")
    
    # Enfileirar pipeline
    pipeline = chain(
        transcribe_audio_task.s(session_id, ai_job_id),
        process_images_task.s(),
        generate_summary_task.s()
    )
    
    result = pipeline.delay()
    
    print(f"\n✅ Pipeline enfileirado!")
    print(f"   Task ID: {result.id}")
    print(f"\n📊 Acompanhe os logs do worker com:")
    print(f"   docker logs sb-worker -f")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

