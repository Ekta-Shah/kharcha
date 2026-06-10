import { useCallback, useEffect, useState } from "react";
import { api, type Expense, type ParsedItem } from "../api";
import { CATEGORIES } from "../constants";
import ParsePreview from "../components/ParsePreview";
import VoiceInput from "../components/VoiceInput";

function fmt(n: number) {
  return "₹" + n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function groupByDate(expenses: Expense[]) {
  const map = new Map<string, Expense[]>();
  for (const e of expenses) {
    const list = map.get(e.date) ?? [];
    list.push(e);
    map.set(e.date, list);
  }
  return [...map.entries()].sort((a, b) => b[0].localeCompare(a[0]));
}

interface EditState {
  id: string;
  field: "item" | "category" | "cost";
  value: string;
}

export default function Ledger() {
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [preview, setPreview] = useState<{ items: ParsedItem[]; warnings: string[] } | null>(null);
  const [parsing, setParsing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [edit, setEdit] = useState<EditState | null>(null);

  const load = useCallback(async () => {
    try {
      setExpenses(await api.listExpenses());
    } catch (e) {
      setError(String(e));
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleText(text: string) {
    setError(null);
    setParsing(true);
    try {
      const result = await api.parse(text);
      setPreview(result);
    } catch (e) {
      setError("Parse failed: " + String(e));
    } finally {
      setParsing(false);
    }
  }

  async function handleConfirm(items: ParsedItem[]) {
    try {
      await api.createExpenses(
        items.map((i) => ({ ...i, source: "voice" as const, raw_text: null }))
      );
      setPreview(null);
      await load();
    } catch (e) {
      setError("Save failed: " + String(e));
    }
  }

  async function handleDelete(id: string) {
    await api.deleteExpense(id);
    setExpenses((prev) => prev.filter((e) => e.id !== id));
  }

  async function commitEdit() {
    if (!edit) return;
    const patch: Record<string, string | number> = {};
    if (edit.field === "cost") {
      patch.cost = parseFloat(edit.value) || 0;
    } else {
      patch[edit.field] = edit.value;
    }
    try {
      const updated = await api.patchExpense(edit.id, patch);
      setExpenses((prev) => prev.map((e) => (e.id === edit.id ? updated : e)));
    } catch (e) {
      setError("Update failed: " + String(e));
    }
    setEdit(null);
  }

  async function downloadXlsx() {
    const r = await api.exportXlsx();
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "kharcha.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  }

  const groups = groupByDate(expenses);
  const grandTotal = expenses.reduce((s, e) => s + e.cost, 0);

  return (
    <div>
      {/* Input area */}
      <div className="mb-6">
        <VoiceInput onResult={handleText} disabled={parsing} />
        {parsing && <p className="text-xs text-ink/40 mt-2 animate-pulse">Parsing…</p>}
        {error && <p className="text-xs text-ledgerRed mt-2">{error}</p>}
        {preview && (
          <ParsePreview
            items={preview.items}
            warnings={preview.warnings}
            onConfirm={handleConfirm}
            onDiscard={() => setPreview(null)}
          />
        )}
      </div>

      {/* Toolbar */}
      {expenses.length > 0 && (
        <div className="flex justify-between items-center mb-3">
          <p className="text-xs text-ink/40">{expenses.length} entries</p>
          <button
            onClick={downloadXlsx}
            className="text-xs border border-ink/20 px-3 py-1 rounded hover:border-ink"
          >
            ↓ Export Excel
          </button>
        </div>
      )}

      {/* Ledger table */}
      {groups.length === 0 ? (
        <p className="text-sm text-ink/30 text-center py-16">No entries yet. Say or type an expense above.</p>
      ) : (
        <div className="space-y-0">
          {groups.map(([date, rows]) => {
            const dayTotal = rows.reduce((s, e) => s + e.cost, 0);
            return (
              <div key={date}>
                <table className="w-full text-sm mb-0">
                  <tbody>
                    {rows.map((exp) => (
                      <tr key={exp.id} className="border-b border-ink/5 group hover:bg-ink/[0.02]">
                        <td className="py-1.5 pr-3 w-32 text-xs text-ink/40">{exp.date}</td>
                        <td className="py-1.5 pr-3">
                          {edit?.id === exp.id && edit.field === "item" ? (
                            <input
                              autoFocus
                              className="border-b border-ink w-full bg-transparent outline-none"
                              value={edit.value}
                              onChange={(e) => setEdit({ ...edit, value: e.target.value })}
                              onBlur={commitEdit}
                              onKeyDown={(e) => e.key === "Enter" && commitEdit()}
                            />
                          ) : (
                            <span
                              className="cursor-pointer hover:underline"
                              onClick={() => setEdit({ id: exp.id, field: "item", value: exp.item })}
                            >
                              {exp.item}
                            </span>
                          )}
                        </td>
                        <td className="py-1.5 pr-3 w-40">
                          {edit?.id === exp.id && edit.field === "category" ? (
                            <select
                              autoFocus
                              className="bg-transparent border-b border-ink outline-none text-xs w-full"
                              value={edit.value}
                              onChange={(e) => setEdit({ ...edit, value: e.target.value })}
                              onBlur={commitEdit}
                            >
                              {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
                            </select>
                          ) : (
                            <span
                              className="text-xs bg-ink/5 px-2 py-0.5 rounded cursor-pointer hover:bg-ink/10"
                              onClick={() => setEdit({ id: exp.id, field: "category", value: exp.category })}
                            >
                              {exp.category}
                            </span>
                          )}
                        </td>
                        <td className="py-1.5 pr-3 text-right font-mono w-28">
                          {edit?.id === exp.id && edit.field === "cost" ? (
                            <input
                              autoFocus
                              type="number"
                              className="border-b border-ink bg-transparent outline-none text-right w-full font-mono"
                              value={edit.value}
                              onChange={(e) => setEdit({ ...edit, value: e.target.value })}
                              onBlur={commitEdit}
                              onKeyDown={(e) => e.key === "Enter" && commitEdit()}
                            />
                          ) : (
                            <span
                              className="cursor-pointer hover:underline"
                              onClick={() => setEdit({ id: exp.id, field: "cost", value: String(exp.cost) })}
                            >
                              {fmt(exp.cost)}
                            </span>
                          )}
                        </td>
                        <td className="py-1.5 w-6 opacity-0 group-hover:opacity-100">
                          <button
                            onClick={() => handleDelete(exp.id)}
                            className="text-ink/30 hover:text-ledgerRed text-xs"
                          >
                            ✕
                          </button>
                        </td>
                      </tr>
                    ))}
                    {/* Daily total row — double rule accountant underline */}
                    <tr
                      style={{
                        borderTop: "1px solid #AE2B26",
                        borderBottom: "3px double #AE2B26",
                      }}
                      className="bg-paper"
                    >
                      <td className="py-1 pr-3 text-xs text-ink/40">{date}</td>
                      <td className="py-1 pr-3 text-xs font-medium text-ledgerRed">
                        Daily Total ({rows.length} item{rows.length !== 1 ? "s" : ""})
                      </td>
                      <td />
                      <td className="py-1 pr-3 text-right font-mono font-medium text-ledgerRed">
                        {fmt(dayTotal)}
                      </td>
                      <td />
                    </tr>
                  </tbody>
                </table>
              </div>
            );
          })}

          {/* Grand total */}
          <div className="flex justify-end pt-4 border-t-2 border-ink mt-4">
            <span className="font-mono font-bold text-lg">
              Grand Total: {fmt(grandTotal)}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
