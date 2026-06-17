"""
divergence_linter.py — Predicts, from a .rune file's structure alone, which
genome steps are likely to produce divergent behavior across different model
backends, before you spend API calls finding out empirically.

This is a heuristic, not a model. It scores each step on three structural
signals that plausibly correlate with cross-backend divergence:

1. Instruction specificity — vague step instructions ("analyze") leave more
   room for different models to take different approaches than narrow ones
   ("call this exact tool with these exact args").
2. Tool ambiguity — steps that reference tools without constraining how to
   use them invite different invocation patterns per backend.
3. Constraint coverage — steps with no constraints applied have no anchor
   pulling different backends toward the same behavior.

The linter's predictions are falsifiable: scores should correlate with
measured divergence from evaluation.py. See validate_linter.py for the
harness that checks this against real runs. Until that validation has been
run with real data, treat the risk score as a hypothesis, not a fact.
"""
import argparse
import json
import sys

from rune_loader import load_rune, RuneValidationError


# --- Structural risk signals -------------------------------------------

# Lower specificity = more interpretive freedom = higher predicted divergence.
# Scored 0.0 (fully constrained) to 1.0 (wide open) based on how much the
# step instruction in runtime.py leaves to model judgment.
STEP_SPECIFICITY = {
    "search":    0.6,   # "describe what you'd search for" — open-ended phrasing
    "analyze":   0.8,   # "reason through key facts" — maximally interpretive
    "summarize": 0.3,   # constrained: fixed length, clear goal
    "code":      0.5,   # open on approach, constrained on output format
    "test":      0.75,  # "verify your code works" has no fixed format models
                         # converge on — some write unit tests, some reason in
                         # prose, some mentally trace execution. That's a wider
                         # behavioral fork than the original 0.55 assumed; closer
                         # to analyze's ambiguity than to code's. Revised
                         # 2026-06-17 after coder.rune scored 0.152 correlation
                         # with the old value — see docs/roadmap.md Stage 1 for
                         # the full reasoning. This is a substantive re-read of
                         # what the instruction demands, not a fit to that one
                         # dataset; re-validate after this change, don't assume
                         # it fixes the result.
}

TOOL_STEPS = {"search"}  # steps in runtime.py that reference a tool


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


def lint(rune) -> dict:
    step_scores = [score_step(step, rune) for step in rune.genome]
    overall = round(sum(s["risk_score"] for s in step_scores) / len(step_scores), 3) if step_scores else 0.0

    return {
        "species": rune.species,
        "genome": rune.genome,
        "overall_risk": overall,
        "steps": step_scores,
        "note": (
            "Structural heuristic, not a measured result. Run validate_linter.py "
            "against real backend executions to check whether these scores "
            "actually predict observed divergence."
        ),
    }


def print_report(report: dict):
    print(f"=== Divergence Risk Lint: species '{report['species']}' ===\n")
    print(f"Overall predicted risk: {report['overall_risk']}\n")
    for s in report["steps"]:
        marker = {"high": "🔴", "medium": "🟡", "low": "🟢"}[s["risk_band"]]
        print(f"{marker} {s['step']:<12} risk={s['risk_score']:<6} ({s['risk_band']})")
        sig = s["signals"]
        print(f"    specificity={sig['specificity_risk']}  tool={sig['tool_risk']}  constraint={sig['constraint_risk']}")
    print(f"\nNote: {report['note']}")


def main():
    parser = argparse.ArgumentParser(
        description="Predict which .rune genome steps are likely to diverge across backends."
    )
    parser.add_argument("rune_path")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        rune = load_rune(args.rune_path)
    except RuneValidationError as e:
        print(f"❌ Invalid .rune file: {e}", file=sys.stderr)
        sys.exit(1)

    report = lint(rune)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)


if __name__ == "__main__":
    main()
