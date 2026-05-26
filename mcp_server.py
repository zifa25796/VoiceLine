"""MCP server exposing VoiceLine as a tool for AI assistants.

Usage (add to your MCP client config):
  {
    "mcpServers": {
      "voice-line": {
        "command": "python",
        "args": ["C:/Root/CS/Python/POI/VoiceLine/mcp_server.py"]
      }
    }
  }

Tools exposed:
  - voice_speak: Convert text to Machine-style speech (returns .wav path)
  - voice_stats: Show word library coverage stats
  - voice_missing: List common words not yet in the library
"""

import sys
import os
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from voice_line import VoiceLine

vl = VoiceLine()


def handle_request(request: dict) -> dict | None:
    method = request.get("method", "")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request["id"],
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "voice-line",
                    "version": "0.1.0",
                },
            },
        }

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request["id"],
            "result": {
                "tools": [
                    {
                        "name": "voice_speak",
                        "description": "Convert text to Person of Interest 'The Machine' style speech. Each word is spoken in a different voice with radio/phone EQ, static bursts, and channel-switching effects. Returns the path to the generated .wav file.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "text": {
                                    "type": "string",
                                    "description": "The sentence to speak in Machine style",
                                },
                            },
                            "required": ["text"],
                        },
                    },
                    {
                        "name": "voice_stats",
                        "description": "Show VoiceLine word library coverage statistics.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {},
                        },
                    },
                    {
                        "name": "voice_missing",
                        "description": "List common English words not yet in the VoiceLine library.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "top": {
                                    "type": "integer",
                                    "description": "Number of missing words to show (default: 20)",
                                },
                            },
                        },
                    },
                ]
            },
        }

    if method == "tools/call":
        params = request.get("params", {})
        tool_name = params.get("name", "")
        args = params.get("arguments", {})

        if tool_name == "voice_speak":
            text = args.get("text", "")
            if not text:
                return {"jsonrpc": "2.0", "id": request["id"],
                        "result": {"content": [{"type": "text", "text": "Error: text is required"}]}}

            vl.speak(text)  # play directly, no file output

            return {
                "jsonrpc": "2.0",
                "id": request["id"],
                "result": {
                    "content": [
                        {"type": "text", "text": "ok"},
                    ],
                },
            }

        if tool_name == "voice_stats":
            stats = vl.stats()
            return {
                "jsonrpc": "2.0",
                "id": request["id"],
                "result": {
                    "content": [{"type": "text", "text": stats}],
                },
            }

        if tool_name == "voice_missing":
            top = args.get("top", 20)
            missing = vl.missing(top)
            lines = [f"  #{r:4d}  {w}" for r, w in missing]
            return {
                "jsonrpc": "2.0",
                "id": request["id"],
                "result": {
                    "content": [{"type": "text", "text": "\n".join(lines)}],
                },
            }

    return None


def main():
    # Read JSON-RPC messages from stdin, write to stdout
    buffer = ""
    while True:
        try:
            chunk = sys.stdin.readline()
            if not chunk:
                break
            buffer += chunk
            try:
                request = json.loads(buffer)
                buffer = ""
            except json.JSONDecodeError:
                continue  # wait for more data

            response = handle_request(request)
            if response is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
        except Exception as e:
            error = {
                "jsonrpc": "2.0",
                "id": request.get("id") if "request" in dir() else None,
                "error": {"code": -32000, "message": str(e)},
            }
            sys.stdout.write(json.dumps(error) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
