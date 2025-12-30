"""
OpenAI provider implementation.
Uses OpenAI SDK for embeddings and chat completions.
Uses cheapest models: text-embedding-3-small and gpt-3.5-turbo.
"""
from typing import List, Dict, Any
import logging
from openai import OpenAI
from app.ai.base import LLMProvider
from app.config import settings

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """
    OpenAI LLM provider implementation.
    
    Uses OpenAI API for:
    - Embeddings: text-embedding-3-small (cheapest, 1536 dimensions)
    - Summaries: gpt-3.5-turbo (cheapest chat model)
    
    API keys are stored in environment variables and never exposed to clients.
    """
    
    def __init__(self):
        """Initialize OpenAI provider with API key from settings."""
        self.api_key = settings.openai_api_key
        # Use configurable embedding model (default: text-embedding-3-small)
        self.embedding_model = settings.openai_embedding_model
        self.chat_model = "gpt-3.5-turbo"  # Cheapest chat model
        self.embedding_dimension = 1536  # Standard dimension for OpenAI embeddings
        
        # Initialize OpenAI client
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None
    
    def is_configured(self) -> bool:
        """Check if OpenAI API key is configured."""
        return bool(self.api_key)
    
    def embed(self, text: str) -> List[float]:
        """
        Generate embedding using OpenAI API.
        
        Args:
            text: Input text to embed
            
        Returns:
            1536-dimensional embedding vector
            
        Raises:
            ValueError: If API key not configured
            Exception: If API call fails
        """
        if not self.is_configured() or not self.client:
            raise ValueError("OpenAI API key not configured")
        
        try:
            # Call OpenAI embeddings API
            # Note: dimensions parameter not needed, model default is 1536
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            
            embedding = response.data[0].embedding
            logger.debug(f"Generated OpenAI embedding for text (length: {len(text)})")
            return embedding
            
        except Exception as e:
            logger.error(f"OpenAI embedding API error: {e}")
            raise Exception(f"Failed to generate OpenAI embedding: {str(e)}")
    
    def summarize(self, blocks: List[Dict[str, Any]], language: str = "pt") -> str:
        """
        Generate enriched summary using OpenAI chat completion.
        
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
            raise ValueError("OpenAI API key not configured")
        
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
        max_chars = 8000  # Reasonable limit for gpt-3.5-turbo
        if len(combined_text) > max_chars:
            combined_text = combined_text[:max_chars] + "... [truncated]"
            logger.warning(f"Text truncated to {max_chars} characters for summary")
        
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
        
        try:
            # Call OpenAI chat completion API with enriched summary prompt
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
            logger.info(f"Generated OpenAI enriched summary (length: {len(summary)})")
            return summary
            
        except Exception as e:
            logger.error(f"OpenAI chat completion API error: {e}")
            raise Exception(f"Failed to generate OpenAI summary: {str(e)}")
    
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
            raise ValueError("OpenAI API key not configured")
        
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
            
            logger.info(f"Generated OpenAI title: {title}")
            return title
            
        except Exception as e:
            logger.error(f"OpenAI title generation error: {e}")
            raise Exception(f"Failed to generate title: {str(e)}")

