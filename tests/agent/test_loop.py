from code_reviewer.agent.loop import AgentLoop
from code_reviewer.agent.prompt import SYSTEM_PROMPT
from code_reviewer.agent.registry import ToolRegistry
from code_reviewer.llm.client import ChatResponse, ToolCall


class FakeClient:
    """Scripted ChatClient: returns queued responses, records each call."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[list[dict]] = []

    def chat(self, messages, tools, tool_choice="auto"):
        self.calls.append([dict(m) for m in messages])
        return self._responses.pop(0)


def _read_file_registry(record):
    """Registry with one read_file tool that appends invocations to record."""
    reg = ToolRegistry()
    reg.register({
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the given file.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    }, lambda path: record.append(path) or f"content of {path}")
    return reg


def test_loop_runs_tool_then_answers():
    record = []
    reg = _read_file_registry(record)
    client = FakeClient([
        ChatResponse(tool_calls=[ToolCall(id="1", name="read_file",
                                          arguments={"path": "src/app.py"})],
                     usage={"total_tokens": 10}),
        ChatResponse(content="## 代码审查报告\nok", usage={"total_tokens": 5}),
    ])
    loop = AgentLoop(client, reg, max_iterations=4)
    answer = loop.run("审查 src/app.py")
    assert answer.content.startswith("## 代码审查报告")
    assert answer.tools_used == ["read_file"]
    assert answer.total_tokens == 15
    # Tool was actually executed with the model-supplied arguments
    assert record == ["src/app.py"]
    # Second call feeds the tool result back as a tool message
    msgs = client.calls[1]
    assert msgs[-1]["role"] == "tool"
    assert msgs[-1]["tool_call_id"] == "1"
    assert msgs[-1]["content"] == "content of src/app.py"
    # Assistant turn with the tool call precedes it
    assert msgs[-2]["role"] == "assistant"
    assert msgs[-2]["tool_calls"][0]["function"]["name"] == "read_file"


def test_loop_content_only():
    record = []
    reg = _read_file_registry(record)
    client = FakeClient([ChatResponse(content="没有发现问题")])
    loop = AgentLoop(client, reg, max_iterations=4)
    answer = loop.run("审查 a.py")
    assert answer.content == "没有发现问题"
    assert answer.tools_used == []
    assert record == []
    assert len(client.calls) == 1


def test_loop_caps_at_max_iterations():
    record = []
    reg = _read_file_registry(record)
    # Model never stops asking for the tool
    endless = ChatResponse(tool_calls=[ToolCall(id="x", name="read_file",
                                                arguments={"path": "a.py"})],
                           usage={"total_tokens": 1})
    client = FakeClient([endless, endless, endless])
    loop = AgentLoop(client, reg, max_iterations=3)
    answer = loop.run("审查 a.py")
    assert "达到最大推理轮数" in answer.content
    assert answer.tools_used == ["read_file"] * 3
    assert answer.total_tokens == 3
    # Loop stopped exactly at the cap, no fourth call
    assert len(client.calls) == 3


def test_loop_sends_system_prompt_first():
    record = []
    reg = _read_file_registry(record)
    client = FakeClient([ChatResponse(content="ok")])
    AgentLoop(client, reg).run("hi")
    msgs = client.calls[0]
    assert msgs[0]["role"] == "system"
    assert "CodeReviewer" in msgs[0]["content"]
    assert msgs[0]["content"] == SYSTEM_PROMPT
    assert msgs[1] == {"role": "user", "content": "hi"}
