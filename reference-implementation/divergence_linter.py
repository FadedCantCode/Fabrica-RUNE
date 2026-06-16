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
    "test":      0.55,  # open on what counts as a sufficient test
}

TOOL_STEPS = {"search"}  # steps in runtime.py that reference a tool


def score_step(step: str, rune) -> dict:
    """Return a structural divergence-risk score in [0, 1] for one step."""
    specificity_risk = STEP_SPECIFICITY.get(step, 0.7)  # unknown step = treat as risky

    tool_risk = 0.0
    if step in TOOL_STEPS:
        # Risk is lower if the rune declares constraints that narrow tool use,
        # higher if tools are listed with no behavioral anchor.
        tool_risk = 0.5 if not rune.constraints else 0.25

    constraint_coverage = len(rune.constraints) / max(len(rune.genome), 1)
    constraint_risk = max(0.0, 0.4 - constraint_coverage)  # less coverage -> more risk, capped

    # Weighted combination. Weights are a starting hypothesis, not derived
    # from data yet — see validate_linter.py.
    raw = (0.5 * specificity_risk) + (0.3 * tool_risk) + (0.2 * constraint_risk)
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
