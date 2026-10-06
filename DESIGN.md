# CodeReviewer — AI 代码审查 Agent

> 输入代码文件或 git diff → agent 用 ReAct 循环分析 → 结构化审查报告(bug/安全/性能/风格)

## 架构(迁移 AgentRadar 模式)

```
输入(文件路径 / diff)→ ReAct Agent → 工具调用(读文件)→ 结构化审查报告
```

## MVP 范围(Phase 1)

| | |
|---|---|
| 输入 | 文件路径(`review <path>`)或 stdin diff(`review-diff`) |
| 审查 | 单 agent · 4 维度(Bug/安全/性能/风格) |
| 工具 | read_file / get_file_info |
| 输出 | 结构化报告(🔴Critical / 🟡Warning / 🔵Suggestion / 📊总结) |
| LLM | GLM-4(主)+ DeepSeek(兜底),复用 ResilientClient 模式 |

## 从 AgentRadar 迁移的

| 模式 | 来源 | 改动 |
|---|---|---|
| ReAct 循环 | `agent/loop.py` | 复制,改 prompt |
| 工具注册表 | `agent/registry.py` | 复制,换工具 |
| LLM 客户端 | `llm/client.py` | 原样复制(GLM+DeepSeek+fallback) |
| 配置 | `config.py` | 复制,换 env 前缀 |
| UTF-8 stdout | `config.py` | 原样复制 |

## 新增的

| 组件 | 说明 |
|---|---|
| `tools/file_ops.py` | read_file / get_file_info |
| `REVIEW_TEMPLATE` | 审查报告输出模板 |
| `SYSTEM_PROMPT` | 代码审查专家(4 维度) |
| `diff_parser.py` | 解析 git diff(提取 +/- 行) |

## 目录结构

```
code_reviewer/
├── code_reviewer/
│   ├── __init__.py
│   ├── cli.py              # 入口(one-shot CLI)
│   ├── config.py
│   ├── diff_parser.py      # git diff 解析
│   ├── agent/
│   │   ├── loop.py         # ReAct(从 AgentRadar 迁移)
│   │   └── registry.py
│   ├── llm/
│   │   └── client.py       # GLM+DeepSeek(原样迁移)
│   └── tools/
│       └── file_ops.py     # 读文件/文件信息
├── tests/
├── requirements.txt
├── .env.example
└── DESIGN.md               # 本文件
```

## Phase 2(未来)

- 多专家路由(bug/security/perf/style 各一个专家)
- Evals(已知 bug 代码集 + 检出率)
- Web UI
- IDE 集成(VS Code extension)

## 使用方式(MVP)

```bash
# 审查单个文件
python -m code_reviewer review path/to/file.py

# 审查 git diff(管道输入)
git diff | python -m code_reviewer review-diff
```
