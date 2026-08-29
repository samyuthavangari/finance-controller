from __future__ import annotations

from io import BytesIO
from pathlib import Path
from time import perf_counter

import pdfplumber
from pypdf import PdfReader

from app.config.policy import policy
from app.core.ids import new_id
from app.providers import get_llm, get_ocr
from app.schemas.finance import InvoiceExtraction


def extract_pdf_text(data: bytes) -> str:
    try:
        with pdfplumber.open(BytesIO(data)) as pdf:
            texts = [(p.extract_text() or "") for p in pdf.pages]
            joined = "\n".join(texts).strip()
            if joined:
                return joined
    except Exception:
        pass
    try:
        reader = PdfReader(BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in reader.pages).strip()
    except Exception:
        return ""


def pdf_page_images(data: bytes) -> list[bytes]:
    """Best-effort rasterization is optional; return empty if unavailable."""
    try:
        from pdf2image import convert_from_bytes

        images = convert_from_bytes(data, dpi=150)
        out = []
        for im in images[:8]:
            buf = BytesIO()
            im.save(buf, format="PNG")
            out.append(buf.getvalue())
        return out
    except Exception:
        return []


def route_and_extract(filename: str, data: bytes, mime: str) -> dict:
    started = perf_counter()
    ext = Path(filename).suffix.lower()
    text = ""
    method = "none"
    confidence = 0.0
    extra: dict = {}

    if ext in {".txt", ".csv", ".json"}:
        text = data.decode("utf-8", errors="replace")
        method = "native_text"
        confidence = 0.99
    elif ext == ".pdf" or mime == "application/pdf":
        text = extract_pdf_text(data)
        if len(text) >= policy.min_text_chars:
            method = "pdf_text"
            confidence = 0.93
        else:
            method = "ocr"
            ocr = get_ocr()
            pages = pdf_page_images(data)
            if pages:
                parts = []
                confs = []
                for img in pages:
                    r = ocr.ocr(img, "image/png")
                    parts.append(r.get("text") or "")
                    confs.append(float(r.get("confidence") or 0))
                text = "\n".join(parts)
                confidence = sum(confs) / len(confs) if confs else 0.0
                extra["ocr"] = True
            else:
                r = ocr.ocr(data, "application/pdf")
                text = r.get("text") or ""
                confidence = float(r.get("confidence") or 0)
                extra["ocr_direct_pdf"] = True
            if confidence < policy.vision_fallback_confidence and len(text) < policy.min_text_chars:
                try:
                    llm = get_llm()
                    vision = pages[0] if pages else data
                    text = llm.generate_vision(
                        "Extract all visible invoice/receipt text. Do not invent amounts.",
                        vision,
                        "image/png" if pages else mime,
                    )
                    method = "vision_fallback"
                    confidence = 0.5
                    extra["vision"] = True
                except Exception as exc:
                    extra["vision_error"] = str(exc)
    elif ext in {".png", ".jpg", ".jpeg", ".webp"} or (mime or "").startswith("image/"):
        method = "ocr"
        r = get_ocr().ocr(data, mime or "image/png")
        text = r.get("text") or ""
        confidence = float(r.get("confidence") or 0)
        extra["ocr"] = r.get("extra")
        if confidence < policy.vision_fallback_confidence:
            try:
                text = get_llm().generate_vision(
                    "Extract all visible invoice/receipt text. Do not invent amounts.",
                    data,
                    mime or "image/png",
                )
                method = "vision_fallback"
                confidence = max(confidence, 0.5)
            except Exception as exc:
                extra["vision_error"] = str(exc)
    elif ext == ".mp4":
        method = "video_frames_unsupported_without_ffmpeg"
        extra["note"] = "Video OCR requires ffmpeg frame extract; skipped in this run"
        confidence = 0.0
    else:
        method = "unsupported"

    duration_ms = int((perf_counter() - started) * 1000)
    return {
        "id": new_id("EXT"),
        "method": method,
        "raw_text": text,
        "confidence": confidence,
        "duration_ms": duration_ms,
        "extra": extra,
        "status": "ok" if text else "failed",
    }


def parse_invoice_from_text(text: str, confidence: float) -> InvoiceExtraction | None:
    """Layout-light structured parse for synthetic invoices; fails closed."""
    import re
    from datetime import datetime
    from decimal import Decimal, InvalidOperation

    def grab(label: str) -> str | None:
        m = re.search(rf"^(?:{label})\s*[:\-]\s*(.+)$", text, re.I | re.M)
        return m.group(1).strip() if m else None

    def num(s: str | None) -> Decimal | None:
        if not s:
            return None
        s = re.sub(r"[^\d.\-]", "", s)
        try:
            return Decimal(s)
        except (InvalidOperation, ValueError):
            return None

    def dt(s: str | None):
        if not s:
            return None
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(s.strip()[:10], fmt).date()
            except ValueError:
                continue
        return None

    total = num(grab("Total") or grab("Invoice Total") or grab("Amount"))
    subtotal = num(grab("Subtotal") or grab("Sub-total"))
    tax = num(grab("Tax") or grab("GST") or grab("VAT"))
    if total is None:
        return None
    if subtotal is None and tax is not None:
        subtotal = total - tax
    if tax is None and subtotal is not None:
        tax = total - subtotal
    if subtotal is None:
        subtotal = total
        tax = Decimal("0.00")
    items = []
    for line in text.splitlines():
        if line.strip().startswith("ITEM"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4:
                amt = num(parts[-1])
                if amt is not None:
                    items.append(
                        {
                            "description": parts[1] if len(parts) > 1 else "item",
                            "quantity": Decimal("1"),
                            "unit_price": amt,
                            "amount": amt,
                        }
                    )
    extraction = InvoiceExtraction(
        invoice_number=grab("Invoice Number") or grab("Invoice"),
        vendor_name=grab("Vendor") or grab("From"),
        invoice_date=dt(grab("Invoice Date") or grab("Date")),
        due_date=dt(grab("Due Date")),
        currency=grab("Currency") or "INR",
        subtotal=subtotal,
        tax_amount=tax or Decimal("0"),
        total_amount=total,
        payment_reference=grab("Payment Ref") or grab("Reference"),
        bank_account=grab("Bank"),
        line_items=items,
        extraction_confidence=confidence,
    )
    extraction.validate_totals()
    return extraction
