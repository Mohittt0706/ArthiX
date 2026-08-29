from data.data_sources import screen_universe, DataUnavailableError


def run(evidence, strict_live=False):
    """Scout agent: screens universe and reports on the analyzed stock.

    In pipeline mode (single stock analysis): reports on that stock's data quality.
    In screen mode: called separately via /api/screen for universe screening.

    Args:
        evidence: The normalized evidence bundle for the stock being analyzed.
        strict_live: If True, universe screening uses live data strictly.
    """
    symbol = evidence.get("symbol", "UNKNOWN")
    name = evidence.get("name", "Unknown")
    sector = evidence.get("sector", "Unknown")
    cap_segment = evidence.get("cap_segment", "unknown")
    source = evidence.get("source", "unknown")
    gaps = evidence.get("data_gaps", [])

    coverage = 100 - min(len(gaps) * 3, 50)

    shortlist = {}
    screening_error = None
    try:
        shortlist = screen_universe(strict=strict_live)
    except DataUnavailableError as e:
        screening_error = str(e)
    except Exception as e:
        screening_error = f"Screening error: {e}"

    signals = []
    for bucket, stocks in shortlist.items():
        if stocks:
            top = stocks[0]
            signals.append(
                f"{bucket}: top mover {top['symbol']} ({top['name']}) "
                f"day change {top['day_change_pct']:+.2f}%"
            )

    if screening_error:
        signals.append(f"Screening unavailable: {screening_error}")

    summary = (
        f"Scanned {name} ({symbol}) in {sector} sector, {cap_segment} cap. "
        f"Data source: {source}. Coverage: {coverage}%. {len(gaps)} data gaps. "
    )
    if shortlist:
        summary += f"Universe screening: {len(shortlist)} buckets scanned."
    elif screening_error:
        summary += f"Universe screening failed: {screening_error}"
    else:
        summary += "Universe screening: no data."

    return {
        "agent": "Scout",
        "status": "complete",
        "output": {
            "symbol": symbol,
            "name": name,
            "sector": sector,
            "cap_segment": cap_segment,
            "data_source": source,
            "data_coverage": coverage,
            "gaps_count": len(gaps),
            "shortlist": shortlist,
            "signals": signals,
            "summary": summary,
            "screening_error": screening_error,
        },
    }
