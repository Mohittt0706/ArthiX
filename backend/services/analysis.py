import time
import json
from data.data_sources import get_evidence, DataUnavailableError
from data.evidence import normalize_evidence
from agents.scout import run as scout_run
from agents.technician import run as tech_run
from agents.fundamentalist import run as fund_run
from agents.newsdesk import run as news_run
from agents.bull import run as bull_run
from agents.bear import run as bear_run
from agents.judge import run as judge_run
from agents.messenger import run as messenger_run
from engine.scoring import evaluate
from engine.verifier import (
    verify_grounding, verify_scout_grounding, verify_verdict_integrity,
)


_SINGLE_STOCK_AGENTS = ("technician", "fundamentalist", "newsdesk", "bull", "bear", "judge")


def run_pipeline(symbol, user_settings=None, force_live=False):
    """Run the full analysis pipeline for a stock.

    Pipeline flow:
      Evidence -> Scout -> Technician -> Fundamentalist -> Newsdesk -> Bull -> Bear -> Judge -> Messenger

    Each agent tries LLM analysis first, falls back to deterministic logic.

    Raises:
        DataUnavailableError: If live mode is on and data cannot be fetched.
    """
    start_time = time.time()
    agent_outputs = {}

    raw_evidence = get_evidence(symbol, force_live=force_live)
    evidence = normalize_evidence(raw_evidence)

    agent_outputs["scout"] = scout_run(evidence, strict_live=force_live)

    agent_outputs["technician"] = tech_run(evidence)
    agent_outputs["fundamentalist"] = fund_run(evidence)
    agent_outputs["newsdesk"] = news_run(evidence)

    tech_output = agent_outputs["technician"].get("output", {})
    fund_output = agent_outputs["fundamentalist"].get("output", {})
    news_output = agent_outputs["newsdesk"].get("output", {})

    agent_outputs["bull"] = bull_run(evidence, tech_output=tech_output, fund_output=fund_output, news_output=news_output)
    agent_outputs["bear"] = bear_run(evidence, tech_output=tech_output, fund_output=fund_output, news_output=news_output)

    scoring_result = evaluate(evidence)

    bull_output = agent_outputs["bull"].get("output", {})
    bear_output = agent_outputs["bear"].get("output", {})

    agent_outputs["judge"] = judge_run(
        evidence,
        scoring_result=scoring_result,
        tech_output=agent_outputs["technician"],
        fund_output=agent_outputs["fundamentalist"],
        news_output=agent_outputs["newsdesk"],
        bull_output=agent_outputs["bull"],
        bear_output=agent_outputs["bear"],
    )

    judge_output = agent_outputs["judge"]
    verdict_data = judge_output["output"]

    scout_out = agent_outputs.get("scout", {}).get("output", {})
    evidence["_computed"] = {
        "data_coverage": scout_out.get("data_coverage"),
        "pct_from_high_abs": abs(evidence.get("range_52w", {}).get("pct_from_high", 0) or 0),
        "position_pct_rounded": round(evidence.get("range_52w", {}).get("position_pct", 0) or 0),
        "net_score": verdict_data.get("net"),
    }

    screening_data = scout_out.get("shortlist", {})
    scout_grounding = verify_scout_grounding(
        agent_outputs["scout"], evidence, screening_data
    )

    single_stock_outputs = {
        k: v for k, v in agent_outputs.items() if k in _SINGLE_STOCK_AGENTS
    }
    stock_grounding = verify_grounding(single_stock_outputs, evidence)

    per_agent_grounding = {"scout": scout_grounding}
    per_agent_grounding.update(stock_grounding.get("per_agent", {}))

    all_flagged = scout_grounding.get("flagged", []) + stock_grounding.get("flagged", [])
    grounding_check = {
        "valid": len(all_flagged) == 0,
        "per_agent": per_agent_grounding,
        "flagged": all_flagged,
        "warnings": (
            scout_grounding.get("warnings", [])
            + stock_grounding.get("warnings", [])
        ),
    }

    verdict_check = verify_verdict_integrity(verdict_data, evidence)

    messenger_output = messenger_run(evidence, verdict_data, user_settings)
    agent_outputs["messenger"] = messenger_output

    llm_used = any(
        agent_outputs.get(a, {}).get("llm_powered", False)
        for a in ("technician", "fundamentalist", "newsdesk", "bull", "bear", "judge")
    )

    elapsed = round(time.time() - start_time, 2)

    return {
        "evidence": evidence,
        "agent_outputs": agent_outputs,
        "scoring": scoring_result,
        "verdict": verdict_data,
        "llm_used": llm_used,
        "grounding": grounding_check,
        "verdict_integrity": verdict_check,
        "elapsed_seconds": elapsed,
    }
