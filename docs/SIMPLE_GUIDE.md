# Vertex — simple guide (what is what)

This product is an **AI Finance Controller**.  
It tries to **match money that left the bank** to **invoices**.  
If it cannot prove a match, it **refuses**. It does not guess.

Think of it like this:

- Bank statement = “we paid someone ₹10,000”
- Invoice = “Tata billed us ₹10,000”
- The controller = “are these the same thing? prove it.”

**SQL** = the real numbers (truth).  
**Qdrant** = contract / policy text (evidence, not cash).  
**Gemini** = a helper that can *suggest* an answer.  
**The gate** = the adult in the room. It checks IDs and math. Gemini cannot write the books.

---

## Can I upload a PDF? Will PaddleOCR read it?

**Yes, you can upload a PDF** on **Close books** (file picker).  
Allowed types (max **25 MB**):

| File | What it is |
|---|---|
| `.pdf` | Invoice / receipt / statement |
| `.png` `.jpg` `.jpeg` `.webp` | Photo of a paper invoice |
| `.csv` `.json` `.txt` | Spreadsheet / text dump |
| `.mp4` | Allowed by the form, **not really read** (needs ffmpeg; skipped) |

### What kind of PDF works best?

1. **Digital PDF** (you can select text with the mouse)  
   Best. The system reads the text with `pdfplumber` / `pypdf`.  
   **PaddleOCR is not used.** Faster and more accurate.

2. **Scanned PDF** (it looks like a photo of paper; you cannot select text)  
   If there are fewer than **40 characters** of real text, it calls **Hugging Face PaddleOCR-VL** (`PaddlePaddle/PaddleOCR-VL`).  
   That is the “read the pixels” step. Needs `HF_TOKEN` in `.env`.

3. **Still unreadable after OCR**  
   Last resort: **Gemini vision**. Python still checks that line items + tax add up.

**Good PDFs**

- One invoice per file (or a few clear pages)
- Amounts, invoice number, vendor name, date visible
- Not password-protected
- Not a 200-page book

**Bad PDFs**

- Password locked
- Tiny blurry phone photo
- Handwriting only
- Logo-only page with no numbers

### Honest note about this demo

**Run demo does not use your PDF.**  
It loads a **fake (synthetic) 200-transaction pack** (seed 42).  

Upload **saves** the file as a document. The extraction code *can* OCR a scan. The numbers you see after **Run demo** still come from that synthetic pack, not from your PDF. For the hackathon story: “we built the reader; the judged close is the 200-record batch.”

---

## Dashboard — each screen, with an example

Do this first: open **http://localhost:5173/app** → click **Run demo** → wait until the button says **Run demo** again (can take 1–2 minutes).

### Overview

**What:** One page: “how much of the close did we prove?”

**After demo, example**

- About **200** records
- **F1 ~ 78.5%** (score vs hidden answer key)
- Rough split: **131** exact matches + **20** vendor-alias matches + **3** contract-variance resolves + **46** refused = **200**
- **LLM calls 0** on that run (rules were enough)
- Cash like **₹2.5 crore** current

If you see “No close yet”, you have not finished **Run demo**.

---

### Close books

**What:** Start a close. Upload a file, or run the same demo.

- **Close books** = match whatever is already in the database  
- **Run demo** = wipe, plant 200 fake payments + invoices, then match them

---

### Ledger

**What:** Every bank line and the decision.

| Example ID | What you see | Meaning |
|---|---|---|
| **TX_0022** | Tata, amount ~₹6.97L, **AUTO_RESOLVE** | Paid a bit more than invoice. Variance **1.20%**, vendor cap **2%**. Gate OK. |
| **TX_0002** | Ambiguous, **UNRESOLVED** | Three possible invoices. System did **not** pick one. |
| Many others | **AUTO_MATCH** | Same amount + same reference (exact or alias). |

Click **Why** to see the score. That is the posted trail.

---

### Exceptions

**What:** The “I don’t know” pile.

**Example:** `EX_…` for **TX_0002**

- Type: **AMBIGUOUS_MATCH**
- Candidates: **INV_0002, INV_0010, INV_0018**
- Decision: **UNRESOLVED**
- Reason: not enough unique evidence

Open a row → invoices, investigation, **authorized: true/false**.

---

### Settlement

**What:** Ask English questions about the *already closed* books.

Try:

- “Why did TX_0022 auto-resolve?”
- “Why is TX_0002 unresolved?”

Answers use SQL + Decimal. **This chat cannot approve a match.**

---

### Cash

**What:** “How much money will we have?” for 7 / 14 / 30 days.

Example buttons: delay receivables 7 days, delay settlement 5 days, expenses +10%, collect ₹5L early.  
Math is a formula. **Not** Qdrant. **Not** Gemini inventing a balance.

---

### Benchmark

**What:** Report card vs a **hidden** answer key (you don’t see the key in the UI).

Example: F1 **78.5%**, match accuracy, precision, recall, how often humans would be needed.

We do **not** claim 100%. Refusing 46 items is part of the score story.

---

### Stress

**What:** Same job at 100, 500, 1k, 5k, 10k records.  
Checks speed and that accuracy doesn’t fall over. 5k/10k skip heavy investigation.

---

### Audit

**What:** Diary of what the machine did.

Example event: **GATE_REJECTED_HALLUCINATION** — someone proposed a fake contract `CONTRACT_HALLUCINATED_99`. Gate said **no**.

---

## What happens when you click Run demo? (step by step)

1. Old demo data is cleared.  
2. A **generator** (seed **42**) creates fake vendors, invoices, bank txs, settlements, contracts. About **200** payments. Some are messy on purpose (aliases, amount gaps, two invoices that look similar).  
3. A **hidden ground-truth file** is stored for scoring only. The matcher is **not** allowed to read it to cheat.  
4. Contract / policy text is indexed in **Qdrant** (if Qdrant is up).  
5. **Close books** runs:
   - **L0** exact match (same ref / amount) → auto  
   - **L1** vendor nickname (e.g. “Tata Comm” vs “Tata Communications”) → auto  
   - **L2** fuzzy text score  
   - **L3** LightGBM **ranks** pairs only; it cannot post the ledger  
   - Hard leftovers become **exceptions**  
6. For some exceptions, Python checks **contract variance** (TX_0022: 1.20% vs 2% cap) → **AUTO_RESOLVE** without Gemini.  
7. Ambiguous ones stay **UNRESOLVED**.  
8. Eval compares decisions to hidden truth → **F1**, etc.  
9. Cash forecast is computed from the ledger.  
10. Overview / Ledger / Exceptions fill with **live API numbers**.

Typical judged result (do not fake a prettier one):

```
131 L0 exact + 20 L1 alias + 3 gate AUTO_RESOLVE + 46 UNRESOLVED = 200
F1 ≈ 78.5%
LLM calls = 0
```

---

## Tiny map of the AI pieces

| Tool | When | Kid version |
|---|---|---|
| Native PDF text | You can highlight text in the PDF | “Copy the words, don’t photograph them” |
| **PaddleOCR** | Scan / image / empty PDF | “Read the picture of the page” |
| Gemini vision | OCR still junk | “Look with a smarter camera, still don’t invent ₹” |
| Qdrant | Exception needs a clause | “Find the contract paragraph” |
| Gemini JSON | Messy exception, not a duplicate | “Suggest a decision” |
| Gate | Always before posting | “Show your homework. Wrong ID or wrong math = no.” |

---

## How to run (two windows)

**Window 1 — API**

```powershell
cd "C:\Users\RAHUL\Postman Agent\finance-controller\backend"
$env:PYTHONPATH="C:\Users\RAHUL\Postman Agent\finance-controller\backend"
$env:DATABASE_URL="sqlite:///C:/Users/RAHUL/Postman Agent/finance-controller/data/synthetic/dev.db"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Window 2 — UI**

```powershell
cd "C:\Users\RAHUL\Postman Agent\finance-controller\frontend"
npm run dev -- --port 5173
```

Browser:

- Landing: http://localhost:5173  
- Dashboard: http://localhost:5173/app  
- Then **Run demo**, wait, then open Ledger + Exceptions.
