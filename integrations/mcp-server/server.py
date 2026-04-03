import httpx
from mcp.server.fastmcp import FastMCP

from compile_settings import (
    build_compile_body,
    build_compile_headers,
    resolve_api_key,
    resolve_compile_post_url,
    resolve_prompt_mode,
)

# Initialize FastMCP server
mcp = FastMCP("myCompiler")


@mcp.tool()
async def optimize_prompt(text: str) -> str:
    """
    Optimize a prompt using the myCompiler API.

    Args:
        text: The raw prompt text to optimize.
    """
    url = resolve_compile_post_url()
    mode = resolve_prompt_mode()
    headers = build_compile_headers(mode, resolve_api_key())
    payload = build_compile_body(text, mode)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers, timeout=30.0)
            response.raise_for_status()
            data = response.json()

            # Prefer V2 expanded prompt, fallback to V1
            result = data.get("expanded_prompt_v2") or data.get("expanded_prompt")
            if not result:
                return "Error: API returned success but no optimized prompt found in response."
            return result

        except httpx.RequestError as e:
            return f"Error: Failed to connect to myCompiler API at {url}. Is the server running? Details: {e}"
        except httpx.HTTPStatusError as e:
            return (
                f"Error: API returned status {e.response.status_code}. Details: {e.response.text}"
            )
        except Exception as e:
            return f"Error: Unexpected error during optimization: {e}"


if __name__ == "__main__":
    # Run the server using stdio transport (default for FastMCP.run())
    mcp.run()
