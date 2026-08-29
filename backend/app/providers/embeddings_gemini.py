from google import genai

from app.config.settings import settings
from app.providers.base import EmbeddingProvider


class GeminiEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        self._client = None
        if settings.gemini_api_key:
            self._client = genai.Client(api_key=settings.gemini_api_key)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self._client:
            # Deterministic hash embedding so indexing/demo works without a key
            return [self._hash_embed(t) for t in texts]
        out: list[list[float]] = []
        for text in texts:
            resp = self._client.models.embed_content(
                model=settings.embedding_model,
                contents=text,
            )
            out.append(list(resp.embeddings[0].values))
        return out

    def _hash_embed(self, text: str, dim: int = 64) -> list[float]:
        vec = [0.0] * dim
        for i, ch in enumerate(text.encode("utf-8")):
            vec[i % dim] += (ch / 255.0) * 0.01
        n = sum(v * v for v in vec) ** 0.5 or 1.0
        return [v / n for v in vec]
