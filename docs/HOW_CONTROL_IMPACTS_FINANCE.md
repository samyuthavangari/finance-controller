# How finance control impacts finance people

This is for controllers, AP clerks, treasurers, and auditors — not for engineers.

Vertex is an **AI finance controller**. It closes books by matching **bank money** to **invoices**, then it **stops** when it cannot prove the match. That stop is the product. Guessing a match is how companies lose money, fail audits, and fight with vendors.

---

## What finance people actually do today

| Job | Pain today |
|---|---|
| Accounts payable | 200 lines in Excel. Same vendor, three names. “Looks close enough.” |
| Controller | Month-end: match rate unknown. Exceptions live in Slack. |
| Treasurer | Cash forecast built on “we think these invoices are paid.” |
| Auditor | “Show me why this ₹6.9L posted.” Screenshot of a chatbot is not evidence. |

If matching is sloppy, **cash is a lie**, **P&L is a lie**, and **vendor disputes** start after the money has already left.

---

## What this control changes

**1. Speed without fake accuracy**  
Exact and alias matches close alone (in the demo: 131 + 20 of 200). Finance does not sit on those. Humans only see the pile that failed the proof test (46 unresolved). That is **review time on exceptions**, not on every row.

**2. Honest exceptions instead of forced matches**  
Example: **TX_0002** — three invoices, no unique evidence → **UNRESOLVED**. A junior clerk is not pressured to pick INV_0002 because the F1 “looks better” if they do. Unmatched cash stays visible. That protects the close.

**3. Contract variance with math, not vibes**  
Example: **TX_0022** Tata paid ₹697,217.48 vs invoice ₹688,950.08. Variance **1.20%** vs vendor cap **2%**. Python recomputes Decimal. The LLM is not asked. Finance can defend the post in an audit: cap, IDs, math.

**4. Cash that is allowed to be slightly wrong in the open items, not silently wrong in the total**  
Forecast uses posted ledger + known schedule. It does **not** treat a chatbot paragraph as a balance. If 46 items are open, the cash story must include “this much is unmatched.” That is how treasurers avoid bouncing a payment.

**5. Audit trail you can hand to Big Four**  
Every gate reject is a log line. Fake contract `CONTRACT_HALLUCINATED_99` dies. Finance’s job in an audit is **reproduce the decision**, not “the model said so.”

---

## How a *failed* control hurts finance (why we refuse)

| Failure | Who feels it | What happens |
|---|---|---|
| Auto-match the wrong invoice | AP + vendor | Double pay or unpaid real bill. Recovery is months. |
| LLM invents a clause | Controller + legal | Books close on fiction. Restatement risk. |
| Vector DB used as cash | Treasurer | Forecast moves when embeddings change. |
| Hide exceptions to raise F1 | Auditor | Findings. Material weakness narrative. |
| Chat “approve” from Q&A | All of the above | Settlement chat **cannot** post a match. That is on purpose. |

A **78.5% F1** with **46 refused** is better for finance than **99%** with silent wrong posts. The controller’s bonus is not “rows closed.” It is **books that survive scrutiny**.

---

## What you should do in the product (role by role)

**AP / ops**  
Run demo or close. Work **Exceptions** first. Open the row. If three candidates, escalate — do not pick a winner in your head and type it into Excel.

**Controller**  
Read **Overview** F1 + refused rate. Open **Benchmark**. Ask: “is unmatched cash explained?” Then **Audit**.

**Treasurer**  
**Cash** page. Run what-ifs (receivables delay, settlement delay). Treat unmatched as a haircut until resolved.

**Auditor / risk**  
**Ledger** → Why. **TX_0022** authorized. **TX_0002** refused. **Audit** hallucination reject. That is the control design.

---

## Upload an invoice — what *should* happen (real system)

1. File saved.  
2. If you can select text in the PDF → native text. **No vision.**  
3. If it is a scan → **OCR vision model** reads pixels.  
4. If still junk → LLM vision (must not invent ₹).  
5. Python: line items + tax = total, or **EXTRACTION_ERROR**.  
6. Numbers land in **SQL** (truth).  
7. Matcher L0→L3. Ranker cannot post.  
8. Exception → evidence store + optional **LLM proposal**.  
9. **Gate**: real IDs + Decimal. Post or refuse.

The judged **Run demo** uses a **200-row synthetic pack**, not your PDF. Your upload is stored; the live numbers you show judges are that batch. See `docs/SIMPLE_GUIDE.md`.

For a **click-through** of the same story (upload → lights on the pipe), open:

`how-it-works/index.html`
