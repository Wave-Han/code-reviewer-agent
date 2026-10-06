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
        elif line.startswith("+++"):
            # e.g. "+++ /dev/null" for a deleted file: no target file,
            # subsequent removed lines must not leak into the previous file.
            current_file = None
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
