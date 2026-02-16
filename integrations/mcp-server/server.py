import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("myCompiler")

API_URL = "http://localhost:8000/compile"


@mcp.tool()
async def optimize_prompt(text: str) -> str:
    """
    Optimize a prompt using the myCompiler API.

    Args:
        text: The raw prompt text to optimize.
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(API_URL, json={"text": text, "v2": True}, timeout=30.0)
            response.raise_for_status()
            data = response.json()

            # Prefer V2 expanded prompt, fallback to V1
            result = data.get("expanded_prompt_v2") or data.get("expanded_prompt")
            if not result:
                return "Error: API returned success but no optimized prompt found in response."
            return result

        except httpx.RequestError as e:
            return f"Error: Failed to connect to myCompiler API at {API_URL}. Is the server running? Details: {e}"
        except httpx.HTTPStatusError as e:
            return (
                f"Error: API returned status {e.response.status_code}. Details: {e.response.text}"
            )
        except Exception as e:
            return f"Error: Unexpected error during optimization: {e}"


if __name__ == "__main__":
    # Run the server using stdio transport (default for FastMCP.run())
    mcp.run()
