"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardHeader } from "@/components/ui/card";
import { QueryState } from "@/components/ui/query-state";
import { abbreviate, formatDate, formatMoney, formatNumber, formatPercent } from "@/lib/format";
import { marketApi, type Fundamentals } from "@/lib/market";

type Year = Fundamentals["years"][number];
type Row = {
  label: string;
  get: (y: Year) => number | null;
  fmt: (v: number) => string;
  hint?: string;
};

const usd = (v: number) => abbreviate(v, "USD");
const pct = (v: number) => formatPercent(v);
const pctU = (v: number) => formatPercent(v, { signed: false });

const SECTIONS: { title: string; rows: Row[] }[] = [
  {
    title: "Income",
    rows: [
      { label: "Revenue", get: (y) => y.revenue, fmt: usd },
      { label: "Revenue growth", get: (y) => y.revenue_growth, fmt: pct },
      { label: "Gross margin", get: (y) => y.gross_margin, fmt: pctU },
      { label: "Operating margin", get: (y) => y.operating_margin, fmt: pct },
      { label: "Net income", get: (y) => y.net_income, fmt: usd },
      { label: "Net margin", get: (y) => y.net_margin, fmt: pct },
      { label: "EPS (diluted)", get: (y) => y.eps_diluted, fmt: (v) => formatMoney(v, "USD") },
    ],
  },
  {
    title: "Cash flow",
    rows: [
      { label: "Operating cash flow", get: (y) => y.operating_cash_flow, fmt: usd },
      { label: "Capital spending", get: (y) => y.capex, fmt: usd },
      { label: "Free cash flow", get: (y) => y.free_cash_flow, fmt: usd },
    ],
  },
  {
    title: "Balance sheet",
    rows: [
      { label: "Cash", get: (y) => y.cash, fmt: usd },
      { label: "Total assets", get: (y) => y.total_assets, fmt: usd },
      { label: "Total liabilities", get: (y) => y.total_liabilities, fmt: usd },
      { label: "Long-term debt", get: (y) => y.long_term_debt, fmt: usd },
      { label: "Shareholders' equity", get: (y) => y.equity, fmt: usd },
      { label: "Debt / equity", get: (y) => y.debt_to_equity, fmt: (v) => `${formatNumber(v)}×` },
    ],
  },
];

export function FundamentalsPanel({ id }: { id: string }) {
  const query = useQuery({
    queryKey: ["fundamentals", id],
    queryFn: () => marketApi.fundamentals(id),
  });
  return (
    <QueryState query={query}>
      {(f) =>
        !f.available ? (
          <Card>
            <CardHeader title="Fundamentals" />
            <p className="text-sm text-muted">Fundamentals not available. {f.reason}</p>
          </Card>
        ) : (
          <Card>
            <CardHeader
              title="Fundamentals"
              subtitle={`Annual, from 10-K filings${f.last_filed ? `, latest filed ${formatDate(f.last_filed)}` : ""}`}
            />
            <div className="overflow-x-auto">
              <table className="num w-full text-sm">
                <caption className="sr-only">Annual financials in US dollars</caption>
                <thead>
                  <tr className="text-xs text-muted">
                    <th scope="col" className="py-1.5 pr-3 text-left font-medium">
                      Fiscal year
                    </th>
                    {f.years.map((y) => (
                      <th
                        key={y.period_end}
                        scope="col"
                        className="px-2 text-right font-medium"
                        title={`Year ended ${formatDate(y.period_end)}`}
                      >
                        FY{String(y.fiscal_year).slice(2)}
                      </th>
                    ))}
                  </tr>
                </thead>
                {SECTIONS.map((sec) => (
                  <tbody key={sec.title}>
                    <tr>
                      <th
                        scope="rowgroup"
                        colSpan={f.years.length + 1}
                        className="label pb-1 pt-3 text-left"
                      >
                        {sec.title}
                      </th>
                    </tr>
                    {sec.rows.map((r) => (
                      <tr key={r.label} className="border-t border-border">
                        <th scope="row" className="py-1.5 pr-3 text-left font-normal text-muted">
                          {r.label}
                        </th>
                        {f.years.map((y) => {
                          const v = r.get(y);
                          return (
                            <td key={y.period_end} className="px-2 text-right">
                              {v === null ? "—" : r.fmt(v)}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                ))}
              </table>
            </div>
            <p className="mt-3 text-xs text-subtle">
              Source: {f.source}. Figures are as reported in US dollars; a dash means the company
              did not report that line in a standard form. Fiscal years end on the company&apos;s
              own year-end date.
            </p>
          </Card>
        )
      }
    </QueryState>
  );
}
