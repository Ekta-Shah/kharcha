export interface ParsedItem {
  date: string;
  item: string;
  category: string;
  cost: number;
}

export interface ParseResponse {
  items: ParsedItem[];
  warnings: string[];
}

export interface Expense {
  id: string;
  date: string;
  item: string;
  category: string;
  cost: number;
  source: string;
  raw_text: string | null;
  created_at: string;
}

export interface ExpensePatch {
  date?: string;
  item?: string;
  category?: string;
  cost?: number;
}

export interface BankTxn {
  id: string;
  txn_date: string;
  description: string;
  amount: number;
  is_debit: boolean;
  suggested_item?: string;
}

export interface MatchedRow {
  match_id: string;
  status: string;
  confidence: number | null;
  rationale: string | null;
  confirmed: boolean;
  expense: Expense | null;
  bank_txn: BankTxn | null;
}

export interface ReconBuckets {
  matched: MatchedRow[];
  ledger_only: Expense[];
  bank_only: (BankTxn & { suggested_item: string })[];
  summary: {
    total_matched: number;
    total_ledger_only: number;
    total_bank_only: number;
    unaccounted_amount: number;
  };
}

const BASE = "/api";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export const api = {
  parse: (text: string) =>
    req<ParseResponse>("/parse", { method: "POST", body: JSON.stringify({ text }) }),

  createExpenses: (items: Omit<Expense, "id" | "created_at">[]) =>
    req<Expense[]>("/expenses", { method: "POST", body: JSON.stringify(items) }),

  listExpenses: (from?: string, to?: string) => {
    const params = new URLSearchParams();
    if (from) params.set("from_date", from);
    if (to) params.set("to_date", to);
    return req<Expense[]>(`/expenses?${params}`);
  },

  patchExpense: (id: string, patch: ExpensePatch) =>
    req<Expense>(`/expenses/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),

  deleteExpense: (id: string) =>
    fetch(BASE + `/expenses/${id}`, { method: "DELETE" }),

  exportXlsx: (from?: string, to?: string) => {
    const params = new URLSearchParams();
    if (from) params.set("from_date", from);
    if (to) params.set("to_date", to);
    return fetch(BASE + `/export/xlsx?${params}`);
  },

  uploadStatement: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return fetch(BASE + "/statements/upload", { method: "POST", body: form }).then(
      (r) => r.json() as Promise<{ statement_id: string; bank: string; filename: string; total: number; new: number; duplicates: number; period_start: string; period_end: string }>
    );
  },

  runRecon: (statement_id: string) =>
    req<{ matched: number; ledger_only: number; bank_only: number }>(
      "/recon/run", { method: "POST", body: JSON.stringify({ statement_id }) }
    ),

  getReconBuckets: (statement_id: string) =>
    req<ReconBuckets>(`/recon/${statement_id}`),

  confirmMatch: (match_id: string, accepted: boolean) =>
    req<{ accepted: boolean }>("/recon/confirm", {
      method: "POST", body: JSON.stringify({ match_id, accepted }),
    }),

  manualMatch: (expense_id: string, bank_txn_id: string) =>
    req("/recon/match", { method: "POST", body: JSON.stringify({ expense_id, bank_txn_id }) }),

  monthlySummary: () =>
    req<{
      months: Array<{
        month: string;
        total: number;
        by_category: Record<string, number>;
        mom_delta_pct: number | null;
      }>;
      recurring: Array<{ item: string; avg_amount: number; months: string[] }>;
    }>("/dashboard/monthly"),

  insights: (month: string) =>
    req<{ month: string; insights: string; cached: boolean }>(`/dashboard/insights?month=${month}`),
};
