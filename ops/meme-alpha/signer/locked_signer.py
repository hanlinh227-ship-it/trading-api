#!/usr/bin/env python3
import json
import os
import socket
import sys

SOCKET_PATH = "/run/meme-alpha-signer/signer.sock"


def reply(conn, payload):
    conn.sendall((json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8"))


def handle(conn):
    conn.settimeout(3.0)
    data = b""
    while len(data) < 16384 and not data.endswith(b"\n"):
        chunk = conn.recv(4096)
        if not chunk:
            break
        data += chunk
    try:
        req = json.loads(data.decode("utf-8").strip() or "{}")
    except Exception:
        reply(conn, {"ok": False, "error": "INVALID_JSON"})
        return

    op = req.get("op")
    if op == "health":
        reply(conn, {
            "ok": True,
            "service": "meme-alpha-signer",
            "mode": "LOCKED",
            "signingEnabled": False,
            "walletLoaded": False,
            "liveExecution": False,
        })
        return

    if op in {"sign", "signTransaction", "swap"}:
        reply(conn, {
            "ok": False,
            "error": "SIGNING_LOCKED",
            "signingEnabled": False,
        })
        return

    reply(conn, {"ok": False, "error": "UNSUPPORTED_OPERATION"})


def main():
    os.makedirs(os.path.dirname(SOCKET_PATH), exist_ok=True)
    try:
        os.unlink(SOCKET_PATH)
    except FileNotFoundError:
        pass

    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(SOCKET_PATH)
    os.chmod(SOCKET_PATH, 0o660)
    srv.listen(16)

    print("SIGNER_MODE=LOCKED", flush=True)
    print("SIGNING_ENABLED=false", flush=True)
    print("WALLET_LOADED=false", flush=True)

    while True:
        conn, _ = srv.accept()
        with conn:
            try:
                handle(conn)
            except Exception as exc:
                try:
                    reply(conn, {"ok": False, "error": "INTERNAL_ERROR"})
                except Exception:
                    pass
                print(f"request_error={type(exc).__name__}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
