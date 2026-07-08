"""
Prints the before/after comparison, overall and per difficulty tier.
Run after both baseline_eval.py and finetuned_eval.py.
"""
import json
import os

HERE = os.path.dirname(__file__)


def load_results(name):
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        print(f"Missing {path} -- run the corresponding eval script first.")
        return None
    with open(path) as f:
        return json.load(f)


def main():
    baseline = load_results("baseline_results.json")
    finetuned = load_results("finetuned_results.json")
    if baseline is None or finetuned is None:
        return

    print("=" * 65)
    print(f"{'Tier':<12}{'Baseline (few-shot)':>22}{'Fine-tuned (QLoRA)':>22}{'Delta':>9}")
    print("-" * 65)
    for tier in ["easy", "medium", "hard", "overall"]:
        if tier == "overall":
            b = baseline["overall_accuracy"]
            f = finetuned["overall_accuracy"]
        else:
            b = baseline["tier_accuracy"].get(tier)
            f = finetuned["tier_accuracy"].get(tier)
        if b is None or f is None:
            continue
        delta = f - b
        print(f"{tier:<12}{b:>21.2%} {f:>21.2%} {delta:>+8.2%}")
    print("=" * 65)


if __name__ == "__main__":
    main()
