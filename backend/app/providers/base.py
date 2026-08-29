from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, system: str | None = None, json_mode: bool = False) -> str:
        raise NotImplementedError

    @abstractmethod
    def generate_vision(self, prompt: str, image_bytes: bytes, mime: str) -> str:
        raise NotImplementedError


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class OCRProvider(ABC):
    @abstractmethod
    def ocr(self, image_bytes: bytes, mime: str = "image/png") -> dict[str, Any]:
        """Return {text, confidence, extra}."""
        raise NotImplementedError


class MatchingModel(ABC):
    @abstractmethod
    def predict_proba(self, features: dict[str, float]) -> float:
        raise NotImplementedError
