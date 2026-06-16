def score_step(step: str, rune) -> dict:
    """Return a structural divergence-risk score in [0, 1] for one step."""
    # Defensive: rune_loader.py currently always coerces constraints to a
    # list (never None), but guard here anyway so a future loader change
    # can't silently crash this function with a TypeError on len(None).
    constraints = rune.constraints if rune.constraints is not None else []
    genome = rune.genome if rune.genome is not None else []

    specificity_risk = STEP_SPECIFICITY.get(step, 0.7)  # unknown step = treat as risky

    is_tool_step = step in TOOL_STEPS
    if is_tool_step:
        # Risk is lower if the rune declares constraints that narrow tool use,
        # higher if tools are listed with no behavioral anchor.
        tool_risk = 0.5 if not constraints else 0.25
        w_specificity, w_tool, w_constraint = 0.5, 0.3, 0.2
    else:
        # Bug fix: with fixed weights of 0.5/0.3/0.2, a non-tool step's
        # tool_risk is always 0.0, which caps its maximum possible raw
        # score at 0.58 even in the worst case (specificity=0.8,
        # constraint_risk=0.4 for "analyze", the riskiest known step).
        # That means no non-tool step could ever be flagged "high" (>=0.6),
        # regardless of how vague or unconstrained it actually is. Since
        # tool_risk doesn't apply here, redistribute its 0.3 weight across
        # the two signals that do apply, so a genuinely risky non-tool step
        # can actually reach the high band.
        tool_risk = 0.0
        w_specificity, w_tool, w_constraint = 0.7, 0.0, 0.3

    constraint_coverage = len(constraints) / max(len(genome), 1)
    constraint_risk = max(0.0, 0.4 - constraint_coverage)  # less coverage -> more risk, capped

    # Weighted combination. Weights are a starting hypothesis, not derived
    # from data yet — see validate_linter.py.
    raw = (w_specificity * specificity_risk) + (w_tool * tool_risk) + (w_constraint * constraint_risk)
    score = round(min(raw, 1.0), 3)

    if score >= 0.6:
        band = "high"
    elif score >= 0.35:
        band = "medium"
    else:
        band = "low"

    return {
        "step": step,
        "risk_score": score,
        "risk_band": band,
        "signals": {
            "specificity_risk": specificity_risk,
            "tool_risk": tool_risk,
            "constraint_risk": round(constraint_risk, 3),
        },
    }
