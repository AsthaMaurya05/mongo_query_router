#tests/evaluate_router.py
"""Evaluate natural-language routing accuracy using labelled examples."""

import json
import os
from collections import Counter
from datetime import date, datetime

from dotenv import load_dotenv
from groq import Groq

from app.ai.router import QueryRouter
from tests.router_questions import ROUTER_QUESTIONS


from datetime import date, datetime


def normalize(value):
    """Normalize dates and nested values for fair comparison."""
    if isinstance(value, datetime):
        return value.date().isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            key: normalize(item)
            for key, item in sorted(value.items())
        }

    if isinstance(value, list):
        return [normalize(item) for item in value]

    return value


def main():
    load_dotenv()

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is missing from your .env file.")

    router = QueryRouter(client=Groq(api_key=api_key))

    total = len(ROUTER_QUESTIONS)
    if total == 0:
        print("No evaluation questions found.")
        return

    pipeline_correct = 0
    params_correct = 0
    both_correct = 0
    failures = []

    for index, item in enumerate(ROUTER_QUESTIONS, start=1):
        question = item["question"]
        expected_pipeline = item["expected_pipeline"]
        expected_params = normalize(item["expected_params"])

        try:
            result = router.route(question)

            actual_pipeline = result["pipeline"]
            actual_params = normalize(result["params"])

            pipeline_ok = actual_pipeline == expected_pipeline
            params_ok = actual_params == expected_params

            pipeline_correct += pipeline_ok
            params_correct += params_ok
            both_correct += pipeline_ok and params_ok

            print(
                f"[{index:02}/{total:02}] "
                f"pipeline={'PASS' if pipeline_ok else 'FAIL'} "
                f"params={'PASS' if params_ok else 'FAIL'}"
            )

            if not pipeline_ok or not params_ok:
                failures.append({
                    "question": question,
                    "expected_pipeline": expected_pipeline,
                    "actual_pipeline": actual_pipeline,
                    "expected_params": expected_params,
                    "actual_params": actual_params,
                })

        except Exception as exc:
            print(f"[{index:02}/{total:02}] ERROR: {exc}")
            failures.append({
                "question": question,
                "error": str(exc),
            })

    print("\n===== ROUTER EVALUATION =====")
    print(f"Questions:          {total}")
    print(f"Pipeline accuracy:  {pipeline_correct / total:.1%}")
    print(f"Parameter accuracy: {params_correct / total:.1%}")
    print(f"Exact-match rate:   {both_correct / total:.1%}")
    print(f"Failures:           {len(failures)}")

    if failures:
        print("\n===== INCORRECT OR FAILED CASES =====")
        print(json.dumps(failures, indent=2, default=str))


if __name__ == "__main__":
    main()
