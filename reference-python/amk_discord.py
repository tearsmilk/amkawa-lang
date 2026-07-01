#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
amk_discord.py — a tiny Discord bot client written from scratch.
No discord.py, no external packages: only the Python standard library
(raw WebSocket over TLS for the gateway + http.client for REST).

Used by the Aminakawa language via built-ins: bot(), on_message(), say(), run().

NOTE: needs the "Message Content Intent" turned ON in the Discord
Developer Portal (Bot page) so the bot can read message text.
"""
import os
import io
import ssl
import json
import time
import socket
import struct
import base64
import threading
import http.client

# ---- endpoints ----
API_HOST = "discord.com"
API_BASE = "/api/v10"
GW_HOST = "gateway.discord.gg"
GW_PATH = "/?v=10&encoding=json"

# intents: GUILDS | GUILD_MESSAGES | MESSAGE_CONTENT | DIRECT_MESSAGES
INTENTS = (1 << 0) | (1 << 9) | (1 << 15) | (1 << 12)

_token = None
_handler = None


def set_token(token):
    global _token
    _token = (token or "").strip()


def set_handler(fn):
    global _handler
    _handler = fn


# ============================================================
#  REST  (sending messages)
# ============================================================
def send_message(channel_id, content):
    if not _token:
        print('[bot] no token — call bot("...") first')
        return
    conn = http.client.HTTPSConnection(API_HOST, timeout=15)
    body = json.dumps({"content": content})
    headers = {
        "Authorization": "Bot " + _token,
        "Content-Type": "application/json",
        "User-Agent": "Aminakawa (custom bot, 0.1)",
    }
    try:
        conn.request("POST", "%s/channels/%s/messages" % (API_BASE, channel_id), body, headers)
        resp = conn.getresponse()
        data = resp.read()
        if resp.status >= 300:
            print("[bot] send failed (%s): %s" % (resp.status, data[:200].decode("utf-8", "replace")))
    except Exception as e:
        print("[bot] send error: %s" % e)
    finally:
        conn.close()


# ============================================================
#  WebSocket framing (RFC 6455) — pure bytes helpers
# ============================================================
def _encode_frame(payload, opcode=0x1, mask=True):
    header = bytearray()
    header.append(0x80 | opcode)  # FIN + opcode
    ln = len(payload)
    mbit = 0x80 if mask else 0x00
    if ln < 126:
        header.append(mbit | ln)
    elif ln < 65536:
        header.append(mbit | 126)
        header += struct.pack(">H", ln)
    else:
        header.append(mbit | 127)
        header += struct.pack(">Q", ln)
    if mask:
        m = os.urandom(4)
        header += m
        payload = bytes(payload[i] ^ m[i % 4] for i in range(ln))
    return bytes(header) + payload


def _read_frame(recv_exact):
    h = recv_exact(2)
    b1, b2 = h[0], h[1]
    fin = b1 & 0x80
    opcode = b1 & 0x0F
    masked = b2 & 0x80
    length = b2 & 0x7F
    if length == 126:
        length = struct.unpack(">H", recv_exact(2))[0]
    elif length == 127:
        length = struct.unpack(">Q", recv_exact(8))[0]
    mask = recv_exact(4) if masked else None
    payload = recv_exact(length) if length else b""
    if mask:
        payload = bytes(payload[i] ^ mask[i % 4] for i in range(len(payload)))
    return fin, opcode, payload


# ============================================================
#  WebSocket client (over TLS socket)
# ============================================================
class _WS:
    def __init__(self, host, path):
        raw = socket.create_connection((host, 443), timeout=30)
        ctx = ssl.create_default_context()
        self.sock = ctx.wrap_socket(raw, server_hostname=host)
        self.lock = threading.Lock()
        self._handshake(host, path)

    def _handshake(self, host, path):
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            "GET %s HTTP/1.1\r\n"
            "Host: %s\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: %s\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ) % (path, host, key)
        self.sock.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.sock.recv(1024)
            if not chunk:
                raise ConnectionError("handshake failed (empty reply)")
            buf += chunk
        status_line = buf.split(b"\r\n")[0]
        if b" 101 " not in status_line:
            raise ConnectionError("handshake failed: " + status_line.decode("utf-8", "replace"))

    def _recv_exact(self, n):
        data = b""
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("connection closed")
            data += chunk
        return data

    def recv(self):
        """Return the text of the next data frame. Handles ping/pong/close."""
        frags = b""
        first_op = None
        while True:
            fin, opcode, payload = _read_frame(self._recv_exact)
            if opcode == 0x9:      # ping -> pong
                self._send_raw(payload, 0xA)
                continue
            if opcode == 0xA:      # pong
                continue
            if opcode == 0x8:      # close
                raise ConnectionError("gateway sent close")
            if opcode == 0x0:      # continuation
                frags += payload
            else:
                first_op = opcode
                frags = payload
            if fin:
                return frags.decode("utf-8", "replace")

    def _send_raw(self, payload_bytes, opcode):
        frame = _encode_frame(payload_bytes, opcode, mask=True)
        with self.lock:
            self.sock.sendall(frame)

    def send_text(self, text):
        self._send_raw(text.encode("utf-8"), 0x1)

    def close(self):
        try:
            self._send_raw(b"", 0x8)
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass


# ============================================================
#  Gateway loop
# ============================================================
def run():
    if not _token:
        print('[bot] no token — call bot("...") first')
        return
    try:
        ws = _WS(GW_HOST, GW_PATH)
    except Exception as e:
        print("[bot] cannot connect to Discord: %s" % e)
        return

    seq = {"v": None}
    stop = threading.Event()

    # HELLO (op 10)
    try:
        hello = json.loads(ws.recv())
    except Exception as e:
        print("[bot] gateway error: %s" % e)
        ws.close()
        return
    interval = hello.get("d", {}).get("heartbeat_interval", 41250) / 1000.0

    def heartbeat():
        while not stop.is_set():
            time.sleep(interval)
            if stop.is_set():
                break
            try:
                ws.send_text(json.dumps({"op": 1, "d": seq["v"]}))
            except Exception:
                break

    threading.Thread(target=heartbeat, daemon=True).start()

    # IDENTIFY (op 2)
    ws.send_text(json.dumps({
        "op": 2,
        "d": {
            "token": _token,
            "intents": INTENTS,
            "properties": {"os": "linux", "browser": "aminakawa", "device": "aminakawa"},
        },
    }))

    print("[bot] connected — waiting for messages (Ctrl+C to stop)")
    try:
        while True:
            packet = json.loads(ws.recv())
            op = packet.get("op")
            if packet.get("s") is not None:
                seq["v"] = packet["s"]

            if op == 1:            # server requests a heartbeat now
                ws.send_text(json.dumps({"op": 1, "d": seq["v"]}))
            elif op == 11:         # heartbeat ack
                pass
            elif op == 7:          # reconnect
                print("[bot] Discord asked to reconnect — stopping.")
                break
            elif op == 9:          # invalid session
                print("[bot] invalid session (check token / enable Message Content Intent).")
                break
            elif op == 0:          # dispatch
                if packet.get("t") == "MESSAGE_CREATE":
                    d = packet.get("d", {})
                    author = d.get("author", {})
                    if author.get("bot"):
                        continue   # ignore other bots and self
                    content = d.get("content", "")
                    channel = d.get("channel_id", "")
                    name = author.get("username", "")
                    if _handler:
                        try:
                            _handler(content, channel, name)
                        except Exception as e:
                            print("[bot] handler error: %s" % e)
    except KeyboardInterrupt:
        print("\n[bot] stopping...")
    except Exception as e:
        print("[bot] gateway error: %s" % e)
    finally:
        stop.set()
        ws.close()


# ============================================================
#  self-test (framing only — no network)
# ============================================================
def _selftest():
    # masked client frame round-trip
    frame = _encode_frame(b'{"op":1,"d":null}', 0x1, mask=True)
    bio = io.BytesIO(frame)
    def rx(n):
        b = bio.read(n)
        if len(b) < n:
            raise EOFError("short read")
        return b
    fin, op, payload = _read_frame(rx)
    assert fin and op == 0x1 and payload == b'{"op":1,"d":null}', (fin, op, payload)

    # unmasked server-style frame + larger payload (16-bit length)
    big = ("x" * 300).encode()
    bio2 = io.BytesIO(_encode_frame(big, 0x1, mask=False))
    fin, op, payload = _read_frame(bio2.read)
    assert payload == big and len(payload) == 300

    print("amk_discord framing self-test: OK")


if __name__ == "__main__":
    _selftest()
