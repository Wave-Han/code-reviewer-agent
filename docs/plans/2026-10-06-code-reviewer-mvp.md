# CodeReviewer MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a code review agent that reads a source file or git diff and produces a structured review report (bugs/security/performance/style).

**Architecture:** Single ReAct agent with 3 file-reading tools. GLM-4 primary + DeepSeek fallback via ResilientClient. CLI one-shot + REPL.

**Tech Stack:** Python 3.11+, zhipuai SDK, requests, python-dotenv, pytest.

## Global Constraints

- Python 3.11+; no new dependencies beyond requirements.txt.
- This is a NEW project — copy patterns from AgentRadar conceptually, but do NOT import from agent_radar package.
- Env prefix: `CR_` (e.g., `CR_ZHIPU_API_KEY`, `CR_DB_PATH` is not needed — no DB).
- Code identifiers/comments in English; user-facing strings in Chinese.
- TDD: failing test first → minimal impl → green → commit.
- All tests mock — no real LLM/network calls in tests.

---

## Task 1: Config + LLM Client

**Files:**
- Create: `code_reviewer/config.py`
- Create: `code_reviewer/llm/client.py`
- Test: `tests/test_config.py`, `tests/llm/test_client.py`

**Interfaces:**
- Produces: `Config` dataclass with `zhipu_api_key`, `deepseek_api_key`, `deepseek_model`, `model`. `load_config(env_file=".env") -> Config`. `ensure_utf8_stdout()`.
- Produces: `ToolCall(id,name,arguments)`, `ChatResponse(content,tool_calls,raw,usage)`, `ChatClient` protocol, `ZhipuChatClient(api_key,model)`, `DeepSeekChatClient(api_key,model)`, `ResilientClient(primary,fallback,on_switch)`.

- [ ] **Step 1:** Write `code_reviewer/config.py`

```python
"""Configuration loaded from environment / .env."""
import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv


def ensure_utf8_stdout() -> None:
    """Reconfigure stdout to UTF-8 (Windows GBK console fix)."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


@dataclass
class Config:
    zhipu_api_key: str
    model: str = "glm-4"
    deepseek_api_key: str | None = None
    deepseek_model: str = "deepseek-chat"


def load_config(env_file: str = ".env") -> Config:
    load_dotenv(env_file)
    return Config(
        zhipu_api_key=os.environ.get("ZHIPU_API_KEY", ""),
        model=os.environ.get("CR_MODEL", "glm-4"),
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY") or None,
        deepseek_model=os.environ.get("CR_DEEPSEEK_MODEL", "deepseek-chat"),
    )
```

- [ ] **Step 2:** Write `code_reviewer/llm/client.py` — copy the full content from AgentRadar's `agent_radar/llm/client.py` at `D:\develop-project\dr-project\ai_test\ai_agent\agent_radar\llm\client.py`, but:
  - Change `from agent_radar.config import ...` to no config import (not needed)
  - Remove `ZhipuEmbeddingClient` and `cosine_similarity` (not needed for MVP)
  - Keep: ToolCall, ChatResponse (with content=None default), ChatClient protocol, _parse_tool_calls, ZhipuChatClient, _parse_dict_tool_calls, DeepSeekChatClient, ResilientClient
  - Keep the `stream()` methods on all three clients

- [ ] **Step 3:** Write tests

```python
# tests/test_config.py
from code_reviewer.config import load_config, ensure_utf8_stdout


def test_load_config_reads_env(monkeypatch):
    monkeypatch.setenv("ZHIPU_API_KEY", "k")
    cfg = load_config(env_file="/does/not/exist")
    assert cfg.zhipu_api_key == "k"
    assert cfg.model == "glm-4"


def test_load_config_deepseek(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds")
    cfg = load_config(env_file="/does/not/exist")
    assert cfg.deepseek_api_key == "ds"
```

- [ ] **Step 4:** Run `venv/Scripts/python -m pytest tests/ -v` → pass
- [ ] **Step 5:** `git add -A && git commit -m "feat: config + LLM client (GLM/DeepSeek/Resilient)"`

---

## Task 2: Tool Registry + File Tools

**Files:**
- Create: `code_reviewer/agent/registry.py`
- Create: `code_reviewer/tools/file_ops.py`
- Test: `tests/agent/test_registry.py`, `tests/tools/test_file_ops.py`

- [ ] **Step 1:** Write `code_reviewer/agent/registry.py` — identical structure to AgentRadar's `agent_radar/agent/registry.py` (ToolRegistry with register/get/to_tools_param/execute/names).

- [ ] **Step 2:** Write `code_reviewer/tools/file_ops.py`

```python
"""File operation tools for code review."""
import os

READ_FILE_SPEC = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read the content of a source code file.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to read."}
            },
            "required": ["path"],
        },
    },
}

GET_FILE_INFO_SPEC = {
    "type": "function",
    "function": {
        "name": "get_file_info",
        "description": "Get file metadata (size, lines, extension).",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file."}
            },
            "required": ["path"],
        },
    },
}


def make_read_file_tool(base_dir: str = "."):
    def run(path: str) -> str:
        full = os.path.join(base_dir, path) if not os.path.isabs(path) else path
        if not os.path.exists(full):
            return f"File not found: {path}"
        try:
            with open(full, encoding="utf-8", errors="replace") as f:
                content = f.read()
            # Truncate very large files
            if len(content) > 10000:
                return content[:10000] + "\n... (truncated)"
            return content
        except Exception as e:
            return f"Error reading {path}: {e}"
    return run


def make_get_file_info_tool(base_dir: str = "."):
    def run(path: str) -> str:
        full = os.path.join(base_dir, path) if not os.path.isabs(path) else path
        if not os.path.exists(full):
            return f"File not found: {path}"
        stat = os.stat(full)
        with open(full, encoding="utf-8", errors="replace") as f:
            lines = sum(1 for _ in f)
        return (f"path={path}, size={stat.st_size}B, lines={lines}, "
                f"ext={os.path.splitext(path)[1]}")
    return run
```

- [ ] **Step 3:** Write tests (test read_file with tmp files, test file_info, test missing file)
- [ ] **Step 4:** Run tests → pass
- [ ] **Step 5:** Commit

---

## Task 3: Agent Loop + System Prompt + Review Template

**Files:**
- Create: `code_reviewer/agent/loop.py`
- Create: `code_reviewer/agent/prompt.py`
- Test: `tests/agent/test_loop.py`

- [ ] **Step 1:** Write `code_reviewer/agent/prompt.py`

```python
"""System prompt and review output template for the code reviewer."""

REVIEW_TEMPLATE = """## 代码审查报告

### 🔴 Critical(必须修复)
- (列出严重 bug / 安全漏洞,含文件:行号)

### 🟡 Warning(建议修复)
- (列出性能问题 / 潜在 bug,含文件:行号)

### 🔵 Suggestion(可选优化)
- (列出风格建议 / 代码改进,含文件:行号)

### 📊 总结
- Bug 风险: N 个 | 安全风险: N 个 | 性能问题: N 个 | 风格建议: N 个
"""

SYSTEM_PROMPT = f"""你是一个专业的代码审查专家(CodeReviewer),负责分析代码质量。

审查维度:
1. **Bug 检测**:逻辑错误、边界条件、空指针、资源泄漏
2. **安全漏洞**:SQL 注入、XSS、硬编码密钥、不安全加密
3. **性能问题**:N+1 查询、不必要循环、内存浪费
4. **代码风格**:命名规范、代码重复、过长函数、缺少注释

工作方式:
1. 用 read_file 读取指定文件
2. 可用 get_file_info 了解文件基本信息
3. 仔细分析每个维度
4. 按下面的模板输出审查报告:

{REVIEW_TEMPLATE}

注意:
- 只报告真实问题,不要凑数
- 每个问题标注文件名和大致行号
- 用简体中文
"""
```

- [ ] **Step 2:** Write `code_reviewer/agent/loop.py` — copy AgentLoop from AgentRadar's `agent_radar/agent/loop.py`, importing SYSTEM_PROMPT from `code_reviewer.agent.prompt` instead.

- [ ] **Step 3:** Write tests (test loop runs tool then answers, test max iterations, test system prompt is sent)
- [ ] **Step 4:** Run tests → pass
- [ ] **Step 5:** Commit

---

## Task 4: Diff Parser

**Files:**
- Create: `code_reviewer/diff_parser.py`
- Test: `tests/test_diff_parser.py`

- [ ] **Step 1:** Write `code_reviewer/diff_parser.py`

```python
"""Parse unified git diff to extract added/removed lines per file."""
import re

def parse_diff(diff_text: str) -> dict[str, dict]:
    """Parse a unified diff, returning {file: {"added": [...], "removed": [...]}} ."""
    result = {}
    current_file = None
    for line in diff_text.splitlines():
        match = re.match(r"^\+\+\+ b/(.+)$", line)
        if match:
            current_file = match.group(1)
            result[current_file] = {"added": [], "removed": []}
            continue
        if current_file is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            result[current_file]["added"].append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            result[current_file]["removed"].append(line[1:])
    return result


def format_changes(changes: dict) -> str:
    """Format parsed diff into a readable prompt block."""
    parts = []
    for file, data in changes.items():
        parts.append(f"文件: {file}")
        if data["removed"]:
            parts.append("删除的行:")
            for line in data["removed"]:
                parts.append(f"  - {line}")
        if data["added"]:
            parts.append("新增的行:")
            for line in data["added"]:
                parts.append(f"  + {line}")
        parts.append("")
    return "\n".join(parts)
```

- [ ] **Step 2:** Write tests (parse sample diff, verify added/removed extraction)
- [ ] **Step 3:** Run tests → pass
- [ ] **Step 4:** Commit

---

## Task 5: CLI + Integration

**Files:**
- Create: `code_reviewer/cli.py`
- Test: `tests/test_integration.py`

- [ ] **Step 1:** Write `code_reviewer/cli.py`

```python
"""CLI entrypoint: review a file or a git diff."""
import sys

from code_reviewer.config import ensure_utf8_stdout, load_config


def build_client(config):
    """Build ResilientClient: Zhipu primary, DeepSeek fallback."""
    from code_reviewer.llm.client import DeepSeekChatClient, ResilientClient, ZhipuChatClient
    primary = ZhipuChatClient(config.zhipu_api_key, model=config.model)
    if config.deepseek_api_key:
        fallback = DeepSeekChatClient(config.deepseek_api_key, model=config.deepseek_model)
        return ResilientClient(primary, fallback,
                               on_switch=lambda: print("⚠️ GLM 不可用,已切换到 DeepSeek"))
    return primary


def build_registry():
    from code_reviewer.agent.registry import ToolRegistry
    from code_reviewer.tools.file_ops import (
        GET_FILE_INFO_SPEC, READ_FILE_SPEC,
        make_get_file_info_tool, make_read_file_tool,
    )
    reg = ToolRegistry()
    reg.register(READ_FILE_SPEC, make_read_file_tool())
    reg.register(GET_FILE_INFO_SPEC, make_get_file_info_tool())
    return reg


def review_file(path: str):
    """One-shot: review a single file."""
    from code_reviewer.agent.loop import AgentLoop
    ensure_utf8_stdout()
    config = load_config()
    if not config.zhipu_api_key:
        raise SystemExit("缺少 ZHIPU_API_KEY,请在 .env 中配置。")
    client = build_client(config)
    registry = build_registry()
    agent = AgentLoop(client, registry)
    question = f"请审查文件 {path} 的代码质量,使用 read_file 工具读取后分析。"
    ans = agent.run(question)
    print(ans.content)
    if ans.tools_used:
        print(f"\n(使用工具: {', '.join(ans.tools_used)})")


def review_diff():
    """Read diff from stdin and review."""
    from code_reviewer.agent.loop import AgentLoop
    from code_reviewer.diff_parser import format_changes, parse_diff
    ensure_utf8_stdout()
    config = load_config()
    if not config.zhipu_api_key:
        raise SystemExit("缺少 ZHIPU_API_KEY,请在 .env 中配置。")
    diff_text = sys.stdin.read()
    if not diff_text.strip():
        raise SystemExit("未检测到 diff 内容。")
    changes = parse_diff(diff_text)
    formatted = format_changes(changes)
    client = build_client(config)
    registry = build_registry()
    agent = AgentLoop(client, registry)
    ans = agent.run(f"请审查以下代码变更:\n\n{formatted}")
    print(ans.content)


def main():
    if len(sys.argv) < 2:
        print("用法: python -m code_reviewer review <file>")
        print("      git diff | python -m code_reviewer review-diff")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "review" and len(sys.argv) > 2:
        review_file(sys.argv[2])
    elif cmd == "review-diff":
        review_diff()
    else:
        print("用法: python -m code_reviewer review <file>")
        print("      git diff | python -m code_reviewer review-diff")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2:** Write integration test (mock client, verify agent runs with file tool)
- [ ] **Step 3:** Run full suite → all pass
- [ ] **Step 4:** Commit
- [ ] **Step 5:** Create `code_reviewer/__main__.py`:

```python
from code_reviewer.cli import main
main()
```

---

## Definition of Done

- `python -m pytest -v` fully green; no real network calls.
- `python -m code_reviewer review <file>` works with real LLM (manual smoke).
- `git diff | python -m code_reviewer review-diff` works (manual smoke).
