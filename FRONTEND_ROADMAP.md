# 📱 BrainGlass Frontend Roadmap

Este documento serve como guia completo para integração do aplicativo mobile (frontend) com o backend BrainGlass.

---

## 🏗️ Arquitetura Geral

```
┌─────────────────────────────────────────────────────────────────┐
│                        MOBILE APP                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   Camera    │  │   Audio     │  │    UI Components        │  │
│  │   Module    │  │   Module    │  │ (Sessions, Search, etc) │  │
│  └──────┬──────┘  └──────┬──────┘  └────────────┬────────────┘  │
│         │                │                      │               │
│  ┌──────┴────────────────┴──────────────────────┴────────────┐  │
│  │                   API Client Layer                         │  │
│  │  • Firebase Auth (JWT)                                     │  │
│  │  • HTTP Client (REST)                                      │  │
│  │  • File Upload Manager                                     │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        BACKEND                                   │
│  FastAPI + Celery + PostgreSQL + Cloudflare R2                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📋 Fases de Implementação

### **Fase 1: Configuração Base** (Prioridade: CRÍTICA)

#### 1.1 Firebase Authentication
```
Objetivo: Configurar autenticação com Firebase
```

**Passos:**
1. Configurar Firebase SDK no app
2. Implementar login/registro (Email/Password ou Google)
3. Obter JWT token após login
4. Armazenar token de forma segura (Keychain/Keystore)
5. Implementar refresh token automático

**Código de Exemplo (Swift):**
```swift
import FirebaseAuth

func getIdToken(completion: @escaping (String?) -> Void) {
    Auth.auth().currentUser?.getIDToken { token, error in
        if let error = error {
            print("Error: \(error)")
            completion(nil)
            return
        }
        completion(token)
    }
}
```

**Código de Exemplo (Kotlin):**
```kotlin
Firebase.auth.currentUser?.getIdToken(true)
    ?.addOnSuccessListener { result ->
        val token = result.token
        // Use token for API calls
    }
```

#### 1.2 API Client Setup
```
Objetivo: Criar cliente HTTP com autenticação
```

**Headers Obrigatórios:**
```
Authorization: Bearer <FIREBASE_JWT_TOKEN>
Content-Type: application/json
```

**Base URL:**
- Development: `http://localhost:8000`
- Production: `https://api.brainglass.app`

---

### **Fase 2: Fluxo Básico de Sessões** (Prioridade: ALTA)

#### 2.1 Verificar Créditos
```
Antes de criar sessões, verificar se o usuário tem créditos
```

**Endpoint:** `GET /api/me/credits`

**Response:**
```json
{
  "credits": 7,
  "user_id": "uuid"
}
```

**Lógica do App:**
```
IF credits == 0:
    Mostrar UI de "Comprar Créditos"
    Desabilitar criação de sessões com AI
ELSE:
    Habilitar funcionalidades normais
```

#### 2.2 Criar Sessão
```
Objetivo: Iniciar uma nova sessão de captura
```

**Endpoint:** `POST /api/sessions`

**Request:**
```json
{
  "session_type": "voice" | "image" | "mixed"
}
```

**Response:**
```json
{
  "id": "uuid",
  "session_type": "voice",
  "status": "OPEN",
  "created_at": "2025-12-21T17:00:00Z",
  "finalized_at": null,
  "processed_at": null
}
```

**Armazenamento Local:**
```
Guardar session_id para usar nas próximas chamadas
```

#### 2.3 Adicionar Blocos
```
Objetivo: Enviar dados capturados (texto transcrito, metadados)
```

**Endpoint:** `POST /api/sessions/{session_id}/blocks`

**Request (Voz/Transcrição):**
```json
{
  "block_type": "voice",
  "content": "Texto transcrito do áudio...",
  "metadata": {
    "duration_seconds": 45.5,
    "language": "pt-BR"
  }
}
```

**Request (Imagem com Descrição):**
```json
{
  "block_type": "image",
  "content": "Descrição ou OCR da imagem",
  "metadata": {
    "width": 1920,
    "height": 1080,
    "location": {"lat": -23.5505, "lng": -46.6333}
  }
}
```

**Request (Marcador):**
```json
{
  "block_type": "marker",
  "content": "highlight",
  "metadata": {
    "reason": "importante"
  }
}
```

**Response:**
```json
{
  "id": "block-uuid",
  "block_type": "voice",
  "content": "Texto transcrito...",
  "metadata": {...},
  "sequence": 1,
  "created_at": "2025-12-21T17:01:00Z"
}
```

#### 2.4 Finalizar Sessão
```
Objetivo: Marcar sessão como completa e iniciar AI processing
```

**Endpoint:** `POST /api/sessions/{session_id}/finalize`

**Response (Com Créditos):**
```json
{
  "status": "PENDING_AI",
  "ai_job_id": "job-uuid",
  "credits_remaining": 6
}
```

**Response (Sem Créditos):**
```json
{
  "status": "RAW_ONLY",
  "ai_job_id": null,
  "credits_remaining": 0
}
```

**Lógica do App:**
```
IF status == "PENDING_AI":
    Mostrar "Processando com AI..."
    Opcionalmente fazer polling para verificar status
ELSE IF status == "RAW_ONLY":
    Mostrar "Sessão salva (sem AI)"
```

---

### **Fase 3: Upload de Arquivos** (Prioridade: ALTA)

#### 3.1 Fluxo Presigned URL (Recomendado)
```
Upload direto para Cloudflare R2 sem passar pelo backend
```

**Passo 1 - Obter URL Presigned:**

**Endpoint:** `POST /api/uploads/presign`

**Request:**
```json
{
  "session_id": "uuid",
  "type": "audio",
  "content_type": "audio/m4a"
}
```

**Response:**
```json
{
  "upload_url": "https://r2.cloudflare.com/...",
  "object_key": "sessions/uuid/audio/file-uuid.m4a",
  "media_id": "media-uuid",
  "expires_in": 600
}
```

**Passo 2 - Upload Direto para R2:**

```swift
// Swift exemplo
func uploadFile(data: Data, uploadUrl: String, contentType: String) {
    var request = URLRequest(url: URL(string: uploadUrl)!)
    request.httpMethod = "PUT"
    request.setValue(contentType, forHTTPHeaderField: "Content-Type")
    request.httpBody = data
    
    URLSession.shared.dataTask(with: request) { _, response, error in
        if let httpResponse = response as? HTTPURLResponse,
           httpResponse.statusCode == 200 {
            // Upload successful
        }
    }.resume()
}
```

**Passo 3 - Confirmar Upload:**

**Endpoint:** `POST /api/uploads/commit`

**Request:**
```json
{
  "media_id": "media-uuid",
  "size_bytes": 1048576
}
```

**Response:**
```json
{
  "success": true,
  "media_id": "media-uuid"
}
```

#### 3.2 Content Types Suportados

| Tipo | Extensão | Content-Type |
|------|----------|--------------|
| Audio | .m4a | `audio/m4a` |
| Audio | .mp3 | `audio/mpeg` |
| Audio | .wav | `audio/wav` |
| Audio | .webm | `audio/webm` |
| Image | .jpg | `image/jpeg` |
| Image | .png | `image/png` |
| Image | .webp | `image/webp` |
| Image | .heic | `image/heic` |

---

### **Fase 4: Busca Semântica** (Prioridade: MÉDIA)

#### 4.1 Implementar Busca
```
Objetivo: Buscar em todas as sessões do usuário por significado
```

**Endpoint:** `POST /api/search/semantic`

**Request:**
```json
{
  "query": "reunião sobre marketing digital",
  "limit": 10,
  "min_similarity": 0.7
}
```

**Response:**
```json
{
  "results": [
    {
      "session_id": "uuid",
      "block_id": "uuid", 
      "content": "Discutimos estratégias de marketing digital...",
      "similarity": 0.89,
      "block_type": "voice",
      "created_at": "2025-12-21T15:00:00Z"
    }
  ],
  "total": 1
}
```

**UI Sugerida:**
```
┌────────────────────────────────────┐
│ 🔍 [    Buscar memórias...     ]  │
├────────────────────────────────────┤
│ 📝 Resultado 1 (89% relevância)   │
│    "Discutimos estratégias de..." │
│    🕐 21/12/2025 • 📍 Reunião     │
├────────────────────────────────────┤
│ 📝 Resultado 2 (75% relevância)   │
│    "O cliente mencionou que..."    │
│    🕐 20/12/2025 • 🎤 Voz         │
└────────────────────────────────────┘
```

---

### **Fase 5: Monetização** (Prioridade: MÉDIA)

#### 5.1 Sistema de Créditos

**Modelo de Negócio:**
- Trial: 3 créditos gratuitos
- Cada sessão com AI consome 1 crédito
- Sessões sem AI (RAW_ONLY) são gratuitas

**UI de Créditos:**
```
┌────────────────────────────────────┐
│ 💎 Seus Créditos: 7               │
├────────────────────────────────────┤
│  [ Comprar 10 créditos - R$9,90 ] │
│  [ Comprar 50 créditos - R$39,90] │
│  [ Comprar 100 créditos - R$69,90]│
└────────────────────────────────────┘
```

#### 5.2 Integração com Stripe (Futuro)

O backend já possui webhook configurado para Stripe.

**Fluxo:**
1. App abre checkout Stripe
2. Usuário paga
3. Stripe envia webhook para backend
4. Backend credita automaticamente
5. App atualiza saldo via `GET /api/me/credits`

---

## 🔧 Implementação Técnica

### Estado do App (Sugestão)

```typescript
interface AppState {
  // Auth
  user: {
    firebaseUid: string;
    email: string;
    token: string;
    tokenExpiry: Date;
  } | null;
  
  // Credits
  credits: number;
  
  // Active Session
  currentSession: {
    id: string;
    type: 'voice' | 'image' | 'mixed';
    status: 'OPEN' | 'PENDING_AI' | 'PROCESSED' | 'RAW_ONLY';
    blocks: Block[];
    pendingUploads: Upload[];
  } | null;
  
  // Search
  searchResults: SearchResult[];
  
  // Sync
  syncStatus: 'idle' | 'syncing' | 'error';
  pendingOperations: Operation[];
}
```

### Offline-First Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                    OFFLINE QUEUE                             │
├─────────────────────────────────────────────────────────────┤
│ 1. Capturar dados localmente                                │
│ 2. Armazenar em SQLite/Realm local                         │
│ 3. Quando online:                                           │
│    a. Criar sessão via API                                  │
│    b. Upload arquivos para R2                               │
│    c. Enviar blocos                                         │
│    d. Finalizar sessão                                      │
│ 4. Marcar como sincronizado                                 │
└─────────────────────────────────────────────────────────────┘
```

### Retry Strategy

```typescript
const retryConfig = {
  maxRetries: 3,
  backoff: 'exponential', // 1s, 2s, 4s
  retryOn: [408, 429, 500, 502, 503, 504],
  timeout: 30000 // 30s
};
```

---

## 📱 Telas Necessárias

### MVP (Mínimo Viável)

| # | Tela | Descrição | Prioridade |
|---|------|-----------|------------|
| 1 | **Login** | Firebase Auth | CRÍTICA |
| 2 | **Home** | Lista de sessões + créditos | CRÍTICA |
| 3 | **Captura** | Gravação de áudio/fotos | CRÍTICA |
| 4 | **Sessão** | Detalhes de uma sessão | ALTA |
| 5 | **Busca** | Busca semântica | ALTA |
| 6 | **Perfil** | Créditos + configurações | MÉDIA |

### Fluxo de Navegação

```
          ┌──────────────┐
          │    Login     │
          └──────┬───────┘
                 │
          ┌──────▼───────┐
    ┌─────│     Home     │─────┐
    │     └──────┬───────┘     │
    │            │             │
┌───▼───┐  ┌─────▼─────┐  ┌────▼────┐
│Captura│  │   Busca   │  │ Perfil  │
└───┬───┘  └───────────┘  └─────────┘
    │
┌───▼───┐
│Sessão │
│Ativa  │
└───────┘
```

---

## 🔐 Segurança

### Token Management

```typescript
// Renovar token antes de expirar
async function ensureValidToken(): Promise<string> {
  const currentUser = firebase.auth().currentUser;
  if (!currentUser) throw new Error('Not authenticated');
  
  // Force refresh se expirar em < 5 minutos
  const forceRefresh = tokenExpiresIn() < 5 * 60 * 1000;
  return await currentUser.getIdToken(forceRefresh);
}
```

### Secure Storage

| Plataforma | Solução |
|------------|---------|
| iOS | Keychain Services |
| Android | EncryptedSharedPreferences |
| Flutter | flutter_secure_storage |
| React Native | react-native-keychain |

---

## 🧪 Testes Recomendados

### Test Cases Essenciais

1. **Auth Flow**
   - [ ] Login com email/senha
   - [ ] Token refresh automático
   - [ ] Logout limpa dados

2. **Session Flow**
   - [ ] Criar sessão
   - [ ] Adicionar múltiplos blocos
   - [ ] Finalizar com créditos
   - [ ] Finalizar sem créditos

3. **Upload Flow**
   - [ ] Gerar URL presigned
   - [ ] Upload direto para R2
   - [ ] Confirmar upload
   - [ ] Retry em caso de falha

4. **Search Flow**
   - [ ] Busca retorna resultados
   - [ ] Busca sem resultados
   - [ ] Navegação para sessão

5. **Offline**
   - [ ] Captura funciona offline
   - [ ] Sincroniza ao reconectar
   - [ ] Não perde dados

---

## 📊 Métricas e Logs

### Eventos para Analytics

```typescript
// Eventos importantes para tracking
const events = {
  // Auth
  'user_login': { method: 'email' | 'google' },
  'user_logout': {},
  
  // Sessions
  'session_created': { type: string },
  'session_finalized': { blocks_count: number, with_ai: boolean },
  
  // Uploads
  'upload_started': { type: 'audio' | 'image', size: number },
  'upload_completed': { duration_ms: number },
  'upload_failed': { error: string },
  
  // Search
  'search_performed': { query_length: number, results_count: number },
  
  // Monetization
  'credits_viewed': { current_balance: number },
  'purchase_initiated': { credits: number, price: number }
};
```

---

## 🚀 Checklist de Lançamento

### Pré-Launch

- [ ] Firebase configurado (iOS + Android)
- [ ] API client implementado
- [ ] Auth flow completo
- [ ] Fluxo de sessão funcional
- [ ] Upload de arquivos funcionando
- [ ] Busca implementada
- [ ] Offline mode básico
- [ ] Error handling robusto
- [ ] Analytics configurado

### Launch

- [ ] Testes com usuários reais
- [ ] Performance otimizada
- [ ] Crash reporting (Crashlytics/Sentry)
- [ ] App Store / Play Store ready

### Pós-Launch

- [ ] Monitorar métricas
- [ ] Coletar feedback
- [ ] Iterar features

---

## 📞 Contato e Suporte

**API Documentation:** http://localhost:8000/docs (Swagger UI)

**Erros Comuns:**

| Código | Significado | Ação |
|--------|-------------|------|
| 401 | Token inválido | Renovar token Firebase |
| 403 | Não autorizado | Verificar Firebase UID |
| 404 | Recurso não encontrado | Verificar IDs |
| 422 | Dados inválidos | Verificar payload |
| 500 | Erro interno | Reportar ao backend |

---

*Última atualização: Dezembro 2025*



