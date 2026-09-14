




# tools/web_research.py

from __future__ import annotations

import shutil
import uuid
from typing import Any

from strands.tools.mcp import MCPClient


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_SEARCH_REGION = "in-en"

MAX_SEARCH_RESULTS = 20
DEFAULT_SEARCH_RESULTS = 10

DEFAULT_WEBPAGE_MAX_LENGTH = 10000
MAX_WEBPAGE_LENGTH = 20000


# ============================================================
# COMMAND RESOLUTION
# ============================================================

def _resolve_command(
    command: str,
) -> str:
    """
    Resolve a subprocess command in a cross-platform way.

    Examples:
        uvx
        npx

    On Windows this may resolve to:
        uvx.exe
        npx.cmd
    """

    resolved = shutil.which(
        command
    )

    if resolved:
        return resolved

    # Try common Windows variants explicitly.
    for candidate in (
        f"{command}.exe",
        f"{command}.cmd",
        f"{command}.bat",
    ):
        resolved = shutil.which(
            candidate
        )

        if resolved:
            return resolved

    raise RuntimeError(
        f"Required command '{command}' was not found "
        "on PATH."
    )


# ============================================================
# TOOL RESULT HELPERS
# ============================================================

def _result_value(
    result: Any,
    key: str,
    default=None,
):
    """
    Read a field from either a mapping-like ToolResult or
    attribute-based result object.
    """

    if result is None:
        return default

    if isinstance(
        result,
        dict,
    ):
        return result.get(
            key,
            default,
        )

    try:
        return result[
            key
        ]
    except Exception:
        pass

    return getattr(
        result,
        key,
        default,
    )


def _tool_failed(
    result: Any,
) -> bool:
    """
    Support both current and older Strands MCP result shapes.
    """

    status = str(
        _result_value(
            result,
            "status",
            "",
        )
        or ""
    ).lower()

    is_error = _result_value(
        result,
        "isError",
        False,
    )

    return (
        status == "error"
        or bool(is_error)
    )


def _extract_text_content(
    result: Any,
) -> str:
    """
    Extract all text items from a Strands MCP ToolResult.
    """

    content = _result_value(
        result,
        "content",
        [],
    )

    if not content:
        return ""

    parts = []

    for item in content:

        if isinstance(
            item,
            dict,
        ):
            text = item.get(
                "text"
            )

        else:
            text = getattr(
                item,
                "text",
                None,
            )

        if text:
            parts.append(
                str(text)
            )

    return "\n".join(
        parts
    ).strip()


def _raise_tool_error(
    label: str,
    result: Any,
):
    text = _extract_text_content(
        result
    )

    if text:
        raise RuntimeError(
            f"{label}: {text}"
        )

    raise RuntimeError(
        f"{label}: {result}"
    )


# ============================================================
# DUCKDUCKGO MCP CLIENT
# ============================================================

def create_search_client() -> MCPClient:
    """
    Create the DuckDuckGo MCP client using Strands MCP support.

    Requires:
        uv / uvx

    Server:
        duckduckgo-mcp-server
    """

    uvx_command = _resolve_command(
        "uvx"
    )

    clients = MCPClient.load_servers({
        "duckduckgo": {
            "command":
                uvx_command,

            "args": [
                "--with",
                "duckduckgo-mcp-server[browser]",
                "duckduckgo-mcp-server",
                "--search-backend",
                "auto",
            ],
        }
    })

    if not clients:
        raise RuntimeError(
            "DuckDuckGo MCP client could not be created."
        )

    return clients[0]


# ============================================================
# WEB SEARCH
# ============================================================

def search_web(
    query: str,
    max_results: int = DEFAULT_SEARCH_RESULTS,
    region: str = DEFAULT_SEARCH_REGION,
) -> str:
    """
    Search the public web using DuckDuckGo MCP through the
    Strands MCPClient.

    Returns formatted search-result text containing:
        - titles
        - URLs
        - snippets

    This function is used by PURSUIT's Strands Discovery Agent.
    """

    query = str(
        query or ""
    ).strip()

    if not query:
        raise ValueError(
            "Search query cannot be empty."
        )

    max_results = max(
        1,
        min(
            int(max_results),
            MAX_SEARCH_RESULTS,
        ),
    )

    region = str(
        region
        or DEFAULT_SEARCH_REGION
    ).strip()

    client = create_search_client()

    with client:

        result = client.call_tool_sync(
            tool_use_id=
                str(
                    uuid.uuid4()
                ),

            name=
                "search",

            arguments={
                "query":
                    query,

                "max_results":
                    max_results,

                "region":
                    region,
            },
        )

    if _tool_failed(
        result
    ):
        _raise_tool_error(
            "DuckDuckGo search failed",
            result,
        )

    return _extract_text_content(
        result
    )


# ============================================================
# DEFUDDLE MCP CLIENT
# ============================================================

def create_webpage_client() -> MCPClient:
    """
    Create the Defuddle MCP client through Strands MCP support.

    Requires:
        Node.js
        npm / npx

    Server:
        defuddle-stdio-mcp
    """

    npx_command = _resolve_command(
        "npx"
    )

    clients = MCPClient.load_servers({
        "defuddle": {
            "command":
                npx_command,

            "args": [
                "-y",
                "defuddle-stdio-mcp",
            ],
        }
    })

    if not clients:
        raise RuntimeError(
            "Defuddle MCP client could not be created."
        )

    return clients[0]


# ============================================================
# WEBPAGE FETCH
# ============================================================

def fetch_webpage(
    url: str,
    max_length: int = DEFAULT_WEBPAGE_MAX_LENGTH,
) -> str:
    """
    Fetch and clean one webpage through the Defuddle MCP server.

    This function is used by PURSUIT's Strands Research Agent.
    """

    url = str(
        url or ""
    ).strip()

    if not url:
        raise ValueError(
            "URL is required."
        )

    if not (
        url.startswith(
            "http://"
        )
        or url.startswith(
            "https://"
        )
    ):
        raise ValueError(
            "URL must begin with http:// or https://."
        )

    max_length = max(
        1000,
        min(
            int(max_length),
            MAX_WEBPAGE_LENGTH,
        ),
    )

    client = create_webpage_client()

    with client:

        result = client.call_tool_sync(
            tool_use_id=
                str(
                    uuid.uuid4()
                ),

            name=
                "fetch",

            arguments={
                "url":
                    url,

                "max_length":
                    max_length,
            },
        )

    if _tool_failed(
        result
    ):
        _raise_tool_error(
            "Defuddle webpage fetch failed",
            result,
        )

    return _extract_text_content(
        result
    )


# ============================================================
# DUCKDUCKGO URL EXPANSION
# ============================================================

def expand_search_link(
    token: str,
) -> str:
    """
    Expand a DuckDuckGo ref:// token into its full URL.

    Some DuckDuckGo MCP responses may return reference tokens
    rather than direct URLs.
    """

    token = str(
        token or ""
    ).strip()

    if not token:
        raise ValueError(
            "Search result token is required."
        )

    client = create_search_client()

    with client:

        result = client.call_tool_sync(
            tool_use_id=
                str(
                    uuid.uuid4()
                ),

            name=
                "expand_link",

            arguments={
                "token":
                    token,
            },
        )

    if _tool_failed(
        result
    ):
        _raise_tool_error(
            "DuckDuckGo link expansion failed",
            result,
        )

    return _extract_text_content(
        result
    )


# ============================================================
# HEALTH CHECKS
# ============================================================

def check_search_mcp() -> dict:
    """
    Verify the DuckDuckGo MCP server starts and exposes tools.
    """

    client = create_search_client()

    with client:
        tools = client.list_tools_sync()

    return {
        "service":
            "DuckDuckGo MCP",

        "available":
            bool(
                tools
            ),

        "tools": [
            tool.tool_name
            for tool in tools
        ],
    }


def check_webpage_mcp() -> dict:
    """
    Verify the Defuddle MCP server starts and exposes tools.
    """

    client = create_webpage_client()

    with client:
        tools = client.list_tools_sync()

    return {
        "service":
            "Defuddle MCP",

        "available":
            bool(
                tools
            ),

        "tools": [
            tool.tool_name
            for tool in tools
        ],
    }


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":

    print(
        "Testing PURSUIT web research layer..."
    )

    print(
        "\nDuckDuckGo MCP:"
    )

    print(
        check_search_mcp()
    )

    print(
        "\nDefuddle MCP:"
    )

    print(
        check_webpage_mcp()
    )

    print(
        "\nTesting DuckDuckGo search..."
    )

    results = search_web(
        query=
            "AI data engineering jobs India",

        max_results=
            3,

        region=
            "in-en",
    )

    print(
        "\n--- SEARCH RESULTS ---"
    )

    print(
        results
    )


    