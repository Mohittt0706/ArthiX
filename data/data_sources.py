import os
import json
import time
import random
from pathlib import Path

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False


UNIVERSE_PATH = Path(__file__).parent / "universe.json"
DEMO_DATA_DIR = Path(__file__).parent.parent / "demo_data"


class DataUnavailableError(Exception):
    """Raised when live data cannot be fetched and demo fallback is not allowed."""
    pass


def load_universe():
    with open(UNIVERSE_PATH, "r") as f:
        return json.load(f)


def resolve_symbol(query):
    """Resolve a user query to the correct NSE .NS ticker.

    Accepts:
      - Raw NSE symbol: 'TCS' -> 'TCS.NS'
      - Full ticker: 'TCS.NS' -> 'TCS.NS'
      - Company name search: 'Tata Consultancy' -> first match
    Returns (symbol, stock_info) or (None, None) if not found.
    """
    q = query.strip().upper()
    if not q:
        return None, None

    universe = load_universe()

    for segment, stocks in universe.items():
        for stock in stocks:
            if stock["symbol"].upper() == q or stock["symbol"].upper() == q + ".NS":
                return stock["symbol"], {**stock, "cap_segment": segment}

    for segment, stocks in universe.items():
        for stock in stocks:
            if q in stock["symbol"].upper() or q in stock["name"].upper():
                return stock["symbol"], {**stock, "cap_segment": segment}

    return None, None


def search_stocks(query, cap_segment=None):
    universe = load_universe()
    results = []
    q = query.upper().strip()
    if not q:
        return results
    for segment, stocks in universe.items():
        if cap_segment and segment != cap_segment:
            continue
        for stock in stocks:
            if q in stock["symbol"].upper() or q in stock["name"].upper():
                results.append({**stock, "cap_segment": segment})
    return results


def fetch_live_evidence(symbol):
    """Fetch live market data for a stock. Returns evidence dict or None."""
    if not HAS_YFINANCE:
        return None
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
        hist = ticker.history(period="1mo", interval="1d")

        if hist.empty:
            return None

        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        if current_price is None and not hist.empty:
            current_price = float(hist["Close"].iloc[-1])

        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        if prev_close is None and len(hist) >= 2:
            prev_close = float(hist["Close"].iloc[-2])

        day_open = info.get("open") or info.get("regularMarketOpen")
        if day_open is None and not hist.empty:
            day_open = float(hist["Open"].iloc[-1])

        day_high = info.get("dayHigh") or info.get("regularMarketDayHigh")
        if day_high is None and not hist.empty:
            day_high = float(hist["High"].iloc[-1])

        day_low = info.get("dayLow") or info.get("regularMarketDayLow")
        if day_low is None and not hist.empty:
            day_low = float(hist["Low"].iloc[-1])

        volume = info.get("volume") or info.get("regularMarketVolume")
        if volume is None and not hist.empty:
            volume = int(hist["Volume"].iloc[-1])

        high_52w = info.get("fiftyTwoWeekHigh")
        low_52w = info.get("fiftyTwoWeekLow")

        avg_volume_20d = info.get("averageVolume") or info.get("averageDailyVolume10Day")
        if avg_volume_20d is None and len(hist) >= 5:
            avg_volume_20d = float(hist["Volume"].tail(20).mean()) if len(hist) >= 20 else float(hist["Volume"].mean())

        rvol = None
        if volume and avg_volume_20d and avg_volume_20d > 0:
            rvol = round(volume / avg_volume_20d, 2)

        sma_20 = None
        if len(hist) >= 20:
            sma_20 = round(float(hist["Close"].tail(20).mean()), 2)
        elif len(hist) >= 5:
            sma_20 = round(float(hist["Close"].mean()), 2)

        price_vs_sma_pct = None
        if current_price and sma_20 and sma_20 > 0:
            price_vs_sma_pct = round(((current_price - sma_20) / sma_20) * 100, 2)

        window_return_pct = None
        if len(hist) >= 2 and float(hist["Close"].iloc[0]) > 0:
            window_return_pct = round(
                ((float(hist["Close"].iloc[-1]) - float(hist["Close"].iloc[0])) / float(hist["Close"].iloc[0])) * 100, 2
            )

        day_change_pct = None
        if current_price and prev_close and prev_close > 0:
            day_change_pct = round(((current_price - prev_close) / prev_close) * 100, 2)

        day_range_position_pct = None
        if day_high and day_low and day_high != day_low and current_price:
            day_range_position_pct = round(((current_price - day_low) / (day_high - day_low)) * 100, 2)

        pct_from_high = None
        position_pct = None
        if current_price and high_52w and low_52w:
            if high_52w > 0:
                pct_from_high = round(((current_price - high_52w) / high_52w) * 100, 2)
            range_52 = high_52w - low_52w
            if range_52 > 0:
                position_pct = round(((current_price - low_52w) / range_52) * 100, 2)

        trend = "sideways"
        if price_vs_sma_pct is not None:
            if price_vs_sma_pct > 2:
                trend = "up"
            elif price_vs_sma_pct < -2:
                trend = "down"

        swing_high = float(hist["High"].max()) if not hist.empty else None
        swing_low = float(hist["Low"].min()) if not hist.empty else None

        news_items = []
        try:
            news = ticker.news or []
            for item in news[:10]:
                news_items.append({
                    "title": item.get("title", ""),
                    "publisher": item.get("publisher", ""),
                    "link": item.get("link", ""),
                })
        except Exception:
            pass

        pos_count, neg_count, neu_count = _score_news_sentiment(news_items)

        consensus = info.get("recommendationKey", "")
        num_analysts = info.get("numberOfAnalystOpinions")
        target_mean = info.get("targetMeanPrice")
        target_low = info.get("targetLowPrice")
        target_high = info.get("targetHighPrice")

        buy_pct = None
        hold_pct = None
        sell_pct = None
        try:
            rec = info.get("recommendationKey", "").lower()
            if rec == "buy":
                buy_pct = 70
                hold_pct = 25
                sell_pct = 5
            elif rec == "hold":
                buy_pct = 30
                hold_pct = 55
                sell_pct = 15
            elif rec == "sell":
                buy_pct = 10
                hold_pct = 30
                sell_pct = 60
        except Exception:
            pass

        upside_pct = None
        if target_mean and current_price and current_price > 0:
            upside_pct = round(((target_mean - current_price) / current_price) * 100, 2)

        evidence = {
            "symbol": symbol,
            "name": info.get("shortName") or info.get("longName", symbol),
            "sector": info.get("sector", "Unknown"),
            "cap_segment": "unknown",
            "price": {
                "live": current_price,
                "day_open": day_open,
                "high": day_high,
                "low": day_low,
                "prev_close": prev_close,
                "day_change_pct": day_change_pct,
                "volume": volume,
            },
            "range_52w": {
                "high": high_52w,
                "low": low_52w,
                "pct_from_high": pct_from_high,
                "position_pct": position_pct,
            },
            "technicals": {
                "rvol": rvol,
                "price_vs_sma_pct": price_vs_sma_pct,
                "window_return_pct": window_return_pct,
                "swing_high": swing_high,
                "swing_low": swing_low,
                "day_range_position_pct": day_range_position_pct,
                "trend": trend,
            },
            "analyst": {
                "consensus": consensus,
                "num_analysts": num_analysts,
                "buy_pct": buy_pct,
                "hold_pct": hold_pct,
                "sell_pct": sell_pct,
                "target_mean": target_mean,
                "target_low": target_low,
                "target_high": target_high,
                "upside_pct": upside_pct,
            },
            "news": {
                "total": len(news_items),
                "positive": pos_count,
                "negative": neg_count,
                "neutral": neu_count,
                "recent": news_items[:5],
            },
            "data_gaps": [],
            "source": "live",
            "fetched_at": time.time(),
        }

        gaps = []
        for section_key, section in evidence.items():
            if section_key in ("symbol", "name", "sector", "cap_segment", "source", "fetched_at", "data_gaps"):
                continue
            if isinstance(section, dict):
                for k, v in section.items():
                    if v is None:
                        gaps.append(f"{section_key}.{k}")
        evidence["data_gaps"] = gaps

        return evidence

    except Exception as e:
        print(f"Error fetching live data for {symbol}: {e}")
        return None


def load_demo_evidence(symbol):
    """Generate deterministic demo evidence for a stock."""
    demo_file = DEMO_DATA_DIR / f"{symbol.replace('.NS', '')}.json"
    if demo_file.exists():
        with open(demo_file, "r") as f:
            data = json.load(f)
            data["source"] = "demo"
            data["fetched_at"] = time.time()
            return data

    universe = load_universe()
    stock_info = None
    for segment, stocks in universe.items():
        for s in stocks:
            if s["symbol"] == symbol:
                stock_info = {**s, "cap_segment": segment}
                break
        if stock_info:
            break

    if not stock_info:
        stock_info = {"symbol": symbol, "name": symbol, "sector": "Unknown", "cap_segment": "unknown"}

    random.seed(hash(symbol))
    base_price = random.uniform(500, 5000)
    prev_close = base_price * random.uniform(0.97, 1.03)
    day_change_pct = round(((base_price - prev_close) / prev_close) * 100, 2)

    high_52w = base_price * random.uniform(1.1, 1.5)
    low_52w = base_price * random.uniform(0.5, 0.9)

    rvol = round(random.uniform(0.3, 3.5), 2)
    sma_20 = base_price * random.uniform(0.95, 1.05)
    price_vs_sma_pct = round(((base_price - sma_20) / sma_20) * 100, 2)

    position_pct = round(((base_price - low_52w) / (high_52w - low_52w)) * 100, 2)
    pct_from_high = round(((base_price - high_52w) / high_52w) * 100, 2)

    trend = "sideways"
    if price_vs_sma_pct > 2:
        trend = "up"
    elif price_vs_sma_pct < -2:
        trend = "down"

    num_analysts = random.randint(5, 30)
    buy_pct = random.randint(20, 80)
    sell_pct = random.randint(0, 30)
    hold_pct = 100 - buy_pct - sell_pct
    target_mean = base_price * random.uniform(1.0, 1.3)
    upside_pct = round(((target_mean - base_price) / base_price) * 100, 2)

    sentiment_roll = random.random()
    pos = random.randint(1, 5)
    neg = random.randint(0, 3)
    neu = random.randint(2, 8)

    demo_news = [
        {"title": f"{stock_info['name']} reports quarterly results", "publisher": "Economic Times", "sentiment": "neutral"},
        {"title": f"Market analysts review {stock_info['name']} outlook", "publisher": "Moneycontrol", "sentiment": "positive" if sentiment_roll > 0.5 else "negative"},
        {"title": f"Sector trends impact {stock_info['name']}", "publisher": "LiveMint", "sentiment": "neutral"},
    ]

    evidence = {
        "symbol": symbol,
        "name": stock_info["name"],
        "sector": stock_info["sector"],
        "cap_segment": stock_info["cap_segment"],
        "price": {
            "live": round(base_price, 2),
            "day_open": round(base_price * random.uniform(0.99, 1.01), 2),
            "high": round(base_price * random.uniform(1.0, 1.03), 2),
            "low": round(base_price * random.uniform(0.97, 1.0), 2),
            "prev_close": round(prev_close, 2),
            "day_change_pct": day_change_pct,
            "volume": random.randint(500000, 10000000),
        },
        "range_52w": {
            "high": round(high_52w, 2),
            "low": round(low_52w, 2),
            "pct_from_high": pct_from_high,
            "position_pct": position_pct,
        },
        "technicals": {
            "rvol": rvol,
            "price_vs_sma_pct": price_vs_sma_pct,
            "window_return_pct": round(random.uniform(-10, 15), 2),
            "swing_high": round(high_52w * random.uniform(0.9, 1.0), 2),
            "swing_low": round(low_52w * random.uniform(1.0, 1.1), 2),
            "day_range_position_pct": round(random.uniform(10, 90), 2),
            "trend": trend,
        },
        "analyst": {
            "consensus": random.choice(["buy", "hold", "sell"]),
            "num_analysts": num_analysts,
            "buy_pct": buy_pct,
            "hold_pct": hold_pct,
            "sell_pct": sell_pct,
            "target_mean": round(target_mean, 2),
            "target_low": round(target_mean * random.uniform(0.75, 0.9), 2),
            "target_high": round(target_mean * random.uniform(1.1, 1.3), 2),
            "upside_pct": upside_pct,
        },
        "news": {
            "total": pos + neg + neu,
            "positive": pos,
            "negative": neg,
            "neutral": neu,
            "recent": demo_news,
        },
        "data_gaps": [],
        "source": "demo",
        "fetched_at": time.time(),
    }

    os.makedirs(DEMO_DATA_DIR, exist_ok=True)
    with open(demo_file, "w") as f:
        json.dump(evidence, f, indent=2)

    return evidence


def get_evidence(symbol, force_live=False):
    """Get evidence for a stock.

    In DEMO mode: always returns demo evidence.
    In LIVE mode (force_live=True or DEMO_MODE=false):
      - Tries live data first.
      - If live fails, raises DataUnavailableError (no silent fallback).
    """
    from config import config

    if not force_live and config.is_demo_mode():
        return load_demo_evidence(symbol)

    live = fetch_live_evidence(symbol)
    if live:
        return live

    raise DataUnavailableError(
        f"Live data unavailable for {symbol}. "
        f"Market may be closed or network error. "
        f"Use DEMO_MODE=true for testing."
    )


def collect_analysis(symbol, force_live=False):
    """Collect evidence for analysis. Raises DataUnavailableError in live mode if fetch fails."""
    return get_evidence(symbol, force_live=force_live)


_POSITIVE_KEYWORDS = [
    "surge", "rally", "gain", "profit", "upgrade", "buy", "bullish",
    "record high", "outperform", "beat", "strong", "growth", "boom",
    "breakout", "soar", "jump", "rise", "climb", "recovery", "positive",
    "upbeat", "optimistic", "bull", "uptick", "momentum",
]

_NEGATIVE_KEYWORDS = [
    "crash", "plunge", "drop", "loss", "downgrade", "sell", "bearish",
    "record low", "underperform", "miss", "weak", "decline", "slump",
    "breakdown", "tumble", "fall", "sink", "dump", "crisis", "negative",
    "downturn", "pessimistic", "bear", "downtick", "correction",
]


def _classify_headline(title):
    t = title.lower()
    pos = sum(1 for kw in _POSITIVE_KEYWORDS if kw in t)
    neg = sum(1 for kw in _NEGATIVE_KEYWORDS if kw in t)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def _score_news_sentiment(news_items):
    pos = 0
    neg = 0
    neu = 0
    for item in news_items:
        label = _classify_headline(item.get("title", ""))
        item["sentiment"] = label
        if label == "positive":
            pos += 1
        elif label == "negative":
            neg += 1
        else:
            neu += 1
    return pos, neg, neu


def screen_universe(strict=False):
    """Screen the full stock universe and return shortlisted stocks per bucket.

    Args:
        strict: If True, raises DataUnavailableError when any live fetch fails.
                If False, skips stocks with unavailable data (no demo fallback).
    """
    from config import config
    universe = load_universe()
    per_bucket = config.SHORTLIST_PER_BUCKET
    results = {}

    for segment, stocks in universe.items():
        bucket_candidates = []
        for stock in stocks:
            symbol = stock["symbol"]

            if config.is_demo_mode() and not strict:
                ev = load_demo_evidence(symbol)
            else:
                ev = fetch_live_evidence(symbol)
                if ev is None:
                    if strict:
                        raise DataUnavailableError(
                            f"Live data unavailable for {symbol} during universe screening. "
                            f"Cannot complete screening in strict live mode."
                        )
                    continue

            day_change = None
            if ev and ev.get("price"):
                day_change = ev["price"].get("day_change_pct")

            bucket_candidates.append({
                "symbol": symbol,
                "name": stock["name"],
                "sector": stock["sector"],
                "cap_segment": segment,
                "day_change_pct": day_change,
                "price": ev["price"].get("live") if ev and ev.get("price") else None,
            })

        bucket_candidates.sort(
            key=lambda x: abs(x["day_change_pct"]) if x["day_change_pct"] is not None else 0,
            reverse=True,
        )
        results[segment] = bucket_candidates[:per_bucket]

    return results
