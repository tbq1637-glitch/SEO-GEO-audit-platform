"""Run-scoped OpenAI budget gateway. No API keys or request bodies in ledger."""
import argparse
import copy
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LIMITS = {"landing_page": 250000, "website": 500000}
DEFAULT_OUTPUT = 32768
UPSTREAM = "https://api.openai.com"
LEDGER = Path("reports/openai_token_budget.json")
CREATE_PATHS = {"/v1/responses", "/v1/chat/completions"}
RESPONSE_PATH = re.compile(r"/v1/responses/(resp_[A-Za-z0-9_-]+)$")


class BudgetExceeded(Exception):
    pass


def estimate_input(body):
    """Conservative estimate, not provider-certified token count.
    Do not tokenize image base64 as text; reserve 20k per bounded image.
    """
    import tiktoken
    encoding = tiktoken.get_encoding("o200k_base")
    images = 0

    def sanitize(value):
        nonlocal images
        if isinstance(value, dict):
            if value.get("type") in ("input_image", "image_url"):
                images += 1
                return {"type": "image"}
            return {k: sanitize(v) for k, v in value.items()}
        if isinstance(value, list):
            return [sanitize(v) for v in value]
        return value

    data = json.dumps(sanitize(body), ensure_ascii=False, separators=(",", ":"))
    text_tokens = len(encoding.encode(data, disallowed_special=()))
    return (text_tokens * 120 + 99) // 100 + 1024 + images * 20000


class Budget:
    def __init__(self, path, scope, reset=False):
        self.path = Path(path)
        self.lock = threading.RLock()
        limit = LIMITS[scope]
        if reset:
            self.data = {"scope": scope, "limit": limit, "blocked": False, "requests": []}
            self.save()
        else:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            if self.data["scope"] != scope or self.data["limit"] != limit:
                raise RuntimeError("Budget scope mismatch")

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.data, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def totals(self):
        rows = self.data["requests"]
        return {
            "input_tokens": sum(r.get("input_tokens", 0) for r in rows),
            "output_tokens": sum(r.get("output_tokens", 0) for r in rows),
            "confirmed_tokens": sum(r.get("total_tokens", 0) for r in rows),
            "unconfirmed_reserved_tokens": sum(r["reservation"] for r in rows if r["state"] != "confirmed"),
        }

    def block(self, reason):
        self.data["blocked"] = True
        self.data["blocked_reason"] = reason
        self.save()

    def reserve(self, stage, path, body):
        body = copy.deepcopy(body)
        if body.get("stream") or body.get("tools") or body.get("previous_response_id") or body.get("conversation"):
            with self.lock:
                self.block("Unsupported request shape; refused before API call")
            raise BudgetExceeded("Unsupported request shape")
        if path == "/v1/responses":
            output_key = "max_output_tokens"
        else:
            output_key = "max_tokens" if "max_tokens" in body else "max_completion_tokens"
        output = body.get(output_key, DEFAULT_OUTPUT)
        if type(output) is not int or output <= 0:
            with self.lock:
                self.block("Invalid output token bound")
            raise BudgetExceeded("Invalid output token bound")
        body[output_key] = output
        estimate = estimate_input(body)
        reservation = estimate + output
        with self.lock:
            totals = self.totals()
            available = self.data["limit"] - totals["confirmed_tokens"] - totals["unconfirmed_reserved_tokens"]
            if self.data["blocked"] or reservation > available:
                if not self.data["blocked"]:
                    self.block("Estimated request exceeds remaining budget")
                raise BudgetExceeded("OpenAI token budget exhausted or insufficient")
            row = {"stage": stage, "endpoint": path, "model": str(body.get("model", "")),
                   "estimated_input_tokens": estimate, "max_output_tokens": output,
                   "reservation": reservation, "state": "reserved"}
            self.data["requests"].append(row)
            self.save()
            return len(self.data["requests"]) - 1, body

    def observe(self, index, response):
        with self.lock:
            row = self.data["requests"][index]
            if row["state"] == "confirmed":
                return
            response_id = response.get("id")
            if isinstance(response_id, str) and RESPONSE_PATH.fullmatch("/v1/responses/" + response_id):
                row["response_id"] = response_id
            usage = response.get("usage")
            if response.get("status") in ("queued", "in_progress"):
                self.save()
                return
            if isinstance(usage, dict):
                inp = usage.get("input_tokens", usage.get("prompt_tokens"))
                out = usage.get("output_tokens", usage.get("completion_tokens"))
                total = usage.get("total_tokens")
                if all(type(x) is int and x >= 0 for x in (inp, out, total)) and total >= inp + out:
                    row.update(input_tokens=inp, output_tokens=out, total_tokens=total, state="confirmed")
                    totals = self.totals()
                    if total > row["reservation"] or totals["confirmed_tokens"] + totals["unconfirmed_reserved_tokens"] > self.data["limit"]:
                        self.block("Provider usage exceeded reserved estimate")
            self.save()

    def find_response(self, response_id):
        with self.lock:
            for i, row in enumerate(self.data["requests"]):
                if row.get("response_id") == response_id:
                    return i
        raise BudgetExceeded("Untracked response ID")

    def summary(self):
        totals = self.totals()
        charged = totals["confirmed_tokens"] + totals["unconfirmed_reserved_tokens"]
        status = "STOPPED - budget protection" if self.data["blocked"] else (
            "Usage incomplete - reservations retained" if totals["unconfirmed_reserved_tokens"] else "Within budget")
        lines = ["## OpenAI API Usage Summary", "",
                 "| Metric | Tokens |", "| --- | ---: |",
                 f"| Scope | {self.data['scope']} |",
                 f"| Token budget | {self.data['limit']:,} |",
                 f"| Confirmed input | {totals['input_tokens']:,} |",
                 f"| Confirmed output (includes reasoning where reported) | {totals['output_tokens']:,} |",
                 f"| Confirmed total | {totals['confirmed_tokens']:,} |",
                 f"| Unconfirmed reserved (not billed usage) | {totals['unconfirmed_reserved_tokens']:,} |",
                 f"| Remaining estimated budget | {max(0, self.data['limit'] - charged):,} |",
                 f"| Status | {status} |", ""]
        if self.data.get("blocked_reason"):
            lines += [self.data["blocked_reason"], ""]
        lines += ["| Stage | Confirmed input | Confirmed output | Confirmed total | Unconfirmed reserved |",
                  "| --- | ---: | ---: | ---: | ---: |"]
        for stage in dict.fromkeys(row["stage"] for row in self.data["requests"]):
            rows = [r for r in self.data["requests"] if r["stage"] == stage]
            fields = [sum(r.get(k, 0) for r in rows) for k in ("input_tokens", "output_tokens", "total_tokens")]
            pending = sum(r["reservation"] for r in rows if r["state"] != "confirmed")
            lines.append(f"| {stage} | {fields[0]:,} | {fields[1]:,} | {fields[2]:,} | {pending:,} |")
        lines += ["", "Input admission uses a conservative estimate; actual provider usage can differ. "
                  "All uncertain submissions retain their reservation. SerpApi is separate.", ""]
        return "\n".join(lines)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def make_handler(budget, stage, upstream_key, local_key, opener=None):
    opener = opener or urllib.request.build_opener(NoRedirect())

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send_json(self, status, value):
            self.send_bytes(status, json.dumps(value).encode())

        def send_bytes(self, status, payload):
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_POST(self):
            self.handle_api("POST")

        def do_GET(self):
            self.handle_api("GET")

        def handle_api(self, method):
            if self.headers.get("Authorization") != "Bearer " + local_key:
                self.send_json(401, {"error": {"message": "Local gateway authentication failed"}})
                return
            path = self.path
            try:
                if method == "POST" and path in CREATE_PATHS:
                    size = int(self.headers.get("Content-Length", "0"))
                    if not 0 < size <= 32 * 1024 * 1024:
                        raise BudgetExceeded("Unsupported payload size")
                    body = json.loads(self.rfile.read(size))
                    index, body = budget.reserve(stage, path, body)
                    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
                elif method == "GET" and RESPONSE_PATH.fullmatch(path):
                    index = budget.find_response(RESPONSE_PATH.fullmatch(path).group(1))
                    data = None
                else:
                    raise BudgetExceeded("Unsupported API endpoint")
            except BudgetExceeded as exc:
                self.send_json(400, {"error": {"message": str(exc), "type": "token_budget_error"}})
                return
            except Exception:
                self.send_json(400, {"error": {"message": "Invalid budget gateway request"}})
                return
            request = urllib.request.Request(UPSTREAM + path, data=data, method=method,
                                             headers={"Authorization": "Bearer " + upstream_key,
                                                      "Content-Type": "application/json"})
            try:
                with opener.open(request, timeout=420) as response:
                    payload = response.read()
                    status = response.status
                value = json.loads(payload)
                budget.observe(index, value)
                self.send_bytes(status, payload)
            except urllib.error.HTTPError as exc:
                # No trustworthy usage: keep full reservation, never refund.
                self.send_json(exc.code if 400 <= exc.code <= 599 else 502,
                               {"error": {"message": "Upstream OpenAI HTTP error; reservation retained"}})
            except Exception:
                self.send_json(502, {"error": {"message": "Upstream response uncertain; reservation retained"}})

    return Handler


def run_stage(budget, stage, command):
    if budget.data["blocked"]:
        return 1
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("Missing OPENAI_API_KEY")
    local_key = "local-budget-" + secrets.token_hex(24)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(budget, stage, key, local_key))
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    env = os.environ.copy()
    endpoint = f"http://127.0.0.1:{server.server_port}/v1"
    env["OPENAI_API_KEY"] = local_key
    env["OPENAI_BASE_URL"] = endpoint
    command = [arg.replace("__BUDGET_ENDPOINT__", endpoint) for arg in command]
    try:
        code = subprocess.run(command, env=env, check=False).returncode
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    return 1 if budget.data["blocked"] else code


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["init", "run", "summary"])
    parser.add_argument("stage", nargs="?")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    scope = os.environ["AUDIT_SCOPE"]
    budget = Budget(LEDGER, scope, reset=args.action == "init")
    if args.action == "run":
        command = args.command
        if command and command[0] == "--":
            command = command[1:]
        if not args.stage or not command:
            parser.error("run requires stage and command")
        sys.exit(run_stage(budget, args.stage, command))
    if args.action == "summary":
        text = budget.summary()
        LEDGER.with_name("OPENAI_TOKEN_USAGE.md").write_text(text, encoding="utf-8")
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
                f.write("\n" + text)


if __name__ == "__main__":
    main()
