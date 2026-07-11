"""
OpenAI Client for the Personal Assistant Bot.
Provides methods for text generation, vision, STT, TTS, and DALL-E image generation.
"""

import json
from datetime import datetime
from typing import List, Dict, Optional, Any
from openai import AsyncOpenAI
from pathlib import Path

import aiofiles
import aiohttp

from config import (
    PROXYAPI_KEY,
    PROXYAPI_OPENAI_URL,
    GPT_MODEL,
    WHISPER_MODEL,
    TTS_MODEL,
    VISION_MODEL,
    DALLE_MODEL,
    DALLE_DEFAULT_SIZE,
    DALLE_DEFAULT_QUALITY,
    DALLE_DEFAULT_STYLE,
    DATA_DIR,
    TEMPERATURE,
    MAX_TOKENS,
)
from utils.logging import logger


GENERATED_IMAGES_DIR = DATA_DIR / "generated_images"
GENERATED_IMAGES_DIR.mkdir(exist_ok=True)


class OpenAIClient:
    """Async client for OpenAI-compatible API via ProxyAPI."""

    def __init__(self):
        """Initialize the client with ProxyAPI endpoint."""
        self.client = AsyncOpenAI(
            api_key=PROXYAPI_KEY,
            base_url=PROXYAPI_OPENAI_URL,
        )
        logger.info(f"ProxyAPI client initialized: {PROXYAPI_OPENAI_URL}")
    
    async def generate_text_response(
        self,
        messages: List[Dict[str, str]],
        model: str = GPT_MODEL,
        temperature: float = TEMPERATURE,
        max_tokens: int = MAX_TOKENS
    ) -> str:
        """
        Generate text response using GPT model.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            model: Model to use
            temperature: Response randomness (0-2)
            max_tokens: Maximum tokens in response
        
        Returns:
            Generated text response
        """
        try:
            logger.debug(f"Generating text response with {model}")
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            result = response.choices[0].message.content
            logger.info(f"Generated response: {len(result)} characters")
            return result
            
        except Exception as e:
            logger.error(f"Error generating text response: {e}")
            raise
    
    async def analyze_image(
        self,
        image_url: str,
        prompt: str = "Опиши это изображение подробно. Что ты видишь?",
        model: str = VISION_MODEL
    ) -> str:
        """
        Analyze an image using GPT-4 Vision.
        
        Args:
            image_url: URL or base64 encoded image
            prompt: Analysis prompt
            model: Vision model to use
        
        Returns:
            Image analysis result
        """
        try:
            logger.debug(f"Analyzing image with {model}")
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": image_url}
                            }
                        ]
                    }
                ],
                max_tokens=MAX_TOKENS
            )
            
            result = response.choices[0].message.content
            logger.info(f"Image analyzed: {len(result)} characters")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing image: {e}")
            raise
    
    async def transcribe_audio(
        self,
        audio_file_path: Path,
        model: str = WHISPER_MODEL
    ) -> str:
        """
        Transcribe audio file to text using Whisper.
        
        Args:
            audio_file_path: Path to audio file
            model: Whisper model to use
        
        Returns:
            Transcribed text
        """
        try:
            logger.debug(f"Transcribing audio: {audio_file_path}")
            
            with open(audio_file_path, "rb") as audio_file:
                response = await self.client.audio.transcriptions.create(
                    model=model,
                    file=audio_file,
                    response_format="json",
                )

            if isinstance(response, str):
                result = response
            elif hasattr(response, "text"):
                result = response.text
            elif isinstance(response, dict):
                result = response.get("text", "")
            else:
                result = str(response)

            logger.info(f"Audio transcribed: {len(result)} characters")
            return result
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            raise
    
    async def generate_speech(
        self,
        text: str,
        voice: str = "alloy",
        model: str = TTS_MODEL,
        output_path: Optional[Path] = None
    ) -> Path:
        """
        Generate speech from text using TTS.
        
        Args:
            text: Text to convert to speech
            voice: Voice to use (alloy, echo, nova, fable, onyx, shimmer)
            model: TTS model to use
            output_path: Path to save audio file
        
        Returns:
            Path to generated audio file
        """
        try:
            logger.debug(f"Generating speech with voice: {voice}")
            
            response = await self.client.audio.speech.create(
                model=model,
                voice=voice,
                input=text
            )
            
            # Default output path
            if output_path is None:
                from config import DATA_DIR
                import uuid
                output_path = DATA_DIR / f"tts_{uuid.uuid4()}.mp3"
            
            # Save audio to file
            response.stream_to_file(str(output_path))
            
            logger.info(f"Speech generated: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error generating speech: {e}")
            raise

    async def generate_image(
        self,
        prompt: str,
        size: str = DALLE_DEFAULT_SIZE,
        quality: str = DALLE_DEFAULT_QUALITY,
        style: str = DALLE_DEFAULT_STYLE
    ) -> Dict[str, Any]:
        """Generate an image using DALL-E via ProxyAPI."""
        try:
            logger.info(f"Generating image with DALL-E: {prompt[:100]}...")

            response = await self.client.images.generate(
                model=DALLE_MODEL,
                prompt=prompt,
                n=1,
                size=size,
                quality=quality,
                style=style,
            )

            image_data = response.data[0]
            image_url = image_data.url
            revised_prompt = getattr(image_data, "revised_prompt", None) or prompt
            image_path = await download_generated_image(image_url)

            return {
                "image_path": image_path,
                "revised_prompt": revised_prompt,
                "url": image_url,
                "original_prompt": prompt
            }

        except Exception as e:
            logger.error(f"Error generating image: {e}")
            raise


openai_client = OpenAIClient()


async def detect_image_generation_intent(
    text: str,
    conversation_history: list = None
) -> Dict[str, Any]:
    """Detect if user wants to generate an image."""
    strong_keywords = [
        'нарисуй', 'сгенерируй изображение', 'создай картинку', 'сделай изображение',
        'покажи как выглядит', 'визуализируй', 'generate image', 'draw',
        'create picture', 'сгенерируй картинку', 'создай изображение',
    ]
    text_lower = text.lower()
    has_strong_keyword = any(kw in text_lower for kw in strong_keywords)

    detection_prompt = f"""Определи, хочет ли пользователь сгенерировать изображение.
Запрос: "{text}"
Ответь JSON: {{"needs_generation": true/false, "prompt": "...", "confidence": 0.0-1.0}}"""

    try:
        response = await openai_client.generate_text_response(
            [{"role": "user", "content": detection_prompt}], temperature=0.3
        )
        response_clean = response.strip()
        if response_clean.startswith('```'):
            lines = response_clean.split('\n')
            response_clean = '\n'.join(lines[1:-1])
        result = json.loads(response_clean)

        if has_strong_keyword and not result.get('needs_generation'):
            result['needs_generation'] = True
            if not result.get('prompt'):
                result['prompt'] = text
        return result
    except Exception as e:
        logger.error(f"Error detecting image generation intent: {e}")
        if has_strong_keyword:
            return {"needs_generation": True, "prompt": text, "confidence": 0.8}
        return {"needs_generation": False, "confidence": 0.0}


async def generate_image(
    prompt: str,
    size: str = DALLE_DEFAULT_SIZE,
    quality: str = DALLE_DEFAULT_QUALITY,
    style: str = DALLE_DEFAULT_STYLE
) -> Dict[str, Any]:
    """Generate an image using the global OpenAI client."""
    return await openai_client.generate_image(prompt, size, quality, style)


async def download_generated_image(url: str) -> Path:
    """Download a generated image from URL."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = GENERATED_IMAGES_DIR / f"generated_{timestamp}.png"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise Exception(f"Failed to download image: {response.status}")
            async with aiofiles.open(filepath, 'wb') as f:
                await f.write(await response.read())
    logger.info(f"Image downloaded to: {filepath}")
    return filepath

