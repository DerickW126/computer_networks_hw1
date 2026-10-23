import os
import json
import time
import base64
import datetime
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PROTOCOL_VERSION = "2026-07-28"
SERVER_INFO = {"name": "project1_mcp", "version": "1.0.0"}
ENDPOINT = "/mcp"

HOST = os.environ.get("MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("MCP_PORT", "5210"))

META_VERSION = "io.modelcontextprotocol/protocolVersion"
META_CAPS = "io.modelcontextprotocol/clientCapabilities"

DEFAULT_ORIGINS = {
    "http://localhost", "https://localhost",
    "http://127.0.0.1", "https://127.0.0.1",
}

EXTRA_ORIGINS = {
    o.strip() for o in os.environ.get("MCP_ALLOWED_ORIGINS", "").split(",")
    if o.strip()
}

TOOLS = [
    {
        "name": "today",
        "title": "Today's date",
        "description": "Return today's date with a specified Python strftime format.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "description": "Python strftime format"
                }
            },
            "required": ["format"]
        }
    },
    {
        "name": "weekday",
        "title": "Weekday of a given date",
        "description": "Return the weekday for a given date.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format"
                }
            },
            "required": ["date"]
        }
    },
    {
        "name": "timer",
        "title": "Egg timer",
        "description": "Send progress every 10 seconds until the alarm.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "alarm": {
                    "type": "integer",
                    "description": "Number of seconds until the alarm"
                }
            },
            "required": ["alarm"]
        }
    },
    {
        "name": "calculator",
        "title": "Calculator",
        "description": "Evaluate an expression using bc.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Expression to evaluate"
                }
            },
            "required": ["expression"]
        }
    }
]


def decode_header_value(value):
    if isinstance(value, str) and value.startswith("=?base64?") and value.endswith("?="):
        inner = value[len("=?base64?"):-len("?=")]
        try:
            return base64.b64decode(inner).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
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


def validate_request(headers, body):
    params = body.get("params") or {}

    if not isinstance(params, dict):
        return -32602, "Invalid params"

    meta = params.get("_meta")

    if not isinstance(meta, dict):
        return -32602, "Missing params._meta"

    if META_VERSION not in meta or META_CAPS not in meta:
        return -32602, "Missing required metadata"

    version = meta[META_VERSION]

    if headers.get("MCP-Protocol-Version") != version:
        return -32020, "Protocol version header mismatch"

    if headers.get("Mcp-Method") != body.get("method"):
        return -32020, "Method header mismatch"

    if body.get("method") == "tools/call":
        name = headers.get("Mcp-Name")

        if name is None:
            return -32020, "Missing Mcp-Name header"

        if decode_header_value(name) != params.get("name"):
            return -32020, "Tool name header mismatch"

    if version != PROTOCOL_VERSION:
        return -32022, "Unsupported protocol version"

    return None


def tool_result(message, error=False):
    return {
        "resultType": "complete",
        "content": [{"type": "text", "text": str(message)}],
        "isError": error
    }


def today(args):
    form = args.get("format")

    if not isinstance(form, str) or not form.strip():
        return tool_result("Invalid format argument", True)

    try:
        res = datetime.date.today().strftime(form.strip())
        return tool_result(res)
    except ValueError:
        return tool_result("Invalid date format", True)


def weekday(args):
    date = args.get("date")

    if not isinstance(date, str) or not date.strip():
        return tool_result("Invalid date argument", True)

    try:
        res = datetime.date.fromisoformat(date.strip())
        return tool_result(res.strftime("%A"))
    except ValueError:
        return tool_result("Invalid date. Use YYYY-MM-DD", True)


def calculator(args):
    expr = args.get("expression")

    if not isinstance(expr, str) or not expr.strip():
        return tool_result("Invalid expression", True)

    try:
        proc = subprocess.run(
            ["bc", "-l"],
            input=expr.strip() + "\n",
            capture_output=True,
            text=True,
            timeout=10
        )
    except subprocess.TimeoutExpired:
        return tool_result("Calculation timed out", True)
    except FileNotFoundError:
        return tool_result("bc is not installed", True)

    if proc.returncode != 0 or proc.stderr.strip():
        return tool_result(proc.stderr.strip() or "Calculation failed", True)

    if not proc.stdout.strip():
        return tool_result("No output from bc", True)

    return tool_result(proc.stdout.strip())


def timer(args):
    alarm = args.get("alarm")

    if type(alarm) is not int or alarm <= 0:
        yield tool_result("Alarm must be a positive integer", True)
        return

    elapsed = 0

    while elapsed + 10 < alarm:
        time.sleep(10)
        elapsed += 10
        yield {"progress": elapsed, "total": alarm}

    time.sleep(alarm - elapsed)

    yield tool_result(f"Time's up! {alarm} seconds elapsed.")


HANDLERS = {
    "today": today,
    "weekday": weekday,
    "calculator": calculator
}


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

        self.send_json({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": err
        }, status=status)

    def open_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "close")
        self.end_headers()

        self.close_connection = True

    def send_sse(self, obj):
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
            return self.send_error_rpc(
                None, -32600, "Origin not allowed", 403
            )

        if self.path.split("?")[0] != ENDPOINT:
            return self.send_error_rpc(
                None, -32601, "Not found", 404
            )

        try:
            length = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, ValueError):
            return self.send_error_rpc(
                None, -32700, "Parse error", 400
            )

        if not isinstance(req, dict):
            return self.send_error_rpc(
                None, -32600, "Invalid request", 400
            )

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params") or {}

        if not isinstance(params, dict):
            return self.send_error_rpc(
                req_id, -32602, "Invalid params", 400
            )

        err = validate_request(self.headers, req)

        if err:
            code, message = err
            return self.send_error_rpc(req_id, code, message, 400)

        if method == "server/discover":
            return self.send_json({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "resultType": "complete",
                    "supportedVersions": [PROTOCOL_VERSION],
                    "capabilities": {"tools": {}},
                    "_meta": {
                        "io.modelcontextprotocol/serverInfo": SERVER_INFO
                    }
                }
            })

        if method == "tools/list":
            return self.send_json({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "resultType": "complete",
                    "tools": TOOLS,
                    "ttlMs": 300000,
                    "cacheScope": "public"
                }
            })

        if method == "tools/call":
            name = params.get("name")
            args = params.get("arguments") or {}

            if not isinstance(args, dict):
                return self.send_error_rpc(
                    req_id, -32602, "Invalid tool arguments", 400
                )

            if name == "timer":
                token = (params.get("_meta") or {}).get("progressToken")

                print(f"[timer] args={args} progressToken={token!r}", flush=True)

                self.open_sse()

                try:
                    for item in timer(args):
                        if "resultType" in item:
                            self.send_sse({
                                "jsonrpc": "2.0",
                                "id": req_id,
                                "result": item
                            })
                        else:
                            self.send_sse({
                                "jsonrpc": "2.0",
                                "method": "notifications/progress",
                                "params": {
                                    "progressToken": token,
                                    "progress": item["progress"],
                                    "total": item["total"],
                                    "message": f"{item['progress']} of {item['total']} seconds elapsed"
                                }
                            })

                except (BrokenPipeError, ConnectionResetError):
                    print("[timer] client disconnected", flush=True)

                return

            if name not in HANDLERS:
                return self.send_error_rpc(
                    req_id, -32602, f"Unknown tool: {name}", 404
                )

            return self.send_json({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": HANDLERS[name](args)
            })

        return self.send_error_rpc(
            req_id, -32601, f"Method not found: {method}", 404
        )

    def log_message(self, fmt, *a):
        print(f"{self.address_string()} {fmt % a}", flush=True)


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), MCPHandler)
    print(f"MCP server on http://{HOST}:{PORT}{ENDPOINT}", flush=True)
    server.serve_forever()