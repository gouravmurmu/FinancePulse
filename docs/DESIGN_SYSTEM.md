# Design system

All colors are CSS variables in `frontend/src/app/globals.css`, exposed to
Tailwind as utilities (`bg-surface`, `text-muted`, `text-positive`, …).
Components never use raw hex values.

## Themes
Dark is the default look; the app follows the OS setting and has a toggle.
Token values match section 9.1 of the spec. Light-theme `--text-subtle`
(`#64748B`) and `--neutral` (`#71717A`) were not specified and were chosen to
meet 4.5:1 on white.

| Token | Dark | Light |
|---|---|---|
| `--bg` | `#0B1220` | `#F6F8FB` |
| `--surface` | `#111A2B` | `#FFFFFF` |
| `--surface-raised` | `#172238` | `#F1F5F9` |
| `--text` | `#E6EAF2` | `#0F172A` |
| `--text-muted` | `#94A3B8` | `#475569` |
| `--text-subtle` | `#64748B` | `#64748B` |
| `--accent` | `#2DD4BF` | `#0D9488` |
| `--accent-2` | `#60A5FA` | `#2563EB` |
| `--positive` | `#34D399` | `#059669` |
| `--negative` | `#F87171` | `#DC2626` |
| `--warning` | `#FBBF24` | `#D97706` |

`--text-subtle` on the dark background is below 4.5:1, so it is used only for
captions, axis labels and the footer (large/secondary text), never body copy.

## Chart palette
Fixed order: teal `#2DD4BF`, blue `#60A5FA`, violet `#A78BFA`, amber `#F59E0B`,
pink `#F472B6`, green `#34D399`, orange `#FB923C`, slate `#94A3B8`. Gold
`#E5B94E` and silver `#C0C7D1` are reserved for the metals.

## Typography
Inter via `next/font` (self-hosted, `display: swap`); JetBrains Mono for code
and dense tickers. Scale 12/13/14/16/20/24/32 px, body 14 px / 1.5. Numbers use
the `.num` class (tabular figures). Labels use `.label` (12 px, uppercase,
0.04em tracking, muted).

## Formatting (`src/lib/format.ts`)
- Currency symbol always shown; Indian grouping for INR (`₹12,34,567.00`).
- Abbreviations: K/M/B/T, or K/L/Cr for INR.
- Percentages to 2 decimals with sign; gains/losses also carry ▲/▼.
- Dates as `10 Oct 2026`, in the instrument's time zone.

## Freshness chips
`Live`, `Delayed N min`, `End of day · 9 Oct`, `Stale · <date>` (amber),
`Unavailable` (muted), `Demo data` (amber). Every number group shows one.

## Components so far
`Card`, `CardHeader`, `MetricCard`, `FreshnessChip`, `SkeletonCard`,
`EmptyState`, `ErrorState`, app shell (collapsible sidebar, top bar, mobile
bottom tab bar, skip link, visible focus rings).
