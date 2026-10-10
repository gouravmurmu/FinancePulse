# Methodology

All analytics are computed in `backend/app/analytics/` and covered by tests
against hand-calculated values (`backend/tests/test_analytics.py`). Nothing
here is a forecast.

## Returns
- **Prices**: adjusted close (dividends and splits) where available, else close.
- **Daily return**: `P_t / P_{t-1} − 1`.
- **Total return**: last price / first price − 1 over the period.
- **CAGR**: `(1 + total return)^(365.25 / days) − 1`, using exact elapsed time.
- **Growth of 100**: each series divided by its value on the first date every
  series has a price, times 100.

## Calendars
- Stocks, indices, ETFs, futures and FX: 252 trading days per year.
- Crypto alone: 365 days per year.
- When crypto is compared with exchange-traded assets, crypto is sampled on the
  exchange trading days and everything uses 252.
- Multi-asset statistics use only dates on which every selected instrument has
  a price.

## Risk
- **Volatility**: standard deviation of daily returns × √(periods per year).
- **Sharpe**: annualized mean return ÷ annualized volatility, risk-free rate 0%.
- **Sortino**: as Sharpe, using downside deviation (returns below 0).
- **Drawdown**: price ÷ running peak − 1. Max drawdown reports the peak,
  trough and recovery dates (or "not recovered").
- **VaR**: historical, one day; the loss at the chosen confidence (90/95/99%),
  using a linearly interpolated quantile. Reported as a positive loss.
- **Expected shortfall**: average loss on days worse than VaR.
- **Beta**: covariance with the benchmark ÷ benchmark variance on aligned
  daily returns (S&P 500 for US stocks, Nifty 50 for Indian stocks).
- **Correlation**: Pearson correlation of daily returns. Rolling correlation
  uses a 60-day window; rolling volatility a 30-day window.
- **Risk level** (a plain-language label): low below 15% annualized
  volatility, moderate from 15% to 30%, high from 30%.
- At least 20 observations are required; otherwise the metric is "—".

## Technical indicators
Computed on 300 extra days of history so that long averages are valid from the
first visible date.
- SMA 20/50/200; EMA 20 (seeded with the SMA).
- RSI 14 with Wilder smoothing.
- MACD 12/26/9.
- Bollinger Bands: 20-day SMA ± 2 population standard deviations.

## Monte Carlo
Daily returns are drawn from a multivariate normal distribution with the mean
and covariance measured over the look-back window (Cholesky factorization),
with daily rebalancing to the chosen weights. A fixed seed makes results
reproducible. Real markets have fatter tails than a normal distribution, so
extreme losses are likely understated. Results show the 5th, 50th and 95th
percentile paths, the distribution of final values and the share of paths that
ended below the starting value.

## Stress tests
Instant one-off price moves applied to the current weights:
- **Global equity sell-off**: stocks, indices and ETFs −20%, crypto −35%,
  gold +5%, silver −5%.
- **Crypto winter**: crypto −60%.
- **Rupee falls 10%**: Indian stocks and indices −8%; USD assets +10% in INR.

## Currency conversion
USD prices are converted to INR with the daily USD/INR close, carried forward
over days without a rate. Index levels and exchange rates are never converted.
For USD-priced metals, the INR return is decomposed as
`(1 + USD return) × (1 + change in USD/INR) − 1`.

## Fundamentals (US only)
From SEC company facts, annual 10-K figures only:
- Flow items (revenue, profit, cash flow) must cover 350 to 380 days.
- When a later filing restates a year, the most recently filed value is used.
- When a company changed XBRL tags, the preferred tag is used and older tags
  fill earlier years.
- Margins are divided by revenue; free cash flow = operating cash flow −
  capital spending; growth is shown only between consecutive fiscal years and
  not from a negative base.

## Portfolios
- **Cost basis: weighted average cost.** Buy fees add to cost; sell fees reduce
  proceeds. A sale removes `quantity / holding` of the remaining cost; the rest
  of the proceeds is realized P&L. Same-day trades apply buys first, then in
  entry order. A sale larger than the holding at that date is rejected.
- **Two currencies per position.** Amounts are kept in the instrument's
  currency and in the portfolio's base currency at the USD/INR close of each
  trade date. Unrealized P&L in the base currency splits exactly into a
  *price effect* (local P&L at today's rate) and a *currency effect* (cost
  restated at today's rate minus the cost actually paid).
- **Physical metal** is entered in grams or troy ounces (1 troy oz =
  31.1034768 g) and valued at the COMEX futures reference price. That is not a
  dealer's buy or sell price; an ETF holding is entered as the ETF.
- **Time-weighted return.** Holdings are valued at each day's close (prices
  carried forward over gaps) on exchange business days, or every day if the
  portfolio holds only crypto. Daily return
  `r = (V_t + O_t − I_t) / V_{t−1} − 1`, where `I` is money put in (cost incl.
  fees) and `O` money taken out (sale proceeds net of fees). When a purchase is
  larger than the existing portfolio (including the first purchase) it counts
  from the start of the day instead, `r = (V_t + O_t) / (V_{t−1} + I_t) − 1`,
  so a small base cannot produce an extreme daily return. Returns are chained
  into a growth-of-100 line.
- **Risk contribution** of holding *i*: `w_i (Σw)_i / wᵀΣw`, using today's
  weights and the covariance of daily base-currency returns over the last year.
  Contributions sum to 100%.
- **Benchmark**: S&P 500 for USD portfolios and NIFTY 50 for INR portfolios by
  default; price index in its own currency, no dividends.
- Dividends, splits after the trade date and other corporate actions are not
  applied automatically; record them as transactions.
- **Rebalancing** is hypothetical: trades needed to reach target weights at
  today's prices, ignoring fees and taxes. Nothing is traded.
