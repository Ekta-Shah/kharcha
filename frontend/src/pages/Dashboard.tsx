import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from "recharts";
import { api } from "../api";

type MonthData = {
  month: string;
  total: number;
  by_category: Record<string, number>;
  mom_delta_pct: number | null;
};

type Summary = {
  months: MonthData[];
  recurring: Array<{ item: string; avg_amount: number; months: string[] }>;
};

const CAT_COLORS = [
  "#173F35", "#2D6A57", "#4A9E82", "#6DC4A8", "#99D8C4",
  "#AE2B26", "#D45C57", "#E88F8C", "#F4C2C0",
  "#5B4A3A", "#8C7B6A", "#BDB0A4",
  "#3A5B4A", "#7A9E8C", "#B0CABF",
];

function fmt(n: number) {
  return "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function MonthSelector({
  months, selected, onChange,
}: { months: string[]; selected: string; onChange: (m: string) => void }) {
  return (
    <div className="flex gap-2 flex-wrap">
      {months.map((m) => (
        <button
          key={m}
          onClick={() => onChange(m)}
          className={`px-3 py-1 rounded text-sm font-medium border transition-colors ${
            m === selected
              ? "bg-ink text-paper border-ink"
              : "bg-paper text-ink border-ink/20 hover:border-ink/50"
          }`}
        >
          {m}
        </button>
      ))}
    </div>
  );
}

function DeltaChip({ pct }: { pct: number | null }) {
  if (pct === null) return null;
  const up = pct > 0;
  return (
    <span
      className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
        up ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700"
      }`}
    >
      {up ? "▲" : "▼"} {Math.abs(pct)}%
    </span>
  );
}

function SpendCard({ month }: { month: MonthData | undefined }) {
  if (!month) return null;
  return (
    <div className="bg-paper border border-ink/10 rounded-xl p-5 flex flex-col gap-1">
      <div className="text-xs text-ink/50 uppercase tracking-wider">Total Spend</div>
      <div className="text-3xl font-bold text-ink">{fmt(month.total)}</div>
      <DeltaChip pct={month.mom_delta_pct} />
    </div>
  );
}

function TopCategoryCard({ month }: { month: MonthData | undefined }) {
  if (!month) return null;
  const entries = Object.entries(month.by_category);
  if (!entries.length) return null;
  const [top, amt] = entries[0];
  return (
    <div className="bg-paper border border-ink/10 rounded-xl p-5 flex flex-col gap-1">
      <div className="text-xs text-ink/50 uppercase tracking-wider">Top Category</div>
      <div className="text-xl font-bold text-ink truncate">{top}</div>
      <div className="text-ink/70 text-sm">{fmt(amt)}</div>
    </div>
  );
}

function CategoryBar({ month }: { month: MonthData | undefined }) {
  if (!month) return null;
  const data = Object.entries(month.by_category).map(([name, value]) => ({ name, value }));
  return (
    <div className="bg-paper border border-ink/10 rounded-xl p-5">
      <div className="text-sm font-semibold text-ink mb-4">Spend by Category</div>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
          <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} />
          <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={110} />
          <Tooltip formatter={(v: number) => fmt(v)} />
          <Bar dataKey="value" radius={[0, 4, 4, 0]}>
            {data.map((_, i) => <Cell key={i} fill={CAT_COLORS[i % CAT_COLORS.length]} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function MonthlyTrendBar({ months }: { months: MonthData[] }) {
  if (months.length < 2) return null;
  const data = months.map((m) => ({ month: m.month, total: m.total }));
  return (
    <div className="bg-paper border border-ink/10 rounded-xl p-5">
      <div className="text-sm font-semibold text-ink mb-4">Monthly Trend</div>
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={data} margin={{ left: 8, right: 8 }}>
          <XAxis dataKey="month" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} />
          <Tooltip formatter={(v: number) => fmt(v)} />
          <Bar dataKey="total" fill="#173F35" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function CategoryPie({ month }: { month: MonthData | undefined }) {
  if (!month) return null;
  const data = Object.entries(month.by_category)
    .slice(0, 8)
    .map(([name, value]) => ({ name, value }));
  return (
    <div className="bg-paper border border-ink/10 rounded-xl p-5">
      <div className="text-sm font-semibold text-ink mb-4">Category Split</div>
      <ResponsiveContainer width="100%" height={220}>
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            outerRadius={80}
            label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
            labelLine={false}
          >
            {data.map((_, i) => <Cell key={i} fill={CAT_COLORS[i % CAT_COLORS.length]} />)}
          </Pie>
          <Legend iconSize={10} wrapperStyle={{ fontSize: 11 }} />
          <Tooltip formatter={(v: number) => fmt(v)} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

function RecurringList({ recurring, month }: { recurring: Summary["recurring"]; month: string }) {
  const forMonth = recurring.filter((r) => r.months.includes(month));
  if (!forMonth.length) return null;
  return (
    <div className="bg-paper border border-ink/10 rounded-xl p-5">
      <div className="text-sm font-semibold text-ink mb-3">Recurring Payments</div>
      <ul className="space-y-2">
        {forMonth.map((r) => (
          <li key={r.item} className="flex justify-between text-sm">
            <span className="text-ink capitalize">{r.item}</span>
            <span className="font-mono text-ink/80">{fmt(r.avg_amount)}/mo</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function InsightsBlock({ month }: { month: string }) {
  const [text, setText] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setText(null);
    setErr(null);
    setLoading(true);
    api.insights(month)
      .then((r) => setText(r.insights))
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [month]);

  return (
    <div className="bg-paper border border-ink/10 rounded-xl p-5">
      <div className="text-sm font-semibold text-ink mb-3">AI Insights</div>
      {loading && <div className="text-ink/40 text-sm animate-pulse">Generating…</div>}
      {err && <div className="text-red-600 text-sm">{err}</div>}
      {text && <p className="text-sm text-ink/80 leading-relaxed">{text}</p>}
    </div>
  );
}

export default function Dashboard() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.monthlySummary()
      .then((s) => {
        setSummary(s);
        if (s.months.length > 0) setSelected(s.months[s.months.length - 1].month);
      })
      .catch((e) => setErr(e.message));
  }, []);

  if (err) return <div className="text-red-600 p-4">{err}</div>;
  if (!summary) return <div className="text-ink/40 p-4 animate-pulse">Loading…</div>;
  if (!summary.months.length) return <div className="text-ink/40 p-4">No data yet. Add some expenses first.</div>;

  const month = summary.months.find((m) => m.month === selected);

  return (
    <div className="space-y-6">
      <MonthSelector
        months={summary.months.map((m) => m.month)}
        selected={selected}
        onChange={setSelected}
      />

      <div className="grid grid-cols-2 gap-4">
        <SpendCard month={month} />
        <TopCategoryCard month={month} />
      </div>

      <MonthlyTrendBar months={summary.months} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <CategoryBar month={month} />
        <CategoryPie month={month} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <RecurringList recurring={summary.recurring} month={selected} />
        {selected && <InsightsBlock month={selected} />}
      </div>
    </div>
  );
}
