"""Integration tests: agent loop + real file tools + scripted client, CLI wiring.

No real network calls: the LLM client is faked, everything else (registry,
file tools, diff parser, agent loop, CLI plumbing) runs for real.
"""
import io
import sys

import pytest

from code_reviewer.agent.loop import AgentLoop
from code_reviewer.agent.registry import ToolRegistry
from code_reviewer.cli import build_registry, main, review_diff, review_file
from code_reviewer.config import Config
from code_reviewer.llm.client import ChatResponse, ToolCall
from code_reviewer.tools.file_ops import (
    GET_FILE_INFO_SPEC,
    READ_FILE_SPEC,
    make_get_file_info_tool,
    make_read_file_tool,
)


class FakeClient:
    """Scripted ChatClient: returns queued responses, records every call."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def chat(self, messages, tools, tool_choice="auto"):
        self.calls.append([dict(m) for m in messages])
        return self._responses.pop(0)


def _registry(base_dir: str) -> ToolRegistry:
    """Real registry with real file tools rooted at base_dir."""
    reg = ToolRegistry()
    reg.register(READ_FILE_SPEC, make_read_file_tool(base_dir))
    reg.register(GET_FILE_INFO_SPEC, make_get_file_info_tool(base_dir))
    return reg


def test_agent_reads_real_file_and_answers(tmp_path):
    """End to end: scripted model asks for read_file, the real tool reads a
    real file on disk, the result flows back, and the agent returns an answer."""
    src = tmp_path / "calc.py"
    src.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    client = FakeClient([
        ChatResponse(tool_calls=[
            ToolCall(id="t1", name="read_file", arguments={"path": "calc.py"}),
        ]),
        ChatResponse(content="## 代码审查报告\n函数实现正确。", usage={"total_tokens": 7}),
    ])
    agent = AgentLoop(client, _registry(str(tmp_path)))
    answer = agent.run("请审查文件 calc.py 的代码质量")

    assert answer.content.startswith("## 代码审查报告")
    assert answer.tools_used == ["read_file"]
    assert len(client.calls) == 2
    # The tool observation sent back to the model is the real file content.
    tool_msg = client.calls[1][-1]
    assert tool_msg["role"] == "tool"
    assert tool_msg["tool_call_id"] == "t1"
    assert "return a + b" in tool_msg["content"]


def test_agent_chains_file_tools(tmp_path):
    """Model may call both registered file tools in one turn before answering."""
    src = tmp_path / "mod.py"
    src.write_text("x = 1\n", encoding="utf-8")

    client = FakeClient([
        ChatResponse(tool_calls=[
            ToolCall(id="a", name="get_file_info", arguments={"path": "mod.py"}),
            ToolCall(id="b", name="read_file", arguments={"path": "mod.py"}),
        ]),
        ChatResponse(content="done"),
    ])
    agent = AgentLoop(client, _registry(str(tmp_path)))
    answer = agent.run("检查 mod.py")

    assert answer.tools_used == ["get_file_info", "read_file"]
    assert answer.content == "done"
    tool_msgs = [m for m in client.calls[1] if m["role"] == "tool"]
    assert len(tool_msgs) == 2
    assert "lines=1" in tool_msgs[0]["content"]
    assert tool_msgs[1]["content"] == "x = 1\n"


def test_build_registry_registers_both_file_tools():
    reg = build_registry()
    assert reg.names() == ["read_file", "get_file_info"]
    assert reg.get("read_file").fn.__name__ == "run"


def test_review_file_pipeline(tmp_path, monkeypatch, capsys):
    """CLI review_file with a faked LLM but the real registry/tools/loop."""
    src = tmp_path / "mod.py"
    src.write_text("value = 42\n", encoding="utf-8")

    client = FakeClient([
        ChatResponse(tool_calls=[
            ToolCall(id="t1", name="read_file", arguments={"path": str(src)}),
        ]),
        ChatResponse(content="mock 审查意见"),
    ])
    monkeypatch.setattr("code_reviewer.cli.load_config",
                        lambda: Config(zhipu_api_key="test-key"))
    monkeypatch.setattr("code_reviewer.cli.build_client", lambda config: client)

    review_file(str(src))

    out = capsys.readouterr().out
    assert "mock 审查意见" in out
    assert "(使用工具: read_file)" in out
    # The question names the file; the real tool read it for the model.
    user_msg = client.calls[0][1]
    assert user_msg["role"] == "user"
    assert str(src) in user_msg["content"]
    assert "value = 42" in client.calls[1][-1]["content"]


def test_review_diff_pipeline(monkeypatch, capsys):
    """CLI review_diff: stdin diff -> parse -> format -> agent -> printed answer."""
    diff_text = (
        "diff --git a/app.py b/app.py\n"
        "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
    )
    client = FakeClient([ChatResponse(content="mock diff 审查意见")])
    monkeypatch.setattr("code_reviewer.cli.load_config",
                        lambda: Config(zhipu_api_key="test-key"))
    monkeypatch.setattr("code_reviewer.cli.build_client", lambda config: client)
    monkeypatch.setattr("sys.stdin", io.StringIO(diff_text))

    review_diff()

    out = capsys.readouterr().out
    assert "mock diff 审查意见" in out
    # The formatted changes reached the model as part of the question.
    question = client.calls[0][1]["content"]
    assert "文件: app.py" in question
    assert "+ x = 2" in question
    assert "- x = 1" in question


def test_review_diff_empty_stdin_exits(monkeypatch):
    monkeypatch.setattr("code_reviewer.cli.load_config",
                        lambda: Config(zhipu_api_key="test-key"))
    monkeypatch.setattr("code_reviewer.cli.build_client", lambda config: None)
    monkeypatch.setattr("sys.stdin", io.StringIO("   \n"))

    with pytest.raises(SystemExit) as exc:
        review_diff()
    assert "未检测到 diff 内容" in str(exc.value)


def test_review_file_missing_api_key_exits(tmp_path, monkeypatch):
    monkeypatch.setattr("code_reviewer.cli.load_config",
                        lambda: Config(zhipu_api_key=""))
    with pytest.raises(SystemExit) as exc:
        review_file("whatever.py")
    assert "ZHIPU_API_KEY" in str(exc.value)


def test_main_no_args_shows_usage(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["code_reviewer"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "用法" in out
    assert "review-diff" in out


def test_main_unknown_command_shows_usage(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["code_reviewer", "bogus"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    assert "用法" in capsys.readouterr().out


def test_main_dispatches_review(tmp_path, monkeypatch, capsys):
    """main() wires argv through to review_file."""
    src = tmp_path / "x.py"
    src.write_text("a = 1\n", encoding="utf-8")
    seen = {}

    def fake_review_file(path):
        seen["path"] = path

    monkeypatch.setattr(sys, "argv", ["code_reviewer", "review", str(src)])
    monkeypatch.setattr("code_reviewer.cli.review_file", fake_review_file)
    main()
    assert seen["path"] == str(src)
