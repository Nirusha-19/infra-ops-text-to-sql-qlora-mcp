"""
Execution-accuracy helpers, shared by baseline_eval.py and finetuned_eval.py.
Instead of comparing generated SQL text to the correct SQL text, this module
executes both queries and compares their actual result sets -- this is how
real text-to-SQL benchmarks (e.g. Spider) are scored.
"""
import sqlite3
import re
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from common import DB_PATH


def extract_sql(text):
    text = text.strip()
    text = re.sub(r"^```(sql)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()
    if ";" in text:
        text = text.split(";")[0] + ";"
    return text.strip()


def run_sql(sql):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        conn.close()
        return sorted(rows)
    except Exception:
        return None


def is_execution_match(predicted_raw_output, gold_sql):
    predicted_sql = extract_sql(predicted_raw_output)
    predicted_result = run_sql(predicted_sql)
    gold_result = run_sql(gold_sql)
    if predicted_result is None:
        return False, predicted_result, gold_result
    return predicted_result == gold_result, predicted_result, gold_result
