# Design system

All colors are CSS variables in `frontend/src/app/globals.css`, exposed to
Tailwind as utilities (`bg-surface`, `text-muted`, `text-positive`, …).
Components never use raw hex values.

## Themes
Dark is the default look; the app follows the OS setting and has a toggle.
Token values follow section 9.1 of the spec, except where a spec value fell
below WCAG AA (4.5:1 for text) on the theme's backgrounds; those were darkened
or lightened within the same hue (checked against `--bg`, `--surface` and
`--surface-raised` during step 4). Light-theme `--neutral` (`#71717A`) was not
specified.

| Token | Dark | Light |
|---|---|---|
| `--bg` | `#0B1220` | `#F6F8FB` |
| `--surface` | `#111A2B` | `#FFFFFF` |
| `--surface-raised` | `#172238` | `#F1F5F9` |
| `--text` | `#E6EAF2` | `#0F172A` |
| `--text-muted` | `#94A3B8` | `#475569` |
| `--text-subtle` | `#7D8CA3` (spec `#64748B`, 3.3:1) | `#5B6B80` (spec `#64748B`) |
| `--accent` | `#2DD4BF` | `#0F766E` (spec `#0D9488`, 3.4:1) |
| `--accent-2` | `#60A5FA` | `#2563EB` |
| `--positive` | `#34D399` | `#047857` (spec `#059669`, 3.4:1) |
| `--negative` | `#F87171` | `#B91C1C` (spec `#DC2626`, 4.4:1) |
| `--warning` | `#FBBF24` | `#B45309` (spec `#D97706`, 2.9:1) |

Every text token now meets 4.5:1 on all three backgrounds in both themes.
Buttons on the accent use `--accent-contrast` (dark ink in dark mode, white in
light mode; both above 5:1).

## Chart palette
Categorical slots in fixed order (the order is what keeps adjacent series
distinguishable under colour-vision deficiency):

| Slot | Dark | Light |
|---|---|---|
| 1 blue | `#3987E5` | `#2A78D6` |
| 2 orange | `#D95926` | `#EB6834` |
| 3 aqua | `#199E70` | `#1BAF7A` |
| 4 yellow | `#C98500` | `#EDA100` |
| 5 magenta | `#D55181` | `#E87BA4` |
| 6 green | `#008300` | `#008300` |
| 7 violet | `#9085E9` | `#6250D6` |
| 8 red | `#E66767` | `#E34948` |

Validated (lightness band, chroma, adjacent-pair CVD ΔE ≥ 8, normal-vision
ΔE ≥ 15, contrast) against the dark surface `#111A2B` and white. In light mode
aqua, yellow and magenta are below 3:1 contrast, so every chart has a legend and
a table view. Rules:
- Colour follows the instrument (its position in the user's selection), never
  its rank; removing one series does not repaint the others.
- At most 8 series; one y-axis (multi-asset comparisons are indexed to 100).
- Correlation uses a diverging blue ↔ red scale with a grey midpoint, and
  every cell prints its value.
- Gain/loss colours (`--positive`/`--negative`) are status colours and always
  carry ▲/▼ and a signed number.
- Gold `#E5B94E` and silver `#C0C7D1` are reserved for metal badges, not series.

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
