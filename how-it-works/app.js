const pipe = document.getElementById("pipe");
const drop = document.getElementById("drop");
const fileInput = document.getElementById("file");
const meta = document.getElementById("meta");
const fname = document.getElementById("fname");
const kindEl = document.getElementById("kind");
const verdict = document.getElementById("verdict");
const vtag = document.getElementById("vtag");
const vtitle = document.getElementById("vtitle");
const vbody = document.getElementById("vbody");
const vlog = document.getElementById("vlog");

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function classify(name, type) {
  const n = (name || "").toLowerCase();
  const t = type || "";
  if (n.includes("ambiguous") || n.includes("gap")) return "ambiguous";
  if (n.includes("scan") || n.includes("photo") || t.startsWith("image/")) return "scan";
  return "digital";
}

function plan(mode, name) {
  if (mode === "scan") {
    return {
      kind: "Scan / image — OCR vision model",
      steps: [
        ["route", "ok", "image / scanned PDF"],
        ["extract", "ok", "OCR vision model read pixels"],
        ["validate", "ok", "₹688,950.08 = lines + tax"],
        ["sql", "ok", "INV stored"],
        ["match", "ok", "L0 exact vs TX_0088"],
        ["llm", "skip", "skipped — no exception"],
        ["gate", "ok", "IDs exist · Decimal ok"],
      ],
      verdict: {
        tag: "Posted",
        title: "AUTO_MATCH",
        body: "Scanned page had almost no copyable text, so the OCR vision model ran. Totals added up. Exact match to a bank line. LLM was not called. Gate authorized.",
        log: `${name}\nextract: ocr_vision\ninvoice: INV_DEMO_SCAN\namount: 688950.08 INR\nmatch: L0 exact\nllm: skipped\ngate: authorized true`,
      },
    };
  }
  if (mode === "ambiguous") {
    return {
      kind: "Digital PDF — native text, then exception",
      steps: [
        ["route", "ok", "digital PDF"],
        ["extract", "ok", "native PDF text (no OCR)"],
        ["validate", "ok", "totals consistent"],
        ["sql", "ok", "INV stored"],
        ["match", "fail", "L2/L3: three invoices, scores too close"],
        ["llm", "ok", "proposed HUMAN_REVIEW — did not invent a winner"],
        ["gate", "fail", "insufficient unique evidence → UNRESOLVED"],
      ],
      verdict: {
        tag: "Refused",
        title: "UNRESOLVED",
        body: "Like TX_0002: three candidate invoices. The LLM may suggest review. The gate will not pick a winner. Finance still owns the exception.",
        log: `${name}\nextract: pdf_text\ncandidates: INV_0002, INV_0010, INV_0018\nllm: proposal HUMAN_REVIEW\ngate: authorized false\ndecision: UNRESOLVED`,
      },
    };
  }
  return {
    kind: "Digital PDF — native text",
    steps: [
      ["route", "ok", "digital PDF · selectable text"],
      ["extract", "ok", "native PDF text · OCR not used"],
      ["validate", "ok", "₹688,950.08 + check passed"],
      ["sql", "ok", "INV_0022 stored"],
      ["match", "ok", "amount gap 1.20% vs 2% vendor cap"],
      ["llm", "skip", "skipped — Python variance, not a paragraph"],
      ["gate", "ok", "INV_0022 + TX_0022 · Decimal recomputed"],
    ],
    verdict: {
      tag: "Posted",
      title: "AUTO_RESOLVE",
      body: "Like TX_0022 Tata: settlement a bit above invoice, still inside the contract cap. No LLM. Gate recomputed the percent and posted.",
      log: `${name}\nextract: pdf_text\ninvoice: 688950.08\nbank: 697217.48\nvariance: 1.20%\ncap: 2.00%\nllm: skipped\ngate: authorized true`,
    },
  };
}

function resetPipe() {
  pipe.querySelectorAll("li").forEach((li) => {
    li.className = "";
    li.querySelector(".status").textContent = "waiting";
  });
  verdict.hidden = true;
}

async function run(name, type) {
  const mode = classify(name, type);
  const p = plan(mode, name);
  fname.textContent = name;
  kindEl.textContent = p.kind;
  meta.hidden = false;
  resetPipe();
  vlog.textContent = "";

  for (const [id, state, msg] of p.steps) {
    const li = pipe.querySelector(`[data-step="${id}"]`);
    li.className = "run";
    li.querySelector(".status").textContent = "running";
    await sleep(700);
    li.className = state;
    li.querySelector(".status").textContent = msg;
    await sleep(380);
  }

  vtag.textContent = p.verdict.tag;
  vtitle.textContent = p.verdict.title;
  vbody.textContent = p.verdict.body;
  vlog.textContent = p.verdict.log;
  verdict.hidden = false;
}

drop.addEventListener("click", (e) => {
  if (e.target.closest("button")) return;
  fileInput.click();
});

drop.addEventListener("dragover", (e) => {
  e.preventDefault();
  drop.classList.add("drag");
});
drop.addEventListener("dragleave", () => drop.classList.remove("drag"));
drop.addEventListener("drop", (e) => {
  e.preventDefault();
  drop.classList.remove("drag");
  const f = e.dataTransfer.files[0];
  if (f) run(f.name, f.type);
});

fileInput.addEventListener("change", () => {
  const f = fileInput.files[0];
  if (f) run(f.name, f.type);
});

document.querySelectorAll("[data-sample]").forEach((btn) => {
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    const s = btn.getAttribute("data-sample");
    if (s === "scan") run("scan-invoice-photo.png", "image/png");
    else if (s === "ambiguous") run("ambiguous-pack.pdf", "application/pdf");
    else run("Tata-INV-0022.pdf", "application/pdf");
  });
});
