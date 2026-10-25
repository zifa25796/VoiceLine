import runpy
from pathlib import Path

server = Path(__file__).resolve().parents[1] / "integrations" / "mcp_server.py"
if not server.is_file():
    raise SystemExit("The Daily MCP bridge belongs to POI. Clone poi-project and run integrations/mcp_server.py.")

if __name__ == "__main__":
    runpy.run_path(str(server), run_name="__main__")
