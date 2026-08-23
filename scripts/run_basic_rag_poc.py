"""Run the Stage 3 Basic RAG POC against existing reviewed indices."""

import argparse
import json
import sys
from pathlib import Path

from elasticsearch import Elasticsearch

from weilv.basic_rag import BasicRagRequest, run_basic_rag
from weilv.retrieval_slice import _env_value, load_api_key


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Weilv Stage 3 Basic RAG POC")
    parser.add_argument("query")
    parser.add_argument(
        "--target-stage",
        choices=["primary_upper", "junior_high", "senior_high"],
        default="junior_high",
    )
    parser.add_argument(
        "--current-context",
        choices=["home", "school", "study_space", "commute", "bedroom", "outdoor", "unknown"],
        default="home",
    )
    parser.add_argument("--available-minutes", type=int)
    parser.add_argument(
        "--activity-context",
        choices=["reading", "writing", "screen", "other", "unknown"],
        default="unknown",
    )
    parser.add_argument("--vision-abnormal", action="store_true")
    parser.add_argument("--physical-discomfort", action="store_true")
    parser.add_argument("--medical-request", action="store_true")
    parser.add_argument("--cannot-move", action="store_true")
    parser.add_argument("--unstable-environment", action="store_true")
    parser.add_argument("--sleep-being-crowded", action="store_true")
    return parser


def build_request(args: argparse.Namespace) -> BasicRagRequest:
    return BasicRagRequest(
        query=args.query,
        target_stage=args.target_stage,
        current_context=args.current_context,
        available_minutes=args.available_minutes,
        activity_context=args.activity_context,
        vision_abnormal=args.vision_abnormal,
        physical_discomfort=args.physical_discomfort,
        medical_request=args.medical_request,
        cannot_move=args.cannot_move,
        unstable_environment=args.unstable_environment,
        sleep_being_crowded=args.sleep_being_crowded,
    )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = build_parser().parse_args()

    env_file = Path(".env")
    api_key = load_api_key(env_file)
    es_url = _env_value("ELASTICSEARCH_URL", env_file) or "http://127.0.0.1:9200"
    request = build_request(args)

    client = Elasticsearch(es_url, request_timeout=30)
    try:
        if not client.ping():
            raise RuntimeError(f"Elasticsearch is not reachable: {es_url}")
        result = run_basic_rag(request, client, api_key)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        client.close()


if __name__ == "__main__":
    main()
