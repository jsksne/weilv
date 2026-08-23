import json
from io import StringIO


def test_chunk_markdown_preserves_section_path_and_source_lines():
    from weilv.markdown_chunks import chunk_markdown

    markdown = """# 学生健康指南

总览。

## 久坐

建议每隔一段时间起身活动。

活动时应量力而行。

**睡眠**

保持规律作息。
"""

    chunks = chunk_markdown(
        markdown,
        source_path="data/processed/source.md",
        min_chars=10,
        max_chars=40,
    )

    assert chunks == [
        {
            "section_path": ["学生健康指南"],
            "content": "总览。",
            "source_locator": "data/processed/source.md:L3-L3",
        },
        {
            "section_path": ["学生健康指南", "久坐"],
            "content": "建议每隔一段时间起身活动。\n\n活动时应量力而行。",
            "source_locator": "data/processed/source.md:L7-L9",
        },
        {
            "section_path": ["学生健康指南", "睡眠"],
            "content": "保持规律作息。",
            "source_locator": "data/processed/source.md:L13-L13",
        },
    ]


def test_chunk_markdown_does_not_split_one_complete_oversized_paragraph():
    from weilv.markdown_chunks import chunk_markdown

    paragraph = "一条必须保持完整的建议，即使它超过当前建议的最大字符数。"

    chunks = chunk_markdown(
        paragraph,
        source_path="source.md",
        min_chars=5,
        max_chars=10,
    )

    assert chunks == [
        {
            "section_path": [],
            "content": paragraph,
            "source_locator": "source.md:L1-L1",
        }
    ]


def test_chunk_markdown_normalizes_non_breaking_spaces_from_converted_documents():
    from weilv.markdown_chunks import chunk_markdown

    chunks = chunk_markdown(
        "# 指南\n\n建议\u00a0起身活动。\n",
        source_path="source.md",
        min_chars=5,
        max_chars=20,
    )

    assert chunks[0]["content"] == "建议 起身活动。"


def test_markdown_chunks_module_prints_jsonl_review_candidates(tmp_path, monkeypatch, capsys):
    from weilv import markdown_chunks

    source = tmp_path / "source.md"
    source.write_text("# 指南\n\n久坐后起身活动。\n", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "markdown_chunks",
            str(source),
            "--min-chars",
            "5",
            "--max-chars",
            "20",
        ],
    )

    markdown_chunks.main()

    candidate = json.loads(capsys.readouterr().out)
    assert candidate == {
        "section_path": ["指南"],
        "content": "久坐后起身活动。",
        "source_locator": f"{source.as_posix()}:L3-L3",
    }


def test_markdown_chunks_module_configures_utf8_stdout(tmp_path, monkeypatch):
    from weilv import markdown_chunks

    class Output(StringIO):
        requested_encoding = None

        def reconfigure(self, *, encoding):
            self.requested_encoding = encoding

    source = tmp_path / "source.md"
    source.write_text("# 指南\n\n久坐后起身活动。\n", encoding="utf-8")
    output = Output()
    monkeypatch.setattr("sys.stdout", output)
    monkeypatch.setattr("sys.argv", ["markdown_chunks", str(source)])

    markdown_chunks.main()

    assert output.requested_encoding == "utf-8"
