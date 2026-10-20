import os
import json
import time
import base64
import datetime
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
 
PROTOCOL_VERSION = "2026-07-28"
SERVER_INFO = {"name": "csee4119-mcp", "version": "1.0.0"}
ENDPOINT = "/mcp"
 
HOST = os.environ.get("MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("MCP_PORT", "5210"))
 
META_VERSION = "io.modelcontextprotocol/protocolVersion"
META_CAPS = "io.modelcontextprotocol/clientCapabilities"

DEFAULT_ORIGINS = {
    "http://localhost", "https://localhost",
    "http://127.0.0.1", "https://127.0.0.1",
}
EXTRA_ORIGINS = {o.strip() for o in os.environ.get("MCP_ALLOWED_ORIGINS", "").split(",") if o.strip()}

TOOLS = [
    {
        "name": "today",
        "title": "Today's date",
        "description": "Return today's date with a specified format argument that adheres to the Python strftime() format.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "format": {"type": "string", "description": "provide a format that adheres to Python strftime() format"}
            },
            "required": ["format"],
        },
    },
    {
        "name": "weekday",
        "title": "Weekday of a given date",
        "description": "Return the weekday for a date provided in the date argument.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "provide the date"}
            },
            "required": ["date"],
        },
    },
    {
        "name": "timer",
        "title": "Egg timer",
        "description": "A simple “egg timer” that sends an update every ten seconds and an alarm. The argument alarm specifies the number of seconds until the alarm.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "alarm": {"type": "integer", "description": "the number of seconds until the alarm."}
            },
            "required": ["alarm"],
        },
    },
    {
        "name": "calculator",
        "title": "Calculator tool",
        "description": "Interpret expression element and return answer, using the bc calculator tool.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "provide expression to be computed"}
            },
            "required": ["expression"],
        },
    },
]

def decode_header_value(value):
    if isinstance(value, str) and value.startswith("=?base64?") and value.endswith("?="):
        inner = value[len("=?base64?"):-len("?=")]
        try:
            return base64.b64decode(inner).decode("utf-8")
        except Exception:
            return value
    return value
 
 
def origin_allowed(origin):
    if origin is None:
        return True
    if origin in (DEFAULT_ORIGINS | EXTRA_ORIGINS):
        return True
    for base in ("http://localhost:", "https://localhost:",
                 "http://127.0.0.1:", "https://127.0.0.1:"):
        if origin.startswith(base) and origin[len(base):].isdigit():
            return True
    return False
 
 
def validate_meta(body):
    """Required per-request _meta fields. -> 400 + -32602"""
    meta = (body.get("params") or {}).get("_meta")
    if not isinstance(meta, dict):
        return "Missing params._meta"
    if META_VERSION not in meta:
        return f"Missing required _meta field: {META_VERSION}"
    if META_CAPS not in meta:
        return f"Missing required _meta field: {META_CAPS}"
    return None
 
 
def validate_headers(headers, body):
    """Mirrored headers must match the body. -> 400 + -32020"""
    params = body.get("params") or {}
    meta = params.get("_meta") or {}
 
    hdr_version = headers.get("MCP-Protocol-Version")
    if hdr_version is None:
        return "Missing required header: MCP-Protocol-Version"
    if hdr_version != meta.get(META_VERSION):
        return (f"MCP-Protocol-Version header '{hdr_version}' does not match body value "
                f"'{meta.get(META_VERSION)}'")
 
    hdr_method = headers.get("Mcp-Method")
    if hdr_method is None:
        return "Missing required header: Mcp-Method"
    if hdr_method != body.get("method"):
        return f"Mcp-Method header '{hdr_method}' does not match body method '{body.get('method')}'"
 
    if body.get("method") == "tools/call":
        hdr_name = headers.get("Mcp-Name")
        if hdr_name is None:
            return "Missing required header: Mcp-Name"
        if decode_header_value(hdr_name) != params.get("name"):
            return f"Mcp-Name header '{hdr_name}' does not match body name '{params.get('name')}'"
 
    return None
 
 
def validate_version(body):
    requested = ((body.get("params") or {}).get("_meta") or {}).get(META_VERSION)
    return None if requested == PROTOCOL_VERSION else requested
 

def today(args):
    form = args.get("format")
    if not form or not isinstance(form, str) or not form.strip():
        return {
            "resultType": "complete",
            "content": [{"type": "text", "text": "Require 'format' argument with type string"}],
            "isError": True,
        }
    try:
        res = datetime.date.today().strftime(form.strip())
    except ValueError as e:
        return {
            "resultType": "complete",
            "content": [{"type": "text", "text": f"The format string is not a valid format"}],
            "isError": True,
        }
    return {
        "resultType": "complete",
        "content": [{"type": "text", "text": res}],
        "isError": False,
    }


def weekday(args):
    date = args.get("date")
    if not date or not isinstance(date, str) or not date.strip():
        return {
            "resultType": "complete",
            "content": [{"type": "text", "text": "Require 'date' argument with type string"}],
            "isError": True,
        }
    try:
        res = datetime.date.fromisoformat(date.strip())
    except ValueError:
        return {
            "resultType": "complete",
            "content": [{"type": "text", "text": f"Could not parse '{date}' argument. Please use ISO 8601 format"}],
            "isError": True,
        }
    return {
        "resultType": "complete",
        "content": [{"type": "text", "text": res.strftime("%A")}],
        "isError": False,
    }


def calculator(args):
    expr = args.get("expression")
    if not expr or not isinstance(expr, str) or not expr.strip() :
        return {
            "resultType": "complete",
            "content": [{"type": "text", "text": "Require 'expression' argument with type string"}],
            "isError": True,
        }

    try:
        proc = subprocess.run(["bc", "-l"], input=expr.strip(), capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        return {
            "resultType": "complete",
            "content": [{"type": "text", "text": "Calculation timed out after 10 seconds."}],
            "isError": True,
        }

    if proc.stderr.strip():
        return {
            "resultType": "complete",
            "content": [{"type": "text", "text": f"bc error: {proc.stderr.strip()}"}],
            "isError": True,
        }

    if not proc.stdout.strip():
        return {
            "resultType": "complete",
            "content": [{"type": "text", "text": f"bc failed to provide an output to the expression"}],
            "isError": True,
        }

    return {
        "resultType": "complete",
        "content": [{"type": "text", "text": proc.stdout.strip()}],
        "isError": False,
    }

def timer(args):
    alarm = args.get("alarm")

    if not isinstance(alarm, int) or alarm <= 0:
        yield {
            "resultType": "complete",
            "content": [{"type": "text",
                         "text": "Require 'alarm' argument as a positive integer number of seconds"}],
            "isError": True,
        }
        return

    elapsed = 0
    while elapsed + 10 < alarm:
        time.sleep(10)
        elapsed += 10
        yield {"progress": elapsed, "total": alarm}

    time.sleep(alarm - elapsed)
    yield {
        "resultType": "complete",
        "content": [{"type": "text", "text": f"Time's up! {alarm} seconds elapsed."}],
        "isError": False,
    }

HANDLERS = {"today": today, "weekday": weekday, "calculator": calculator}


class MCPHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
 
    def send_json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
 
    def send_error_rpc(self, req_id, code, message, status, data=None):
        err = {"code": code, "message": message}
        if data is not None:
            err["data"] = data
        self.send_json({"jsonrpc": "2.0", "id": req_id, "error": err}, status=status)
 
    def open_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
 
    def send_sse(self, obj):
        """One SSE event. The blank line ends it; the flush actually sends it."""
        self.wfile.write(f"data: {json.dumps(obj)}\n\n".encode())
        self.wfile.flush()
 
    def do_GET(self):
        self.send_response(405)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_DELETE(self):
        self.send_response(405)
        self.send_header("Content-Length", "0")
        self.end_headers()
 
    def do_POST(self):
        if not origin_allowed(self.headers.get("Origin")):
            return self.send_json(
                {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Origin not allowed"}},
                status=403)
 
        if self.path.split("?")[0] != ENDPOINT:
            return self.send_error_rpc(None, -32601, "Not found", 404)
 
        length = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, ValueError):
            return self.send_error_rpc(None, -32700, "Parse error", 400)
 
        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params") or {}
 
        err = validate_meta(req)
        if err:
            return self.send_error_rpc(req_id, -32602, err, 400)
 
        err = validate_headers(self.headers, req)
        if err:
            return self.send_error_rpc(req_id, -32020, err, 400)
 
        bad_version = validate_version(req)
        if bad_version is not None:
            return self.send_error_rpc(
                req_id, -32022, f"Unsupported protocol version: {bad_version}", 400,
                data={"supported": [PROTOCOL_VERSION]})
 
        if method == "server/discover":
            return self.send_json({
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "resultType": "complete",
                    "supportedVersions": [PROTOCOL_VERSION],
                    "capabilities": {"tools": {}},
                    "_meta": {"io.modelcontextprotocol/serverInfo": SERVER_INFO},
                },
            })
 
        if method == "tools/list":
            return self.send_json({
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "resultType": "complete",
                    "tools": TOOLS,
                    "ttlMs": 300000,
                    "cacheScope": "public",
                },
            })
 
        if method == "tools/call":
            name = params.get("name")
            args = params.get("arguments") or {}
 
            if name == "timer":
                token = (params.get("_meta") or {}).get("progressToken")
                print(f"[timer] args={args} progressToken={token!r}", flush=True)
                self.open_sse()
                try:
                    for item in timer(args):
                        if "resultType" in item:
                            self.send_sse({"jsonrpc": "2.0", "id": req_id, "result": item})
                        else:
                            self.send_sse({
                                "jsonrpc": "2.0",
                                "method": "notifications/progress",
                                "params": {
                                    "progressToken": token,
                                    "progress": item["progress"],
                                    "total": item["total"],
                                    "message": f"{item['progress']} of {item['total']} seconds elapsed",
                                },
                            })
                except (BrokenPipeError, ConnectionResetError):
                    print("[timer] client disconnected", flush=True)
                return
 
            if name not in HANDLERS:
                return self.send_error_rpc(req_id, -32602, f"Unknown tool: {name}", 404)
 
            return self.send_json({
                "jsonrpc": "2.0", "id": req_id,
                "result": HANDLERS[name](args),
            })
 
        return self.send_error_rpc(req_id, -32601, f"Method not found: {method}", 404)
 
    def log_message(self, fmt, *a):
        print(f"{self.address_string()} {fmt % a}", flush=True)
 
 
if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), MCPHandler)
    print(f"MCP server on http://{HOST}:{PORT}{ENDPOINT}", flush=True)
    server.serve_forever()
 