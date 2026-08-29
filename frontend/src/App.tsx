import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  ArrowLeftRight,
  BarChart3,
  Landmark,
  LayoutDashboard,
  MessageSquare,
  Play,
  ScrollText,
  Wallet,
} from "lucide-react";
import Dashboard from "./pages/Dashboard";
import RunPage from "./pages/RunPage";
import Transactions from "./pages/Transactions";
import ExceptionCenter from "./pages/ExceptionCenter";
import ExceptionDetail from "./pages/ExceptionDetail";
import Benchmark from "./pages/Benchmark";
import Stress from "./pages/Stress";
import Cash from "./pages/Cash";
import Audit from "./pages/Audit";
import GraphPage from "./pages/GraphPage";
import Landing from "./pages/Landing";
import SettlementAgent from "./pages/SettlementAgent";
import { RazorpayName } from "./components/RazorpayName";
import { ThemeToggle } from "./components/ThemeToggle";
import { CustomCursor } from "./components/CustomCursor";

const links = [
  ["/app", "Overview", LayoutDashboard],
  ["/app/run", "Close books", Play],
  ["/app/transactions", "Ledger", ArrowLeftRight],
  ["/app/exceptions", "Exceptions", AlertTriangle],
  ["/app/settlement", "Settlement", MessageSquare],
  ["/app/cash", "Cash", Wallet],
  ["/app/benchmark", "Benchmark", BarChart3],
  ["/app/stress", "Stress", Activity],
  ["/app/audit", "Audit", ScrollText],
] as const;

function Shell() {
  return (
    <div className="app-shell flex min-h-screen hero-glow grain text-fg">
      <CustomCursor />
      <aside className="glass flex w-[232px] shrink-0 flex-col border-r px-4 py-5">
        <NavLink to="/" className="mb-8 flex items-center gap-3 px-2">
          <div className="mark">V</div>
        </NavLink>
        <nav className="flex flex-1 flex-col gap-0.5 text-[13px]">
          {links.map(([to, label, Icon]) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/app"}
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded-lg px-2.5 py-2 ${
                  isActive ? "bg-[color:var(--elev)] text-fg" : "text-muted hover:bg-[color:var(--elev)] hover:text-fg"
                }`
              }
            >
              <Icon size={15} strokeWidth={1.75} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-4 flex items-center gap-2 rounded-xl bg-[color:var(--elev)] px-3 py-2 text-[11px] text-muted">
          <Landmark size={14} />
          SQL truth · gate authority
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="control-bar">
          <div className="flex items-center gap-2.5 text-sm">
            <span className="control-dot" />
            <span className="font-medium">Control system</span>
            <span className="text-muted">· books live</span>
          </div>
          <ThemeToggle />
        </header>
        <main className="min-w-0 flex-1 overflow-auto">
          <div className="mx-auto max-w-6xl px-6 py-8">
            <Routes>
              <Route path="/app" element={<Dashboard />} />
              <Route path="/app/run" element={<RunPage />} />
              <Route path="/app/transactions" element={<Transactions />} />
              <Route path="/app/exceptions" element={<ExceptionCenter />} />
              <Route path="/app/exceptions/:id" element={<ExceptionDetail />} />
              <Route path="/app/settlement" element={<SettlementAgent />} />
              <Route path="/app/benchmark" element={<Benchmark />} />
              <Route path="/app/stress" element={<Stress />} />
              <Route path="/app/cash" element={<Cash />} />
              <Route path="/app/audit" element={<Audit />} />
              <Route path="/app/graph/:txId" element={<GraphPage />} />
            </Routes>
          </div>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  const loc = useLocation();
  if (loc.pathname === "/" || loc.pathname === "") return <Landing />;
  return <Shell />;
}
