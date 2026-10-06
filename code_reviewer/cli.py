"""CLI entrypoint: review a file or a git diff."""
import sys

from code_reviewer.config import ensure_utf8_stdout, load_config


def build_client(config):
    """Build ResilientClient: Zhipu primary, DeepSeek fallback."""
    from code_reviewer.llm.client import DeepSeekChatClient, ResilientClient, ZhipuChatClient
    # websearch disabled: prevents sending reviewed code to external search
    primary = ZhipuChatClient(config.zhipu_api_key, model=config.model,
                              enable_websearch=False)
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
    ensure_utf8_stdout()
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
