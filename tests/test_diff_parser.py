"""Tests for code_reviewer.diff_parser."""
from code_reviewer.diff_parser import format_changes, parse_diff

SAMPLE_DIFF = """\
diff --git a/app.py b/app.py
index 1234567..89abcde 100644
--- a/app.py
+++ b/app.py
@@ -1,5 +1,6 @@
 import os
-old_line = "bye"
+new_line = "hello"
 def main():
-    pass
+    print("hi")
     return
"""

MULTI_FILE_DIFF = """\
diff --git a/app.py b/app.py
index 1111111..2222222 100644
--- a/app.py
+++ b/app.py
@@ -1,3 +1,3 @@
-a = 1
+a = 2
 b = 3
diff --git a/utils.py b/utils.py
index 3333333..4444444 100644
--- a/utils.py
+++ b/utils.py
@@ -10,4 +10,5 @@
 def helper():
-    return None
+    return 42
+    # new tail comment
"""


def test_parse_diff_extracts_added_and_removed():
    result = parse_diff(SAMPLE_DIFF)

    assert result == {
        "app.py": {
            "added": ['new_line = "hello"', '    print("hi")'],
            "removed": ['old_line = "bye"', "    pass"],
        }
    }


def test_parse_diff_multiple_files():
    result = parse_diff(MULTI_FILE_DIFF)

    assert set(result.keys()) == {"app.py", "utils.py"}
    assert result["app.py"]["added"] == ["a = 2"]
    assert result["app.py"]["removed"] == ["a = 1"]
    assert result["utils.py"]["added"] == ["    return 42", "    # new tail comment"]
    assert result["utils.py"]["removed"] == ["    return None"]


def test_format_changes_produces_readable_output():
    changes = parse_diff(SAMPLE_DIFF)
    output = format_changes(changes)

    assert "文件: app.py" in output
    assert "删除的行:" in output
    assert "新增的行:" in output
    assert "- old_line = \"bye\"" in output
    assert "-     pass" in output
    assert "+ new_line = \"hello\"" in output
    assert "+     print(\"hi\")" in output
