"""
mcp_provider.py
---------------
MCPToolProvider — plugs into ToolRouter alongside A2AToolProvider and LocalToolProvider.
Supports two MCP transports:
  - "stdio"           → spawns mcp_server_local.py as subprocess, JSON-RPC over stdin/stdout
  - "streamable_http" → connects to mcp_server_http.py over Streamable HTTP / SSE

Usage in OrchestratorService.__init__:

    from .runtime.tools.providers.mcp_provider import MCPToolProvider

    mcp_stdio_provider = MCPToolProvider(
        transport="stdio",
        server_script=str(Path(__file__).parent / "servers" / "mcp_server_local.py"),
    )

    mcp_http_provider = MCPToolProvider(
        transport="streamable_http",
        server_url="http://localhost:9100/mcp",
    )

    self.tool_router = ToolRouter(
        providers={
            "a2a":          a2a_provider,
            "local":        local_provider,
            "mcp_stdio":    mcp_stdio_provider,
            "mcp_http":     mcp_http_provider,
        },
        tool_to_provider={
            ...existing keys...
            "book_hotel_flow_stdio":      "mcp_stdio",
            "booking_stub_stdio":         "mcp_stdio",
            "forecast_weather_mcp":       "mcp_http",
            "recommend_pois_mcp":         "mcp_http",
            "info_visa_policy_mcp":       "mcp_http",
            "info_accommodation_mcp":     "mcp_http",
            "plan_itinerary_mcp":         "mcp_http",
        },
    )
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import httpx, json as _json
import time
from typing import Any, Dict, Literal, Optional

# MCP SDK
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamablehttp_client

from ..models import ToolCall, ToolResult


TransportMode = Literal["stdio", "streamable_http"]


class MCPToolProvider:
    """
    Single provider class handling both MCP transports.
    Conforms to ToolProvider protocol (has provider_name + call()).
    """

    def __init__(
        self,
        transport: TransportMode,
        # stdio params
        server_script: Optional[str] = None,
        python_executable: Optional[str] = None,
        # streamable http params
        server_url: Optional[str] = None,
        # shared
        timeout_sec: float = 30.0,
    ):
        self.transport = transport
        self.server_script = server_script
        self.python_executable = python_executable or sys.executable
        self.server_url = server_url
        self.timeout_sec = timeout_sec

        if transport == "stdio":
            assert server_script, "server_script required for stdio transport"
            self.provider_name = "mcp_stdio"
        elif transport == "streamable_http":
            assert server_url, "server_url required for streamable_http transport"
            self.provider_name = "mcp"
        else:
            raise ValueError(f"Unknown transport: {transport}")

    # ------------------------------------------------------------------
    # Public interface (ToolProvider protocol)
    # ------------------------------------------------------------------

    def call(self, tool_call: ToolCall) -> ToolResult:
        # Strip _mcp/_stdio suffix to get real tool name
        tool_name = tool_call.name
        for suffix in ("_mcp", "_stdio", "_streamable_http"):
            if tool_name.endswith(suffix):
                tool_name = tool_name[: -len(suffix)]
                break

        # Strip orchestrator-internal fields, keep only tool-relevant args
        TOOL_ARG_KEYS = {
            "forecast_weather": {"city", "start_date", "end_date", "days", "country", "time_of_day", "raw_text"},
            "recommend_pois":     {"city", "destination", "days", "travel_style", "country"},
            "info_visa_policy":   {"nationality", "destination"},
            "info_accommodation": {"city", "check_in", "check_out", "guests", "budget_level", "must_have_amenities"},
            "plan_itinerary":     {"destination", "city", "days", "start_date", "travel_style"},
        }
        allowed = TOOL_ARG_KEYS.get(tool_name)
        if allowed:
            tool_call = tool_call.model_copy(update={
                "args": {k: v for k, v in (tool_call.args or {}).items() if k in allowed}
            })

        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self._run_in_new_loop, tool_call)
            try:
                return future.result(timeout=self.timeout_sec + 5)
            except Exception as e:
                t = int(time.perf_counter() * 1000)
                return ToolResult(
                    ok=False,
                    tool_name=tool_call.name,
                    provider="mcp",
                    transport_type=f"mcp_{self.transport}",
                    data=None,
                    error=f"MCPToolProvider.call failed: {e}",
                    latency_ms=0,
                    evidence=[],
                )

    def _run_in_new_loop(self, tool_call: ToolCall) -> ToolResult:
        """Runs in a fresh thread with its own event loop — no conflict with uvicorn."""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._async_call(tool_call))
        finally:
            loop.close()

    # ------------------------------------------------------------------
    # Async internals
    # ------------------------------------------------------------------

    async def _async_call(self, call: ToolCall) -> ToolResult:
        if self.transport == "stdio":
            return await self._call_stdio(call)
        else:
            return await self._call_streamable_http(call)

    async def _call_stdio(self, call: ToolCall) -> ToolResult:
        """
        Spawn MCP server subprocess, execute one tool call, return result.
        The subprocess is spawned fresh per call for now (safe, predictable).
        For production you'd keep it alive — see _StdioSession for that pattern.
        """
        t_start = time.perf_counter()

        params = StdioServerParameters(
            command=self.python_executable,
            args=[self.server_script],
            env=None,  # inherits parent env
        )

        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    # Strip _stdio/_mcp suffix from tool name if present
                    tool_name = _strip_transport_suffix(call.name)

                    result_obj = await asyncio.wait_for(
                        session.call_tool(tool_name, arguments=call.args),
                        timeout=self.timeout_sec,
                    )

            latency_ms = int((time.perf_counter() - t_start) * 1000)
            data = _parse_tool_result(result_obj)

            return ToolResult(
                ok=not result_obj.isError,
                tool_name=call.name,
                provider="mcp",
                transport_type="mcp_stdio",
                data=data,
                error=data.get("error") if result_obj.isError else None,
                latency_ms=latency_ms,
                evidence=[],
                trace_id=call.trace_id,
            )

        except asyncio.TimeoutError:
            latency_ms = int((time.perf_counter() - t_start) * 1000)
            return ToolResult(
                ok=False,
                tool_name=call.name,
                provider="mcp",
                transport_type="mcp_stdio",
                data=None,
                error=f"MCP stdio timeout after {self.timeout_sec}s",
                latency_ms=latency_ms,
                evidence=[],
            )

        except Exception as e:
            latency_ms = int((time.perf_counter() - t_start) * 1000)
            return ToolResult(
                ok=False,
                tool_name=call.name,
                provider="mcp",
                transport_type="mcp_stdio",
                data=None,
                error=str(e),
                latency_ms=latency_ms,
                evidence=[],
            )

    async def _call_streamable_http(self, call: ToolCall) -> ToolResult:
        t_start = time.perf_counter()
        try:
            # Use base URL without trailing slash
            url = self.server_url.rstrip("/")
            
            async with streamablehttp_client(url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    # Wait for initialization to complete
                    await session.initialize()
                    await asyncio.sleep(0.1)  # small grace period

                    tool_name = _strip_transport_suffix(call.name)
                    print(f"[MCP HTTP] calling tool={tool_name!r} args={call.args}")

                    result_obj = await asyncio.wait_for(
                        session.call_tool(tool_name, arguments=call.args),
                        timeout=self.timeout_sec,
                    )

            latency_ms = int((time.perf_counter() - t_start) * 1000)
            data = _parse_tool_result(result_obj)
            print(f"[MCP HTTP] result ok={not result_obj.isError} data_keys={list(data.keys()) if isinstance(data, dict) else 'non-dict'}")

            return ToolResult(
                ok=not result_obj.isError,
                tool_name=call.name,
                provider="mcp",
                transport_type="mcp_streamable_http",
                data=data,
                error=data.get("error") if result_obj.isError else None,
                latency_ms=latency_ms,
                evidence=[],
                trace_id=call.trace_id,
            )
        except asyncio.TimeoutError:
            latency_ms = int((time.perf_counter() - t_start) * 1000)
            return ToolResult(
                ok=False, tool_name=call.name, provider="mcp",
                transport_type="mcp_streamable_http", data=None,
                error=f"MCP streamable HTTP timeout after {self.timeout_sec}s",
                latency_ms=latency_ms, evidence=[],
            )
        except Exception as e:
            latency_ms = int((time.perf_counter() - t_start) * 1000)
            return ToolResult(
                ok=False, tool_name=call.name, provider="mcp",
                transport_type="mcp_streamable_http", data=None,
                error=str(e), latency_ms=latency_ms, evidence=[],
            )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _strip_transport_suffix(name: str) -> str:
    """
    'booking_stub_stdio'  -> 'booking_stub'
    'forecast_weather_mcp' -> 'forecast_weather'
    'book_hotel_flow'     -> 'book_hotel_flow'
    """
    for suffix in ("_stdio", "_mcp", "_streamable_http", "_mcp_http"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _parse_tool_result(result_obj: Any) -> Dict[str, Any]:
    """
    Extract dict from MCP CallToolResult.
    MCP returns content as list of TextContent / ImageContent etc.
    We expect JSON text in content[0].text.
    """
    try:
        if result_obj.content:
            first = result_obj.content[0]
            text = getattr(first, "text", None) or ""
            if text:
                return json.loads(text)
        return {"ok": False, "error": "Empty MCP response"}
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"JSON parse failed: {e}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}