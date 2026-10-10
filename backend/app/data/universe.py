"""Curated instrument universe (~56 instruments).

Kept deliberately small to stay inside the free database tier (see
docs/HOSTING.md). Canonical IDs are stable and never reused. Each entry lists
the provider symbols used to fetch it; `search` aliases power universal search.
"""

from dataclasses import dataclass, field
from typing import Any

Y = "yfinance"
CG = "coingecko"


@dataclass(frozen=True)
class InstrumentDef:
    id: str
    name: str
    asset_class: str
    currency: str
    timezone: str
    exchange: str | None = None
    country: str | None = None
    price_definition: str | None = None
    region: str = "global"  # "global" or "india": which Markets view shows it
    aliases: dict[str, str] = field(default_factory=dict)
    search: tuple[str, ...] = ()
    attributes: dict[str, Any] = field(default_factory=dict)


def _index(
    id_: str,
    name: str,
    sym: str,
    ccy: str,
    tz: str,
    exch: str,
    country: str,
    region: str = "global",
    search: tuple[str, ...] = (),
) -> InstrumentDef:
    return InstrumentDef(
        id=id_,
        name=name,
        asset_class="index",
        currency=ccy,
        timezone=tz,
        exchange=exch,
        country=country,
        region=region,
        aliases={Y: sym},
        search=search,
        price_definition="Index level (points)",
    )


def _us(sym: str, name: str, sector: str, cik: int, search: tuple[str, ...] = ()) -> InstrumentDef:
    return InstrumentDef(
        id=f"eq:us:{sym.replace('-', '.')}",
        name=name,
        asset_class="equity",
        currency="USD",
        timezone="America/New_York",
        exchange="NASDAQ/NYSE",
        country="US",
        aliases={Y: sym},
        search=(sym.replace("-", "."), *search),
        attributes={"sector": sector, "cik": cik, "benchmark": "idx:us:SPX"},
        price_definition="Share price, USD",
    )


def _in(sym: str, name: str, sector: str, search: tuple[str, ...] = ()) -> InstrumentDef:
    return InstrumentDef(
        id=f"eq:in:{sym}",
        name=name,
        asset_class="equity",
        currency="INR",
        timezone="Asia/Kolkata",
        exchange="NSE",
        country="IN",
        region="india",
        aliases={Y: f"{sym}.NS"},
        search=(sym, *search),
        attributes={"sector": sector, "benchmark": "idx:in:NIFTY50"},
        price_definition="Share price on NSE, INR",
    )


def _crypto(sym: str, name: str, cg_id: str, search: tuple[str, ...] = ()) -> InstrumentDef:
    return InstrumentDef(
        id=f"crypto:{sym}",
        name=name,
        asset_class="crypto",
        currency="USD",
        timezone="UTC",
        aliases={Y: f"{sym}-USD", CG: cg_id},
        search=(sym, *search),
        attributes={"benchmark": "crypto:BTC"},
        price_definition="Spot price in USD, daily close at 00:00 UTC",
    )


UNIVERSE: list[InstrumentDef] = [
    # --- Global indices
    _index(
        "idx:us:SPX",
        "S&P 500",
        "^GSPC",
        "USD",
        "America/New_York",
        "NYSE",
        "US",
        search=("SPX", "SP500", "S&P"),
    ),
    _index(
        "idx:us:IXIC",
        "Nasdaq Composite",
        "^IXIC",
        "USD",
        "America/New_York",
        "NASDAQ",
        "US",
        search=("Nasdaq",),
    ),
    _index(
        "idx:us:DJI",
        "Dow Jones Industrial Average",
        "^DJI",
        "USD",
        "America/New_York",
        "NYSE",
        "US",
        search=("Dow", "DJIA"),
    ),
    _index("idx:gb:FTSE", "FTSE 100", "^FTSE", "GBP", "Europe/London", "LSE", "GB"),
    _index("idx:de:DAX", "DAX", "^GDAXI", "EUR", "Europe/Berlin", "XETRA", "DE"),
    _index(
        "idx:eu:SX5E",
        "Euro Stoxx 50",
        "^STOXX50E",
        "EUR",
        "Europe/Berlin",
        "XETRA",
        "EU",
        search=("Stoxx",),
    ),
    _index(
        "idx:jp:N225", "Nikkei 225", "^N225", "JPY", "Asia/Tokyo", "TSE", "JP", search=("Nikkei",)
    ),
    _index("idx:hk:HSI", "Hang Seng", "^HSI", "HKD", "Asia/Hong_Kong", "HKEX", "HK"),
    # --- Indian indices
    _index(
        "idx:in:NIFTY50",
        "Nifty 50",
        "^NSEI",
        "INR",
        "Asia/Kolkata",
        "NSE",
        "IN",
        "india",
        search=("Nifty",),
    ),
    _index(
        "idx:in:SENSEX",
        "BSE Sensex",
        "^BSESN",
        "INR",
        "Asia/Kolkata",
        "BSE",
        "IN",
        "india",
        search=("Sensex",),
    ),
    _index(
        "idx:in:BANKNIFTY",
        "Nifty Bank",
        "^NSEBANK",
        "INR",
        "Asia/Kolkata",
        "NSE",
        "IN",
        "india",
        search=("Bank Nifty",),
    ),
    _index("idx:in:NIFTYIT", "Nifty IT", "^CNXIT", "INR", "Asia/Kolkata", "NSE", "IN", "india"),
    # --- US stocks (CIKs for SEC EDGAR fundamentals)
    _us("AAPL", "Apple Inc.", "Technology", 320193, ("Apple",)),
    _us("MSFT", "Microsoft Corporation", "Technology", 789019, ("Microsoft",)),
    _us("NVDA", "NVIDIA Corporation", "Technology", 1045810, ("Nvidia",)),
    _us("AMZN", "Amazon.com, Inc.", "Consumer Discretionary", 1018724, ("Amazon",)),
    _us(
        "GOOGL",
        "Alphabet Inc. (Class A)",
        "Communication Services",
        1652044,
        ("Google", "Alphabet"),
    ),
    _us("META", "Meta Platforms, Inc.", "Communication Services", 1326801, ("Facebook",)),
    _us("TSLA", "Tesla, Inc.", "Consumer Discretionary", 1318605, ("Tesla",)),
    _us("BRK-B", "Berkshire Hathaway Inc. (Class B)", "Financials", 1067983, ("Berkshire",)),
    _us("JPM", "JPMorgan Chase & Co.", "Financials", 19617, ("JPMorgan", "Chase")),
    _us("V", "Visa Inc.", "Financials", 1403161, ("Visa",)),
    _us("UNH", "UnitedHealth Group Incorporated", "Health Care", 731766, ("UnitedHealth",)),
    _us("XOM", "Exxon Mobil Corporation", "Energy", 34088, ("Exxon",)),
    _us("JNJ", "Johnson & Johnson", "Health Care", 200406, ("Johnson",)),
    _us("WMT", "Walmart Inc.", "Consumer Staples", 104169, ("Walmart",)),
    _us("PG", "The Procter & Gamble Company", "Consumer Staples", 80424, ("Procter",)),
    # --- Indian stocks (NSE)
    _in("RELIANCE", "Reliance Industries Ltd", "Energy", ("Reliance", "RIL")),
    _in("TCS", "Tata Consultancy Services Ltd", "Technology", ("Tata Consultancy",)),
    _in("HDFCBANK", "HDFC Bank Ltd", "Financials", ("HDFC",)),
    _in("INFY", "Infosys Ltd", "Technology", ("Infosys",)),
    _in("ICICIBANK", "ICICI Bank Ltd", "Financials", ("ICICI",)),
    _in("HINDUNILVR", "Hindustan Unilever Ltd", "Consumer Staples", ("HUL", "Unilever")),
    _in("ITC", "ITC Ltd", "Consumer Staples"),
    _in("SBIN", "State Bank of India", "Financials", ("SBI",)),
    _in("BHARTIARTL", "Bharti Airtel Ltd", "Communication Services", ("Airtel",)),
    _in("LT", "Larsen & Toubro Ltd", "Industrials", ("L&T", "Larsen")),
    _in("KOTAKBANK", "Kotak Mahindra Bank Ltd", "Financials", ("Kotak",)),
    _in("AXISBANK", "Axis Bank Ltd", "Financials", ("Axis",)),
    _in("BAJFINANCE", "Bajaj Finance Ltd", "Financials", ("Bajaj",)),
    _in("MARUTI", "Maruti Suzuki India Ltd", "Consumer Discretionary", ("Maruti", "Suzuki")),
    _in("SUNPHARMA", "Sun Pharmaceutical Industries Ltd", "Health Care", ("Sun Pharma",)),
    # --- Crypto
    _crypto("BTC", "Bitcoin", "bitcoin"),
    _crypto("ETH", "Ethereum", "ethereum", ("Ether",)),
    _crypto("SOL", "Solana", "solana"),
    _crypto("BNB", "BNB", "binancecoin", ("Binance Coin",)),
    _crypto("XRP", "XRP", "ripple", ("Ripple",)),
    _crypto("ADA", "Cardano", "cardano"),
    _crypto("DOGE", "Dogecoin", "dogecoin"),
    _crypto("AVAX", "Avalanche", "avalanche-2"),
    # --- Precious metals (futures and ETFs are labelled as such, never as spot)
    InstrumentDef(
        id="metal:XAU:comex-fut",
        name="Gold (COMEX futures)",
        asset_class="commodity",
        currency="USD",
        timezone="America/New_York",
        exchange="COMEX",
        country="US",
        aliases={Y: "GC=F"},
        search=("Gold", "XAU", "GC"),
        price_definition="COMEX gold front-month futures, USD per troy ounce (not spot)",
        attributes={"metal": "gold"},
    ),
    InstrumentDef(
        id="metal:XAG:comex-fut",
        name="Silver (COMEX futures)",
        asset_class="commodity",
        currency="USD",
        timezone="America/New_York",
        exchange="COMEX",
        country="US",
        aliases={Y: "SI=F"},
        search=("Silver", "XAG", "SI"),
        price_definition="COMEX silver front-month futures, USD per troy ounce (not spot)",
        attributes={"metal": "silver"},
    ),
    InstrumentDef(
        id="etf:us:GLD",
        name="SPDR Gold Shares (ETF)",
        asset_class="etf",
        currency="USD",
        timezone="America/New_York",
        exchange="NYSE Arca",
        country="US",
        aliases={Y: "GLD"},
        search=("GLD", "Gold ETF"),
        price_definition="ETF share price, USD (tracks gold bullion less fees)",
        attributes={"metal": "gold"},
    ),
    InstrumentDef(
        id="etf:us:SLV",
        name="iShares Silver Trust (ETF)",
        asset_class="etf",
        currency="USD",
        timezone="America/New_York",
        exchange="NYSE Arca",
        country="US",
        aliases={Y: "SLV"},
        search=("SLV", "Silver ETF"),
        price_definition="ETF share price, USD (tracks silver bullion less fees)",
        attributes={"metal": "silver"},
    ),
    InstrumentDef(
        id="etf:in:GOLDBEES",
        name="Nippon India ETF Gold BeES",
        asset_class="etf",
        currency="INR",
        timezone="Asia/Kolkata",
        exchange="NSE",
        country="IN",
        region="india",
        aliases={Y: "GOLDBEES.NS"},
        search=("GOLDBEES", "Gold BeES", "Gold India"),
        price_definition="ETF unit price on NSE, INR (tracks domestic gold price less fees)",
        attributes={"metal": "gold"},
    ),
    # --- FX (used for USD/INR conversion)
    InstrumentDef(
        id="fx:USDINR",
        name="US Dollar / Indian Rupee",
        asset_class="fx",
        currency="INR",
        timezone="UTC",
        aliases={Y: "USDINR=X"},
        search=("USDINR", "Rupee", "INR"),
        price_definition="Indian rupees per US dollar (reference rate)",
    ),
]

BY_ID: dict[str, InstrumentDef] = {i.id: i for i in UNIVERSE}

# Benchmarks used for beta and "performance vs benchmark".
DEFAULT_BENCHMARK = {"global": "idx:us:SPX", "india": "idx:in:NIFTY50"}
USDINR_ID = "fx:USDINR"
