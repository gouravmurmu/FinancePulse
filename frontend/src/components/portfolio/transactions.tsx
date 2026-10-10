"use client";

import { cn } from "@/lib/cn";
import { useQuery } from "@tanstack/react-query";
import { Download, Pencil, Trash2, Upload } from "lucide-react";
import { useMemo, useState } from "react";
import { Card, CardHeader } from "@/components/ui/card";
import { QueryState } from "@/components/ui/query-state";
import { Segmented } from "@/components/ui/segmented";
import { ApiError } from "@/lib/api";
import { formatDate, formatMoney, formatNumber } from "@/lib/format";
import { ASSET_CLASS_LABEL, marketApi, type Instrument } from "@/lib/market";
import {
  usePortfolioMutations,
  useTransactions,
  type Portfolio,
  type Transaction,
  type TransactionInput,
  type Unit,
} from "@/lib/portfolio";
import { buttonClass, errorMessage, inputClass, primaryClass } from "./forms";

const HOLDABLE = ["equity", "etf", "crypto", "commodity"];
const UNIT_LABEL: Record<Unit, string> = { unit: "units", troy_oz: "troy ounces", gram: "grams" };

function today() {
  return new Date().toISOString().slice(0, 10);
}

export function Transactions({ portfolio }: { portfolio: Portfolio }) {
  const txs = useTransactions(portfolio.id);
  const [editing, setEditing] = useState<Transaction | null>(null);
  return (
    <div className="grid gap-6 lg:grid-cols-[380px_1fr] [&>*]:min-w-0">
      <div className="flex flex-col gap-6">
        <TransactionForm
          key={editing?.id ?? "new"}
          portfolio={portfolio}
          editing={editing}
          onDone={() => setEditing(null)}
        />
        <CsvTools portfolio={portfolio} />
      </div>
      <Card>
        <CardHeader title="Ledger" subtitle="Newest first. Edits recalculate every figure." />
        <QueryState query={txs}>
          {(list) =>
            list.length ? (
              <Ledger portfolio={portfolio} list={list} onEdit={setEditing} />
            ) : (
              <p className="text-muted">
                No transactions yet. Add one on the left or import a CSV.
              </p>
            )
          }
        </QueryState>
      </Card>
    </div>
  );
}

function TransactionForm({
  portfolio,
  editing,
  onDone,
}: {
  portfolio: Portfolio;
  editing: Transaction | null;
  onDone: () => void;
}) {
  const { addTx, updateTx } = usePortfolioMutations();
  const instruments = useQuery({ queryKey: ["instruments"], queryFn: marketApi.instruments });
  const [form, setForm] = useState<TransactionInput>(
    editing
      ? {
          instrument_id: editing.instrument_id,
          side: editing.side,
          trade_date: editing.trade_date,
          quantity: editing.quantity,
          unit: editing.unit,
          price: editing.price,
          fees: editing.fees,
          notes: editing.notes,
        }
      : {
          instrument_id: "",
          side: "buy",
          trade_date: today(),
          quantity: 0,
          unit: "unit",
          price: 0,
          fees: 0,
          notes: null,
        },
  );
  const [saved, setSaved] = useState<string | null>(null);
  const holdable = useMemo(
    () => (instruments.data ?? []).filter((i) => HOLDABLE.includes(i.asset_class)),
    [instruments.data],
  );
  const inst: Instrument | undefined = holdable.find((i) => i.id === form.instrument_id);
  const isMetal = inst?.asset_class === "commodity";
  const mutation = editing ? updateTx : addTx;

  function set<K extends keyof TransactionInput>(k: K, v: TransactionInput[K]) {
    setForm((f) => ({ ...f, [k]: v }));
    setSaved(null);
  }

  function pick(id: string) {
    const i = holdable.find((x) => x.id === id);
    setForm((f) => ({
      ...f,
      instrument_id: id,
      unit: i?.asset_class === "commodity" ? (f.unit === "unit" ? "gram" : f.unit) : "unit",
    }));
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const tx = { ...form, notes: form.notes?.trim() || null };
    const onSuccess = () => {
      setSaved(editing ? "Transaction updated." : "Transaction added.");
      if (editing) onDone();
      else setForm((f) => ({ ...f, quantity: 0, price: 0, fees: 0, notes: null }));
    };
    if (editing) updateTx.mutate({ pid: portfolio.id, id: editing.id, tx }, { onSuccess });
    else addTx.mutate({ pid: portfolio.id, tx }, { onSuccess });
  }

  const groups = ["equity", "etf", "crypto", "commodity"].map((c) => ({
    cls: c,
    items: holdable.filter((i) => i.asset_class === c),
  }));
  const ccy = (inst?.currency ?? "USD") as "USD" | "INR";

  return (
    <Card>
      <CardHeader title={editing ? "Edit transaction" : "Add a transaction"} />
      <form className="flex flex-col gap-3" onSubmit={submit}>
        <Segmented
          label="Side"
          options={[
            { value: "buy", label: "Buy" },
            { value: "sell", label: "Sell" },
          ]}
          value={form.side}
          onChange={(v) => set("side", v)}
        />
        <label className="flex flex-col gap-1 text-sm">
          <span className="label">Instrument</span>
          <select
            required
            value={form.instrument_id}
            onChange={(e) => pick(e.target.value)}
            className={inputClass}
          >
            <option value="" disabled>
              {instruments.isLoading ? "Loading…" : "Choose…"}
            </option>
            {groups.map((g) =>
              g.items.length ? (
                <optgroup
                  key={g.cls}
                  label={
                    g.cls === "commodity"
                      ? "Physical metal (by weight)"
                      : `${ASSET_CLASS_LABEL[g.cls]}s`
                  }
                >
                  {g.items.map((i) => (
                    <option key={i.id} value={i.id}>
                      {g.cls === "commodity" ? i.name.replace(/ \(.*\)$/, "") : i.name} (
                      {i.currency})
                    </option>
                  ))}
                </optgroup>
              ) : null,
            )}
          </select>
          {isMetal ? (
            <span className="text-xs text-subtle">
              Valued at the COMEX futures reference price, not a dealer&apos;s buy-back price. For a
              gold ETF, choose the ETF instead.
            </span>
          ) : null}
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="flex flex-col gap-1 text-sm">
            <span className="label">Date</span>
            <input
              type="date"
              required
              max={today()}
              value={form.trade_date}
              onChange={(e) => set("trade_date", e.target.value)}
              className={inputClass}
            />
          </label>
          {isMetal ? (
            <label className="flex flex-col gap-1 text-sm">
              <span className="label">Weight in</span>
              <select
                value={form.unit}
                onChange={(e) => set("unit", e.target.value as Unit)}
                className={inputClass}
              >
                <option value="gram">grams</option>
                <option value="troy_oz">troy ounces</option>
              </select>
            </label>
          ) : null}
        </div>
        <div className="grid grid-cols-2 gap-3">
          <NumberField
            label={`Quantity (${UNIT_LABEL[form.unit]})`}
            value={form.quantity}
            onChange={(v) => set("quantity", v)}
            min={0}
            required
          />
          <NumberField
            label={`Price per ${form.unit === "gram" ? "gram" : form.unit === "troy_oz" ? "troy oz" : "unit"} (${ccy})`}
            value={form.price}
            onChange={(v) => set("price", v)}
            min={0}
            required
          />
        </div>
        <NumberField
          label={`Fees (${ccy})`}
          value={form.fees}
          onChange={(v) => set("fees", v)}
          min={0}
        />
        <label className="flex flex-col gap-1 text-sm">
          <span className="label">Note (optional)</span>
          <input
            maxLength={200}
            value={form.notes ?? ""}
            onChange={(e) => set("notes", e.target.value)}
            className={inputClass}
          />
        </label>
        {form.quantity > 0 && form.price > 0 ? (
          <p className="num text-sm text-muted">
            Total {form.side === "buy" ? "cost" : "proceeds"}:{" "}
            {formatMoney(
              form.quantity * form.price + (form.side === "buy" ? form.fees : -form.fees),
              ccy,
            )}
          </p>
        ) : null}
        {mutation.error ? (
          <p role="alert" className="text-sm text-negative">
            {errorMessage(mutation.error)}
          </p>
        ) : null}
        {saved ? (
          <p role="status" className="text-sm text-positive">
            {saved}
          </p>
        ) : null}
        <div className="flex gap-2">
          <button
            type="submit"
            className={primaryClass}
            disabled={mutation.isPending || !form.instrument_id || form.quantity <= 0}
          >
            {editing ? "Save changes" : form.side === "buy" ? "Add buy" : "Add sell"}
          </button>
          {editing ? (
            <button type="button" className={buttonClass} onClick={onDone}>
              Cancel
            </button>
          ) : null}
        </div>
      </form>
    </Card>
  );
}

function NumberField({
  label,
  value,
  onChange,
  min,
  required,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min?: number;
  required?: boolean;
}) {
  const [text, setText] = useState(value ? String(value) : "");
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="label">{label}</span>
      <input
        inputMode="decimal"
        required={required}
        value={Number(text) === value ? text : value ? String(value) : ""}
        onChange={(e) => {
          const t = e.target.value.replace(/,/g, "");
          if (!/^\d*\.?\d*$/.test(t)) return;
          setText(t);
          const n = Number(t);
          onChange(Number.isFinite(n) && (min === undefined || n >= min) ? n : 0);
        }}
        className={cn(inputClass, "num")}
      />
    </label>
  );
}

function Ledger({
  portfolio,
  list,
  onEdit,
}: {
  portfolio: Portfolio;
  list: Transaction[];
  onEdit: (t: Transaction) => void;
}) {
  const { deleteTx } = usePortfolioMutations();
  return (
    <div className="-mx-4 overflow-x-auto">
      {deleteTx.error ? (
        <p role="alert" className="mx-4 mb-2 text-sm text-negative">
          {errorMessage(deleteTx.error)}
        </p>
      ) : null}
      <table className="num w-full min-w-[640px] text-sm">
        <caption className="sr-only">Transactions</caption>
        <thead>
          <tr className="border-b border-border text-muted">
            {["Date", "Instrument", "Side", "Quantity", "Price", "Fees", ""].map((h, i) => (
              <th
                key={h || i}
                scope="col"
                className={`px-3 py-2 font-medium ${i <= 2 ? "text-left" : "text-right"}`}
              >
                {h || <span className="sr-only">Actions</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {list.map((t) => (
            <tr
              key={t.id}
              className="border-b border-border odd:bg-text/[0.02] hover:bg-surface-raised"
            >
              <td className="px-3 py-2">{formatDate(t.trade_date)}</td>
              <th scope="row" className="px-3 py-2 text-left font-normal">
                {t.name}
                {t.notes ? <div className="text-xs text-subtle">{t.notes}</div> : null}
              </th>
              <td
                className={`px-3 py-2 font-medium ${t.side === "buy" ? "text-positive" : "text-negative"}`}
              >
                {t.side === "buy" ? "▲ Buy" : "▼ Sell"}
              </td>
              <td className="px-3 py-2 text-right">
                {formatNumber(t.quantity, t.quantity < 1 ? 6 : 2)}
                {t.unit !== "unit" ? (
                  <span className="text-subtle"> {t.unit === "gram" ? "g" : "oz t"}</span>
                ) : null}
              </td>
              <td className="px-3 py-2 text-right">{formatMoney(t.price, t.currency)}</td>
              <td className="px-3 py-2 text-right">{formatMoney(t.fees, t.currency)}</td>
              <td className="px-3 py-2 text-right">
                <div className="inline-flex gap-1">
                  <button
                    type="button"
                    aria-label={`Edit ${t.side} of ${t.name} on ${t.trade_date}`}
                    onClick={() => onEdit(t)}
                    className="rounded-md p-1 text-muted hover:text-text"
                  >
                    <Pencil size={15} aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    aria-label={`Delete ${t.side} of ${t.name} on ${t.trade_date}`}
                    disabled={deleteTx.isPending}
                    onClick={() => {
                      if (window.confirm(`Delete this ${t.side} of ${t.name}?`)) {
                        deleteTx.mutate({ pid: portfolio.id, id: t.id });
                      }
                    }}
                    className="rounded-md p-1 text-muted hover:text-negative"
                  >
                    <Trash2 size={15} aria-hidden="true" />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const SAMPLE = `date,instrument_id,side,quantity,unit,price,fees,notes
2025-03-14,eq:us:AAPL,buy,10,unit,212.50,1.00,
2025-06-02,crypto:BTC,buy,0.05,unit,104000,2.50,
2025-08-20,metal:XAU:comex-fut,buy,20,gram,105.10,0,coins`;

function CsvTools({ portfolio }: { portfolio: Portfolio }) {
  const { importCsv, exportCsv } = usePortfolioMutations();
  const [text, setText] = useState("");
  const [checked, setChecked] = useState<number | null>(null);
  const [done, setDone] = useState<number | null>(null);
  const [exporting, setExporting] = useState(false);
  const details =
    importCsv.error instanceof ApiError && Array.isArray(importCsv.error.details)
      ? (importCsv.error.details as string[])
      : [];

  async function download() {
    setExporting(true);
    try {
      const csv = await exportCsv(portfolio.id);
      const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `${portfolio.name.replace(/[^\w-]+/g, "_")}-transactions.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  }

  return (
    <Card>
      <CardHeader
        title="CSV import and export"
        action={
          <button
            type="button"
            className={buttonClass}
            onClick={download}
            disabled={exporting || portfolio.transaction_count === 0}
          >
            <Download size={15} aria-hidden="true" /> Export
          </button>
        }
      />
      <p className="text-sm text-muted">
        Columns: date, instrument_id, side, quantity, unit, price, fees, notes. Instrument IDs are
        shown on each asset page (for example eq:us:AAPL). Imports are all-or-nothing.
      </p>
      <label className="mt-3 flex flex-col gap-1 text-sm">
        <span className="label">Paste CSV or choose a file</span>
        <textarea
          rows={5}
          value={text}
          placeholder={SAMPLE}
          onChange={(e) => {
            setText(e.target.value);
            setChecked(null);
            setDone(null);
            importCsv.reset();
          }}
          className={cn(inputClass, "font-mono text-xs")}
        />
      </label>
      <input
        type="file"
        accept=".csv,text/csv"
        aria-label="Choose a CSV file"
        className="mt-2 text-sm text-muted file:mr-2 file:rounded-md file:border file:border-border file:bg-surface-raised file:px-2 file:py-1 file:text-text"
        onChange={async (e) => {
          const f = e.target.files?.[0];
          if (f) {
            setText(await f.text());
            setChecked(null);
            setDone(null);
            importCsv.reset();
          }
        }}
      />
      {importCsv.error ? (
        <div role="alert" className="mt-2 text-sm text-negative">
          {errorMessage(importCsv.error)}
          {details.length ? (
            <ul className="mt-1 list-disc pl-5">
              {details.map((d) => (
                <li key={d}>{d}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      {checked !== null && done === null ? (
        <p role="status" className="mt-2 text-sm text-positive">
          {checked} rows look good.
        </p>
      ) : null}
      {done !== null ? (
        <p role="status" className="mt-2 text-sm text-positive">
          Imported {done} transactions.
        </p>
      ) : null}
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          className={buttonClass}
          disabled={!text.trim() || importCsv.isPending}
          onClick={() =>
            importCsv.mutate(
              { pid: portfolio.id, csv: text, dryRun: true },
              { onSuccess: (r) => setChecked(r.rows) },
            )
          }
        >
          Check
        </button>
        <button
          type="button"
          className={primaryClass}
          disabled={checked === null || importCsv.isPending}
          onClick={() =>
            importCsv.mutate(
              { pid: portfolio.id, csv: text, dryRun: false },
              {
                onSuccess: (r) => {
                  setDone(r.rows);
                  setText("");
                  setChecked(null);
                },
              },
            )
          }
        >
          <Upload size={15} aria-hidden="true" /> Import
        </button>
      </div>
    </Card>
  );
}
