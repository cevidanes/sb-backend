"""
DeepSeek provider implementation.
Uses DeepSeek API for embeddings and chat completions.
DeepSeek uses OpenAI-compatible API, so we can use OpenAI SDK.
"""
from typing import List, Dict, Any
import logging
import time
from openai import OpenAI
from app.ai.base import LLMProvider
from app.config import settings
from app.utils.metrics import (
    ai_provider_requests_total,
    ai_provider_failures_total,
    ai_provider_latency_seconds,
    ai_provider_tokens_total
)
from app.utils.logging import log_provider_request, log_provider_failure

logger = logging.getLogger(__name__)


class DeepSeekProvider(LLMProvider):
    """
    DeepSeek LLM provider implementation.
    
    Uses DeepSeek API (OpenAI-compatible) for:
    - Embeddings: deepseek-embedding (1536 dimensions)
    - Summaries: deepseek-chat (cheapest model)
    
    API keys are stored in environment variables and never exposed to clients.
    """
    
    def __init__(self):
        """Initialize DeepSeek provider with API key from settings."""
        self.api_key = settings.deepseek_api_key
        self.chat_model = "deepseek-chat"  # Cheapest DeepSeek model
        self.base_url = "https://api.deepseek.com"
        
        # Initialize OpenAI-compatible client for DeepSeek
        if self.api_key:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        else:
            self.client = None
    
    def is_configured(self) -> bool:
        """Check if DeepSeek API key is configured."""
        return bool(self.api_key)
    
    def embed(self, text: str) -> List[float]:
        """
        DeepSeek does NOT support embeddings API.
        
        This method will always raise an error. Use OpenAI for embeddings instead.
        Configure EMBEDDING_PROVIDER=openai and set OPENAI_API_KEY.
        
        Args:
            text: Input text to embed
            
        Raises:
            NotImplementedError: Always - DeepSeek doesn't support embeddings
        """
        raise NotImplementedError(
            "DeepSeek does NOT support embeddings API. "
            "Use OpenAI for embeddings by setting EMBEDDING_PROVIDER=openai "
            "and configuring OPENAI_API_KEY."
        )
    
    def summarize(self, blocks: List[Dict[str, Any]], language: str = "pt") -> str:
        """
        Generate enriched summary using DeepSeek chat completion.
        
        Returns a structured summary in markdown format with:
        - Key insights
        - Main topics
        - Action items (if any)
        - Important details
        
        Args:
            blocks: List of block dictionaries with text_content
            language: Language code (e.g., 'pt', 'en', 'es') for the output
            
        Returns:
            Enriched summary string in markdown format
            
        Raises:
            ValueError: If API key not configured
            Exception: If API call fails
        """
        if not self.is_configured() or not self.client:
            raise ValueError("DeepSeek API key not configured")
        
        # Extract text content from blocks
        text_contents = [
            block.get("text_content", "")
            for block in blocks
            if block.get("text_content")
        ]
        
        if not text_contents:
            return "No text content available for summary."
        
        # Combine text content (limit to reasonable length)
        combined_text = "\n\n".join(text_contents)
        
        # Truncate if too long (to avoid token limits and costs)
        max_chars = 8000  # Reasonable limit
        if len(combined_text) > max_chars:
            combined_text = combined_text[:max_chars] + "... [truncated]"
            logger.warning(f"Text truncated to {max_chars} characters for summary")
        
        # Map language code to language name for prompts
        language_map = {
            "pt": "português brasileiro",
            "en": "English",
            "es": "español",
        }
        language_name = language_map.get(language[:2].lower(), "português brasileiro")
        
        # Build prompts based on language
        if language[:2].lower() == "en":
            system_prompt = """You are an assistant specialized in creating enriched and structured summaries of voice notes and transcriptions.

Your goal is to transform raw text into a useful and organized summary.

Rules:
1. Always respond in English
2. Use markdown for formatting
3. Be concise but informative
4. Extract insights and key points
5. Identify actions or tasks mentioned
6. Highlight names, dates, and important values"""
            user_prompt = f"""Create an enriched summary of the following content:

---
{combined_text}
---

Structure the summary like this:

## 📌 Summary
[2-3 sentences summarizing the main content]

## 💡 Key Points
- [point 1]
- [point 2]
- [etc...]

## ✅ Actions/Tasks
[List tasks or actions mentioned, or write "No actions identified"]

## 📝 Important Details
[Names, dates, values, or specific information mentioned]"""
        elif language[:2].lower() == "es":
            system_prompt = """Eres un asistente especializado en crear resúmenes enriquecidos y estructurados de notas de voz y transcripciones.

Tu objetivo es transformar texto bruto en un resumen útil y organizado.

Reglas:
1. Responde SIEMPRE en español
2. Usa markdown para formatear
3. Sé conciso pero informativo
4. Extrae insights y puntos clave
5. Identifica acciones o tareas mencionadas
6. Destaca nombres, fechas y valores importantes"""
            user_prompt = f"""Crea un resumen enriquecido del siguiente contenido:

---
{combined_text}
---

Estructura el resumen así:

## 📌 Resumen
[2-3 frases resumiendo el contenido principal]

## 💡 Puntos Clave
- [punto 1]
- [punto 2]
- [etc...]

## ✅ Acciones/Tareas
[Lista tareas o acciones mencionadas, o escribe "Ninguna acción identificada"]

## 📝 Detalles Importantes
[Nombres, fechas, valores, o información específica mencionada]"""
        else:  # Default to Portuguese
            system_prompt = """Você é um assistente especializado em criar resumos enriquecidos e estruturados de notas de voz e transcrições.

Seu objetivo é transformar texto bruto em um resumo útil e organizado.

Regras:
1. Responda SEMPRE em português brasileiro
2. Use markdown para formatação
3. Seja conciso mas informativo
4. Extraia insights e pontos-chave
5. Identifique ações ou tarefas mencionadas
6. Destaque nomes, datas e valores importantes"""
            user_prompt = f"""Crie um resumo enriquecido do seguinte conteúdo:

---
{combined_text}
---

Estruture o resumo assim:

## 📌 Resumo
[2-3 frases resumindo o conteúdo principal]

## 💡 Pontos-Chave
- [ponto 1]
- [ponto 2]
- [etc...]

## ✅ Ações/Tarefas
[Liste tarefas ou ações mencionadas, ou escreva "Nenhuma ação identificada"]

## 📝 Detalhes Importantes
[Nomes, datas, valores, ou informações específicas mencionadas]"""
        
        start_time = time.time()
        ai_provider_requests_total.labels(provider="deepseek", operation="summarize").inc()
        
        try:
            # Call DeepSeek chat completion API with enriched summary prompt
            response = self.client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                temperature=0.3,
                max_tokens=800
            )
            
            summary = response.choices[0].message.content
            duration = time.time() - start_time
            ai_provider_latency_seconds.labels(provider="deepseek", operation="summarize").observe(duration)
            
            # Extract token usage
            if hasattr(response, 'usage') and response.usage:
                if hasattr(response.usage, 'prompt_tokens'):
                    ai_provider_tokens_total.labels(
                        provider="deepseek",
                        operation="summarize",
                        token_type="prompt"
                    ).inc(response.usage.prompt_tokens)
                if hasattr(response.usage, 'completion_tokens'):
                    ai_provider_tokens_total.labels(
                        provider="deepseek",
                        operation="summarize",
                        token_type="completion"
                    ).inc(response.usage.completion_tokens)
            
            # Structured logging
            log_provider_request(
                logger,
                provider="deepseek",
                operation="summarize",
                duration_ms=duration * 1000
            )
            
            return summary
            
        except Exception as e:
            duration = time.time() - start_time
            ai_provider_failures_total.labels(provider="deepseek", operation="summarize").inc()
            ai_provider_latency_seconds.labels(provider="deepseek", operation="summarize").observe(duration)
            
            # Structured logging
            log_provider_failure(
                logger,
                provider="deepseek",
                operation="summarize",
                error=str(e),
                duration_ms=duration * 1000
            )
            
            raise Exception(f"Failed to generate DeepSeek summary: {str(e)}")
    
    def generate_title(self, text: str, language: str = "pt") -> str:
        """
        Generate a concise, descriptive title for the content.
        
        Args:
            text: The content to generate a title for
            language: Language code (e.g., 'pt', 'en', 'es') for the output
            
        Returns:
            A short, descriptive title (max 60 chars)
            
        Raises:
            ValueError: If API key not configured
            Exception: If API call fails
        """
        if not self.is_configured() or not self.client:
            raise ValueError("DeepSeek API key not configured")
        
        # Truncate input if too long
        max_chars = 2000
        truncated_text = text[:max_chars] if len(text) > max_chars else text
        
        # Build prompts based on language
        if language[:2].lower() == "en":
            system_prompt = """You generate short, descriptive titles for voice notes.

Rules:
1. Maximum 60 characters
2. English
3. No quotes or final punctuation
4. Capture the essence of the content
5. Be specific, not generic"""
            user_prompt = f"Create a short title for:\n\n{truncated_text}"
        elif language[:2].lower() == "es":
            system_prompt = """Generas títulos cortos y descriptivos para notas de voz.

Reglas:
1. Máximo 60 caracteres
2. Español
3. Sin comillas o puntuación final
4. Captura la esencia del contenido
5. Sé específico, no genérico"""
            user_prompt = f"Crea un título corto para:\n\n{truncated_text}"
        else:  # Default to Portuguese
            system_prompt = """Você gera títulos curtos e descritivos para notas de voz.

Regras:
1. Máximo 60 caracteres
2. Português brasileiro
3. Sem aspas ou pontuação final
4. Capture a essência do conteúdo
5. Seja específico, não genérico"""
            user_prompt = f"Crie um título curto para:\n\n{truncated_text}"
        
        start_time = time.time()
        ai_provider_requests_total.labels(provider="deepseek", operation="generate_title").inc()
        
        try:
            response = self.client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                temperature=0.5,
                max_tokens=30
            )
            
            title = response.choices[0].message.content.strip()
            # Remove quotes if present
            title = title.strip('"\'')
            # Truncate to 60 chars
            if len(title) > 60:
                title = title[:57] + "..."
            
            duration = time.time() - start_time
            ai_provider_latency_seconds.labels(provider="deepseek", operation="generate_title").observe(duration)
            
            # Extract token usage
            if hasattr(response, 'usage') and response.usage:
                if hasattr(response.usage, 'prompt_tokens'):
                    ai_provider_tokens_total.labels(
                        provider="deepseek",
                        operation="generate_title",
                        token_type="prompt"
                    ).inc(response.usage.prompt_tokens)
                if hasattr(response.usage, 'completion_tokens'):
                    ai_provider_tokens_total.labels(
                        provider="deepseek",
                        operation="generate_title",
                        token_type="completion"
                    ).inc(response.usage.completion_tokens)
            
            # Structured logging
            log_provider_request(
                logger,
                provider="deepseek",
                operation="generate_title",
                duration_ms=duration * 1000
            )
            
            return title
            
        except Exception as e:
            duration = time.time() - start_time
            ai_provider_failures_total.labels(provider="deepseek", operation="generate_title").inc()
            ai_provider_latency_seconds.labels(provider="deepseek", operation="generate_title").observe(duration)
            
            # Structured logging
            log_provider_failure(
                logger,
                provider="deepseek",
                operation="generate_title",
                error=str(e),
                duration_ms=duration * 1000
            )
            
            raise Exception(f"Failed to generate title: {str(e)}")

