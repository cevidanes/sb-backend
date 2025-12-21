# Insomnia Collection - Second Brain API

Esta coleção contém todos os endpoints da API Second Brain para testes no Insomnia.

## 📦 Instalação

1. Abra o Insomnia
2. Clique em **Application** → **Preferences** → **Data** → **Import Data**
3. Selecione o arquivo `Insomnia_Collection.json`
4. A coleção será importada com todas as requisições organizadas

## 🔧 Configuração

### Variáveis de Ambiente

A coleção inclui duas variáveis de ambiente:

#### Base Environment (Local)
- `base_url`: `http://localhost:8000`
- `firebase_token`: Seu token JWT do Firebase
- `session_id`: ID da sessão (será preenchido após criar uma sessão)
- `user_id`: ID do usuário (será preenchido após autenticação)

#### Production Environment
- `base_url`: `https://api.secondbrain.com`
- `firebase_token`: Token JWT de produção
- `session_id`: ID da sessão
- `user_id`: ID do usuário

### Como Obter o Firebase Token

1. No seu app Flutter/mobile, faça login com Firebase
2. Obtenha o ID token:
   ```dart
   final user = FirebaseAuth.instance.currentUser;
   final token = await user?.getIdToken();
   ```
3. Copie o token e cole na variável `firebase_token` no Insomnia

## 📋 Endpoints Disponíveis

### 🏠 Root
- **GET /** - Informações da API

### ❤️ Health
- **GET /api/health** - Verifica saúde da API (database e Redis)

### 📝 Sessions
- **POST /api/sessions** - Criar nova sessão
- **POST /api/sessions/{session_id}/blocks** - Adicionar bloco de voz (voice)
- **POST /api/sessions/{session_id}/blocks** - Adicionar bloco de imagem (image)
- **POST /api/sessions/{session_id}/blocks** - Adicionar bloco marcador (marker)
- **POST /api/sessions/{session_id}/finalize** - Finalizar sessão e processar com AI

### 👤 User Profile
- **GET /api/me/credits** - Obter saldo de créditos AI

### 🔍 Search
- **POST /api/search/semantic** - Busca semântica completa
- **POST /api/search/semantic** - Busca semântica mínima (com defaults)

### 🔔 Webhooks
- **POST /api/webhooks/stripe** - Webhook do Stripe para créditos

## 🚀 Fluxo de Teste Recomendado

### 1. Verificar Saúde da API
```
GET /api/health
```
Deve retornar status `healthy` com database e Redis conectados.

### 2. Criar uma Sessão
```
POST /api/sessions
Body: {
  "session_type": "voice"
}
```
Copie o `session_id` da resposta e atualize a variável `session_id` no Insomnia.

### 3. Adicionar Blocos
```
POST /api/sessions/{session_id}/blocks
Body: {
  "block_type": "voice",
  "text_content": "Seu texto aqui..."
}
```
Tipos de blocos disponíveis:
- `voice`: Transcrição de áudio/voz
- `image`: Imagem com URL
- `marker`: Marcador/nota de anotação

Adicione quantos blocos quiser antes de finalizar.

### 4. Verificar Créditos
```
GET /api/me/credits
```
Verifique se você tem créditos suficientes (>= 1) para processamento AI.

### 5. Finalizar Sessão
```
POST /api/sessions/{session_id}/finalize
```
Isso irá:
- Debitar 1 crédito (se disponível)
- Enfileirar processamento AI assíncrono
- Retornar status da sessão

### 6. Buscar Semanticamente
```
POST /api/search/semantic?query=seu termo de busca&limit=10&threshold=0.7
```
Busque por conteúdo similar nas suas sessões processadas.

## 📝 Exemplos de Payloads

### Criar Sessão
```json
{
  "session_type": "voice"
}
```

### Adicionar Bloco de Voz (Voice)
```json
{
  "block_type": "voice",
  "text_content": "Reunião de equipe: discutimos o cronograma do projeto e decidimos mover o prazo para frente em duas semanas.",
  "metadata": null
}
```

### Adicionar Bloco de Imagem
```json
{
  "block_type": "image",
  "media_url": "https://example.com/image.jpg",
  "metadata": "{\"caption\": \"Diagrama do projeto\"}"
}
```

### Adicionar Bloco Marcador (Marker)
```json
{
  "block_type": "marker",
  "text_content": "Marcador: ponto importante da reunião",
  "metadata": "{\"timestamp\": 300, \"importance\": \"high\"}"
}
```

## 🔐 Autenticação

Todos os endpoints (exceto `/api/health` e `/`) requerem autenticação Firebase JWT:

```
Authorization: Bearer YOUR_FIREBASE_JWT_TOKEN
```

Configure o token na variável de ambiente `firebase_token` para uso automático.

## ⚠️ Notas Importantes

1. **Webhook Stripe**: Requer assinatura válida do Stripe. O endpoint valida a assinatura usando `stripe-signature` header.

2. **Créditos**: Novos usuários recebem 3 créditos de trial automaticamente.

3. **Processamento Assíncrono**: Após finalizar uma sessão, o processamento AI acontece em background via Celery. Verifique os logs do worker para acompanhar.

4. **Busca Semântica**: Requer que as sessões tenham sido processadas com AI (ter embeddings gerados).

5. **Variáveis Dinâmicas**: Use `{{ _.session_id }}` e `{{ _.user_id }}` nas URLs para referenciar valores das variáveis de ambiente.

## 🐛 Troubleshooting

### Erro 401 Unauthorized
- Verifique se o token Firebase está válido e não expirou
- Confirme que o token está configurado na variável `firebase_token`

### Erro 400 Bad Request
- Verifique o formato do JSON no body
- Confirme que a sessão está no status `open` antes de adicionar blocos
- Verifique se a sessão pertence ao usuário autenticado

### Erro 503 Service Unavailable (Health Check)
- Verifique se PostgreSQL está rodando
- Verifique se Redis está rodando
- Confirme as configurações de conexão no `.env`

### Busca Semântica Retorna Vazio
- Verifique se há sessões processadas com embeddings
- Tente reduzir o `threshold` (ex: 0.5)
- Confirme que as sessões foram finalizadas com créditos disponíveis

## 📚 Documentação Adicional

- [FastAPI Docs](http://localhost:8000/docs) - Documentação interativa da API
- [OpenAPI Schema](http://localhost:8000/openapi.json) - Schema OpenAPI completo

