"""
Evaluates the FINE-TUNED model (base + LoRA adapter), zero-shot, reported
both overall and per difficulty tier.
"""
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from common import SYSTEM_PROMPT, MODEL_NAME, ADAPTER_PATH
from eval_utils import is_execution_match

from mlx_lm import load, generate


def build_messages(question):
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]


def main():
    print(f"Loading fine-tuned model: {MODEL_NAME} + adapter at {ADAPTER_PATH}")
    model, tokenizer = load(MODEL_NAME, adapter_path=ADAPTER_PATH)

    test_path = os.path.join(os.path.dirname(__file__), "..", "data", "held_out_eval.jsonl")
    with open(test_path) as f:
        test_examples = [json.loads(line) for line in f]

    tier_correct = defaultdict(int)
    tier_total = defaultdict(int)
    results = []

    for i, ex in enumerate(test_examples):
        messages = build_messages(ex["question"])
        prompt = tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
        output = generate(model, tokenizer, prompt=prompt, max_tokens=150, verbose=False)
        match, pred_result, gold_result = is_execution_match(output, ex["sql"])
        tier = ex.get("tier", "unknown")
        tier_total[tier] += 1
        tier_correct[tier] += int(match)
        results.append({"question": ex["question"], "gold_sql": ex["sql"], "tier": tier,
                         "predicted_raw": output, "match": match})
        print(f"[{i + 1}/{len(test_examples)}] tier={tier} match={match}  Q: {ex['question']}")

    total_correct = sum(tier_correct.values())
    total = sum(tier_total.values())
    overall_accuracy = total_correct / total

    print(f"\n{'='*50}")
    print("Fine-tuned (QLoRA, zero-shot) execution accuracy")
    print(f"{'='*50}")
    for tier in ["easy", "medium", "hard"]:
        if tier_total[tier] > 0:
            acc = tier_correct[tier] / tier_total[tier]
            print(f"  {tier:8s}: {acc:6.2%}  ({tier_correct[tier]}/{tier_total[tier]})")
    print(f"  {'overall':8s}: {overall_accuracy:6.2%}  ({total_correct}/{total})")

    out_path = os.path.join(os.path.dirname(__file__), "finetuned_results.json")
    with open(out_path, "w") as f:
        json.dump({
            "overall_accuracy": overall_accuracy,
            "tier_accuracy": {t: (tier_correct[t] / tier_total[t] if tier_total[t] else None) for t in tier_total},
            "results": results,
        }, f, indent=2)
    print(f"\nSaved detailed results to {out_path}")


if __name__ == "__main__":
    main()
