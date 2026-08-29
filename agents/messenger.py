import os

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def _format_signal(symbol, name, verdict_data, price_data):
    verdict = verdict_data.get("verdict", "WATCH")
    confidence = verdict_data.get("confidence", 0)
    winner = verdict_data.get("winner", "Unknown")
    rationale = verdict_data.get("rationale", "")
    key_catalyst = verdict_data.get("key_catalyst", "")
    current_price = price_data.get("live", "N/A") if price_data else "N/A"
    day_change = price_data.get("day_change_pct", "N/A") if price_data else "N/A"

    emoji = "🟢" if verdict == "BUY" else ("🟡" if verdict == "WATCH" else "🔴")

    signal = f"""{emoji} BUY SIGNAL — {symbol}

Verdict: {verdict} | Confidence: {confidence}/10
Winner: {winner}
Why: {rationale}
Key catalyst: {key_catalyst}
Live price: ₹{current_price} | Day change: {day_change}%

— Analysis only. No trade was placed. Not investment advice."""

    return signal


def send_telegram(signal_text, bot_token=None, chat_id=None):
    if not HAS_REQUESTS:
        return {"sent": False, "error": "requests library not available"}

    bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")

    if not bot_token or not chat_id:
        return {"sent": False, "error": "Telegram credentials not configured"}

    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": signal_text,
            "parse_mode": "HTML",
        }
        resp = requests.post(url, json=payload, timeout=10)
        return {"sent": resp.status_code == 200, "status_code": resp.status_code}
    except Exception as e:
        return {"sent": False, "error": str(e)}


def maybe_send_signal(symbol, name, verdict_data, price_data, confidence_threshold=7):
    verdict = verdict_data.get("verdict", "WATCH")
    confidence = verdict_data.get("confidence", 0)

    if verdict == "BUY" and confidence >= confidence_threshold:
        signal_text = _format_signal(symbol, name, verdict_data, price_data)
        result = send_telegram(signal_text)
        return {"sent": True, "telegram": result}

    return {"sent": False, "reason": "Signal criteria not met"}


def run(evidence, verdict_data, user_settings=None):
    symbol = evidence.get("symbol", "UNKNOWN")
    name = evidence.get("name", "Unknown")
    price_data = evidence.get("price", {})

    threshold = 7
    if user_settings:
        threshold = user_settings.get("confidence_threshold", 7)
        notifications_enabled = user_settings.get("notifications_enabled", False)
        if not notifications_enabled:
            return {
                "agent": "Messenger",
                "status": "complete",
                "output": {
                    "action": "skip",
                    "reason": "Notifications disabled for this user",
                },
            }

    telegram_result = maybe_send_signal(symbol, name, verdict_data, price_data, threshold)

    return {
        "agent": "Messenger",
        "status": "complete",
        "output": {
            "action": "signal_sent" if telegram_result.get("sent") else "no_signal",
            "verdict": verdict_data.get("verdict"),
            "confidence": verdict_data.get("confidence"),
            "threshold": threshold,
            "telegram": telegram_result,
        },
    }
