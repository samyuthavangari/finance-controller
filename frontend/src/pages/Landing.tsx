import { Link } from "react-router-dom";
import { RazorpayName } from "../components/RazorpayName";
import { ThemeToggle } from "../components/ThemeToggle";

const PARTITION = [
  { n: 131, label: "L0 exact", className: "bg-accent" },
  { n: 20, label: "L1 alias", className: "bg-sky-400" },
  { n: 3, label: "Gate resolve", className: "bg-indigo-400" },
  { n: 46, label: "Unresolved", className: "bg-rose-400" },
];

export default function Landing() {
  return (
    <div className="min-h-screen hero-glow grain text-fg">
      <header className="glass sticky top-0 z-20">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <a href="#top" className="flex items-center gap-3">
            <div className="mark">V</div>
            <div>
              <div className="text-sm font-medium tracking-tight">Vertex</div>
            </div>
          </a>
          <nav className="hidden items-center gap-8 text-sm text-muted md:flex">
            <a href="#flow" className="hover:text-fg">
              Flow
            </a>
            <a href="#proof" className="hover:text-fg">
              Proof
            </a>
            <a href="#stack" className="hover:text-fg">
              Stack
            </a>
            <a href="#cases" className="hover:text-fg">
              Cases
            </a>
          </nav>
          <div className="flex items-center gap-3">
            <ThemeToggle />
            <Link to="/app" className="btn btn-primary">
              Open control system
            </Link>
          </div>
        </div>
      </header>

      <section id="top" className="mx-auto max-w-6xl px-6 pb-12 pt-14">
        <p className="text-[11px] uppercase tracking-[0.28em] text-muted">AI finance controller</p>
        <div className="mt-6 overflow-x-auto pb-2">
          <div className="rzp-stage">
            <RazorpayName size="hero" />
          </div>
        </div>
        <p className="mt-3 text-xs text-muted">Click the logo once — lights come on slowly, letter by letter. Click again to fade them off.</p>
      </section>

      <section className="mx-auto grid max-w-6xl items-center gap-14 px-6 pb-20 lg:grid-cols-[1.05fr_0.95fr]">
        <div>
          <h1 className="display text-[52px] leading-[0.95] sm:text-[72px]">
            Close the books.
            <br />
            <em className="text-muted">Refuse the rest.</em>
          </h1>
          <p className="mt-6 max-w-lg text-[17px] leading-relaxed text-muted">
            Verification is the bottleneck — not generation. Match on SQL. Retrieve contracts as evidence. Let the LLM
            propose. A Decimal gate is the only thing that can authorize a match.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/app" className="btn btn-primary">
              Open control system
            </Link>
            <Link to="/app/settlement" className="btn btn-ghost">
              Ask a settlement
            </Link>
          </div>
          <p className="mt-6 text-xs text-muted">
            Live 200-record close · F1 78.5% · LLM calls 0 · 131 + 20 + 3 + 46 = 200
          </p>
        </div>

        <ProductFrame />
      </section>

      <Workflow />

      <section id="proof" className="border-y border-line">
        <div className="mx-auto grid max-w-6xl grid-cols-2 divide-y divide-[color:var(--line)] md:grid-cols-4 md:divide-x md:divide-y-0">
          <Stat n="78.5%" l="F1 vs hidden ground truth" />
          <Stat n="154" l="Authorized matches" />
          <Stat n="46" l="Honest exceptions" />
          <Stat n="0" l="LLM calls on this close" />
        </div>
      </section>

      <section id="stack" className="mx-auto max-w-6xl px-6 py-24">
        <p className="text-[11px] uppercase tracking-[0.28em] text-muted">How it actually runs</p>
        <h2 className="display mt-3 max-w-2xl text-4xl sm:text-5xl">Three models. One authority.</h2>
        <p className="mt-4 max-w-2xl text-muted">
          Color is status. Everything else stays quiet. An OCR vision model reads scans. The evidence store retrieves
          clauses. The LLM proposes. Only the gate can authorize.
        </p>
        <div className="mt-12 grid gap-3 md:grid-cols-3">
          <Engine
            k="01 · Pixels"
            title="OCR vision model"
            model="Scans and images only"
            body="Native PDF text first. If the page is a picture, the OCR vision model reads it. LLM vision is last resort. Totals still have to add in Python."
          />
          <Engine
            k="02 · Evidence"
            title="Evidence store"
            model="Filter, then similarity"
            body="Contracts and policies only. Filter by vendor and document type, then similarity. Never the source of cash or ledger balances."
          />
          <Engine
            k="03 · Proposal"
            title="LLM"
            model="JSON only"
            body="Exceptions only. Duplicates skip the model. Variance inside a vendor cap never needs a paragraph. The gate can still say no."
          />
        </div>

        <ol className="mt-10 grid gap-4 md:grid-cols-4">
          {[
            ["Ingest", "SQL is financial truth. Extraction is a document router, not a chatbot."],
            ["Match", "L0 exact → L1 alias → L2 fuzzy → L3 rank. The ranker cannot post the ledger."],
            ["Investigate", "Score bands. Adaptive retrieval, then optional LLM JSON."],
            ["Authorize", "Evidence IDs must exist. Decimal math must recompute. Fake clauses die here."],
          ].map(([t, b]) => (
            <li key={t} className="pt-4">
              <div className="text-sm font-medium">{t}</div>
              <p className="mt-2 text-sm leading-relaxed text-muted">{b}</p>
            </li>
          ))}
        </ol>
      </section>

      <section id="cases" className="mx-auto max-w-6xl px-6 pb-24">
        <p className="text-[11px] uppercase tracking-[0.28em] text-muted">Worked from the live run</p>
        <h2 className="display mt-3 text-4xl">The controller has a spine.</h2>
        <div className="mt-8 overflow-hidden rounded-2xl hairline">
          <table className="data-table">
            <thead className="bg-panel">
              <tr>
                <th>Verdict</th>
                <th>ID</th>
                <th>What happened</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <span className="text-accent">Authorized</span>
                </td>
                <td className="mono">TX_0022</td>
                <td className="text-muted">
                  Tata ₹697,217.48 vs INV_0022 ₹688,950.08. Variance 1.20% vs 2% cap. Gate recomputed Decimal. LLM not
                  used.
                </td>
              </tr>
              <tr>
                <td>
                  <span className="text-danger">Refused</span>
                </td>
                <td className="mono">TX_0002</td>
                <td className="text-muted">
                  Three invoices, no unique evidence. UNRESOLVED. The controller does not pick a winner.
                </td>
              </tr>
              <tr>
                <td>
                  <span className="text-warn">Blocked</span>
                </td>
                <td className="mono">HALLUCINATED_99</td>
                <td className="text-muted">
                  Invented contract + wrong difference. Unknown evidence ID. authorized: false.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <footer className="border-t border-line px-6 py-10">
        <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-4 text-sm text-muted md:flex-row md:items-center">
          <span>Vertex</span>
          <Link to="/app" className="text-fg hover:opacity-80">
            Open the control system →
          </Link>
        </div>
      </footer>
    </div>
  );
}

function Workflow() {
  return (
    <section id="flow" className="mx-auto max-w-6xl px-6 pb-20">
      <p className="text-[11px] uppercase tracking-[0.28em] text-muted">Workflow</p>
      <h2 className="display mt-3 text-4xl sm:text-5xl">How a document becomes a decision</h2>
      <p className="mt-4 max-w-2xl text-muted">
        We never send every page to the LLM. Extraction is a router. Matching is rules and rank. The LLM only proposes.
        The gate posts — or refuses.
      </p>

      <h3 className="mt-10 text-sm font-medium">1. Extract</h3>
      <div className="flow-row mt-4">
        <FlowBox k="01" t="PDF or image" d="Invoice, receipt, or statement lands in the router." />
        <Arrow />
        <FlowBox k="02" t="Selectable text?" d="If we can copy words, we use native PDF text. No vision. No LLM." />
        <Arrow />
        <FlowBox k="03" t="OCR vision model" d="Scan or photo: too little text. The OCR vision model reads pixels." />
        <Arrow />
        <FlowBox k="04" t="LLM vision (rare)" d="OCR still weak. LLM looks at the page. It must not invent amounts." />
        <Arrow />
        <FlowBox k="05" t="Python check" d="Line items + tax must equal total. Fail → EXTRACTION_ERROR. Pass → SQL." />
      </div>

      <h3 className="mt-12 text-sm font-medium">2. Close the books</h3>
      <div className="flow-row mt-4">
        <FlowBox k="06" t="SQL truth" d="Transactions and invoices live here. This is the ledger, not a chat." />
        <Arrow />
        <FlowBox k="07" t="L0 → L3 match" d="Exact, alias, fuzzy, then rank. The ranker cannot write the books." />
        <Arrow />
        <FlowBox k="08" t="Score bands" d="High score auto-matches. Mid band is an exception. Low score stays unmatched." />
        <Arrow />
        <FlowBox k="09" t="Evidence + LLM" d="Contracts from the evidence store. LLM proposes JSON. Duplicates skip the LLM." />
        <Arrow />
        <FlowBox k="10" t="Decision gate" d="Evidence IDs must exist. Decimal math must recompute. Fake clauses die. Then post or refuse." />
      </div>
    </section>
  );
}

function FlowBox({ k, t, d }: { k: string; t: string; d: string }) {
  return (
    <article className="flow-box">
      <div className="text-[10px] uppercase tracking-[0.16em] text-muted">{k}</div>
      <h4 className="mt-1 text-sm font-medium">{t}</h4>
      <p className="mt-2 text-xs leading-relaxed text-muted">{d}</p>
    </article>
  );
}

function Arrow() {
  return (
    <div className="flow-arrow" aria-hidden="true">
      →
    </div>
  );
}

function Stat({ n, l }: { n: string; l: string }) {
  return (
    <div className="px-6 py-8">
      <div className="display text-4xl">{n}</div>
      <div className="mt-2 text-sm text-muted">{l}</div>
    </div>
  );
}

function Engine({ k, title, model, body }: { k: string; title: string; model: string; body: string }) {
  return (
    <article className="tool-card rounded-2xl p-7">
      <div className="text-[11px] uppercase tracking-[0.18em] text-muted">{k}</div>
      <h3 className="mt-3 text-lg font-medium">{title}</h3>
      <div className="mono mt-1 text-[11px] text-accent">{model}</div>
      <p className="mt-4 text-sm leading-relaxed text-muted">{body}</p>
    </article>
  );
}

function ProductFrame() {
  const total = 200;
  return (
    <div className="relative">
      <div className="absolute -inset-8 rounded-[32px] bg-accent/5 blur-3xl" />
      <div className="relative overflow-hidden rounded-2xl border border-line bg-panel shadow-lift">
        <div className="flex items-center gap-2 border-b border-line px-4 py-3">
          <span className="h-2 w-2 rounded-full bg-[color:var(--muted)]/40" />
          <span className="h-2 w-2 rounded-full bg-[color:var(--muted)]/40" />
          <span className="h-2 w-2 rounded-full bg-[color:var(--muted)]/40" />
          <span className="ml-3 text-[11px] text-muted">Control system · last close</span>
          <span className="ml-auto rounded-full bg-accent/10 px-2 py-0.5 text-[10px] text-accent">live</span>
        </div>
        <div className="p-5">
          <div className="text-[11px] uppercase tracking-[0.16em] text-muted">Match F1</div>
          <div className="display mt-1 text-5xl">78.5%</div>
          <div className="mt-5 flex h-1.5 overflow-hidden rounded-full bg-[color:var(--line)]">
            {PARTITION.map((p) => (
              <div key={p.label} className={p.className} style={{ width: `${(p.n / total) * 100}%` }} />
            ))}
          </div>
          <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-[11px] text-muted">
            {PARTITION.map((p) => (
              <div key={p.label}>
                <span className="mono text-fg">{p.n}</span> {p.label}
              </div>
            ))}
          </div>
          <div className="mt-6 space-y-2">
            {[
              ["TX_0022", "Tata", "AUTO_RESOLVE"],
              ["TX_0002", "Ambiguous", "UNRESOLVED"],
              ["TX_0082", "Microsoft", "AUTO_RESOLVE"],
            ].map(([id, v, d]) => (
              <div key={id} className="flex items-center justify-between rounded-xl bg-[color:var(--elev)] px-3 py-2.5 text-xs">
                <span className="mono">{id}</span>
                <span className="text-muted">{v}</span>
                <span className={d === "UNRESOLVED" ? "text-danger" : "text-accent"}>{d}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
