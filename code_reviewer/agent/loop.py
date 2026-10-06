"""Self-built ReAct loop: think -> call tools -> observe -> repeat -> answer."""
import json
from dataclasses import dataclass, field

from code_reviewer.agent.prompt import SYSTEM_PROMPT
from code_reviewer.agent.registry import ToolRegistry
from code_reviewer.llm.client import ChatClient


@dataclass
class Answer:
    content: str
    tools_used: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    total_tokens: int = 0


def _assistant_message(content, tool_calls) -> dict:
    msg: dict = {"role": "assistant"}
    if content:
        msg["content"] = content
    if tool_calls:
        msg["tool_calls"] = [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.name,
                          "arguments": json.dumps(tc.arguments, ensure_ascii=False)}}
            for tc in tool_calls
        ]
    return msg


class AgentLoop:
    def __init__(self, client: ChatClient, registry: ToolRegistry,
                 max_iterations: int = 8, system_prompt: str = SYSTEM_PROMPT):
        self._client = client
        self._registry = registry
        self._max = max_iterations
        self._system_prompt = system_prompt

    def run(self, user_message: str, history: list[dict] | None = None) -> Answer:
        messages: list[dict] = [{"role": "system", "content": self._system_prompt}]
        messages.extend(history or [])
        messages.append({"role": "user", "content": user_message})
        tools_used: list[str] = []
        total_tokens = 0

        for _ in range(self._max):
            resp = self._client.chat(messages, self._registry.to_tools_param())
            total_tokens += (resp.usage or {}).get("total_tokens", 0)
            messages.append(_assistant_message(resp.content, resp.tool_calls))
            if not resp.tool_calls:
                return Answer(content=resp.content or "", tools_used=tools_used,
                              total_tokens=total_tokens)
            for tc in resp.tool_calls:
                tools_used.append(tc.name)
                result = self._registry.execute(tc.name, tc.arguments)
                messages.append({
                    "role": "tool", "tool_call_id": tc.id, "content": result,
                })

        return Answer(
            content="(达到最大推理轮数,请缩小问题范围后重试。)",
            tools_used=tools_used,
            total_tokens=total_tokens,
        )

    def run_stream(self, user_message: str, history: list[dict] | None = None):
        """Streaming variant of run(): yields delta/tool/done/error events."""
        messages: list[dict] = [{"role": "system", "content": self._system_prompt}]
        messages.extend(history or [])
        messages.append({"role": "user", "content": user_message})
        tools_used: list[str] = []

        for _ in range(self._max):
            content_parts: list[str] = []
            tool_calls = None
            for event in self._client.stream(messages, self._registry.to_tools_param()):
                if event["type"] == "delta":
                    content_parts.append(event["content"])
                    yield event
                elif event["type"] == "tool_calls":
                    tool_calls = event["tool_calls"]
            assistant: dict = {"role": "assistant"}
            if content_parts:
                assistant["content"] = "".join(content_parts)
            if tool_calls:
                assistant["tool_calls"] = [
                    {"id": tc["id"], "type": "function",
                     "function": {"name": tc["name"],
                                  "arguments": json.dumps(tc["arguments"], ensure_ascii=False)}}
                    for tc in tool_calls
                ]
            messages.append(assistant)
            if not tool_calls:
                yield {"type": "done", "tools_used": tools_used}
                return
            for tc in tool_calls:
                tools_used.append(tc["name"])
                yield {"type": "tool", "name": tc["name"]}
                result = self._registry.execute(tc["name"], tc["arguments"])
                messages.append({
                    "role": "tool", "tool_call_id": tc["id"], "content": result,
                })

        yield {"type": "error", "message": "达到最大推理轮数,请缩小问题范围后重试。"}
