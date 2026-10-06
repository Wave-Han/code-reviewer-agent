from code_reviewer.agent.registry import ToolRegistry


def _spec(name="echo"):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": "Echo the given text.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    }


def test_register_and_get():
    reg = ToolRegistry()
    reg.register(_spec(), lambda text: text.upper())
    tool = reg.get("echo")
    assert tool.name == "echo"
    assert tool.spec == _spec()
    assert reg.names() == ["echo"]


def test_to_tools_param_exports_specs_in_registration_order():
    reg = ToolRegistry()
    reg.register(_spec("a"), lambda text: text)
    reg.register(_spec("b"), lambda text: text)
    params = reg.to_tools_param()
    assert [p["function"]["name"] for p in params] == ["a", "b"]


def test_execute_dispatches_arguments_as_kwargs():
    reg = ToolRegistry()
    reg.register(_spec(), lambda text: f"got:{text}")
    assert reg.execute("echo", {"text": "hi"}) == "got:hi"


def test_execute_returns_error_string_when_fn_raises():
    def boom(text):
        raise ValueError("bad input")

    reg = ToolRegistry()
    reg.register(_spec(), boom)
    out = reg.execute("echo", {"text": "x"})
    assert out.startswith("Tool 'echo' failed:")
    assert "bad input" in out


def test_execute_unknown_tool_raises_key_error():
    reg = ToolRegistry()
    raised = False
    try:
        reg.execute("nope", {})
    except KeyError:
        raised = True
    assert raised
