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


def _backend_origin() -> str:
    compile_url = resolve_compile_post_url()
    if compile_url.endswith("/compile"):
        return compile_url[: -len("/compile")]
    return compile_url.rsplit("/", 1)[0]


def _json_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    api_key = resolve_api_key()
    if api_key:
        headers["x-api-key"] = api_key
    return headers


async def _post_json(path: str, payload: dict) -> dict:
    url = f"{_backend_origin()}{path}"
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=_json_headers(), timeout=30.0)
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def compile_prompt(text: str) -> dict:
    """
    Compile a prompt through the Prompt Compiler backend and return the structured response.
    """
    mode = resolve_prompt_mode()
    payload = build_compile_body(text, mode)
    return await _post_json("/compile", payload)


@mcp.tool()
async def generate_agent(description: str, multi_agent: bool = False) -> str:
    """
    Generate a Claude-friendly agent/system prompt from a natural-language description.
    """
    data = await _post_json(
        "/agent-generator/generate",
        {
            "description": description,
            "multi_agent": multi_agent,
            "include_example_code": False,
        },
    )
    return data["system_prompt"]


@mcp.tool()
async def generate_skill(description: str) -> str:
    """
    Generate a structured skill/tool definition from a natural-language capability description.
    """
    data = await _post_json(
        "/skills-generator/generate",
        {
            "description": description,
            "include_example_code": False,
        },
    )
    return data["skill_definition"]


@mcp.tool()
async def export_claude_pack(system_prompt: str) -> dict:
    """
    Convert a generated agent prompt into a Claude Code project pack manifest.
    """
    return await _post_json(
        "/agent-generator/export",
        {
            "system_prompt": system_prompt,
            "format": "claude-project-pack",
            "output_type": "manifest",
            "is_multi_agent": False,
        },
    )


@mcp.tool()
async def benchmark_prompt(text: str, model: str = "llama-3.1-8b-instant") -> dict:
    """
    Benchmark a raw prompt against the compiled prompt and return the comparison payload.
    """
    return await _post_json(
        "/benchmark/run",
        {
            "text": text,
            "model": model,
        },
    )


if __name__ == "__main__":
    # Run the server using stdio transport (default for FastMCP.run())
    mcp.run()
