# ruff: noqa: F821 - parser fixture intentionally omits the MCP runtime

@mcp.tool()
def first_tool():
    pass


@mcp.tool(name="second")
def second_tool():
    pass
