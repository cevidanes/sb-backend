# High Level Design (HLD) - Backend SecondBrain

**Versão:** 1.0  
**Data:** 30 de Dezembro de 2024  
**Status do Deploy:** Produção (VPS)

---

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Arquitetura do Sistema](#arquitetura-do-sistema)
3. [Stack Tecnológico](#stack-tecnológico)
4. [Estrutura do Projeto](#estrutura-do-projeto)
5. [Modelos de Dados](#modelos-de-dados)
6. [API Endpoints](#api-endpoints)
7. [Fluxos Principais](#fluxos-principais)
8. [Infraestrutura e Deploy](#infraestrutura-e-deploy)
9. [Configurações de Produção](#configurações-de-produção)
10. [Segurança](#segurança)
11. [Monitoramento e Logs](#monitoramento-e-logs)

---

## 🎯 Visão Geral

O **SecondBrain Backend** é uma API REST construída com **FastAPI** que serve como backend para o aplicativo mobile **SecondBrain** (BrainGlass). O sistema foi projetado com os seguintes princípios:

### Princípios de Design

| Princípio | Descrição |
|-----------|-----------|
| **Mobile-First** | Otimizado para conectividade instável e uso mobile |
| **Offline-First** | App funciona offline, sincronização quando possível |
| **Backend não-crítico** | Backend NÃO está no caminho crítico da UX |
| **Processamento Assíncrono** | Todo trabalho pesado em workers Celery |
| **Direct Upload** | Arquivos vão direto para R2, não passam pelo backend |
| **Atomic Operations** | Operações de crédito são atômicas para prevenir race conditions |

### Funcionalidades Principais

- ✅ Autenticação via Firebase JWT
- ✅ Gerenciamento de sessões de gravação (voz, imagem, marcadores)
- ✅ Processamento AI assíncrono (embeddings, transcrição, sumarização)
- ✅ Busca semântica com pgvector
- ✅ Upload direto para Cloudflare R2 (S3-compatible)
- ✅ Sistema de créditos AI com débito atômico
- ✅ Integração com Stripe para pagamentos
- ✅ Webhooks para processamento de pagamentos

---

## 🏗 Arquitetura do Sistema

### Diagrama de Arquitetura

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Mobile App (Flutter)                             │
│                  (SecondBrain / BrainGlass)                         │
└───────────────┬─────────────────────────────────┬───────────────────┘
                │                                 │
                │ API Requests                    │ Direct Upload
                │ (JWT Auth)                      │ (Presigned URL)
                │                                 │
                ▼                                 ▼
┌───────────────────────────┐         ┌───────────────────────────┐
│      FastAPI Backend      │         │    Cloudflare R2 (S3)     │
│   (Thin API Layer Only)   │         │    (Object Storage)       │
│                           │         │    Bucket: sb-dtstofiles  │
│  - Authentication         │         │                           │
│  - Session Management     │         │  - Audio files            │
│  - Credit Management      │         │  - Image files            │
│  - Presigned URLs         │         │  - Direct uploads         │
│  - Search API             │         │                           │
└───────────────┬───────────┘         └───────────────────────────┘
                │
                │ Enqueue Tasks
                │ (Celery)
                ▼
┌───────────────────────────┐
│         Redis             │◄────────┐
│     (Message Broker)      │         │
│     (Result Backend)      │         │
└───────────────┬───────────┘         │
                │                     │
                │ Consume Tasks       │ Results
                ▼                     │
┌───────────────────────────┐         │
│     Celery Workers        │─────────┘
│   (AI Processing Only)    │
│                           │
│  - Session Processing     │
│  - Audio Transcription    │
│  - Image Processing       │
│  - Embedding Generation   │
│  - Summary Generation     │
└───────────────┬───────────┘
                │
                │ AI API Calls
                ▼
┌───────────────────────────┐
│   AI Providers            │
│                           │
│  - DeepSeek (Chat/Summary)│
│  - OpenAI (Embeddings)    │
│  - Groq (Transcription)   │
└───────────────────────────┘
                │
                │ Store Results
                ▼
┌───────────────────────────┐
│   PostgreSQL + pgvector   │
│   (Data + Embeddings)     │
│                           │
│  - Users                   │
│  - Sessions                │
│  - Blocks                  │
│  - Embeddings (1536d)      │
│  - Payments                │
│  - AI Jobs                 │
└───────────────────────────┘
```

### Componentes Principais

1. **FastAPI Application** (`sb-api`)
   - API REST thin layer
   - Autenticação Firebase JWT
   - Gerenciamento de sessões
   - Geração de presigned URLs
   - Busca semântica

2. **Celery Workers** (`sb-worker`)
   - Processamento assíncrono de sessões
   - Geração de embeddings
   - Transcrição de áudio
   - Processamento de imagens
   - Geração de resumos

3. **Redis** (`sb-redis`)
   - Message broker para Celery
   - Result backend para tarefas
   - Cache (futuro)

4. **PostgreSQL + pgvector** (`glassly-postgres`)
   - Banco de dados principal
   - Armazenamento de embeddings vetoriais
   - Busca por similaridade

5. **Cloudflare R2**
   - Armazenamento de objetos (S3-compatible)
   - Upload direto do mobile
   - Bucket: `sb-dtstofiles`

6. **Nginx** (`glassly-nginx`)
   - Reverse proxy
   - SSL/TLS termination
   - Load balancing (futuro)

---

## 🛠 Stack Tecnológico

### Backend Core

| Componente | Tecnologia | Versão | Uso |
|------------|------------|--------|-----|
| **Framework** | FastAPI | 0.104.1 | API REST framework |
| **Runtime** | Python | 3.11 | Linguagem principal |
| **ASGI Server** | Uvicorn | 0.24.0 | Servidor ASGI |
| **Validation** | Pydantic | 2.5.0 | Validação de dados |

### Banco de Dados

| Componente | Tecnologia | Versão | Uso |
|------------|------------|--------|-----|
| **Database** | PostgreSQL | 16 | Banco de dados principal |
| **Vector Extension** | pgvector | - | Busca semântica |
| **ORM** | SQLAlchemy | 2.0.23 | ORM assíncrono |
| **Driver** | asyncpg | 0.29.0 | Driver assíncrono PostgreSQL |
| **Migrations** | Alembic | 1.12.1 | Gerenciamento de migrations |

### Processamento Assíncrono

| Componente | Tecnologia | Versão | Uso |
|------------|------------|--------|-----|
| **Task Queue** | Celery | 5.3.4 | Processamento assíncrono |
| **Message Broker** | Redis | 7 | Message broker |
| **Serialization** | JSON | - | Serialização de tarefas |

### AI Providers

| Provider | Uso | Modelo | API |
|----------|-----|--------|-----|
| **DeepSeek** | Chat, Sumarização | `deepseek-chat` | DeepSeek API |
| **OpenAI** | Embeddings | `text-embedding-3-small` (1536d) | OpenAI API |
| **Groq** | Transcrição de Áudio | Whisper | Groq API |

### Storage

| Componente | Tecnologia | Uso |
|------------|------------|-----|
| **Object Storage** | Cloudflare R2 | Armazenamento de arquivos (S3-compatible) |
| **Client** | boto3 | 1.34.0 | Cliente S3/R2 |

### Autenticação e Pagamentos

| Componente | Tecnologia | Versão | Uso |
|------------|------------|--------|-----|
| **Auth** | Firebase Admin SDK | 6.4.0 | Verificação de JWT |
| **Payments** | Stripe | 7.0.0 | Processamento de pagamentos |

### Containerização

| Componente | Tecnologia | Uso |
|------------|------------|-----|
| **Containerization** | Docker | Containerização |
| **Orchestration** | docker-compose | Orquestração local |
| **Image** | python:3.11-slim | Base image |

### Infraestrutura

| Componente | Tecnologia | Uso |
|------------|------------|-----|
| **Reverse Proxy** | Nginx | SSL termination, routing |
| **SSL/TLS** | Let's Encrypt | Certificados SSL |
| **Hosting** | VPS (Contabo) | Servidor de produção |

---

## 📁 Estrutura do Projeto

```
sb-backend/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI app entry point
│   │   ├── config.py                  # Settings (env vars)
│   │   ├── database.py                # SQLAlchemy async engine
│   │   │
│   │   ├── api/                       # API endpoints (thin layer)
│   │   │   ├── __init__.py
│   │   │   ├── router.py              # Router aggregator
│   │   │   ├── health.py              # Health check
│   │   │   ├── sessions.py            # Session CRUD
│   │   │   ├── uploads.py             # Presigned URLs
│   │   │   ├── search.py              # Semantic search
│   │   │   ├── me.py                  # User profile
│   │   │   ├── payments.py            # Payment endpoints
│   │   │   ├── webhooks.py            # Stripe webhooks
│   │   │   └── admin.py                # Admin endpoints
│   │   │
│   │   ├── auth/                      # Authentication
│   │   │   ├── __init__.py
│   │   │   ├── dependencies.py        # FastAPI dependencies
│   │   │   └── firebase.py            # Firebase Admin SDK
│   │   │
│   │   ├── models/                    # SQLAlchemy models
│   │   │   ├── __init__.py
│   │   │   ├── base.py                # Base model
│   │   │   ├── user.py                # User + credits
│   │   │   ├── session.py             # Session lifecycle
│   │   │   ├── session_block.py       # Voice/image/marker blocks
│   │   │   ├── embedding.py           # pgvector embeddings
│   │   │   ├── ai_job.py              # AI job tracking
│   │   │   ├── ai_usage.py            # AI usage tracking
│   │   │   ├── media_file.py          # R2 upload tracking
│   │   │   └── payment.py              # Payment records
│   │   │
│   │   ├── schemas/                   # Pydantic schemas
│   │   │   ├── __init__.py
│   │   │   ├── session.py
│   │   │   └── block.py
│   │   │
│   │   ├── services/                  # Business logic
│   │   │   ├── __init__.py
│   │   │   ├── session_service.py
│   │   │   ├── credit_service.py      # Atomic credit operations
│   │   │   └── capability_service.py
│   │   │
│   │   ├── repositories/               # Data access
│   │   │   ├── __init__.py
│   │   │   └── embedding_repository.py
│   │   │
│   │   ├── storage/                    # R2/S3 integration
│   │   │   ├── __init__.py
│   │   │   ├── r2_client.py           # boto3 S3 client
│   │   │   └── presign.py              # Presigned URL service
│   │   │
│   │   ├── ai/                         # AI providers
│   │   │   ├── __init__.py
│   │   │   ├── base.py                # Abstract interface
│   │   │   ├── factory.py             # Provider factory
│   │   │   ├── openai_provider.py
│   │   │   └── deepseek_provider.py
│   │   │
│   │   ├── tasks/                      # Celery tasks
│   │   │   ├── __init__.py
│   │   │   ├── process_session.py
│   │   │   ├── transcribe_audio.py
│   │   │   ├── process_images.py
│   │   │   └── generate_summary.py
│   │   │
│   │   ├── workers/                    # Worker config
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py
│   │   │   └── ai_processor.py
│   │   │
│   │   └── utils/                      # Utilities
│   │       ├── __init__.py
│   │       └── text_chunker.py
│   │
│   ├── migrations/                     # SQL migrations
│   │   ├── add_open_status.sql
│   │   ├── add_pending_processing_status.sql
│   │   ├── add_processing_and_failed_status.sql
│   │   ├── add_no_credits_status.sql
│   │   ├── add_new_block_types.sql
│   │   ├── add_payments_table.sql
│   │   ├── add_stripe_customer_id_column.sql
│   │   ├── add_ai_summary_columns.sql
│   │   ├── add_fcm_token_column.sql
│   │   ├── add_preferred_language_column.sql
│   │   └── add_session_language_column.sql
│   │
│   ├── tests/                          # Test suite
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_api.py
│   │   ├── test_schemas.py
│   │   └── test_services.py
│   │
│   ├── Dockerfile
│   ├── requirements.txt
│   └── pytest.ini
│
├── docker-compose.yml                  # Docker Compose config
├── Makefile                            # Build commands
├── start.sh                            # Startup script
├── stop.sh                             # Stop script
├── setup-postgres-vps.sh               # PostgreSQL setup
├── stripe-webhooks.sh                  # Stripe webhook listener
├── logs.sh                             # Log viewing script
├── README.md                           # Documentation
└── HLD_BACKEND.md                      # Este documento
```

---

## 📊 Modelos de Dados

### User (Usuário)

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    firebase_uid VARCHAR(128) UNIQUE NOT NULL,
    email VARCHAR(255),
    credits INTEGER DEFAULT 0,
    stripe_customer_id VARCHAR(255),
    preferred_language VARCHAR(10),
    fcm_token VARCHAR(500),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**Campos:**
- `id`: UUID interno
- `firebase_uid`: ID do Firebase (único)
- `email`: Email do usuário
- `credits`: Saldo de créditos AI (inicial: 3 trial)
- `stripe_customer_id`: ID do cliente no Stripe
- `preferred_language`: Idioma preferido
- `fcm_token`: Token para push notifications
- `created_at`: Data de criação
- `updated_at`: Data de atualização

### Session (Sessão)

```sql
CREATE TABLE sessions (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    session_type VARCHAR(50) NOT NULL,
    status sessionstatus NOT NULL,
    language VARCHAR(10),
    ai_summary TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    finalized_at TIMESTAMP,
    processed_at TIMESTAMP
);
```

**Status possíveis (enum `sessionstatus`):**

| Status | Descrição |
|--------|-----------|
| `OPEN` | Sessão aberta, aceitando blocos |
| `PENDING_PROCESSING` | Finalizada, aguardando AI |
| `PROCESSING` | AI processando |
| `PROCESSED` | AI concluído com sucesso |
| `NO_CREDITS` | Finalizada sem AI (sem créditos, salva localmente) |
| `RAW_ONLY` | Finalizada sem AI (legado) |
| `FAILED` | Erro no processamento |

**Tipos de sessão:**
- `voice`: Sessão de áudio
- `image`: Sessão de imagem
- `mixed`: Sessão mista

### SessionBlock (Bloco)

```sql
CREATE TABLE session_blocks (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES sessions(id),
    block_type block_type NOT NULL,
    text_content TEXT,
    media_url VARCHAR(500),
    metadata VARCHAR(1000),
    created_at TIMESTAMP
);
```

**Tipos de bloco (enum `block_type`):**

| Tipo | Descrição | Campos usados |
|------|-----------|---------------|
| `voice` | Transcrição de áudio | `text_content` |
| `image` | Imagem | `media_url` |
| `marker` | Marcador/nota | `text_content` |

### Embedding (Embedding)

```sql
CREATE TABLE embeddings (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES sessions(id),
    block_id UUID REFERENCES session_blocks(id),
    provider VARCHAR(50) NOT NULL,
    embedding VECTOR(1536) NOT NULL,
    text TEXT NOT NULL,
    created_at TIMESTAMP
);
```

**Campos:**
- `embedding`: Vetor de embedding (pgvector, 1536 dimensões)
- `provider`: "openai" ou "deepseek"
- `text`: Chunk de texto original

### MediaFile (Arquivo de Mídia)

```sql
CREATE TABLE media_files (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL,
    type media_type NOT NULL,
    object_key VARCHAR UNIQUE NOT NULL,
    content_type VARCHAR NOT NULL,
    size_bytes INTEGER,
    status media_status NOT NULL,
    created_at TIMESTAMP
);
```

**Tipos:**
- `type`: `audio` ou `image`
- `object_key`: Caminho no R2 (ex: `sessions/{session_id}/audio/{uuid}.m4a`)
- `status`: `pending` ou `uploaded`

### AIJob (Job de AI)

```sql
CREATE TABLE ai_jobs (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    session_id UUID REFERENCES sessions(id),
    job_type VARCHAR(50) DEFAULT 'session_processing',
    credits_used INTEGER DEFAULT 1,
    status ai_job_status NOT NULL,
    created_at TIMESTAMP,
    completed_at TIMESTAMP
);
```

**Status:**
- `pending`: Aguardando processamento
- `processing`: Em processamento
- `completed`: Concluído
- `failed`: Falhou

### Payment (Pagamento)

```sql
CREATE TABLE payments (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    stripe_session_id VARCHAR(255) UNIQUE,
    stripe_payment_intent_id VARCHAR(255),
    package_id VARCHAR(50),
    credits_amount INTEGER,
    amount_cents INTEGER,
    currency VARCHAR(10),
    status payment_status NOT NULL,
    created_at TIMESTAMP,
    completed_at TIMESTAMP
);
```

**Status:**
- `pending`: Checkout iniciado
- `completed`: Pagamento confirmado
- `failed`: Pagamento falhou
- `refunded`: Pagamento estornado

### AIUsage (Uso de AI)

```sql
CREATE TABLE ai_usage (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    session_id UUID REFERENCES sessions(id),
    provider VARCHAR(50),
    operation_type VARCHAR(50),
    tokens_used INTEGER,
    cost_cents INTEGER,
    created_at TIMESTAMP
);
```

---

## 🌐 API Endpoints

### Resumo de Endpoints

| Método | Endpoint | Descrição | Auth |
|--------|----------|-----------|------|
| GET | `/api/health` | Health check | ❌ |
| GET | `/api/me/credits` | Saldo de créditos | ✅ |
| POST | `/api/sessions` | Criar sessão | ✅ |
| GET | `/api/sessions` | Listar sessões | ✅ |
| GET | `/api/sessions/{id}` | Obter sessão | ✅ |
| POST | `/api/sessions/{id}/blocks` | Adicionar bloco | ✅ |
| POST | `/api/sessions/{id}/finalize` | Finalizar sessão | ✅ |
| POST | `/api/uploads/presign` | Gerar URL de upload | ✅ |
| POST | `/api/uploads/commit` | Confirmar upload | ✅ |
| POST | `/api/search/semantic` | Busca semântica | ✅ |
| GET | `/api/payments/packages` | Listar pacotes | ❌ |
| POST | `/api/payments/checkout` | Criar checkout | ✅ |
| GET | `/api/payments/history` | Histórico de pagamentos | ✅ |
| POST | `/api/webhooks/stripe` | Webhook Stripe | ❌* |
| GET | `/api/admin/*` | Endpoints admin | ✅ |

*Usa assinatura Stripe para validação

### Detalhamento dos Principais Endpoints

#### Health Check

```http
GET /api/health
```

**Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected"
}
```

#### Criar Sessão

```http
POST /api/sessions
Authorization: Bearer <firebase_jwt>
Content-Type: application/json

{
  "session_type": "voice"
}
```

#### Finalizar Sessão

```http
POST /api/sessions/{id}/finalize
Authorization: Bearer <firebase_jwt>
```

**Response (com créditos):**
```json
{
  "message": "Session finalized. AI processing started.",
  "session_id": "...",
  "status": "pending_processing"
}
```

**Response (sem créditos):**
```json
{
  "message": "Session finalized without AI processing (no credits available).",
  "session_id": "...",
  "status": "no_credits"
}
```

#### Upload: Gerar URL Presigned

```http
POST /api/uploads/presign
Authorization: Bearer <firebase_jwt>
Content-Type: application/json

{
  "session_id": "...",
  "type": "audio",
  "content_type": "audio/m4a"
}
```

**Response:**
```json
{
  "upload_url": "https://bucket.r2.cloudflarestorage.com/...",
  "object_key": "sessions/.../audio/abc123.m4a",
  "media_id": "...",
  "expires_in": 600
}
```

#### Busca Semântica

```http
POST /api/search/semantic?query=reunião+projeto&limit=10&threshold=0.3
Authorization: Bearer <firebase_jwt>
```

**Response:**
```json
{
  "query": "reunião projeto",
  "results": [
    {
      "session_id": "...",
      "block_id": null,
      "text": "Reunião sobre o projeto...",
      "similarity": 0.85,
      "provider": "openai"
    }
  ],
  "total_results": 1
}
```

---

## 🔄 Fluxos Principais

### 1. Fluxo de Criação e Processamento de Sessão

```
┌─────────┐
│  App    │ 1. POST /sessions
│ Mobile  │ ──────────────────┐
└─────────┘                    │
                               ▼
                    ┌──────────────────┐
                    │  Create Session  │
                    │  status: OPEN    │
                    └────────┬─────────┘
                             │
┌─────────┐                  │
│  App    │ 2. POST /sessions/{id}/blocks
│ Mobile  │ ──────────────────┐
└─────────┘                    │
                               ▼
                    ┌──────────────────┐
                    │  Add Blocks      │
                    │  (voice/image)   │
                    └────────┬─────────┘
                             │
┌─────────┐                  │
│  App    │ 3. POST /uploads/presign
│ Mobile  │ ──────────────────┐
└─────────┘                    │
                               ▼
                    ┌──────────────────┐
                    │  Generate        │
                    │  Presigned URL   │
                    └────────┬─────────┘
                             │
┌─────────┐                  │
│  App    │ 4. PUT to R2
│ Mobile  │ ──────────────────┐
└─────────┘                    │
                               ▼
                    ┌──────────────────┐
                    │  Upload File    │
                    │  to R2          │
                    └────────┬─────────┘
                             │
┌─────────┐                  │
│  App    │ 5. POST /uploads/commit
│ Mobile  │ ──────────────────┐
└─────────┘                    │
                               ▼
                    ┌──────────────────┐
                    │  Update Status  │
                    │  uploaded       │
                    └────────┬─────────┘
                             │
┌─────────┐                  │
│  App    │ 6. POST /sessions/{id}/finalize
│ Mobile  │ ──────────────────┐
└─────────┘                    │
                               ▼
                    ┌──────────────────┐
                    │  Check Credits  │
                    │  has_credits(1)?│
                    └────┬─────────┬───┘
                         │         │
                    Yes  │         │ No
                         │         │
                         ▼         ▼
              ┌──────────────┐  ┌──────────────┐
              │ Debit Credit │  │ NO_CREDITS   │
              │ (atomic)      │  │ status       │
              └──────┬───────┘  └──────────────┘
                     │
                     ▼
              ┌──────────────┐
              │ Create AIJob │
              │ Enqueue Task │
              └──────┬───────┘
                     │
                     ▼
              ┌──────────────┐
              │ Celery Task  │
              │ Processing   │
              └──────┬───────┘
                     │
                     ▼
              ┌──────────────┐
              │ Generate     │
              │ Embeddings   │
              └──────┬───────┘
                     │
                     ▼
              ┌──────────────┐
              │ Update       │
              │ status:      │
              │ PROCESSED    │
              └──────────────┘
```

### 2. Fluxo de Upload Direto para R2

```
Mobile App                    Backend API                  Cloudflare R2
     │                             │                             │
     │  1. POST /uploads/presign   │                             │
     │─────────────────────────────>│                             │
     │                             │  2. Generate presigned URL │
     │                             │  3. Create media_file      │
     │                             │     status: pending         │
     │  4. Return upload_url       │                             │
     │<─────────────────────────────│                             │
     │                             │                             │
     │  5. PUT file to R2          │                             │
     │───────────────────────────────────────────────────────────>│
     │                             │                             │  6. Store file
     │                             │                             │
     │  7. POST /uploads/commit    │                             │
     │─────────────────────────────>│                             │
     │                             │  8. Update status: uploaded │
     │  9. Success                 │                             │
     │<─────────────────────────────│                             │
```

### 3. Fluxo de Pagamento Stripe

```
Mobile App          Backend API         Stripe          Webhook
     │                   │                 │               │
     │ 1. GET /packages  │                 │               │
     │───────────────────>│                 │               │
     │                   │                 │               │
     │ 2. POST /checkout │                 │               │
     │───────────────────>│                 │               │
     │                   │ 3. Create       │               │
     │                   │    Checkout     │               │
     │                   │─────────────────>│               │
     │                   │                 │               │
     │ 4. Return URL     │                 │               │
     │<───────────────────│                 │               │
     │                   │                 │               │
     │ 5. Open URL       │                 │               │
     │─────────────────────────────────────────────────────>│
     │                   │                 │               │
     │                   │                 │ 6. Payment    │
     │                   │                 │    Success    │
     │                   │                 │               │
     │                   │                 │ 7. Webhook    │
     │                   │<─────────────────────────────────│
     │                   │                 │               │
     │                   │ 8. Credit       │               │
     │                   │    Credits      │               │
     │                   │                 │               │
```

### 4. Fluxo de Busca Semântica

```
Mobile App                    Backend API              PostgreSQL
     │                             │                        │
     │ 1. POST /search/semantic    │                        │
     │────────────────────────────>│                        │
     │                             │                        │
     │                             │ 2. Generate embedding │
     │                             │    (query text)       │
     │                             │                        │
     │                             │ 3. Vector search      │
     │                             │───────────────────────>│
     │                             │                        │
     │                             │ 4. Return results     │
     │                             │<───────────────────────│
     │                             │                        │
     │ 5. Return results            │                        │
     │<─────────────────────────────│                        │
```

---

## 🚀 Infraestrutura e Deploy

### Estado Atual do Deploy (VPS)

**Servidor:** Contabo VPS  
**IP:** 193.180.213.104  
**Domínio:** api.glassly.app  
**SSH:** `admin@193.180.213.104`

### Containers em Execução

| Container | Status | Portas | Descrição |
|-----------|--------|--------|-----------|
| `glassly-postgres` | Up 14h | 0.0.0.0:5432 | PostgreSQL + pgvector |
| `glassly-api` | Up 13h | 8000/tcp | FastAPI backend |
| `glassly-worker` | Up 14h | - | Celery worker |
| `glassly-redis` | Up 16h (healthy) | 6379/tcp | Redis broker |
| `glassly-nginx` | Up 15h | 0.0.0.0:80, 443 | Nginx reverse proxy |
| `glassly-landing` | Up 16h | 3000/tcp | Landing page (Next.js) |

### Rede Docker

- **Network:** `glassly_glassly-network` (bridge)
- Todos os containers estão na mesma rede

### Nginx Configuration

**Domínios:**
- `glassly.app` → Landing page
- `api.glassly.app` → Backend API

**SSL/TLS:**
- Certificados Let's Encrypt
- Path: `/etc/letsencrypt/live/glassly.app/`
- Auto-renewal configurado

**Configuração:**
```nginx
# HTTP -> HTTPS redirect
server {
    listen 80;
    server_name glassly.app www.glassly.app api.glassly.app;
    return 301 https://$host$request_uri;
}

# API Server (api.glassly.app) - HTTPS
server {
    listen 443 ssl;
    server_name api.glassly.app;
    
    ssl_certificate /etc/letsencrypt/live/glassly.app/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/glassly.app/privkey.pem;
    
    upstream backend {
        server api:8000;
    }
    
    location / {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Estrutura de Deploy na VPS

```
/home/admin/
└── sb-backend/
    ├── backend/              # Código fonte
    ├── docker-compose.yml    # Configuração Docker
    ├── .env                  # Variáveis de ambiente (não versionado)
    ├── start.sh              # Script de inicialização
    ├── stop.sh               # Script de parada
    └── logs.sh               # Script de visualização de logs
```

### Processo de Deploy

1. **Código:** Push para repositório Git
2. **VPS:** Pull do código
3. **Build:** `docker-compose build`
4. **Restart:** `docker-compose up -d`
5. **Verificação:** Health check endpoint

### Scripts de Deploy

**start.sh:**
- Build das imagens
- Inicia containers
- Verifica saúde da API
- Inicia Stripe webhook listener (local)

**stop.sh:**
- Para containers
- Para Stripe webhook listener

**logs.sh:**
- Visualiza logs dos containers

---

## ⚙️ Configurações de Produção

### Variáveis de Ambiente (Produção)

```env
# Database
DATABASE_URL=postgresql+asyncpg://glassly:Gl4ssly_Pr0d_2024!Secure@postgres:5432/glassly

# Redis
REDIS_URL=redis://redis:6379/0

# AI Provider
AI_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-...
OPENAI_API_KEY=sk-proj-...  # Para embeddings
GROQ_API_KEY=...            # Para transcrição

# Environment
ENVIRONMENT=production

# Firebase
FIREBASE_PROJECT_ID=projectsecondbrain
FIREBASE_CREDENTIALS_JSON={"type":"service_account",...}

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Cloudflare R2
R2_ENDPOINT=https://46c704a8dcdb3296a424fadc9f5af0e6.r2.cloudflarestorage.com/
R2_BUCKET=sb-dtstofiles
R2_ACCESS_KEY=bb3e948533c2a7f5c03fe47d31ae6e2d
R2_SECRET_KEY=bb2b2b5eeff1f78e7448f76fddae4cea1bc1751de531910857aea13ab5c9411e
R2_REGION=auto
R2_PRESIGN_EXPIRATION=600
```

### Configuração do PostgreSQL

**Database:** `glassly`  
**User:** `glassly`  
**Password:** `Gl4ssly_Pr0d_2024!Secure`  
**Host:** `postgres` (container)  
**Port:** `5432`  
**Extensions:** `pgvector`

**Acesso Externo:**
- Porta 5432 exposta para acesso externo
- Configurado via `setup-postgres-vps.sh`

### Configuração do Celery

```python
# app/workers/celery_app.py
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,      # 30 minutos
    task_soft_time_limit=25 * 60,  # 25 minutos
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50, # Restart após 50 tarefas
    worker_concurrency=4,         # 4 tarefas concorrentes
)
```

### Configuração do FastAPI

```python
# app/main.py
app = FastAPI(
    title="Second Brain API",
    description="Backend API for Second Brain mobile app",
    version="0.1.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configurar para produção
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Configuração do SQLAlchemy

```python
# app/database.py
engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)
```

---

## 🔒 Segurança

### Autenticação

- **Firebase JWT:** Todos os endpoints (exceto `/api/health`) requerem autenticação
- **Token Validation:** Verificação via Firebase Admin SDK
- **Auto-criação:** Usuários criados automaticamente no primeiro login

### Upload de Arquivos

- **Presigned URLs:** Expiração de 10 minutos
- **Bucket Privado:** R2 bucket não é público
- **Validação:** Content-type validado antes de gerar URL
- **Ownership:** Validação via `session_id`

### Banco de Dados

- **Senha Forte:** Senha complexa para PostgreSQL
- **Acesso Externo:** Porta 5432 exposta (considerar VPN)
- **Connection Pooling:** Pool de conexões configurado

### API

- **HTTPS:** SSL/TLS via Let's Encrypt
- **CORS:** Configurado (ajustar para produção)
- **Headers de Segurança:** X-Frame-Options, X-Content-Type-Options, X-XSS-Protection

### Créditos

- **Débito Atômico:** Previne race conditions
- **Validação:** Verificação de saldo antes de débito
- **Transações:** Operações em transações SQL

### Webhooks

- **Stripe Signature:** Validação de assinatura Stripe
- **Secret:** Webhook secret armazenado em variável de ambiente

---

## 📊 Monitoramento e Logs

### Logs dos Containers

**Visualizar logs:**
```bash
# API
docker logs glassly-api -f

# Worker
docker logs glassly-worker -f

# Redis
docker logs glassly-redis -f

# PostgreSQL
docker logs glassly-postgres -f

# Nginx
docker logs glassly-nginx -f
```

**Script de logs:**
```bash
./logs.sh
```

### Health Checks

**Endpoint:**
```http
GET /api/health
```

**Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected"
}
```

### Métricas (Futuro)

- **Prometheus:** Métricas de aplicação
- **Grafana:** Dashboards de monitoramento
- **Sentry:** Error tracking
- **Log Aggregation:** ELK Stack ou similar

### Alertas (Futuro)

- Health check failures
- High error rates
- Database connection issues
- Worker queue backlog
- Credit balance alerts

---

## 🔄 Migrations

### Sistema de Migrations

As migrations são executadas via SQL direto no banco de dados. O sistema usa `init_db()` para criar tabelas automaticamente, mas migrations manuais são aplicadas via SQL.

### Migrations Existentes

1. `add_open_status.sql` - Adiciona status `open` ao enum
2. `add_pending_processing_status.sql` - Adiciona status `pending_processing`
3. `add_processing_and_failed_status.sql` - Adiciona status `processing` e `failed`
4. `add_no_credits_status.sql` - Adiciona status `no_credits`
5. `add_new_block_types.sql` - Adiciona novos tipos de blocos
6. `add_payments_table.sql` - Cria tabela de pagamentos
7. `add_stripe_customer_id_column.sql` - Adiciona coluna `stripe_customer_id`
8. `add_ai_summary_columns.sql` - Adiciona colunas de resumo AI
9. `add_fcm_token_column.sql` - Adiciona token FCM
10. `add_preferred_language_column.sql` - Adiciona idioma preferido
11. `add_session_language_column.sql` - Adiciona idioma da sessão

### Aplicar Migrations

```bash
# Via psql
docker exec -i glassly-postgres psql -U glassly -d glassly < migrations/add_*.sql
```

---

## 📈 Melhorias Futuras

### Curto Prazo

- [ ] Configurar CORS adequadamente para produção
- [ ] Implementar rate limiting
- [ ] Adicionar logging estruturado
- [ ] Implementar retry logic para workers
- [ ] Adicionar métricas de performance

### Médio Prazo

- [ ] Migrar para Alembic para migrations
- [ ] Implementar cache Redis
- [ ] Adicionar monitoring (Prometheus/Grafana)
- [ ] Implementar backup automático do banco
- [ ] Adicionar testes de integração

### Longo Prazo

- [ ] Horizontal scaling (múltiplos workers)
- [ ] Load balancing
- [ ] CDN para assets estáticos
- [ ] Multi-region deployment
- [ ] Disaster recovery plan

---

## 📝 Notas Técnicas

### Processamento Assíncrono

- **Celery:** Processamento de tarefas pesadas
- **Redis:** Message broker e result backend
- **Timeouts:** 30 minutos hard limit, 25 minutos soft limit
- **Concurrency:** 4 tarefas concorrentes por worker
- **Memory Management:** Restart worker após 50 tarefas

### Busca Semântica

- **pgvector:** Extensão PostgreSQL para vetores
- **Dimensões:** 1536 (OpenAI embeddings)
- **Similarity:** Cosine distance
- **Threshold:** Configurável (default: 0.7)
- **Chunking:** Texto dividido em chunks de 600 caracteres com overlap de 50

### Sistema de Créditos

- **Custo:** 1 crédito = 1 processamento de sessão
- **Trial:** 3 créditos para novos usuários
- **Atomic Operations:** Débito atômico previne race conditions
- **Validação:** Verificação de saldo antes de processar

### Upload de Arquivos

- **Direct Upload:** Arquivos vão direto para R2
- **Presigned URLs:** Expiração de 10 minutos
- **Content Types:** Validados antes de gerar URL
- **Object Key Pattern:** `sessions/{session_id}/{type}/{uuid}.{ext}`

---

## 🔗 Referências

- **Documentação FastAPI:** https://fastapi.tiangolo.com/
- **Documentação Celery:** https://docs.celeryproject.org/
- **Documentação pgvector:** https://github.com/pgvector/pgvector
- **Documentação Cloudflare R2:** https://developers.cloudflare.com/r2/
- **Documentação Stripe:** https://stripe.com/docs

---

**Documento gerado em:** 30 de Dezembro de 2024  
**Última atualização:** 30 de Dezembro de 2024  
**Versão:** 1.0

