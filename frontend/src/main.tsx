import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import "./index.css";
import Ledger from "./pages/Ledger";
import Reconcile from "./pages/Reconcile";
import Dashboard from "./pages/Dashboard";
import Chat from "./pages/Chat";

function Nav() {
  const cls = ({ isActive }: { isActive: boolean }) =>
    `px-4 py-2 border-b-2 ${isActive ? "border-ink font-medium" : "border-transparent text-ink/50"}`;
  return (
    <nav className="flex gap-2 border-b border-ink/20 mb-6">
      <NavLink to="/" end className={cls}>Ledger</NavLink>
      <NavLink to="/reconcile" className={cls}>Reconcile</NavLink>
      <NavLink to="/dashboard" className={cls}>Dashboard</NavLink>
      <NavLink to="/chat" className={cls}>Ask AI</NavLink>
    </nav>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <div className="max-w-5xl mx-auto px-4 py-6">
        <h1 className="font-display text-3xl text-ink mb-6">Kharcha</h1>
        <Nav />
        <Routes>
          <Route path="/" element={<Ledger />} />
          <Route path="/reconcile" element={<Reconcile />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/chat" element={<Chat />} />
        </Routes>
      </div>
    </BrowserRouter>
  </StrictMode>
);
