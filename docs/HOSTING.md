# Hosting and free-tier limits

MarketPulse must run at **$0 / ₹0 per month**. Free tiers change, so every limit
below was checked against the provider's own page on **10 Oct 2026** (or a
named secondary source where the provider page did not state the number).
Re-check before relying on a number, and update this file when anything moves.

## Chosen services

| Layer | Service | Why |
|---|---|---|
| Web app | Vercel Hobby | Native Next.js hosting, preview deploys per branch |
| API (FastAPI) | Render free web service (Docker) | Runs a long-lived Python process without a card |
| Database + Auth | Supabase free | Postgres, Auth and Row Level Security in one place |
| Scheduled jobs | GitHub Actions cron | Data refreshes and ML batch jobs, writing to Postgres |
| Cache | In-process TTL cache first; Upstash Redis free if needed | Avoids another account until it is needed |
| LLM | Gemini or Groq free tier behind a provider abstraction | Step 3; the app works without a key |

## Verified limits

### Vercel Hobby ([source](https://vercel.com/docs/plans/hobby), page dated 14 Sep 2026)
- Fast data transfer 100 GB, CDN requests 1,000,000, function invocations 1,000,000,
  Active CPU 4 CPU-hours, provisioned memory 360 GB-hours per month.
- Function max duration 300 s. 100 deployments per day.
- Runtime logs kept 1 hour.
- Exceeding a limit pauses the feature for up to 30 days (no surprise bill).
- **Non-commercial, personal use only** (fair-use guidelines). If MarketPulse
  ever earns money, move to Cloudflare Pages or Netlify, or a paid plan.

### Render free web service ([source](https://render.com/docs/free))
- Spins down after **15 minutes** without inbound traffic; spin-up takes **about
  one minute**. The frontend shows "Waking up the analytics server…" meanwhile.
- **750 free instance hours per workspace per month.** One always-awake service
  would use ~744 h, so keep only one free web service in the workspace.
- Outbound bandwidth and build minutes count against the workspace allowance.
  Render's page does not state the amount. A secondary review
  ([jwatte.com](https://jwatte.com/blog/render-com-platform-review.md)) reports
  the Hobby workspace allowance was cut to **5 GB/month on 1 Aug 2026**. With no
  card on file, free services are suspended (not billed) when it runs out.
  JSON API responses are small, but keep payloads compact and cache on the client.
- Free Render Postgres expires after 30 days, so **we do not use it**.
- RAM is not stated on the free page; we design for **512 MB** (the API image has
  no ML libraries).

### Supabase free ([source](https://supabase.com/pricing))
- **500 MB database per project**, 5 GB egress, 1 GB file storage, 50,000 monthly
  active users, 500,000 edge function invocations.
- **2 active projects** per account.
- **Paused after 1 week of inactivity.** The daily GitHub Actions data refresh
  writes to the database, which keeps it active.
- The direct database host is IPv6-only; Render connects through the
  **session pooler** (IPv4) connection string.

### GitHub Actions ([source](https://docs.github.com/en/billing/concepts/product-billing/github-actions))
- Free and unlimited for **public** repositories on standard runners.
- **2,000 minutes/month** for private repositories on GitHub Free. Keep the
  repository public, or keep scheduled jobs short (the daily refresh is budgeted
  at under 5 minutes, about 150 minutes a month).

### Upstash Redis free ([source](https://upstash.com/pricing/redis.md))
- 500,000 commands/month, 250 MB data, 10 GB bandwidth, 1 database.
- Not used in step 1. Only added if the in-process cache proves insufficient.

### LLM providers (step 3)
- Gemini API has a free tier; per-model limits are only shown in AI Studio
  ([rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)).
- Groq lists per-organization limits in account settings
  ([rate limits](https://console.groq.com/docs/rate-limits)).
- Both will be re-checked, with the actual numbers recorded here, when the
  assistant is built. The app enforces its own per-user budget regardless.

## Storage budget (Supabase 500 MB)

Daily bars only, curated universe of ~150 instruments:
150 instruments × ~1,260 trading days (5 years) ≈ 190,000 rows.
At roughly 200 bytes per row including indexes, that is **≈ 40 MB**, leaving
plenty of room for fundamentals, news headlines (no article bodies),
portfolios and model outputs. Raw provider payloads are not stored.

## Consequences for the design
1. The API is a single slim process; heavy work runs in GitHub Actions.
2. The web app tolerates a sleeping API (retries with backoff, clear waking state).
3. Stored data is served first; providers are never called from the browser.
4. Nothing here requires a credit card.
