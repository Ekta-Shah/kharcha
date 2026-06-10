import { useState } from "react";
import type { ParsedItem } from "../api";
import { CATEGORIES } from "../constants";

interface Props {
  items: ParsedItem[];
  warnings: string[];
  onConfirm: (items: ParsedItem[]) => void;
  onDiscard: () => void;
}

export default function ParsePreview({ items, warnings, onConfirm, onDiscard }: Props) {
  const [rows, setRows] = useState<ParsedItem[]>(items);

  function update(i: number, field: keyof ParsedItem, value: string | number) {
    setRows((prev) => prev.map((r, idx) => idx === i ? { ...r, [field]: value } : r));
  }

  function remove(i: number) {
    setRows((prev) => prev.filter((_, idx) => idx !== i));
  }

  return (
    <div className="border border-ink/20 rounded bg-white mt-3 p-4">
      <p className="text-xs text-ink/50 uppercase tracking-widest mb-3">Review before saving</p>
      {warnings.map((w, i) => (
        <p key={i} className="text-xs text-amber-700 mb-2">⚠ {w}</p>
      ))}
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-ink/10 text-xs text-ink/40 uppercase">
            <th className="text-left py-1 pr-2 w-28">Date</th>
            <th className="text-left py-1 pr-2">Item</th>
            <th className="text-left py-1 pr-2 w-40">Category</th>
            <th className="text-right py-1 pr-2 w-24 font-mono">Amount</th>
            <th className="w-6" />
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-ink/5">
              <td className="py-1 pr-2">
                <input
                  type="date"
                  value={row.date}
                  onChange={(e) => update(i, "date", e.target.value)}
                  className="w-full border-b border-transparent focus:border-ink/30 bg-transparent text-xs outline-none"
                />
              </td>
              <td className="py-1 pr-2">
                <input
                  value={row.item}
                  onChange={(e) => update(i, "item", e.target.value)}
                  className="w-full border-b border-transparent focus:border-ink/30 bg-transparent outline-none"
                />
              </td>
              <td className="py-1 pr-2">
                <select
                  value={row.category}
                  onChange={(e) => update(i, "category", e.target.value)}
                  className="w-full bg-transparent border-b border-transparent focus:border-ink/30 outline-none text-xs"
                >
                  {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
                </select>
              </td>
              <td className="py-1 pr-2 text-right">
                <input
                  type="number"
                  value={row.cost}
                  min={0}
                  onChange={(e) => update(i, "cost", parseFloat(e.target.value) || 0)}
                  className="w-full text-right border-b border-transparent focus:border-ink/30 bg-transparent font-mono outline-none"
                />
              </td>
              <td className="py-1 text-center">
                <button onClick={() => remove(i)} className="text-ink/30 hover:text-ledgerRed text-xs">✕</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex gap-2 mt-4 justify-end">
        <button onClick={onDiscard} className="px-4 py-1.5 text-sm border border-ink/20 rounded hover:border-ink">
          Discard
        </button>
        <button
          onClick={() => onConfirm(rows)}
          disabled={rows.length === 0}
          className="px-4 py-1.5 text-sm bg-ink text-white rounded hover:bg-ink/80 disabled:opacity-40"
        >
          Save {rows.length} item{rows.length !== 1 ? "s" : ""}
        </button>
      </div>
    </div>
  );
}
