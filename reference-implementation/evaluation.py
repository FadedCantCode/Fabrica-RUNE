"""
evaluation.py — Runs the same .rune spec across multiple backends and reports
how similar their behavior was.

This is intentionally simple: it checks genome-step coverage (did every backend
actually produce non-empty output for every declared step?) and rough output
length parity. It does NOT compute semantic similarity yet — see docs/roadmap.md
Stage 1 for the planned embedding-based comparison. Don't oversell what this
script proves: it shows the steps ran, not that the *meaning* was identical.

Usage:
    python evaluation.py ../examples/research.rune --task "Who is Alan Turing?" \\
        --backends openai anthropic ollama
"""
import argparse
import json
import sys

from dotenv import load_dotenv

from rune_loader import load_rune, RuneValidationError
from runtime import run_agent, BACKEND_REGISTRY

load_dotenv()


def compare(rune, task: str, backend_names: list[str]) -> dict:
    results = {}
    errors = {}

    for name in backend_names:
        backend_cls = BACKEND_REGISTRY[name]
        try:
            backend = backend_cls()
            results[name] = run_agent(rune, backend, task)
        except Exception as e:
            errors[name] = str(e)

    report = {
        "species": rune.species,
        "task": task,
        "genome": rune.genome,
        "backends_attempted": backend_names,
        "backends_succeeded": list(results.keys()),
        "backends_failed": errors,
        "step_coverage": {},
        "final_answers": {},
    }

    for name, result in results.items():
        steps_with_output = [t["step"] for t in result["transcript"] if t["output"].strip()]
        report["step_coverage"][name] = {
            "expected": rune.genome,
            "completed": steps_with_output,
            "full_coverage": steps_with_output == rune.genome,
        }
        report["final_answers"][name] = result["final_answer"]

    return report


def print_report(report: dict):
    print(f"=== Cross-backend comparison: species '{report['species']}' ===")
    print(f"Task: {report['task']}")
    print(f"Genome: {' -> '.join(report['genome'])}\n")

    if report["backends_failed"]:
        print("⚠️  Backends that failed to run:")
        for name, err in report["backends_failed"].items():
            print(f"   - {name}: {err}")
        print()

    print("Step coverage (did each backend complete every declared step?):")
    for name, cov in report["step_coverage"].items():
        mark = "✅" if cov["full_coverage"] else "⚠️ "
        print(f"  {mark} {name}: {' -> '.join(cov['completed'])}")
    print()

    print("Final answers side by side:")
    for name, answer in report["final_answers"].items():
        print(f"\n--- {name} ---")
        print(answer)


def main():
    parser = argparse.ArgumentParser(description="Compare a .rune agent's behavior across backends.")
    parser.add_argument("rune_path", help="Path to a .rune file")
    parser.add_argument("--task", required=True)
    parser.add_argument("--backends", nargs="+", default=["openai", "anthropic", "ollama"],
                         choices=BACKEND_REGISTRY.keys())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        rune = load_rune(args.rune_path)
    except RuneValidationError as e:
        print(f"❌ Invalid .rune file: {e}", file=sys.stderr)
        sys.exit(1)

    report = compare(rune, args.task, args.backends)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)


if __name__ == "__main__":
    main()
