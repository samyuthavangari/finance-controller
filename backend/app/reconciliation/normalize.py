import re
import unicodedata


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    s = unicodedata.normalize("NFKC", value)
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


VENDOR_ALIASES = {
    "aws": "amazon web services",
    "amazon web services india pvt ltd": "amazon web services",
    "amazon web services": "amazon web services",
    "msft": "microsoft",
    "microsoft india": "microsoft",
    "gcp": "google cloud",
    "google cloud platform": "google cloud",
}


def canonical_vendor(name: str) -> str:
    n = normalize_text(name)
    return VENDOR_ALIASES.get(n, n)


def normalize_ref(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]", "", value.lower())
