import re
import json


def _extract_numbers(text):
    if not text:
        return []
    patterns = [
        r'[\+\-]?\d+\.?\d*%',
        r'[\+\-]?\d+\.?\d*(?: points| pts)',
        r'(?:score|confidence|net|bull|bear)[:\s]*(\d+\.?\d*)',
        r'(\d+\.?\d*)/10',
        r'₹[\d,]+\.?\d*',
    ]
    numbers = []
    seen = set()
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            if m not in seen:
                seen.add(m)
                numbers.append(m)
    return numbers


def _build_evidence_numbers(evidence):
    numbers = set()
    for section in ("price", "range_52w", "technicals", "analyst", "news"):
        data = evidence.get(section, {})
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, (int, float)):
                    numbers.add(str(v))
                    numbers.add(f"{v:.1f}")
                    numbers.add(f"{v:.2f}")
                    numbers.add(f"{v:+.1f}")
                    numbers.add(f"{v:+.2f}")
                    numbers.add(str(abs(v)))
                    numbers.add(f"{abs(v):.1f}")
                    numbers.add(f"{abs(v):.2f}")
                    numbers.add(f"{round(v)}")
    computed = evidence.get("_computed", {})
    if isinstance(computed, dict):
        for v in computed.values():
            if isinstance(v, (int, float)):
                numbers.add(str(v))
                numbers.add(f"{v:.1f}")
                numbers.add(f"{v:.2f}")
                numbers.add(f"{v:+.1f}")
                numbers.add(f"{v:+.2f}")
                numbers.add(str(abs(v)))
                numbers.add(f"{abs(v):.1f}")
                numbers.add(f"{abs(v):.2f}")
                numbers.add(f"{round(v)}")
    return numbers


def _build_screening_numbers(shortlist):
    """Build set of all numbers traceable to screening data."""
    numbers = set()
    if not isinstance(shortlist, dict):
        return numbers
    for bucket, stocks in shortlist.items():
        if not isinstance(stocks, list):
            continue
        for stock in stocks:
            if not isinstance(stock, dict):
                continue
            for key in ("day_change_pct", "price"):
                val = stock.get(key)
                if val is not None and isinstance(val, (int, float)):
                    numbers.add(str(val))
                    numbers.add(f"{val:+.2f}")
                    numbers.add(f"{abs(val):.2f}")
    return numbers


def _check_numbers_against_evidence(output_text, evidence_numbers):
    """Check extracted numbers against a set of evidence numbers. Returns flagged list."""
    output_numbers = _extract_numbers(output_text)
    flagged = []
    for num_str in output_numbers:
        clean = num_str.rstrip('%').replace('₹', '').replace(',', '').strip()
        if clean in evidence_numbers:
            continue
        try:
            val = float(clean)
            found = False
            for en in evidence_numbers:
                try:
                    en_val = float(en)
                    if abs(en_val - val) < 0.01:
                        found = True
                        break
                except (ValueError, TypeError):
                    continue
            if not found:
                flagged.append(num_str)
        except (ValueError, TypeError):
            pass
    return flagged


def verify_grounding(agent_output, evidence):
    """Verify all agent outputs are grounded in evidence.

    Returns per-agent grounding results.
    """
    if not agent_output:
        return {"valid": True, "per_agent": {}, "flagged": [], "warnings": ["No agent output to verify"]}

    stock_numbers = _build_evidence_numbers(evidence)

    per_agent = {}
    all_flagged = []

    if isinstance(agent_output, dict):
        for agent_name, agent_data in agent_output.items():
            output_text = json.dumps(agent_data) if not isinstance(agent_data, str) else agent_data
            flagged = _check_numbers_against_evidence(output_text, stock_numbers)
            per_agent[agent_name] = {
                "valid": len(flagged) == 0,
                "flagged": flagged,
            }
            all_flagged.extend(flagged)
    else:
        flagged = _check_numbers_against_evidence(str(agent_output), stock_numbers)
        all_flagged.extend(flagged)

    warnings = []
    if all_flagged:
        warnings.append(f"Found {len(all_flagged)} number(s) not traceable to evidence bundle")

    return {
        "valid": len(all_flagged) == 0,
        "per_agent": per_agent,
        "flagged": all_flagged,
        "warnings": warnings,
    }


def verify_scout_grounding(scout_output, stock_evidence, screening_evidence):
    """Verify Scout grounding against both stock evidence and screening evidence.

    Scout is allowed to reference:
    - Numbers from the selected stock's evidence (same as other agents)
    - Numbers from the screening/shortlist data (cross-stock references)
    """
    stock_numbers = _build_evidence_numbers(stock_evidence)
    screening_numbers = _build_screening_numbers(screening_evidence)
    allowed_numbers = stock_numbers | screening_numbers

    output_text = json.dumps(scout_output) if not isinstance(scout_output, str) else scout_output
    flagged = _check_numbers_against_evidence(output_text, allowed_numbers)

    return {
        "valid": len(flagged) == 0,
        "flagged": flagged,
        "warnings": [f"Found {len(flagged)} number(s) not traceable to stock or screening evidence"] if flagged else [],
    }


def verify_verdict_integrity(verdict_data, evidence):
    issues = []
    required_fields = ["winner", "verdict", "confidence", "rationale", "key_catalyst", "bull_score", "bear_score", "net"]
    for field in required_fields:
        if field not in verdict_data or verdict_data[field] is None:
            issues.append(f"Missing required field: {field}")

    if verdict_data.get("verdict") not in ("BUY", "WATCH", "AVOID"):
        issues.append(f"Invalid verdict: {verdict_data.get('verdict')}")

    confidence = verdict_data.get("confidence")
    if confidence is not None:
        if not (1 <= confidence <= 10):
            issues.append(f"Confidence out of range: {confidence}")

    bull = verdict_data.get("bull_score", 0) or 0
    bear = verdict_data.get("bear_score", 0) or 0
    net = verdict_data.get("net", 0) or 0
    if abs((bull - bear) - net) > 0.1:
        issues.append(f"Net score mismatch: {bull} - {bear} != {net}")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
    }
