from engine.scoring import evaluate


def run(evidence, scoring_result=None):
    if scoring_result is None:
        scoring_result = evaluate(evidence)

    verdict_data = scoring_result.get("verdict", {})

    bull_output = scoring_result.get("scores", {}).get("bull", {})
    bear_output = scoring_result.get("scores", {}).get("bear", {})

    bull_args = bull_output.get("reasons", [])
    bear_args = bear_output.get("reasons", [])

    debate_summary = []
    if bull_args:
        debate_summary.append(f"Bull arguments ({len(bull_args)}): {'; '.join(bull_args[:3])}")
    if bear_args:
        debate_summary.append(f"Bear arguments ({len(bear_args)}): {'; '.join(bear_args[:3])}")

    return {
        "agent": "Judge",
        "status": "complete",
        "output": {
            "winner": verdict_data.get("winner", "Unknown"),
            "verdict": verdict_data.get("verdict", "WATCH"),
            "confidence": verdict_data.get("confidence", 5),
            "rationale": verdict_data.get("rationale", "Insufficient data for clear verdict"),
            "key_catalyst": verdict_data.get("key_catalyst", "No clear catalyst"),
            "bull_score": verdict_data.get("bull_score", 0),
            "bear_score": verdict_data.get("bear_score", 0),
            "net": verdict_data.get("net", 0),
            "debate_summary": debate_summary,
        },
    }
