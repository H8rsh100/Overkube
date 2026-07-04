"""
Lightweight Flask echo server used by all simulated microservices.
Responds to GET / with a JSON payload identifying the service.
Includes a /burn endpoint that artificially consumes CPU/memory
so the load generator can drive realistic resource usage.
"""

import os
import time
import math
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

SERVICE_NAME = os.environ.get("SERVICE_NAME", "unknown")


@app.route("/")
def index():
    """Health / echo endpoint."""
    return jsonify({
        "service": SERVICE_NAME,
        "status": "ok",
        "timestamp": time.time(),
    })


@app.route("/health")
def health():
    return "OK", 200


@app.route("/burn", methods=["GET", "POST"])
def burn():
    """
    Artificial resource consumer.
    Query params:
      cpu_ms  — approximate milliseconds of CPU spin (default 10)
      mem_kb  — KB of memory to allocate and hold briefly (default 0)
    """
    cpu_ms = int(request.args.get("cpu_ms", 10))
    mem_kb = int(request.args.get("mem_kb", 0))

    # CPU burn — tight math loop
    deadline = time.monotonic() + (cpu_ms / 1000.0)
    x = 0.0
    while time.monotonic() < deadline:
        x += math.sin(x + 1.0)

    # Memory burn — allocate a bytearray
    blob = bytearray(mem_kb * 1024) if mem_kb > 0 else b""

    return jsonify({
        "service": SERVICE_NAME,
        "burned_cpu_ms": cpu_ms,
        "burned_mem_kb": mem_kb,
        "blob_len": len(blob),
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
