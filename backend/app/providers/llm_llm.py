from google import genai
from google.genai import types

from app.config.settings import settings
from app.providers.base import LLMProvider


class LLMLLMProvider(LLMProvider):
    def __init__(self) -> None:
        self._client = None
        if settings.llm_api_key:
            self._client = genai.Client(api_key=settings.llm_api_key)

    def _ensure(self):
        if not self._client:
            raise RuntimeError("LLM_API_KEY is not configured")
        return self._client

    def generate(self, prompt: str, system: str | None = None, json_mode: bool = False) -> str:
        client = self._ensure()
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json" if json_mode else None,
            temperature=0.1,
        )
        resp = client.models.generate_content(
            model=settings.llm_model,
            contents=prompt,
            config=config,
        )
        return resp.text or ""

    def generate_vision(self, prompt: str, image_bytes: bytes, mime: str) -> str:
        client = self._ensure()
        part = types.Part.from_bytes(data=image_bytes, mime_type=mime)
        resp = client.models.generate_content(
            model=settings.llm_vision_model,
            contents=[prompt, part],
            config=types.GenerateContentConfig(temperature=0.1),
        )
        return resp.text or ""
