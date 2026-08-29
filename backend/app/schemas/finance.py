from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.config.policy import policy
from app.core.money import money


class LineItem(BaseModel):
    description: str
    quantity: Decimal = Decimal("1")
    unit_price: Decimal
    amount: Decimal

    @field_validator("unit_price", "amount", "quantity", mode="before")
    @classmethod
    def _dec(cls, v):
        return money(v) if v is not None else v


class InvoiceExtraction(BaseModel):
    invoice_number: str | None = None
    vendor_name: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    currency: str = "INR"
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    payment_reference: str | None = None
    bank_account: str | None = None
    line_items: list[LineItem] = Field(default_factory=list)
    extraction_confidence: float

    @field_validator("subtotal", "tax_amount", "total_amount", mode="before")
    @classmethod
    def _money(cls, v):
        return money(v)

    def validate_totals(self) -> None:
        if not self.line_items:
            expected = money(self.subtotal + self.tax_amount)
            if abs(expected - self.total_amount) > policy.line_item_tolerance:
                raise ValueError("EXTRACTION_ERROR: subtotal + tax != total")
            return
        lines = sum((li.amount for li in self.line_items), Decimal("0"))
        expected = money(lines + self.tax_amount)
        if abs(expected - self.total_amount) > policy.line_item_tolerance:
            raise ValueError("EXTRACTION_ERROR: sum(line_items) + tax != total")


class EvidenceItem(BaseModel):
    source: str
    id: str
    page: int | None = None
    section: str | None = None
    snippet: str | None = None


class AgentDecision(BaseModel):
    decision: str
    confidence: float
    reason_code: str
    reason: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    calculations: dict[str, str] = Field(default_factory=dict)
