from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.ids import utcnow
from app.db import Base

Money = Numeric(18, 2)
JSONType = JSON().with_variant(JSONB, "postgresql")


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    role: Mapped[str] = mapped_column(String(40), default="controller")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Vendor(Base):
    __tablename__ = "vendors"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    legal_name: Mapped[str] = mapped_column(String(255), index=True)
    aliases: Mapped[list] = mapped_column(JSONType, default=list)
    country: Mapped[str] = mapped_column(String(8), default="IN")
    tax_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bank_account: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=30)
    allowed_variance_pct: Mapped[Decimal] = mapped_column(Money, default=Decimal("2.00"))
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_tx_ref", "payment_reference"),
        Index("ix_tx_amount_ccy", "amount", "currency"),
    )
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    vendor_id: Mapped[str | None] = mapped_column(ForeignKey("vendors.id"), nullable=True, index=True)
    vendor_name_raw: Mapped[str] = mapped_column(String(255))
    amount: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(8), index=True)
    txn_date: Mapped[date] = mapped_column(Date, index=True)
    payment_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bank_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="ledger")
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[dict] = mapped_column(JSONType, default=dict)


class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    invoice_number: Mapped[str] = mapped_column(String(64), index=True)
    vendor_id: Mapped[str | None] = mapped_column(ForeignKey("vendors.id"), nullable=True, index=True)
    vendor_name_raw: Mapped[str] = mapped_column(String(255))
    invoice_date: Mapped[date] = mapped_column(Date, index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), index=True)
    subtotal: Mapped[Decimal] = mapped_column(Money)
    tax_amount: Mapped[Decimal] = mapped_column(Money)
    total_amount: Mapped[Decimal] = mapped_column(Money, index=True)
    payment_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bank_account: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    extraction_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    extra: Mapped[dict] = mapped_column(JSONType, default=dict)
    line_items: Mapped[list["InvoiceLineItem"]] = relationship(back_populates="invoice")


class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), index=True)
    description: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("1"))
    unit_price: Mapped[Decimal] = mapped_column(Money)
    amount: Mapped[Decimal] = mapped_column(Money)
    invoice: Mapped[Invoice] = relationship(back_populates="line_items")


class Settlement(Base):
    __tablename__ = "settlements"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    vendor_id: Mapped[str | None] = mapped_column(ForeignKey("vendors.id"), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Money, index=True)
    currency: Mapped[str] = mapped_column(String(8))
    settlement_date: Mapped[date] = mapped_column(Date, index=True)
    payment_reference: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    invoice_id: Mapped[str | None] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    transaction_id: Mapped[str | None] = mapped_column(ForeignKey("transactions.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="posted")
    extra: Mapped[dict] = mapped_column(JSONType, default=dict)


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    account: Mapped[str] = mapped_column(String(64), index=True)
    vendor_id: Mapped[str | None] = mapped_column(ForeignKey("vendors.id"), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(8))
    entry_date: Mapped[date] = mapped_column(Date, index=True)
    direction: Mapped[str] = mapped_column(String(8))
    reference: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="posted", index=True)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    document_type: Mapped[str] = mapped_column(String(64), index=True)
    vendor_id: Mapped[str | None] = mapped_column(ForeignKey("vendors.id"), nullable=True, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(512))
    mime_type: Mapped[str] = mapped_column(String(128))
    country: Mapped[str] = mapped_column(String(8), default="IN")
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DocumentExtraction(Base):
    __tablename__ = "document_extractions"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    method: Mapped[str] = mapped_column(String(64))
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured: Mapped[dict] = mapped_column(JSONType, default=dict)
    confidence: Mapped[float] = mapped_column(Numeric(6, 4), default=0)
    status: Mapped[str] = mapped_column(String(32), default="ok")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    records_total: Mapped[int] = mapped_column(Integer, default=0)
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    counters: Mapped[dict] = mapped_column(JSONType, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost: Mapped[dict] = mapped_column(JSONType, default=dict)


class ReconciliationResult(Base):
    __tablename__ = "reconciliation_results"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("reconciliation_runs.id"), index=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id"), index=True)
    invoice_id: Mapped[str | None] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    settlement_id: Mapped[str | None] = mapped_column(ForeignKey("settlements.id"), nullable=True)
    match_level: Mapped[str] = mapped_column(String(16))
    match_score: Mapped[float] = mapped_column(Numeric(8, 6), default=0)
    decision: Mapped[str] = mapped_column(String(32), index=True)
    confidence: Mapped[float] = mapped_column(Numeric(8, 6), default=0)
    reason_code: Mapped[str] = mapped_column(String(64))
    why: Mapped[dict] = mapped_column(JSONType, default=dict)
    candidate_invoice_ids: Mapped[list] = mapped_column(JSONType, default=list)


class ExceptionRecord(Base):
    __tablename__ = "exceptions"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("reconciliation_runs.id"), index=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id"), index=True)
    exception_type: Mapped[str] = mapped_column(String(64), index=True)
    amount: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(8))
    candidate_invoice_ids: Mapped[list] = mapped_column(JSONType, default=list)
    confidence: Mapped[float] = mapped_column(Numeric(8, 6), default=0)
    reason: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str] = mapped_column(String(32), default="HUMAN_REVIEW")
    final_decision: Mapped[str] = mapped_column(String(32), default="OPEN", index=True)
    evidence: Mapped[list] = mapped_column(JSONType, default=list)


class Investigation(Base):
    __tablename__ = "investigations"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    exception_id: Mapped[str] = mapped_column(ForeignKey("exceptions.id"), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("reconciliation_runs.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    llm_calls: Mapped[int] = mapped_column(Integer, default=0)
    rag_calls: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed: Mapped[dict] = mapped_column(JSONType, default=dict)


class InvestigationAction(Base):
    __tablename__ = "investigation_actions"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    tool: Mapped[str] = mapped_column(String(64))
    arguments: Mapped[dict] = mapped_column(JSONType, default=dict)
    result_preview: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Decision(Base):
    __tablename__ = "decisions"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("reconciliation_runs.id"), index=True)
    exception_id: Mapped[str | None] = mapped_column(ForeignKey("exceptions.id"), nullable=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id"), index=True)
    decision: Mapped[str] = mapped_column(String(32), index=True)
    confidence: Mapped[float] = mapped_column(Numeric(8, 6))
    reason_code: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list] = mapped_column(JSONType, default=list)
    calculations: Mapped[dict] = mapped_column(JSONType, default=dict)
    authorized: Mapped[bool] = mapped_column(Boolean, default=False)
    gate_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    decision_id: Mapped[str | None] = mapped_column(ForeignKey("decisions.id"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(64))
    source_id: Mapped[str] = mapped_column(String(64), index=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String(128), nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[dict] = mapped_column(JSONType, default=dict)


class HistoricalCase(Base):
    __tablename__ = "historical_cases"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    exception_type: Mapped[str] = mapped_column(String(64), index=True)
    vendor_id: Mapped[str | None] = mapped_column(ForeignKey("vendors.id"), nullable=True)
    decision: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list] = mapped_column(JSONType, default=list)
    calculations: Mapped[dict] = mapped_column(JSONType, default=dict)
    narrative: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    run_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    event: Mapped[str] = mapped_column(String(64), index=True)
    detail: Mapped[str] = mapped_column(Text)
    extra: Mapped[dict] = mapped_column(JSONType, default=dict)


class GroundTruth(Base):
    __tablename__ = "ground_truth"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id"), unique=True, index=True)
    expected_invoice_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    expected_status: Mapped[str] = mapped_column(String(32))
    expected_exception_type: Mapped[str | None] = mapped_column(String(64), nullable=True)


class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("reconciliation_runs.id"), index=True)
    metrics: Mapped[dict] = mapped_column(JSONType, default=dict)
    calibration: Mapped[list] = mapped_column(JSONType, default=list)
    by_exception_type: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CashForecast(Base):
    __tablename__ = "cash_forecasts"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("reconciliation_runs.id"), nullable=True)
    scenario: Mapped[str] = mapped_column(String(64), default="base")
    current_cash: Mapped[Decimal] = mapped_column(Money)
    horizon_days: Mapped[int] = mapped_column(Integer, default=30)
    series: Mapped[list] = mapped_column(JSONType, default=list)
    summary: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
