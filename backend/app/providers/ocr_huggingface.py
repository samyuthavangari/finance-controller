from typing import Any

import httpx

from app.config.settings import settings
from app.providers.base import OCRProvider


class HuggingFaceOCRProvider(OCRProvider):
    """Provider OCR Vision Model (or other HF document model) via Inference API."""

    def ocr(self, image_bytes: bytes, mime: str = "image/png") -> dict[str, Any]:
        if not settings.hf_token:
            return {"text": "", "confidence": 0.0, "extra": {"error": "HF_TOKEN missing"}}
        url = f"https://router.huggingface.co/hf-inference/models/{settings.ocr_model}"
        headers = {
            "Authorization": f"Bearer {settings.hf_token}",
            "Content-Type": mime,
        }
        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(url, headers=headers, content=image_bytes)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            return {"text": "", "confidence": 0.0, "extra": {"error": str(exc)}}
        text = self._extract_text(data)
        return {"text": text, "confidence": 0.82 if text else 0.0, "extra": {"raw": data}}

    def _extract_text(self, data: Any) -> str:
        if isinstance(data, str):
            return data
        if isinstance(data, dict):
            for key in ("generated_text", "text", "result"):
                if key in data and isinstance(data[key], str):
                    return data[key]
            if "generated_text" in data:
                return str(data["generated_text"])
        if isinstance(data, list):
            parts = []
            for item in data:
                if isinstance(item, dict):
                    parts.append(item.get("generated_text") or item.get("text") or "")
                else:
                    parts.append(str(item))
            return "\n".join(p for p in parts if p)
        return str(data)
