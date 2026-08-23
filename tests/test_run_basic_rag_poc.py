from scripts.run_basic_rag_poc import build_parser, build_request


def test_activity_context_cli_defaults_to_unknown():
    args = build_parser().parse_args(["query"])

    assert args.activity_context == "unknown"
    assert build_request(args).activity_context == "unknown"


def test_activity_context_cli_accepts_all_frozen_values():
    for value in ("reading", "writing", "screen", "other", "unknown"):
        args = build_parser().parse_args(["query", "--activity-context", value])

        assert build_request(args).activity_context == value
