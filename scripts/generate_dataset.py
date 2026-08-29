"""Deterministic synthetic finance dataset. Hidden ground truth is never sent to the agent."""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "synthetic"
GT = DATA / "ground_truth"
DOCS = ROOT / "data" / "documents"
POL = ROOT / "data" / "policies"

SEED = 42

VENDORS_SPEC = [
    ("VENDOR_AWS", "Amazon Web Services", ["AWS", "AMAZON WEB SERVICES INDIA PVT LTD"], "2.00"),
    ("VENDOR_MSFT", "Microsoft", ["MSFT", "Microsoft India"], "1.50"),
    ("VENDOR_GCP", "Google Cloud", ["GCP", "Google Cloud Platform"], "2.00"),
    ("VENDOR_ACME", "Acme Supplies", ["ACME", "Acme Supplies Pvt Ltd"], "2.00"),
    ("VENDOR_NOKIA", "Nokia Networks", ["Nokia"], "1.00"),
    ("VENDOR_TATA", "Tata Communications", ["Tata Comm"], "2.00"),
    ("VENDOR_INFY", "Infosys Limited", ["Infosys"], "0.50"),
    ("VENDOR_RIL", "Reliance Retail", ["RIL Retail"], "2.00"),
]


def money(n: float) -> str:
    return f"{Decimal(str(n)).quantize(Decimal('0.01')):.2f}"


def generate(n_transactions: int = 1000, seed: int = SEED) -> dict:
    rng = random.Random(seed)
    DATA.mkdir(parents=True, exist_ok=True)
    GT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    POL.mkdir(parents=True, exist_ok=True)

    vendors = []
    for vid, name, aliases, var in VENDORS_SPEC:
        vendors.append(
            {
                "id": vid,
                "legal_name": name,
                "aliases": aliases,
                "country": "IN",
                "tax_id": f"GSTIN{vid[-4:]}",
                "bank_account": f"IN{rng.randint(10**10, 10**11-1)}",
                "payment_terms_days": 30,
                "allowed_variance_pct": var,
            }
        )

    n_inv = max(700, int(n_transactions * 0.85))
    invoices = []
    line_items = []
    start = date(2026, 1, 5)
    for i in range(n_inv):
        v = vendors[i % len(vendors)]
        sub = Decimal(str(rng.randint(5000, 800000))) / Decimal("1")
        tax = (sub * Decimal("0.18")).quantize(Decimal("0.01"))
        total = (sub + tax).quantize(Decimal("0.01"))
        inv_date = start + timedelta(days=rng.randint(0, 200))
        iid = f"INV_{i+1:04d}"
        invoices.append(
            {
                "id": iid,
                "invoice_number": iid.replace("_", "-"),
                "vendor_id": v["id"],
                "vendor_name_raw": v["legal_name"],
                "invoice_date": inv_date.isoformat(),
                "due_date": (inv_date + timedelta(days=30)).isoformat(),
                "currency": "INR",
                "subtotal": f"{sub:.2f}",
                "tax_amount": f"{tax:.2f}",
                "total_amount": f"{total:.2f}",
                "payment_reference": f"PAY-{i+1:04d}",
                "bank_account": v["bank_account"],
                "status": "open",
            }
        )
        line_items.append(
            {
                "id": f"LI_{i+1:04d}",
                "invoice_id": iid,
                "description": "Cloud / services",
                "quantity": "1",
                "unit_price": f"{sub:.2f}",
                "amount": f"{sub:.2f}",
            }
        )

    # Corruption plan for transactions vs invoices
    n_tx = n_transactions
    transactions = []
    settlements = []
    ledger = []
    ground_truth = []
    bank = []

    def add_gt(tx_id, inv_id, status, etype):
        ground_truth.append(
            {
                "id": f"GT_{tx_id}",
                "transaction_id": tx_id,
                "expected_invoice_id": inv_id,
                "expected_status": status,
                "expected_exception_type": etype,
            }
        )

    for i in range(n_tx):
        inv = invoices[i % len(invoices)]
        v = next(x for x in vendors if x["id"] == inv["vendor_id"])
        tx_id = f"TX_{i+1:04d}"
        mode = i % 20
        amount = Decimal(inv["total_amount"])
        vendor_name = v["legal_name"]
        ref = inv["invoice_number"]
        currency = "INR"
        txn_date = date.fromisoformat(inv["invoice_date"]) + timedelta(days=rng.randint(0, 2))
        status_gt = "MATCH"
        etype = None
        expected_inv = inv["id"]

        if mode == 0:
            vendor_name = rng.choice(v["aliases"])  # alias, still match
        elif mode == 1:
            amount = (amount * Decimal("1.012")).quantize(Decimal("0.01"))  # ~1.2% variance, contract allows 2%
            etype = "AMOUNT_MISMATCH"
            status_gt = "MATCH"  # should AUTO_RESOLVE if investigation runs
        elif mode == 2:
            amount = (amount * Decimal("1.08")).quantize(Decimal("0.01"))  # 8% — escalate
            etype = "AMOUNT_MISMATCH"
            status_gt = "EXCEPTION"
            expected_inv = inv["id"]
        elif mode == 3:
            txn_date = txn_date + timedelta(days=12)
            etype = "DATE_MISMATCH"
            status_gt = "EXCEPTION"
        elif mode == 4:
            expected_inv = None
            ref = f"MISSING-{i}"
            etype = "MISSING_INVOICE"
            status_gt = "EXCEPTION"
        elif mode == 5 and i > 10:
            # duplicate of previous matching tx pattern
            prev = transactions[-1]
            amount = Decimal(prev["amount"])
            ref = prev["payment_reference"]
            etype = "DUPLICATE_PAYMENT"
            status_gt = "EXCEPTION"
        elif mode == 6:
            amount = (amount / Decimal("2")).quantize(Decimal("0.01"))
            etype = "PARTIAL_PAYMENT"
            status_gt = "EXCEPTION"
        elif mode == 7:
            currency = "USD"
            etype = "CURRENCY_MISMATCH"
            status_gt = "EXCEPTION"
        elif mode == 8:
            # tax mismatch recorded on extra; keep amount equal so matcher may still auto
            inv_copy_tax = True
            etype = "TAX_MISMATCH"
            status_gt = "EXCEPTION"
        elif mode == 9:
            # two candidate invoices: point ref at a nearby invoice of same vendor/amount-ish
            other = invoices[(i + len(vendors)) % len(invoices)]
            if other["vendor_id"] == inv["vendor_id"]:
                ref = ""
                etype = "AMBIGUOUS_MATCH"
                status_gt = "EXCEPTION"
        elif mode == 10:
            vendor_name = "Unknown Payee " + str(i)
            etype = "VENDOR_MISMATCH"
            status_gt = "EXCEPTION"

        extra = {}
        if mode == 8:
            extra["tax_note"] = "line tax disagrees with header in source PDF"

        transactions.append(
            {
                "id": tx_id,
                "vendor_id": v["id"] if mode != 10 else None,
                "vendor_name_raw": vendor_name,
                "amount": f"{amount:.2f}",
                "currency": currency,
                "txn_date": txn_date.isoformat(),
                "payment_reference": ref,
                "bank_reference": f"BNK{i+1:06d}",
                "source": "bank" if i % 2 == 0 else "ledger",
                "status": "pending",
                "description": f"Pmt {inv['invoice_number']}",
                "extra": extra,
            }
        )
        add_gt(tx_id, expected_inv, status_gt, etype)

        if i < max(500, n_tx // 2):
            stl_amt = amount if mode != 1 else Decimal(inv["total_amount"]) * Decimal("1.012")
            if mode == 1:
                stl_amt = amount
            settlements.append(
                {
                    "id": f"STL_{i+1:04d}",
                    "vendor_id": v["id"],
                    "amount": f"{Decimal(stl_amt).quantize(Decimal('0.01')):.2f}",
                    "currency": currency,
                    "settlement_date": txn_date.isoformat(),
                    "payment_reference": ref,
                    "invoice_id": inv["id"] if expected_inv else None,
                    "transaction_id": tx_id,
                    "status": "posted",
                }
            )
        if i < max(500, n_tx // 2):
            ledger.append(
                {
                    "id": f"LE_{i+1:04d}",
                    "account": "AP" if i % 3 else "BANK",
                    "vendor_id": v["id"],
                    "amount": f"{amount:.2f}",
                    "currency": currency,
                    "entry_date": txn_date.isoformat(),
                    "direction": "out",
                    "reference": ref,
                    "description": "posted",
                    "status": "posted",
                }
            )
        if i < max(500, n_tx // 2):
            bank.append(
                {
                    "id": f"BANK_{i+1:04d}",
                    "transaction_id": tx_id,
                    "amount": f"{amount:.2f}",
                    "currency": currency,
                    "date": txn_date.isoformat(),
                    "narration": vendor_name,
                }
            )

    contracts = []
    for v in vendors:
        cid = f"CONTRACT_{v['id']}"
        text = (
            f"Vendor Contract {cid}\nParty: {v['legal_name']}\n"
            f"Section 4.2 Settlement Variance: The payer may accept settlement differences "
            f"up to {v['allowed_variance_pct']}% of the invoice total without amendment.\n"
            f"Section 5 Tax: GST 18% unless reverse charge.\nEffective: 2026-01-01 Country: IN"
        )
        contracts.append(
            {
                "id": cid,
                "document_type": "vendor_contract",
                "vendor_id": v["id"],
                "document_id": cid,
                "effective_date": "2026-01-01",
                "country": "IN",
                "category": "contract",
                "text": text,
            }
        )
        (DOCS / f"{cid}.txt").write_text(text, encoding="utf-8")

    policies = [
        {
            "id": "SETTLEMENT_POLICY_02",
            "document_type": "payment_policy",
            "vendor_id": None,
            "document_id": "SETTLEMENT_POLICY_02",
            "effective_date": "2026-01-01",
            "country": "IN",
            "category": "payment_policy",
            "text": "Settlement Policy 02: Auto-resolve settlement variance only when contract permits and variance is within contractual percentage. Otherwise HUMAN_REVIEW. Never invent a match.",
        },
        {
            "id": "TAX_POLICY_IN_18",
            "document_type": "tax_policy",
            "vendor_id": None,
            "document_id": "TAX_POLICY_IN_18",
            "effective_date": "2026-01-01",
            "country": "IN",
            "category": "tax_policy",
            "text": "India GST standard rate 18% on taxable cloud and professional services unless exempt.",
        },
        {
            "id": "DUP_POLICY_01",
            "document_type": "payment_policy",
            "vendor_id": None,
            "document_id": "DUP_POLICY_01",
            "effective_date": "2026-01-01",
            "country": "IN",
            "category": "payment_policy",
            "text": "Duplicate payments with identical amount, currency, and payment reference must be escalated.",
        },
    ]
    for p in policies:
        (POL / f"{p['id']}.txt").write_text(p["text"], encoding="utf-8")

    historical = []
    for i in range(40):
        v = vendors[i % len(vendors)]
        historical.append(
            {
                "id": f"HCSEED_{i+1:03d}",
                "exception_type": "AMOUNT_MISMATCH",
                "vendor_id": v["id"],
                "decision": "AUTO_RESOLVE",
                "reason": "Contract permits 2% settlement variance.",
                "evidence": [{"source": "contract", "id": f"CONTRACT_{v['id']}"}],
                "calculations": {"variance_percentage": "1.22", "allowed_variance_percentage": v["allowed_variance_pct"]},
                "narrative": f"Exception: Settlement amount differs from invoice. Resolution: Accepted. Reason: Contract permits {v['allowed_variance_pct']}% settlement variance. Evidence: Contract §4.2 Calculation: Variance = 1.22% Decision: AUTO_RESOLVE",
                "document_type": "historical_case",
                "document_id": f"HCSEED_{i+1:03d}",
                "effective_date": "2026-01-01",
                "country": "IN",
                "category": "historical_case",
                "text": f"Historical case {i}: amount mismatch for {v['legal_name']} auto-resolved within contract variance.",
            }
        )

    # Sample native PDF invoices (subset)
    pdf_dir = DOCS / "invoices"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    for inv in invoices[:25]:
        _write_invoice_pdf(pdf_dir / f"{inv['id']}.pdf", inv)

    bundle = {
        "vendors": vendors,
        "invoices": invoices,
        "invoice_line_items": line_items,
        "transactions": transactions,
        "settlements": settlements,
        "ledger_entries": ledger,
        "bank_records": bank,
        "contracts": contracts,
        "policies": policies,
        "historical_cases": historical,
    }
    (DATA / "dataset.json").write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    (GT / "labels.json").write_text(json.dumps(ground_truth, indent=2), encoding="utf-8")
    (DATA / "meta.json").write_text(json.dumps({"seed": seed, "n_transactions": n_tx, "n_invoices": n_inv}), encoding="utf-8")
    _train_matcher(transactions, invoices, ground_truth)
    return {"transactions": n_tx, "invoices": n_inv, "path": str(DATA / "dataset.json")}


def _train_matcher(transactions, invoices, ground_truth) -> None:
    try:
        import lightgbm as lgb
        import numpy as np
    except Exception:
        return
    inv_by_id = {i["id"]: i for i in invoices}
    gt = {g["transaction_id"]: g for g in ground_truth}
    X, y = [], []
    for tx in transactions:
        g = gt.get(tx["id"])
        for inv in invoices[:: max(1, len(invoices) // 30)]:
            label = 1 if g and g.get("expected_invoice_id") == inv["id"] and g.get("expected_status") == "MATCH" else 0
            if label == 0 and len(y) > 0 and y[-1] == 0 and len(X) % 3 != 0:
                continue
            amt_tx = float(tx["amount"])
            amt_inv = float(inv["total_amount"])
            diff = abs(amt_tx - amt_inv)
            X.append(
                [
                    1.0 if tx.get("vendor_id") == inv.get("vendor_id") else 0.4,
                    diff,
                    diff / amt_inv if amt_inv else 1,
                    1.0,
                    1.0 if (tx.get("payment_reference") or "") == inv.get("invoice_number") else 0.0,
                    1.0 if tx.get("currency") == inv.get("currency") else 0.0,
                    0.5,
                    0.7,
                ]
            )
            y.append(label)
            if len(X) > 4000:
                break
        if len(X) > 4000:
            break
    if len(set(y)) < 2:
        return
    dtrain = lgb.Dataset(np.array(X), label=np.array(y))
    booster = lgb.train({"objective": "binary", "verbosity": -1, "num_leaves": 16}, dtrain, num_boost_round=40)
    out = DATA / "match_model.txt"
    booster.save_model(str(out))


def _write_invoice_pdf(path: Path, inv: dict) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, y, "TAX INVOICE")
    c.setFont("Helvetica", 11)
    lines = [
        f"Invoice Number: {inv['invoice_number']}",
        f"Vendor: {inv['vendor_name_raw']}",
        f"Invoice Date: {inv['invoice_date']}",
        f"Due Date: {inv['due_date']}",
        f"Currency: {inv['currency']}",
        f"Subtotal: {inv['subtotal']}",
        f"Tax: {inv['tax_amount']}",
        f"Total: {inv['total_amount']}",
        f"Payment Ref: {inv['payment_reference']}",
        f"Bank: {inv['bank_account']}",
        f"ITEM | Cloud / services | 1 | {inv['subtotal']}",
    ]
    for line in lines:
        y -= 22
        c.drawString(72, y, line)
    c.save()


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=1000)
    p.add_argument("--seed", type=int, default=SEED)
    args = p.parse_args()
    print(generate(args.n, args.seed))
