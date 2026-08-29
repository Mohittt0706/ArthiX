from engine.scoring import evaluate
from agents.base import _safe, _clamp, build_evidence_text, validate_schema
from engine.llm import call_llm_structured


_SYSTEM_PROMPT = """You are an expert investment judge synthesizing multiple analyst perspectives on an Indian stock.

You receive:
1. Normalized evidence bundle
2. Technician analysis (conviction, bullish_signals, bearish_signals)
3. Fundamentalist analysis (conviction, bullish_points, bearish_points)
4. Newsdesk analysis (sentiment, conviction, catalysts, risks)
5. Bull case (conviction, arguments, risks_acknowledged)
6. Bear case (conviction, arguments, bullish_risks_acknowledged)
7. Deterministic scores (bull_score, bear_score, net)

Your task: Synthesize all perspectives into a final assessment.

CRITICAL RULES:
- The deterministic scoring rules are the SAFETY RAIL. Your recommended_verdict must respect them.
- If your analysis disagrees with the deterministic scores, note this in the assessment.
- Do NOT override the deterministic safety rules.
- Use ONLY evidence and agent outputs provided. Do NOT invent data.
- confidence: 1-10 (how confident you are in your assessment)
- winner: "bull", "bear", or "tie" based on weight of evidence
- recommended_verdict: "BUY", "WATCH", or "AVOID"
- evidence_used: key evidence fields that drove your conclusion

Return ONLY valid JSON:
{
  "agent": "judge",
  "winner": "bull"|"bear"|"tie",
  "assessment": "<3-5 sentence synthesis of all perspectives>",
  "key_catalyst": "<single most important factor>",
  "key_risk": "<single most important risk>",
  "confidence": <1-10>,
  "recommended_verdict": "BUY"|"WATCH"|"AVOID",
  "evidence_used": ["field1", ...]
}"""


def _deterministic(evidence, scoring_result):
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
        "winner": verdict_data.get("winner", "Unknown"),
        "verdict": verdict_data.get("verdict", "WATCH"),
        "confidence": verdict_data.get("confidence", 5),
        "rationale": verdict_data.get("rationale", "Insufficient data for clear verdict"),
        "key_catalyst": verdict_data.get("key_catalyst", "No clear catalyst"),
        "bull_score": verdict_data.get("bull_score", 0),
        "bear_score": verdict_data.get("bear_score", 0),
        "net": verdict_data.get("net", 0),
        "debate_summary": debate_summary,
    }


def _build_judge_prompt(evidence, tech_output, fund_output, news_output, bull_output, bear_output, scoring_result):
    evidence_text = build_evidence_text(evidence)

    det = scoring_result.get("verdict", {})
    det_scores = scoring_result.get("scores", {})

    analysis_text = f"""

TECHNICIAN: conviction={tech_output.get('conviction', 'N/A')}, bullish={tech_output.get('bullish_signals', [])}, bearish={tech_output.get('bearish_signals', [])}

FUNDAMENTALIST: conviction={fund_output.get('conviction', 'N/A')}, bullish={fund_output.get('bullish_points', [])}, bearish={fund_output.get('bearish_points', [])}

NEWSDESK: sentiment={news_output.get('sentiment', 'N/A')}, conviction={news_output.get('conviction', 'N/A')}, catalysts={news_output.get('catalysts', [])}, risks={news_output.get('risks', [])}

BULL CASE: conviction={bull_output.get('conviction', 'N/A')}, arguments={bull_output.get('arguments', [])}, risks_acknowledged={bull_output.get('risks_acknowledged', [])}

BEAR CASE: conviction={bear_output.get('conviction', 'N/A')}, arguments={bear_output.get('arguments', [])}, bullish_risks={bear_output.get('bullish_risks_acknowledged', [])}

DETERMINISTIC SCORES: bull={det.get('bull_score', 0)}, bear={det.get('bear_score', 0)}, net={det.get('net', 0)}, verdict={det.get('verdict', 'WATCH')}

{f"BULL SCORES DETAIL: {det_scores.get('bull', {}).get('reasons', [])}" if det_scores.get('bull', {}).get('reasons') else ""}
{f"BEAR SCORES DETAIL: {det_scores.get('bear', {}).get('reasons', [])}" if det_scores.get('bear', {}).get('reasons') else ""}
"""

    return f"{_SYSTEM_PROMPT}\n\nEVIDENCE:\n{evidence_text}\n\nANALYSIS:\n{analysis_text}"


def run(evidence, scoring_result=None, tech_output=None, fund_output=None, news_output=None, bull_output=None, bear_output=None):
    if scoring_result is None:
        scoring_result = evaluate(evidence)

    det_result = _deterministic(evidence, scoring_result)

    tech_out = tech_output.get("output", {}) if tech_output else {}
    fund_out = fund_output.get("output", {}) if fund_output else {}
    news_out = news_output.get("output", {}) if news_output else {}
    bull_out = bull_output.get("output", {}) if bull_output else {}
    bear_out = bear_output.get("output", {}) if bear_output else {}

    prompt = _build_judge_prompt(evidence, tech_out, fund_out, news_out, bull_out, bear_out, scoring_result)

    llm_result, error = call_llm_structured(prompt, "judge", timeout=30, retries=1)

    ai_judge = None
    disagreement = None
    if llm_result and not error:
        ai_judge = llm_result
        det_verdict = det_result.get("verdict", "WATCH")
        ai_verdict = ai_judge.get("recommended_verdict", "WATCH")
        if det_verdict != ai_verdict:
            disagreement = {
                "deterministic_verdict": det_verdict,
                "ai_verdict": ai_verdict,
                "note": f"Deterministic rules produced {det_verdict}, AI recommended {ai_verdict}. Using deterministic verdict as safety rail.",
            }

    output = dict(det_result)
    if ai_judge:
        output["llm_assessment"] = ai_judge.get("assessment", "")
        output["llm_key_catalyst"] = ai_judge.get("key_catalyst", "")
        output["llm_key_risk"] = ai_judge.get("key_risk", "")
        output["llm_winner"] = ai_judge.get("winner", "")
        output["llm_confidence"] = ai_judge.get("confidence", 5)
        output["llm_recommended_verdict"] = ai_judge.get("recommended_verdict", "WATCH")
    if disagreement:
        output["ai_disagreement"] = disagreement

    return {
        "agent": "Judge",
        "status": "complete",
        "output": output,
        "llm_powered": ai_judge is not None,
    }
