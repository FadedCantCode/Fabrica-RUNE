"""
validate_linter.py — Checks whether divergence_linter.py's predicted risk
scores actually correlate with measured divergence across real backend runs.

This is the honesty check for the whole project. Run this with real API
keys across enough tasks before claiming the linter predicts anything.

Measured divergence per step, across N backends running the same task:
  - output_length_variance: variance in response length (word count) across
    backends for that step. Cheap proxy, not semantic, but free of any
    embedding dependency.
  - lexical_overlap: average pairwise Jaccard similarity of word sets across
    backend outputs for that step. Higher overlap = lower divergence.

divergence_score = 1 - lexical_overlap  (so higher = more divergent, same
direction as the linter's risk_score, making correlation meaningful)

Usage:
    python validate_linter.py ../examples/research.rune \\
        --tasks "Who is Alan Turing?" "Explain how photosynthesis works" \\
        --backends openai anthropic
"""
import argparse
import itertools
import sys
from statistics import correlation, mean

from dotenv import load_dotenv

from rune_loader import load_rune, RuneValidationError
from runtime import run_agent, BACKEND_REGISTRY
from divergence_linter import lint

load_dotenv()


def jaccard(a: str, b: str) -> float:
    set_a = set(a.lower().split())
    set_b = set(b.lower().split())
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def measure_divergence_for_task(rune, task: str, backend_names: list[str]) -> dict:
    """Run one task across all backends, return per-step divergence scores."""
    per_backend_transcripts = {}

    for name in backend_names:
        backend_cls = BACKEND_REGISTRY[name]
        backend = backend_cls()
        result = run_agent(rune, backend, task)
        per_backend_transcripts[name] = {t["step"]: t["output"] for t in result["transcript"]}

    step_divergence = {}
    for step in rune.genome:
        outputs = [per_backend_transcripts[b][step] for b in backend_names if step in per_backend_transcripts[b]]
        if len(outputs) < 2:
            step_divergence[step] = None
            continue
        pairwise_overlaps = [jaccard(a, b) for a, b in itertools.combinations(outputs, 2)]
        avg_overlap = mean(pairwise_overlaps)
        step_divergence[step] = round(1 - avg_overlap, 3)

    return step_divergence


def validate(rune, tasks: list[str], backend_names: list[str]) -> dict:
    lint_report = lint(rune)
    predicted = {s["step"]: s["risk_score"] for s in lint_report["steps"]}

    measured_per_task = [measure_divergence_for_task(rune, task, backend_names) for task in tasks]

    # Average measured divergence per step across all tasks
    measured_avg = {}
    for step in rune.genome:
        vals = [m[step] for m in measured_per_task if m.get(step) is not None]
        measured_avg[step] = round(mean(vals), 3) if vals else None

    steps_with_data = [s for s in rune.genome if measured_avg[s] is not None]
    pred_series = [predicted[s] for s in steps_with_data]
    measured_series = [measured_avg[s] for s in steps_with_data]

    corr = None
    if len(steps_with_data) >= 2 and len(set(measured_series)) > 1 and len(set(pred_series)) > 1:
        corr = round(correlation(pred_series, measured_series), 3)

    return {
        "species": rune.species,
        "tasks_tested": tasks,
        "backends": backend_names,
        "predicted_risk": predicted,
        "measured_divergence": measured_avg,
        "correlation": corr,
        "interpretation": _interpret(corr, len(steps_with_data)),
    }


def _interpret(corr, n_steps):
    if n_steps < 3:
        return f"Only {n_steps} steps with data — too few to draw a conclusion. Test more genomes/tasks."
    if corr is None:
        return "Could not compute correlation (no variance in one of the series)."
    if corr >= 0.5:
        return f"Positive correlation ({corr}). Linter's structural heuristic shows some predictive signal."
    if corr <= -0.5:
        return f"Negative correlation ({corr}). The heuristic is predicting backwards — the signals or weights in divergence_linter.py need rethinking."
    return f"Weak/no correlation ({corr}). The current heuristic does not meaningfully predict measured divergence; treat risk_score as unvalidated."


def print_report(report: dict):
    print(f"=== Linter Validation: species '{report['species']}' ===")
    print(f"Tasks tested: {len(report['tasks_tested'])}")
    print(f"Backends: {', '.join(report['backends'])}\n")

    print(f"{'Step':<12} {'Predicted':<12} {'Measured':<12}")
    for step in report["predicted_risk"]:
        pred = report["predicted_risk"][step]
        meas = report["measured_divergence"][step]
        meas_str = str(meas) if meas is not None else "N/A"
        print(f"{step:<12} {pred:<12} {meas_str:<12}")

    print(f"\nCorrelation (predicted vs measured): {report['correlation']}")
    print(f"Interpretation: {report['interpretation']}")


def main():
    parser = argparse.ArgumentParser(description="Validate divergence_linter.py predictions against real backend runs.")
    parser.add_argument("rune_path")
    parser.add_argument("--tasks", nargs="+", required=True, help="One or more task prompts to test")
    parser.add_argument("--backends", nargs="+", default=["openai", "anthropic"], choices=BACKEND_REGISTRY.keys())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        rune = load_rune(args.rune_path)
    except RuneValidationError as e:
        print(f"❌ Invalid .rune file: {e}", file=sys.stderr)
        sys.exit(1)

    if len(args.backends) < 2:
        print("❌ Need at least 2 backends to measure divergence.", file=sys.stderr)
        sys.exit(1)

    report = validate(rune, args.tasks, args.backends)

    if args.json:
        import json
        print(json.dumps(report, indent=2))
    else:
        print_report(report)


if __name__ == "__main__":
    main()
