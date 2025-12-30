# BrainGlass Backend API

Backend API para o aplicativo mobile-first **BrainGlass** (Second Brain).

Aplicativo de captura de sessões de áudio e imagem com processamento AI assíncrono e busca semântica.

---

## 📋 Índice

1. [Visão Geral](#-visão-geral)
2. [Arquitetura](#-arquitetura)
3. [Tech Stack](#-tech-stack)
4. [Estrutura do Projeto](#-estrutura-do-projeto)
5. [Configuração e Instalação](#-configuração-e-instalação)
6. [Variáveis de Ambiente](#-variáveis-de-ambiente)
7. [Modelos de Dados](#-modelos-de-dados)
8. [API Endpoints](#-api-endpoints)
9. [Autenticação](#-autenticação)
10. [Sistema de Créditos](#-sistema-de-créditos)
11. [Upload de Arquivos](#-upload-de-arquivos)
12. [Processamento AI](#-processamento-ai)
13. [Busca Semântica](#-busca-semântica)
14. [Workers e Tarefas](#-workers-e-tarefas)
15. [Webhooks](#-webhooks)
16. [Exemplos de Uso](#-exemplos-de-uso)

---

## 🎯 Visão Geral

O BrainGlass Backend é uma API REST construída com FastAPI que:

- **Autentica** usuários via Firebase JWT
- **Gerencia** sessões de gravação (voz, imagem, marcadores)
- **Processa** conteúdo com IA de forma assíncrona
- **Gera** embeddings para busca semântica
- **Armazena** arquivos diretamente no Cloudflare R2 (S3-compatible)
- **Gerencia** créditos de IA com sistema de débito atômico

### Princípios de Design

| Princípio | Descrição |
|-----------|-----------|
| **Mobile-First** | Otimizado para conectividade instável |
| **Offline-First** | App funciona offline, sync quando possível |
| **Backend não-crítico** | Backend NÃO está no caminho crítico da UX |
| **Processamento Assíncrono** | Todo trabalho pesado em workers Celery |
| **Direct Upload** | Arquivos vão direto para R2, não passam pelo backend |

---

## 🏗 Arquitetura

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Mobile App (Flutter)                         │
└───────────────┬─────────────────────────────────┬───────────────────┘
                │                                 │
                │ API Requests                    │ Direct Upload
                │ (JWT Auth)                      │ (Presigned URL)
                ▼                                 ▼
┌───────────────────────────┐         ┌───────────────────────────┐
│      FastAPI Backend      │         │    Cloudflare R2 (S3)     │
│   (Thin API Layer Only)   │         │    (Object Storage)       │
└───────────────┬───────────┘         └───────────────────────────┘
                │
                │ Enqueue Tasks
                ▼
┌───────────────────────────┐
│         Redis             │◄────────┐
│     (Message Broker)      │         │
└───────────────┬───────────┘         │
                │                     │
                │ Consume Tasks       │ Results
                ▼                     │
┌───────────────────────────┐         │
│     Celery Workers        │─────────┘
│   (AI Processing Only)    │
└───────────────┬───────────┘
                │
                │ AI Calls
                ▼
┌───────────────────────────┐
│   OpenAI / DeepSeek       │
│   (Embeddings + LLM)      │
└───────────────────────────┘
                │
                │ Store Results
                ▼
┌───────────────────────────┐
│   PostgreSQL + pgvector   │
│   (Data + Embeddings)     │
└───────────────────────────┘
```

---

## 🛠 Tech Stack

| Componente | Tecnologia | Versão |
|------------|------------|--------|
| **Framework** | FastAPI | 0.104.1 |
| **Runtime** | Python | 3.11 |
| **Database** | PostgreSQL + pgvector | 16 |
| **Queue** | Redis | 7 |
| **Workers** | Celery | 5.3.4 |
| **Auth** | Firebase Admin SDK | 6.4.0 |
| **AI** | OpenAI / DeepSeek | 1.3.7 |
| **Storage** | Cloudflare R2 (boto3) | 1.34.0 |
| **Payments** | Stripe | 7.0.0 |
| **Container** | Docker + docker-compose | - |

---

## 📁 Estrutura do Projeto

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Settings (env vars)
│   ├── database.py          # SQLAlchemy async engine
│   │
│   ├── api/                 # API endpoints (thin layer)
│   │   ├── __init__.py
│   │   ├── router.py        # Router aggregator
│   │   ├── health.py        # Health check
│   │   ├── sessions.py      # Session CRUD
│   │   ├── uploads.py       # Presigned URLs
│   │   ├── search.py        # Semantic search
│   │   ├── me.py            # User profile
│   │   └── webhooks.py      # Stripe webhooks
│   │
│   ├── auth/                # Authentication
│   │   ├── __init__.py
│   │   ├── dependencies.py  # FastAPI dependencies
│   │   └── firebase.py      # Firebase Admin SDK
│   │
│   ├── models/              # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── base.py          # Base model
│   │   ├── user.py          # User + credits
│   │   ├── session.py       # Session lifecycle
│   │   ├── session_block.py # Voice/image/marker blocks
│   │   ├── embedding.py     # pgvector embeddings
│   │   ├── ai_job.py        # AI job tracking
│   │   └── media_file.py    # R2 upload tracking
│   │
│   ├── schemas/             # Pydantic schemas
│   │   ├── __init__.py
│   │   ├── session.py
│   │   └── block.py
│   │
│   ├── services/            # Business logic
│   │   ├── __init__.py
│   │   ├── session_service.py
│   │   ├── credit_service.py
│   │   └── capability_service.py
│   │
│   ├── repositories/        # Data access
│   │   ├── __init__.py
│   │   └── embedding_repository.py
│   │
│   ├── storage/             # R2/S3 integration
│   │   ├── __init__.py
│   │   ├── r2_client.py     # boto3 S3 client
│   │   └── presign.py       # Presigned URL service
│   │
│   ├── ai/                  # AI providers
│   │   ├── __init__.py
│   │   ├── base.py          # Abstract interface
│   │   ├── factory.py       # Provider factory
│   │   ├── openai_provider.py
│   │   └── deepseek_provider.py
│   │
│   ├── tasks/               # Celery tasks
│   │   ├── __init__.py
│   │   └── process_session.py
│   │
│   ├── workers/             # Worker config
│   │   ├── __init__.py
│   │   ├── celery_app.py
│   │   └── ai_processor.py
│   │
│   └── utils/               # Utilities
│       ├── __init__.py
│       └── text_chunker.py
│
├── tests/                   # Test suite
├── Dockerfile
├── requirements.txt
└── pytest.ini
```

---

## ⚙️ Configuração e Instalação

### CI/CD Pipeline

The backend uses GitHub Actions to build and push Docker images to GitHub Container Registry (GHCR).

#### Workflow

**Trigger**: Pushes to `main` branch

**Actions**:
1. Builds two Docker images:
   - `ghcr.io/<org>/sb-api:latest` and `ghcr.io/<org>/sb-api:sha-<commit>`
   - `ghcr.io/<org>/sb-worker:latest` and `ghcr.io/<org>/sb-worker:sha-<commit>`
2. Uses Docker Buildx with layer caching (GitHub Actions cache)
3. Pushes images to GHCR using `GITHUB_TOKEN` (automatic)

#### Image Tags

- `latest`: Always points to the latest build from `main` branch
- `sha-<commit>`: Immutable tag for specific commit (e.g., `sha-abc123def`)

#### Usage

**Pull images**:
```bash
# Pull latest API image
docker pull ghcr.io/<org>/sb-api:latest

# Pull specific commit
docker pull ghcr.io/<org>/sb-api:sha-abc123def

# Pull latest Worker image
docker pull ghcr.io/<org>/sb-worker:latest
```

**Authenticate** (if pulling private images):
```bash
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
```

**Workflow File**: `.github/workflows/backend-ci.yml`

**Note**: Images are built in CI, not on the VPS. The VPS only pulls and runs pre-built images.

### Pré-requisitos

- Docker e docker-compose
- Conta Firebase (para autenticação)
- API Key OpenAI ou DeepSeek (para AI)
- Conta Cloudflare R2 (para storage)

### Instalação com Docker

```bash
# Clone o repositório
git clone <repo-url>
cd sb-backend

# Crie o arquivo .env
cp .env.example .env
# Edite .env com suas credenciais

# Inicie os serviços
docker-compose up --build -d

# Verifique os logs
docker-compose logs -f api
docker-compose logs -f worker
```

### Verificar Instalação

```bash
# Health check
curl http://localhost:8000/api/health

# Resposta esperada:
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected"
}
```

---

## 🔐 Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto:

```env
# ============================================
# DATABASE
# ============================================
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=secondbrain

# ============================================
# AI PROVIDER
# ============================================
# Escolha: "openai" ou "deepseek"
AI_PROVIDER=openai

# OpenAI (obrigatório se AI_PROVIDER=openai)
OPENAI_API_KEY=sk-proj-...

# DeepSeek (obrigatório se AI_PROVIDER=deepseek)
DEEPSEEK_API_KEY=sk-...

# ============================================
# FIREBASE AUTHENTICATION
# ============================================
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_CREDENTIALS_JSON=./firebase-credentials.json

# ============================================
# CLOUDFLARE R2 STORAGE
# ============================================
R2_ENDPOINT=https://<account_id>.r2.cloudflarestorage.com
R2_BUCKET=brainglass-media
R2_ACCESS_KEY=your-access-key
R2_SECRET_KEY=your-secret-key
R2_REGION=auto
R2_PRESIGN_EXPIRATION=600  # 10 minutos

# ============================================
# STRIPE (opcional)
# ============================================
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# ============================================
# ENVIRONMENT
# ============================================
ENVIRONMENT=dev
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
    created_at TIMESTAMP
);
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | UUID | Identificador interno |
| `firebase_uid` | String | ID do Firebase (único) |
| `email` | String | Email do usuário |
| `credits` | Integer | Saldo de créditos AI |
| `created_at` | DateTime | Data de criação |

### Session (Sessão)

```sql
CREATE TABLE sessions (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    session_type VARCHAR(50) NOT NULL,
    status session_status NOT NULL,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    finalized_at TIMESTAMP,
    processed_at TIMESTAMP
);
```

**Status possíveis:**

| Status | Descrição |
|--------|-----------|
| `OPEN` | Sessão aberta, aceitando blocos |
| `PENDING_PROCESSING` | Finalizada, aguardando AI |
| `PROCESSING` | AI processando |
| `PROCESSED` | AI concluído com sucesso |
| `NO_CREDITS` | Finalizada sem AI (sem créditos, salva localmente) |
| `RAW_ONLY` | Finalizada sem AI (legado, use NO_CREDITS) |
| `FAILED` | Erro no processamento |

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

**Tipos de bloco:**

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

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `embedding` | Vector(1536) | Vetor de embedding (pgvector) |
| `provider` | String | "openai" ou "deepseek" |
| `text` | Text | Chunk de texto original |

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

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `type` | Enum | `audio` ou `image` |
| `object_key` | String | Caminho no R2 |
| `status` | Enum | `pending` ou `uploaded` |

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

---

## 🌐 API Endpoints

### Resumo

| Método | Endpoint | Descrição | Auth |
|--------|----------|-----------|------|
| GET | `/api/health` | Health check | ❌ |
| GET | `/api/me/credits` | Saldo de créditos | ✅ |
| POST | `/api/sessions` | Criar sessão | ✅ |
| POST | `/api/sessions/{id}/blocks` | Adicionar bloco | ✅ |
| POST | `/api/sessions/{id}/finalize` | Finalizar sessão | ✅ |
| POST | `/api/uploads/presign` | Gerar URL de upload | ✅ |
| POST | `/api/uploads/commit` | Confirmar upload | ✅ |
| POST | `/api/search/semantic` | Busca semântica | ✅ |
| GET | `/api/payments/packages` | Listar pacotes de créditos | ❌ |
| POST | `/api/payments/checkout` | Criar sessão de checkout Stripe | ✅ |
| GET | `/api/payments/history` | Histórico de pagamentos | ✅ |
| POST | `/api/webhooks/stripe` | Webhook Stripe | ❌* |

*Usa assinatura Stripe para validação

---

### Health Check

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

---

### Créditos do Usuário

```http
GET /api/me/credits
Authorization: Bearer <firebase_jwt>
```

**Response:**
```json
{
  "credits": 10,
  "user_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

### Criar Sessão

```http
POST /api/sessions
Authorization: Bearer <firebase_jwt>
Content-Type: application/json

{
  "session_type": "voice"
}
```

**Response (201):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "660e8400-e29b-41d4-a716-446655440000",
  "session_type": "voice",
  "status": "open",
  "created_at": "2025-12-21T17:30:00.000Z",
  "updated_at": "2025-12-21T17:30:00.000Z",
  "finalized_at": null,
  "processed_at": null
}
```

---

### Adicionar Bloco

```http
POST /api/sessions/{session_id}/blocks
Authorization: Bearer <firebase_jwt>
Content-Type: application/json

{
  "block_type": "voice",
  "text_content": "Reunião sobre o projeto...",
  "media_url": null,
  "metadata": null
}
```

**Response (201):**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "block_type": "voice",
  "text_content": "Reunião sobre o projeto...",
  "media_url": null,
  "metadata": null,
  "created_at": "2025-12-21T17:31:00.000Z"
}
```

**Tipos de bloco:**

| block_type | Campos obrigatórios |
|------------|---------------------|
| `voice` | `text_content` |
| `image` | `media_url` |
| `marker` | `text_content` |

---

### Finalizar Sessão

```http
POST /api/sessions/{session_id}/finalize
Authorization: Bearer <firebase_jwt>
```

**Response (202) - Com créditos:**
```json
{
  "message": "Session finalized. AI processing started.",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending_processing"
}
```

**Response (202) - Sem créditos:**
```json
{
  "message": "Session finalized without AI processing (no credits available). Session saved locally.",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "no_credits"
}
```

---

### Upload: Gerar URL Presigned

```http
POST /api/uploads/presign
Authorization: Bearer <firebase_jwt>
Content-Type: application/json

{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "audio",
  "content_type": "audio/m4a"
}
```

**Response:**
```json
{
  "upload_url": "https://bucket.r2.cloudflarestorage.com/sessions/550e.../audio/abc123.m4a?X-Amz-...",
  "object_key": "sessions/550e8400.../audio/abc123.m4a",
  "media_id": "880e8400-e29b-41d4-a716-446655440000",
  "expires_in": 600
}
```

**Content types suportados:**

| Tipo | Content Types |
|------|---------------|
| `audio` | `audio/m4a`, `audio/mp4`, `audio/mpeg`, `audio/wav`, `audio/webm`, `audio/ogg`, `audio/aac` |
| `image` | `image/jpeg`, `image/png`, `image/webp`, `image/heic` |

---

### Upload: Confirmar

```http
POST /api/uploads/commit
Authorization: Bearer <firebase_jwt>
Content-Type: application/json

{
  "media_id": "880e8400-e29b-41d4-a716-446655440000",
  "size_bytes": 1048576
}
```

**Response:**
```json
{
  "success": true,
  "media_id": "880e8400-e29b-41d4-a716-446655440000"
}
```

---

### Busca Semântica

```http
POST /api/search/semantic?query=reunião+projeto&limit=10&threshold=0.3
Authorization: Bearer <firebase_jwt>
```

**Query Parameters:**

| Param | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| `query` | string | (obrigatório) | Texto de busca |
| `limit` | int | 10 | Máximo de resultados (1-50) |
| `threshold` | float | 0.7 | Similaridade mínima (0.0-1.0) |

**Response:**
```json
{
  "query": "reunião projeto",
  "results": [
    {
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "block_id": null,
      "text": "Reunião sobre o projeto Second Brain...",
      "similarity": 0.85,
      "provider": "openai"
    }
  ],
  "total_results": 1
}
```

---

### Pacotes de Créditos (Payments)

#### Listar Pacotes Disponíveis

```http
GET /api/payments/packages
```

**Response:**
```json
{
  "packages": [
    {
      "id": "starter",
      "name": "Starter Pack",
      "credits": 10,
      "price_cents": 499,
      "price_formatted": "$4.99",
      "currency": "usd",
      "description": "Perfect for trying out SecondBrain",
      "popular": false,
      "price_per_credit": 49.9
    },
    {
      "id": "popular",
      "name": "Popular Pack",
      "credits": 50,
      "price_cents": 1999,
      "price_formatted": "$19.99",
      "currency": "usd",
      "description": "Best value for regular users",
      "popular": true,
      "price_per_credit": 39.98
    },
    {
      "id": "pro",
      "name": "Pro Pack",
      "credits": 100,
      "price_cents": 3499,
      "price_formatted": "$34.99",
      "currency": "usd",
      "description": "For power users",
      "popular": false,
      "price_per_credit": 34.99
    },
    {
      "id": "enterprise",
      "name": "Enterprise Pack",
      "credits": 500,
      "price_cents": 14999,
      "price_formatted": "$149.99",
      "currency": "usd",
      "description": "Maximum credits for heavy usage",
      "popular": false,
      "price_per_credit": 29.998
    }
  ]
}
```

---

#### Criar Checkout Session

```http
POST /api/payments/checkout
Authorization: Bearer <firebase_jwt>
Content-Type: application/json

{
  "package_id": "popular",
  "success_url": "secondbrain://payment/success",
  "cancel_url": "secondbrain://payment/cancel"
}
```

**Response:**
```json
{
  "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_...",
  "session_id": "cs_test_...",
  "expires_at": 1703385600
}
```

**Notas:**
- O `checkout_url` deve ser aberto em um browser/webview
- `success_url` e `cancel_url` podem ser deep links do app
- A sessão expira em ~24 horas

---

#### Histórico de Pagamentos

```http
GET /api/payments/history?limit=20
Authorization: Bearer <firebase_jwt>
```

**Response:**
```json
{
  "payments": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "credits_amount": 50,
      "amount_cents": 1999,
      "currency": "usd",
      "status": "completed",
      "package_id": "popular",
      "created_at": "2025-12-21T17:30:00.000Z",
      "completed_at": "2025-12-21T17:31:00.000Z"
    }
  ],
  "total_credits_purchased": 50
}
```

**Status possíveis:**

| Status | Descrição |
|--------|-----------|
| `pending` | Checkout iniciado, aguardando pagamento |
| `completed` | Pagamento confirmado, créditos adicionados |
| `failed` | Pagamento falhou |
| `refunded` | Pagamento estornado |

---

## 🔑 Autenticação

### Firebase JWT

Todos os endpoints (exceto `/api/health`) requerem autenticação via Firebase JWT.

**Header:**
```http
Authorization: Bearer <firebase_jwt_token>
```

### Fluxo de Autenticação

```
┌─────────┐     1. Login     ┌─────────────┐
│  App    │ ───────────────► │  Firebase   │
│ Mobile  │ ◄─────────────── │   Auth      │
└─────────┘    2. JWT Token  └─────────────┘
     │
     │  3. API Request + JWT
     ▼
┌─────────────────────────────────────────┐
│            FastAPI Backend              │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │  get_current_user dependency    │   │
│  │                                 │   │
│  │  1. Extract Bearer token        │   │
│  │  2. Verify with Firebase SDK    │   │
│  │  3. Extract uid, email          │   │
│  │  4. Lookup/Create user in DB    │   │
│  │  5. Return User object          │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

### Auto-criação de Usuário

Novos usuários são criados automaticamente no primeiro login:
- `firebase_uid` extraído do token
- `email` extraído do token
- `credits = 3` (créditos de trial)

---

## 💳 Sistema de Créditos

### Visão Geral

- **1 crédito = 1 processamento de sessão com AI**
- Usuários novos recebem **3 créditos de trial**
- Créditos adicionais via pagamento Stripe
- Débito **atômico** previne race conditions

### Fluxo de Créditos

```
Finalize Session
       │
       ▼
┌──────────────────┐
│ has_credits(1)?  │
└────────┬─────────┘
         │
    ┌────┴────┐
    │         │
   Yes        No
    │         │
    ▼         ▼
┌────────┐  ┌──────────────┐
│ Debit  │  │ NO_CREDITS   │
│ Credit │  │ (saved local)│
└───┬────┘  └──────────────┘
    │
    ▼
┌────────────────┐
│ Create AIJob   │
│ Enqueue Task   │
└────────────────┘
```

### Operações de Crédito

```python
# Verificar saldo
await CreditService.has_credits(db, user_id, amount=1)

# Débito atômico (previne saldo negativo)
success = await CreditService.debit(db, user_id, amount=1)

# Crédito (Stripe webhook)
await CreditService.credit(db, user_id, amount=10)

# Consultar saldo
balance = await CreditService.get_balance(db, user_id)
```

---

## 📤 Upload de Arquivos

### Arquitetura de Upload Direto

O backend **NUNCA** recebe bytes de arquivo. Arquivos vão direto para R2.

```
┌──────────┐                              ┌──────────┐
│  Mobile  │  1. POST /uploads/presign    │ Backend  │
│   App    │ ────────────────────────────►│  (API)   │
└──────────┘                              └────┬─────┘
     │                                         │
     │                                         │ 2. Generate presigned URL
     │                                         │    Create media_file record
     │                                         │    status = "pending"
     │       3. Return upload_url, media_id   │
     │◄────────────────────────────────────────┘
     │
     │  4. PUT file directly to R2
     │     (using presigned URL)
     ▼
┌──────────┐
│   R2     │
│ Storage  │
└──────────┘
     │
     │  5. Upload complete
     ▼
┌──────────┐                              ┌──────────┐
│  Mobile  │  6. POST /uploads/commit     │ Backend  │
│   App    │ ────────────────────────────►│  (API)   │
└──────────┘                              └────┬─────┘
                                               │
                                               │ 7. Update status = "uploaded"
```

### Segurança

- URLs presigned expiram em **10 minutos**
- Bucket permanece **privado**
- Validação de ownership via `session_id`
- Content-type validado antes de gerar URL

### Object Key Pattern

```
sessions/{session_id}/{type}/{uuid}.{ext}

Exemplo:
sessions/550e8400-e29b.../audio/abc123.m4a
sessions/550e8400-e29b.../image/def456.jpg
```

---

## 🤖 Processamento AI

### Providers Suportados

| Provider | Embeddings | Summarization | Modelo Embedding |
|----------|------------|---------------|------------------|
| OpenAI | ✅ | ✅ | `text-embedding-3-small` (1536d) |
| DeepSeek | ✅ | ✅ | `deepseek-embedding` (1536d) |

### Fluxo de Processamento

```
Celery Worker
      │
      ▼
┌─────────────────────────────────────────┐
│           process_session_task          │
│                                         │
│  1. Fetch session + blocks              │
│  2. Update status → PROCESSING          │
│                                         │
│  3. Generate Embeddings:                │
│     ├─ Combine all text content         │
│     ├─ Chunk text (600 chars, 50 overlap│
│     └─ For each chunk:                  │
│        └─ provider.embed(chunk)         │
│        └─ Store in embeddings table     │
│                                         │
│  4. Generate Summary:                   │
│     └─ provider.summarize(blocks)       │
│                                         │
│  5. Update AIJob → COMPLETED            │
│  6. Update session → PROCESSED          │
└─────────────────────────────────────────┘
```

### Interface do Provider

```python
class LLMProvider(ABC):
    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Gera embedding de 1536 dimensões."""
        pass
    
    @abstractmethod
    def summarize(self, blocks: List[dict]) -> str:
        """Gera resumo do conteúdo."""
        pass
    
    @abstractmethod
    def is_configured(self) -> bool:
        """Verifica se API key está configurada."""
        pass
```

### Seleção de Provider

```python
# Configurado via AI_PROVIDER env var
provider = get_llm_provider()  # Retorna OpenAI ou DeepSeek

# Factory pattern
if settings.ai_provider == "openai":
    return OpenAIProvider()
elif settings.ai_provider == "deepseek":
    return DeepSeekProvider()
```

---

## 🔍 Busca Semântica

### Como Funciona

1. Query de texto é convertida em embedding
2. Busca por similaridade no pgvector
3. Retorna resultados ordenados por similaridade

### pgvector

```sql
-- Operador de distância coseno
SELECT id, (embedding <=> query_vector) AS distance
FROM embeddings
WHERE session_id = ANY(user_session_ids)
  AND (embedding <=> query_vector) < threshold
ORDER BY embedding <=> query_vector
LIMIT limit;
```

### Conversão Distância → Similaridade

```
similarity = 1 - cosine_distance

| Distância | Similaridade |
|-----------|--------------|
| 0.0       | 1.0 (idêntico) |
| 0.3       | 0.7 |
| 0.5       | 0.5 |
| 1.0       | 0.0 (ortogonal) |
```

---

## ⚙️ Workers e Tarefas

### Celery Configuration

```python
# app/workers/celery_app.py
celery_app = Celery(
    "brainglass",
    broker=settings.redis_url,
    backend=settings.redis_url
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)
```

### Tarefas Disponíveis

| Task | Descrição | Trigger |
|------|-----------|---------|
| `process_session` | Processa sessão com AI | `POST /sessions/{id}/finalize` |

### Executar Worker

```bash
# Via docker-compose
docker-compose up worker

# Manual
celery -A app.workers.celery_app worker --loglevel=info
```

---

## 🪝 Webhooks

### Stripe Webhook

```http
POST /api/webhooks/stripe
stripe-signature: <stripe_signature>
```

**Evento tratado:** `checkout.session.completed`

**Metadata esperada:**
```json
{
  "user_id": "uuid",
  "credits": "10"
}
```

**Fluxo:**
1. Valida assinatura Stripe
2. Extrai `user_id` e `credits` do metadata
3. Credita créditos ao usuário
4. Retorna sucesso

---

## 📊 Observability

### Metrics and Monitoring

The observability stack includes Prometheus for metrics collection and Grafana for visualization.

#### Services

- **Prometheus**: Scrapes metrics from API, worker, and Redis exporter (port 9090)
- **Grafana**: Visualization dashboard (port 3001)
- **Redis Exporter**: Exposes Redis queue metrics (port 9121)

#### Accessing Grafana

1. Start all services:
   ```bash
   docker-compose up -d
   ```

2. Access Grafana:
   - URL: `http://localhost:3001`
   - Username: `admin`
   - Password: Set via `GRAFANA_ADMIN_PASSWORD` environment variable (default: `admin`)

3. Configure Prometheus data source:
   - Go to Configuration → Data Sources → Add data source
   - Select Prometheus
   - URL: `http://prometheus:9090`
   - Save & Test

#### Metrics Endpoints

- **FastAPI**: `http://localhost:8000/metrics`
- **Celery Worker**: `http://localhost:9090/metrics` (exposed in worker container)
- **Redis Exporter**: `http://localhost:9121/metrics`

#### Available Metrics

**FastAPI Metrics:**
- `http_requests_total{method, path, status}` - Total HTTP requests
- `http_request_duration_seconds{method, path}` - Request latency histogram
- `sessions_created_total` - Total sessions created
- `sessions_finalized_total` - Total sessions finalized
- `errors_total{error_type}` - Total errors by type

**Celery Worker Metrics:**
- `ai_jobs_created_total{job_type}` - Total AI jobs created
- `ai_jobs_processing{job_type}` - Currently processing jobs
- `ai_jobs_completed_total{job_type, status}` - Completed jobs
- `ai_jobs_failed_total{job_type}` - Failed jobs
- `ai_job_duration_seconds{job_type, status}` - Job execution duration

**AI Provider Metrics:**
- `ai_provider_requests_total{provider, operation}` - Total provider requests
- `ai_provider_failures_total{provider, operation}` - Provider failures
- `ai_provider_latency_seconds{provider, operation}` - Provider latency
- `ai_provider_tokens_total{provider, operation, token_type}` - Token usage

**Redis Metrics:**
- `redis_queue_length{queue}` - Queue backlog (from redis_exporter)

#### Example Grafana Queries

**Request Rate:**
```
rate(http_requests_total[5m])
```

**Error Rate:**
```
rate(errors_total[5m])
```

**Average Request Latency:**
```
rate(http_request_duration_seconds_sum[5m]) / rate(http_request_duration_seconds_count[5m])
```

**Active Jobs:**
```
sum(ai_jobs_processing)
```

**Provider Success Rate:**
```
rate(ai_provider_requests_total[5m]) - rate(ai_provider_failures_total[5m])
```

#### Structured Logging

All services use structured JSON logging with mandatory fields:

```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "level": "INFO",
  "service": "sb-api",
  "event": "session_created",
  "session_id": "uuid",
  "user_id": "uuid",
  "duration_ms": 123.45,
  "message": "Session created: uuid"
}
```

**Mandatory Fields:**
- `service`: Service name (sb-api or sb-worker)
- `event`: Event name (e.g., session_created, job_completed)
- `timestamp`: ISO 8601 timestamp
- `level`: Log level (DEBUG, INFO, WARNING, ERROR)
- `message`: Log message

**Optional Fields:**
- `session_id`: Session ID (when applicable)
- `job_id`: Job ID (when applicable)
- `user_id`: User ID (when applicable)
- `duration_ms`: Duration in milliseconds (when applicable)

#### Log Retention

- Prometheus metrics: 7 days (configured via `--storage.tsdb.retention.time=7d`)
- Grafana dashboards: Stored locally in container volume
- Application logs: Available via `docker logs` (no retention limit)

#### Environment Variables

```bash
# Grafana
GRAFANA_ADMIN_PASSWORD=your_password  # Default: admin
GRAFANA_PORT=3001                    # Default: 3001

# Prometheus
PROMETHEUS_PORT=9090                 # Default: 9090
```

---

## 💻 Exemplos de Uso

### Fluxo Completo com cURL

```bash
# Variável de ambiente
export TOKEN="eyJhbGciOiJS..."

# 1. Verificar créditos
curl -X GET "http://localhost:8000/api/me/credits" \
  -H "Authorization: Bearer $TOKEN"

# 2. Criar sessão
SESSION=$(curl -s -X POST "http://localhost:8000/api/sessions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"session_type": "voice"}')
SESSION_ID=$(echo $SESSION | jq -r '.id')

# 3. Solicitar URL de upload
PRESIGN=$(curl -s -X POST "http://localhost:8000/api/uploads/presign" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$SESSION_ID\", \"type\": \"audio\", \"content_type\": \"audio/m4a\"}")
UPLOAD_URL=$(echo $PRESIGN | jq -r '.upload_url')
MEDIA_ID=$(echo $PRESIGN | jq -r '.media_id')

# 4. Upload direto para R2
curl -X PUT "$UPLOAD_URL" \
  -H "Content-Type: audio/m4a" \
  --data-binary @audio.m4a

# 5. Confirmar upload
curl -X POST "http://localhost:8000/api/uploads/commit" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"media_id\": \"$MEDIA_ID\", \"size_bytes\": 1048576}"

# 6. Adicionar bloco de texto (transcrição)
curl -X POST "http://localhost:8000/api/sessions/$SESSION_ID/blocks" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "block_type": "voice",
    "text_content": "Reunião sobre FastAPI e Flutter. Prazo março 2025."
  }'

# 7. Finalizar sessão (dispara AI)
curl -X POST "http://localhost:8000/api/sessions/$SESSION_ID/finalize" \
  -H "Authorization: Bearer $TOKEN"

# 8. Aguardar processamento (10s)
sleep 10

# 9. Buscar semanticamente
curl -X POST "http://localhost:8000/api/search/semantic?query=FastAPI&limit=5&threshold=0.3" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 📚 Documentação Adicional

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **OpenAPI JSON:** http://localhost:8000/openapi.json

---

## 🧪 Testes

```bash
# Executar testes
docker-compose exec api pytest

# Com coverage
docker-compose exec api pytest --cov=app

# Testes específicos
docker-compose exec api pytest tests/test_api.py -v
```

---

## 📝 Licença

Projeto proprietário - Todos os direitos reservados.

---

## 🤝 Contribuição

1. Fork o repositório
2. Crie uma branch (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -m 'Add nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

---

**Desenvolvido com ❤️ para BrainGlass**

