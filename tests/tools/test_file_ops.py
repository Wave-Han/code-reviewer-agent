from code_reviewer.tools.file_ops import (
    make_get_file_info_tool,
    make_read_file_tool,
)


def test_read_file_returns_content(tmp_path):
    f = tmp_path / "app.py"
    f.write_text("print('hello')\n", encoding="utf-8")
    tool = make_read_file_tool(base_dir=str(tmp_path))
    assert tool("app.py") == "print('hello')\n"


def test_read_file_missing_returns_not_found(tmp_path):
    tool = make_read_file_tool(base_dir=str(tmp_path))
    assert tool("nope.py") == "File not found: nope.py"


def test_read_file_accepts_absolute_path(tmp_path):
    f = tmp_path / "abs.txt"
    f.write_text("abs content", encoding="utf-8")
    tool = make_read_file_tool()  # default base_dir="."
    assert tool(str(f)) == "abs content"


def test_read_file_truncates_very_large_files(tmp_path):
    f = tmp_path / "big.py"
    f.write_text("x" * 15000, encoding="utf-8")
    tool = make_read_file_tool(base_dir=str(tmp_path))
    out = tool("big.py")
    assert out.startswith("x" * 10000)
    assert out.endswith("\n... (truncated)")


def test_file_info_reports_size_lines_ext(tmp_path):
    f = tmp_path / "app.py"
    # Binary write keeps on-disk size at exactly 6 bytes (no CRLF translation).
    f.write_bytes(b"a\nb\nc\n")
    tool = make_get_file_info_tool(base_dir=str(tmp_path))
    out = tool("app.py")
    assert "path=app.py" in out
    assert "size=6B" in out
    assert "lines=3" in out
    assert "ext=.py" in out


def test_file_info_missing_returns_not_found(tmp_path):
    tool = make_get_file_info_tool(base_dir=str(tmp_path))
    assert tool("ghost.py") == "File not found: ghost.py"
