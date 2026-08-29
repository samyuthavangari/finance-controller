from app.config.settings import settings
from app.providers.base import EmbeddingProvider, LLMProvider, MatchingModel, OCRProvider
from app.providers.embeddings_gemini import GeminiEmbeddingProvider
from app.providers.llm_gemini import GeminiLLMProvider
from app.providers.matching_lgbm import LightGBMMatchingModel
from app.providers.ocr_huggingface import HuggingFaceOCRProvider


def get_llm() -> LLMProvider:
    if settings.llm_provider.lower() == "gemini":
        return GeminiLLMProvider()
    raise ValueError(f"Unsupported LLM_PROVIDER={settings.llm_provider}")


def get_embeddings() -> EmbeddingProvider:
    if settings.embedding_provider.lower() == "gemini":
        return GeminiEmbeddingProvider()
    raise ValueError(f"Unsupported EMBEDDING_PROVIDER={settings.embedding_provider}")


def get_ocr() -> OCRProvider:
    if settings.ocr_provider.lower() == "huggingface":
        return HuggingFaceOCRProvider()
    raise ValueError(f"Unsupported OCR_PROVIDER={settings.ocr_provider}")


_matching_model = None


def get_matching_model() -> MatchingModel:
    global _matching_model
    if _matching_model is None:
        _matching_model = LightGBMMatchingModel()
    return _matching_model
