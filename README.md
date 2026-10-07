# CodeReviewer

![Tests](https://img.shields.io/badge/tests-47%20passed-brightgreen)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)

AI 代码审查 agent:读取源文件或 git diff → ReAct 循环分析 → 结构化审查报告(Bug / 安全 / 性能 / 风格)。

## 快速开始

```bash
python -m venv .venv
source .venv/Scripts/activate       # Windows Git Bash
pip install -r requirements.txt
cp .env.example .env               # 填入 ZHIPU_API_KEY

# 审查单个文件
python -m code_reviewer review path/to/file.py

# 审查 git diff(管道输入)
git diff | python -m code_reviewer review-diff
```

## 输出示例

```
## 代码审查报告

### 🔴 Critical(必须修复)
- [app.py:42] SQL 查询使用字符串拼接,存在 SQL 注入风险

### 🟡 Warning(建议修复)
- [app.py:18] 循环内执行数据库查询,存在 N+1 问题

### 🔵 Suggestion(可选优化)
- [app.py:5] 函数超过 50 行,建议拆分

### 📊 总结
Bug 风险: 1 | 安全风险: 1 | 性能问题: 1 | 风格建议: 1
```

## 架构

```
输入(文件/diff) → ReAct Agent → read_file/get_file_info → GLM-4(主)/ DeepSeek(兜底) → 审查报告
```

- **ReAct 循环**:感知 → 决策 → 工具调用 → 观察 → 回答
- **容错**:GLM 失败自动切 DeepSeek(ResilientClient)
- **工具**:read_file + get_file_info(安全读取)
- **Diff 解析**:提取 +/- 行,支持多文件和删除文件

## 测试

```bash
python -m pytest -v     # 47 tests, all mock-based (no network)
```

## 技术栈

Python 3.11+ · 智谱 GLM-4 + DeepSeek · zhipuai SDK · pytest

## 设计文档

详见 [DESIGN.md](DESIGN.md)
