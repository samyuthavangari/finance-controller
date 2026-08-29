"""Settlement Q&A: answers over closed-book SQL facts. LLM proposes; tools and Decimal are truth."""

from __future__ import annotations

import json
import re

from sqlalchemy.orm import Session

from app.agents import tools
from app.models import Decision, ExceptionRecord, Transaction
from app.providers import get_llm
from sqlalchemy import select

SYSTEM = """You answer settlement questions for a finance controller.
Use only the JSON facts provided. Do not invent invoice IDs, contracts, or amounts.
If facts are insufficient, say HUMAN_REVIEW / unknown.
Return JSON: decision (one of ANSWER, HUMAN_REVIEW), confidence, reason_code, reason, evidence[{source,id,snippet}], calculations.
"""


def ask(db: Session, question: str) -> dict:
    q = (question or "").strip()
    q_upper = q.upper().replace("-", "_")
    actions: list[dict] = []
    facts: dict = {"question": q}

    # --- Multi-signal entity extraction ---
    # 1. Transaction IDs
    tx_ids = re.findall(r"TX[_-]?\d+", q_upper)
    # 2. Invoice IDs
    inv_ids = re.findall(r"INV[_-]?\d+", q_upper)
    # 3. Amount patterns (₹ 1,23,456 / INR 500.00 / bare decimals)
    amounts = re.findall(r"(?:₹|INR\s*)[\d,]+(?:\.\d+)?|\b\d{4,}(?:\.\d+)?\b", q)
    # 4. Vendor name lookup from DB (fuzzy: any vendor name token found in question)
    from sqlalchemy import select as _sel
    from app.models import Vendor as _Vendor
    all_vendors = db.execute(_sel(_Vendor)).scalars().all()
    matched_vendor = None
    for v in all_vendors:
        names = [v.legal_name] + (v.aliases or [])
        if any(n.lower() in q.lower() for n in names if len(n) > 3):
            matched_vendor = v
            break

    if tx_ids:
        tid = tx_ids[0] if tx_ids[0].startswith("TX_") else f"TX_{tx_ids[0][2:]}"
        if not tid.startswith("TX_"):
            tid = tx_ids[0]
        facts["transaction"] = tools.search_transactions(db, id=tid)
        facts["settlements"] = tools.search_settlement(db, payment_reference=None)
        tx = db.get(Transaction, tid)
        if tx:
            facts["settlements"] = tools.search_settlement(
                db, vendor_id=tx.vendor_id, payment_reference=tx.payment_reference
            )
            facts["invoices"] = tools.search_invoice(db, vendor_id=tx.vendor_id)
            facts["ledger"] = tools.search_ledger(db, reference=tx.payment_reference)
            dec = db.execute(select(Decision).where(Decision.transaction_id == tid)).scalars().first()
            exc = db.execute(select(ExceptionRecord).where(ExceptionRecord.transaction_id == tid)).scalars().first()
            facts["decision"] = (
                {
                    "decision": dec.decision,
                    "reason_code": dec.reason_code,
                    "reason": dec.reason,
                    "calculations": dec.calculations,
                    "evidence": dec.evidence,
                    "authorized": dec.authorized,
                }
                if dec
                else None
            )
            facts["exception"] = (
                {
                    "id": exc.id,
                    "tx": exc.transaction_id,
                    "type": exc.exception_type,
                    "reason": exc.reason,
                    "final_decision": exc.final_decision,
                    "candidates": exc.candidate_invoice_ids,
                }
                if exc
                else None
            )
            if facts["settlements"] and facts.get("invoices"):
                invs = facts["invoices"]
                if invs:
                    facts["variance"] = tools.calculate_variance(
                        invs[0]["total_amount"], facts["settlements"][0]["amount"]
                    )
        actions.append({"tool": "search_transactions", "id": tid})
        actions.append({"tool": "search_settlement", "id": tid})

    elif inv_ids:
        # Invoice-keyed question
        iid = inv_ids[0] if inv_ids[0].startswith("INV_") else inv_ids[0].replace("INV-", "INV_")
        facts["invoices"] = tools.search_invoice(db, id=iid)
        if facts["invoices"]:
            inv = facts["invoices"][0]
            facts["settlements"] = tools.search_settlement(db, vendor_id=inv.get("vendor_id"))
        actions.append({"tool": "search_invoice", "id": iid})

    elif matched_vendor:
        # Vendor-keyed question
        facts["vendor"] = tools.search_vendor(db, vendor_id=matched_vendor.id)
        facts["invoices"] = tools.search_invoice(db, vendor_id=matched_vendor.id)
        facts["settlements"] = tools.search_settlement(db, vendor_id=matched_vendor.id)
        actions.append({"tool": "search_vendor", "vendor": matched_vendor.legal_name})

    else:
        facts["recent_unresolved"] = [
            {"id": e.id, "tx": e.transaction_id, "type": e.exception_type, "reason": e.reason[:200]}
            for e in db.execute(select(ExceptionRecord).where(ExceptionRecord.final_decision == "UNRESOLVED").limit(5)).scalars()
        ]
        facts["recent_auto_resolve"] = [
            {"tx": d.transaction_id, "reason_code": d.reason_code, "reason": d.reason}
            for d in db.execute(select(Decision).where(Decision.decision == "AUTO_RESOLVE").limit(5)).scalars()
        ]
        actions.append({"tool": "list_exceptions"})

    # Surface extracted signals into facts for LLM context
    if amounts:
        facts["amounts_mentioned"] = amounts
    if inv_ids:
        facts["invoice_ids_mentioned"] = inv_ids

    deterministic = _deterministic_answer(q, facts)
    if deterministic:
        return {**deterministic, "actions": actions, "facts_used": _public_facts(facts)}

    try:
        llm = get_llm()
        raw = llm.generate(json.dumps(facts, default=str)[:12000], SYSTEM, json_mode=True)
        data = json.loads(raw)
        if str(data.get("decision") or "").upper() in {"AUTO_RESOLVE", "AUTO_MATCH"}:
            data["decision"] = "HUMAN_REVIEW"
            data["reason"] = (data.get("reason") or "") + " [stripped: Q&A cannot authorize ledger closes]"
        return {
            "answer": data.get("reason") or data.get("answer") or raw[:800],
            "decision": data.get("decision") or "ANSWER",
            "confidence": data.get("confidence") or 0.5,
            "evidence": data.get("evidence") or [],
            "calculations": data.get("calculations") or {},
            "authorized": False,
            "used_llm": True,
            "gate_notes": "Q&A path cannot AUTO_RESOLVE",
            "actions": actions,
            "facts_used": _public_facts(facts),
        }
    except Exception:
        return {
            "answer": facts.get("decision", {}).get("reason")
            if isinstance(facts.get("decision"), dict)
            else "No settlement facts matched that question. Name a transaction id (e.g. TX_0022) or run DEMO first.",
            "decision": "HUMAN_REVIEW",
            "confidence": 0.4,
            "evidence": [],
            "calculations": {},
            "authorized": False,
            "used_llm": False,
            "actions": actions,
            "facts_used": _public_facts(facts),
        }


def _deterministic_answer(q: str, facts: dict) -> dict | None:
    dec = facts.get("decision") if isinstance(facts.get("decision"), dict) else None
    exc = facts.get("exception") if isinstance(facts.get("exception"), dict) else None
    var = facts.get("variance") or {}
    ql = q.lower()
    if dec and ("why" in ql or "resolve" in ql or "match" in ql or "variance" in ql or "tx_" in ql):
        calc = dec.get("calculations") or var
        return {
            "answer": (
                f"{dec.get('decision')} ({dec.get('reason_code')}). {dec.get('reason')} "
                f"Authorized={dec.get('authorized')}. Calculations={calc}."
            ),
            "decision": "ANSWER",
            "confidence": 0.93,
            "evidence": dec.get("evidence") or [],
            "calculations": calc,
            "authorized": True,
            "used_llm": False,
            "gate_notes": "answered from stored decision + SQL facts; LLM not required",
        }
    if exc and ("unresolved" in ql or "exception" in ql or "not match" in ql or "ambiguous" in ql or "tx_" in ql) and not dec:
        return {
            "answer": f"{exc['id']} {exc['tx']}: {exc['type']}. {exc['reason']} Decision={exc['final_decision']}. Candidates={exc['candidates']}.",
            "decision": "ANSWER",
            "confidence": 0.9,
            "evidence": [{"source": "exception", "id": exc["id"]}],
            "calculations": {},
            "authorized": True,
            "used_llm": False,
            "gate_notes": "answered from exception row",
        }
    return None


def _public_facts(facts: dict) -> dict:
    out = {}
    for k in ("transaction", "settlements", "variance", "decision", "exception", "recent_unresolved", "recent_auto_resolve"):
        if k in facts:
            out[k] = facts[k]
    return out
