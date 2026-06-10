import { useCallback, useRef, useState } from "react";
import { api, type MatchedRow, type ReconBuckets } from "../api";

function fmt(n: number) {
  return "₹" + n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function ConfidenceChip({ status, confidence }: { status: string; confidence: number | null }) {
  const pct = confidence != null ? Math.round(confidence * 100) : null;
  const color =
    status === "exact" ? "bg-emerald-100 text-emerald-800" :
    status === "fuzzy" ? "bg-amber-100 text-amber-800" :
    status === "llm"   ? "bg-purple-100 text-purple-800" :
    "bg-blue-100 text-blue-800";
  return (
    <span className={`text-xs px-2 py-0.5 rounded font-medium ${color}`}>
      {status}{pct != null ? ` ${pct}%` : ""}
    </span>
  );
}

interface UploadResult {
  statement_id: string;
  bank: string;
  filename: string;
  total: number;
  new: number;
  period_start: string;
  period_end: string;
}

export default function Reconcile() {
  const [uploading, setUploading] = useState(false);
  const [upload, setUpload] = useState<UploadResult | null>(null);
  const [running, setRunning] = useState(false);
  const [buckets, setBuckets] = useState<ReconBuckets | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(async (file: File) => {
    setError(null);
    setUploading(true);
    setBuckets(null);
    try {
      const result = await api.uploadStatement(file);
      setUpload(result as UploadResult);
    } catch (e) {
      setError("Upload failed: " + String(e));
    } finally {
      setUploading(false);
    }
  }, []);

  async function runRecon() {
    if (!upload) return;
    setError(null);
    setRunning(true);
    try {
      await api.runRecon(upload.statement_id);
      const b = await api.getReconBuckets(upload.statement_id);
      setBuckets(b);
    } catch (e) {
      setError("Reconciliation failed: " + String(e));
    } finally {
      setRunning(false);
    }
  }

  async function handleConfirm(match_id: string, accepted: boolean) {
    await api.confirmMatch(match_id, accepted);
    if (!upload) return;
    const b = await api.getReconBuckets(upload.statement_id);
    setBuckets(b);
  }

  async function addToLedger(txn: ReconBuckets["bank_only"][0]) {
    await api.createExpenses([{
      date: txn.txn_date,
      item: txn.suggested_item || txn.description.slice(0, 40),
      category: "Other",
      cost: txn.amount,
      source: "bank_import" as const,
      raw_text: txn.description,
    }]);
    if (upload) {
      const b = await api.getReconBuckets(upload.statement_id);
      setBuckets(b);
    }
  }

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  return (
    <div>
      {/* Upload zone */}
      {!upload && (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors ${
            dragging ? "border-ink bg-ink/5" : "border-ink/20 hover:border-ink/50"
          }`}
        >
          <p className="text-ink/50 text-sm">
            {uploading ? "Uploading…" : "Drop bank statement (CSV or XLSX) here, or click to browse"}
          </p>
          <input
            ref={inputRef}
            type="file"
            accept=".csv,.xlsx"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
          />
        </div>
      )}

      {error && <p className="text-xs text-ledgerRed mt-2">{error}</p>}

      {/* Statement info + run button */}
      {upload && !buckets && (
        <div className="border border-ink/20 rounded p-4 bg-white">
          <div className="flex justify-between items-start">
            <div>
              <p className="font-medium">{upload.filename}</p>
              <p className="text-xs text-ink/50 mt-1">
                {upload.bank.toUpperCase()} · {upload.period_start} → {upload.period_end} · {upload.total} transactions ({upload.new} new)
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => { setUpload(null); setBuckets(null); }}
                className="text-xs border border-ink/20 px-3 py-1.5 rounded hover:border-ink"
              >
                Change file
              </button>
              <button
                onClick={runRecon}
                disabled={running}
                className="text-sm bg-ink text-white px-4 py-1.5 rounded hover:bg-ink/80 disabled:opacity-50"
              >
                {running ? "Running…" : "Run Reconciliation"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Results */}
      {buckets && (
        <div className="space-y-6">
          {/* Summary header */}
          <div className="flex gap-6 items-center border-b border-ink/10 pb-4">
            <span className="text-sm font-medium text-emerald-700">
              ✓ {buckets.summary.total_matched} matched
            </span>
            <span className="text-sm text-ink/50">
              {buckets.summary.total_ledger_only} ledger-only (likely cash)
            </span>
            <span className="text-sm text-ledgerRed">
              {buckets.summary.total_bank_only} bank-only · {fmt(buckets.summary.unaccounted_amount)} unaccounted
            </span>
            <button
              onClick={runRecon}
              className="ml-auto text-xs border border-ink/20 px-3 py-1 rounded hover:border-ink"
            >
              Re-run
            </button>
          </div>

          {/* Matched */}
          {buckets.matched.length > 0 && (
            <section>
              <h3 className="text-xs uppercase tracking-widest text-ink/40 mb-2">Matched</h3>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-ink/40 border-b border-ink/10">
                    <th className="text-left py-1 pr-3 w-32">Date</th>
                    <th className="text-left py-1 pr-3">Ledger item</th>
                    <th className="text-left py-1 pr-3">Bank description</th>
                    <th className="text-right py-1 pr-3 w-24 font-mono">Amount</th>
                    <th className="text-left py-1 pr-3 w-28">Confidence</th>
                    <th className="w-20" />
                  </tr>
                </thead>
                <tbody>
                  {buckets.matched.map((m) => (
                    <MatchRow key={m.match_id} m={m} onConfirm={handleConfirm} />
                  ))}
                </tbody>
              </table>
            </section>
          )}

          {/* Bank-only */}
          {buckets.bank_only.length > 0 && (
            <section>
              <h3 className="text-xs uppercase tracking-widest text-ledgerRed mb-2">
                Bank-only — not in ledger
              </h3>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-ink/40 border-b border-ink/10">
                    <th className="text-left py-1 pr-3 w-28">Date</th>
                    <th className="text-left py-1 pr-3">Description</th>
                    <th className="text-left py-1 pr-3">Suggested item</th>
                    <th className="text-right py-1 pr-3 w-24 font-mono">Amount</th>
                    <th className="w-24" />
                  </tr>
                </thead>
                <tbody>
                  {buckets.bank_only.map((t) => (
                    <tr key={t.id} className="border-b border-ink/5">
                      <td className="py-1.5 pr-3 text-xs text-ink/40">{t.txn_date}</td>
                      <td className="py-1.5 pr-3 text-xs text-ink/60 truncate max-w-xs">{t.description}</td>
                      <td className="py-1.5 pr-3 text-xs italic text-ink/50">{t.suggested_item}</td>
                      <td className="py-1.5 pr-3 text-right font-mono text-ledgerRed">{fmt(t.amount)}</td>
                      <td className="py-1.5">
                        <button
                          onClick={() => addToLedger(t)}
                          className="text-xs bg-ink/5 hover:bg-ink/10 px-2 py-0.5 rounded"
                        >
                          + Add to ledger
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          {/* Ledger-only */}
          {buckets.ledger_only.length > 0 && (
            <section>
              <h3 className="text-xs uppercase tracking-widest text-ink/40 mb-2">
                Ledger-only — likely cash
              </h3>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-ink/40 border-b border-ink/10">
                    <th className="text-left py-1 pr-3 w-28">Date</th>
                    <th className="text-left py-1 pr-3">Item</th>
                    <th className="text-left py-1 pr-3">Category</th>
                    <th className="text-right py-1 pr-3 w-24 font-mono">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {buckets.ledger_only.map((e) => (
                    <tr key={e.id} className="border-b border-ink/5">
                      <td className="py-1.5 pr-3 text-xs text-ink/40">{e.date}</td>
                      <td className="py-1.5 pr-3">{e.item}</td>
                      <td className="py-1.5 pr-3 text-xs text-ink/50">{e.category}</td>
                      <td className="py-1.5 pr-3 text-right font-mono">{fmt(e.cost)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}
        </div>
      )}
    </div>
  );
}

function MatchRow({
  m,
  onConfirm,
}: {
  m: MatchedRow;
  onConfirm: (id: string, accepted: boolean) => void;
}) {
  return (
    <tr className="border-b border-ink/5 group">
      <td className="py-1.5 pr-3 text-xs text-ink/40">
        {m.expense?.date ?? m.bank_txn?.txn_date}
      </td>
      <td className="py-1.5 pr-3">{m.expense?.item ?? "—"}</td>
      <td className="py-1.5 pr-3 text-xs text-ink/60 truncate max-w-[200px]">
        {m.bank_txn?.description ?? "—"}
      </td>
      <td className="py-1.5 pr-3 text-right font-mono">
        {m.expense ? fmt(m.expense.cost) : "—"}
      </td>
      <td className="py-1.5 pr-3">
        <div className="flex flex-col gap-0.5">
          <ConfidenceChip status={m.status} confidence={m.confidence} />
          {m.rationale && (
            <span className="text-xs text-ink/40">{m.rationale}</span>
          )}
        </div>
      </td>
      <td className="py-1.5">
        {m.confirmed ? (
          <span className="text-xs text-emerald-600">✓ confirmed</span>
        ) : (
          <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={() => onConfirm(m.match_id, true)}
              className="text-xs px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded hover:bg-emerald-100"
            >
              ✓
            </button>
            <button
              onClick={() => onConfirm(m.match_id, false)}
              className="text-xs px-2 py-0.5 bg-red-50 text-ledgerRed rounded hover:bg-red-100"
            >
              ✕
            </button>
          </div>
        )}
      </td>
    </tr>
  );
}
