from __future__ import annotations

import json
import uuid
from typing import Any

import httpx


class McpToolError(RuntimeError):
    """Raised when an MCP tool returns an error result."""


class McpClient:
    def __init__(self, endpoint: str, timeout: float = 15.0) -> None:
        endpoint = endpoint.rstrip("/")
        self.endpoint = endpoint if endpoint.endswith("/mcp") else f"{endpoint}/mcp"
        self.timeout = timeout

    async def _post(self, message: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.endpoint, json=message, headers=headers)
            response.raise_for_status()

        if not response.content:
            return {}

        if response.headers.get("content-type", "").startswith("text/event-stream"):
            for line in response.text.splitlines():
                if line.startswith("data:"):
                    return json.loads(line[5:].strip())
            raise McpToolError("MCP returned an empty event stream.")

        return response.json()

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        await self._post({
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "telegram-banking-bot", "version": "1.0.0"},
            },
        })
        await self._post({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        })
        payload = await self._post({
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        })

        if "error" in payload:
            raise McpToolError(str(payload["error"].get("message", "MCP request failed.")))

        result = payload.get("result", {})
        if result.get("isError"):
            message = next(
                (item.get("text") for item in result.get("content", []) if item.get("type") == "text"),
                "MCP tool failed.",
            )
            raise McpToolError(message)

        text = next(
            (item.get("text") for item in result.get("content", []) if item.get("type") == "text"),
            "{}",
        )
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {"message": text}
        return parsed if isinstance(parsed, dict) else {"data": parsed}
