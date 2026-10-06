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
