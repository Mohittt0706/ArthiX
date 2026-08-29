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


def _classify(title):
    t = title.lower()
    pos = sum(1 for kw in _POSITIVE_KEYWORDS if kw in t)
    neg = sum(1 for kw in _NEGATIVE_KEYWORDS if kw in t)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def run(evidence):
    news = evidence.get("news", {})
    total = news.get("total", 0)
    recent = news.get("recent", [])

    classified = []
    pos = 0
    neg = 0
    neu = 0
    for item in recent:
        label = _classify(item.get("title", ""))
        classified.append({
            "title": item.get("title", ""),
            "publisher": item.get("publisher", ""),
            "sentiment": label,
        })
        if label == "positive":
            pos += 1
        elif label == "negative":
            neg += 1
        else:
            neu += 1

    if total == 0:
        sentiment_label = "no data"
    elif pos > neg * 2:
        sentiment_label = "positive"
    elif neg > pos * 2:
        sentiment_label = "negative"
    elif pos > neg:
        sentiment_label = "mildly positive"
    elif neg > pos:
        sentiment_label = "mildly negative"
    else:
        sentiment_label = "neutral"

    signals = []
    if total > 0:
        signals.append(f"{total} news items tracked")
        signals.append(
            f"Sentiment: {sentiment_label} "
            f"({pos} positive, {neg} negative, {neu} neutral)"
        )
    else:
        signals.append("No recent news available")

    if classified:
        signals.append(f"Latest: {classified[0].get('title', 'N/A')}")

    summary = f"News analysis: {'; '.join(signals)}."

    return {
        "agent": "Newsdesk",
        "status": "complete",
        "output": {
            "total": total,
            "positive": pos,
            "negative": neg,
            "neutral": neu,
            "sentiment_label": sentiment_label,
            "classified": classified,
            "headlines": [
                {"title": c["title"], "publisher": c["publisher"]}
                for c in classified
            ],
            "signals": signals,
            "summary": summary,
        },
    }
