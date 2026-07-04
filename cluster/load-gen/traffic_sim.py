"""
Overkube — Traffic Simulator
=============================
Generates configurable HTTP traffic against the simulated microservices
running inside the kind cluster. Supports multiple traffic patterns to
drive realistic and varied resource usage for the right-sizing engine.

Patterns
--------
- steady   : constant-rate requests (even load)
- spiky    : short intense bursts separated by idle windows
- sine     : daily-cycle sine wave simulating business-hour traffic
- idle     : very low background traffic (near-zero)
- mixed    : randomly cycles through all patterns over time

Usage
-----
    python traffic_sim.py --target http://localhost:8080 --pattern steady --duration 600
    python traffic_sim.py --all --duration 3600          # hit all services via kubectl port-forward
    python traffic_sim.py --help
"""

from __future__ import annotations

import argparse
import math
import random
import sys
import time
import threading
import signal
from dataclasses import dataclass
from typing import Optional

try:
    import requests
except ImportError:
    print("ERROR: 'requests' is required.  pip install requests")
    sys.exit(1)


# ── Service Registry ──────────────────────────────────────────────────────────

# Maps service name → (default traffic pattern, base CPU burn ms, base MEM burn kb)
SERVICE_PROFILES: dict[str, tuple[str, int, int]] = {
    # Over-provisioned (low actual usage)
    "api-gateway":           ("steady",  8,   0),
    "user-service":          ("steady",  5,   0),
    "inventory-service":     ("steady",  6,   0),
    # Under-provisioned (high actual usage → will throttle)
    "order-processor":       ("steady", 25,  50),
    "payment-service":       ("steady", 20,  40),
    "search-service":        ("steady", 30,  60),
    # Right-sized (moderate, stable)
    "auth-service":          ("steady", 10,   0),
    "notification-service":  ("steady",  5,   0),
    # Spiky
    "recommendation-engine": ("spiky",  40, 100),
    "report-generator":      ("sine",   35,  80),
}

# Default base URL template when using --all mode (kubectl port-forward based)
# Each service gets forwarded to a unique local port
SERVICE_PORT_MAP: dict[str, int] = {
    "api-gateway":           9001,
    "user-service":          9002,
    "inventory-service":     9003,
    "order-processor":       9004,
    "payment-service":       9005,
    "search-service":        9006,
    "auth-service":          9007,
    "notification-service":  9008,
    "recommendation-engine": 9009,
    "report-generator":      9010,
}


# ── Traffic Pattern Generators ────────────────────────────────────────────────

@dataclass
class RequestSpec:
    """What a single simulated request looks like."""
    cpu_ms: int = 10
    mem_kb: int = 0
    delay_after: float = 1.0   # seconds to wait before the next request


def _steady(base_cpu: int, base_mem: int, elapsed: float, duration: float) -> RequestSpec:
    """Constant load — slight jitter to avoid looking robotic."""
    return RequestSpec(
        cpu_ms=max(1, base_cpu + random.randint(-2, 2)),
        mem_kb=max(0, base_mem + random.randint(-5, 5)),
        delay_after=round(random.uniform(0.8, 1.2), 2),
    )


def _spiky(base_cpu: int, base_mem: int, elapsed: float, duration: float) -> RequestSpec:
    """
    Alternates between idle windows (10s) and intense bursts (5s).
    Cycle = 15s total.
    """
    cycle_pos = elapsed % 15.0
    if cycle_pos < 10.0:
        # Idle window
        return RequestSpec(cpu_ms=1, mem_kb=0, delay_after=round(random.uniform(1.5, 3.0), 2))
    else:
        # Burst window
        return RequestSpec(
            cpu_ms=base_cpu * 3 + random.randint(0, 20),
            mem_kb=base_mem * 2 + random.randint(0, 30),
            delay_after=round(random.uniform(0.05, 0.2), 2),
        )


def _sine(base_cpu: int, base_mem: int, elapsed: float, duration: float) -> RequestSpec:
    """
    Sine-wave pattern simulating a daily business-hour cycle.
    Compressed to fit the --duration window: one full cycle = duration.
    """
    phase = (2 * math.pi * elapsed) / max(duration, 1)
    multiplier = 0.5 + 0.5 * math.sin(phase)   # 0.0 → 1.0
    return RequestSpec(
        cpu_ms=max(1, int(base_cpu * multiplier) + random.randint(-2, 2)),
        mem_kb=max(0, int(base_mem * multiplier) + random.randint(-3, 3)),
        delay_after=round(0.3 + (1 - multiplier) * 2.0, 2),  # faster at peak
    )


def _idle(base_cpu: int, base_mem: int, elapsed: float, duration: float) -> RequestSpec:
    """Near-zero background traffic."""
    return RequestSpec(cpu_ms=1, mem_kb=0, delay_after=round(random.uniform(3.0, 6.0), 2))


PATTERN_FNS = {
    "steady": _steady,
    "spiky":  _spiky,
    "sine":   _sine,
    "idle":   _idle,
}


def get_request_spec(pattern: str, base_cpu: int, base_mem: int,
                     elapsed: float, duration: float) -> RequestSpec:
    """Resolve a pattern name to a concrete RequestSpec."""
    if pattern == "mixed":
        # Rotate through patterns every 30s
        choices = ["steady", "spiky", "sine", "idle"]
        idx = int(elapsed / 30.0) % len(choices)
        pattern = choices[idx]
    fn = PATTERN_FNS[pattern]
    return fn(base_cpu, base_mem, elapsed, duration)


# ── Worker ────────────────────────────────────────────────────────────────────

_shutdown = threading.Event()


def _signal_handler(sig, frame):
    print("\n⏹  Shutting down gracefully...")
    _shutdown.set()


def run_traffic(target_url: str, pattern: str, duration: float,
                base_cpu: int, base_mem: int, label: str = "") -> None:
    """
    Send traffic to a single target for `duration` seconds.
    Runs in a loop until duration expires or _shutdown is set.
    """
    session = requests.Session()
    start = time.monotonic()
    total_requests = 0
    total_errors = 0
    tag = f"[{label}]" if label else ""

    print(f"🚀 {tag} Starting  pattern={pattern}  target={target_url}  duration={duration}s")

    while not _shutdown.is_set():
        elapsed = time.monotonic() - start
        if elapsed >= duration:
            break

        spec = get_request_spec(pattern, base_cpu, base_mem, elapsed, duration)

        try:
            resp = session.get(
                f"{target_url}/burn",
                params={"cpu_ms": spec.cpu_ms, "mem_kb": spec.mem_kb},
                timeout=5,
            )
            total_requests += 1
            if resp.status_code != 200:
                total_errors += 1
        except requests.RequestException:
            total_errors += 1
            total_requests += 1

        _shutdown.wait(timeout=spec.delay_after)

    elapsed_total = time.monotonic() - start
    rps = total_requests / max(elapsed_total, 0.001)
    print(
        f"✅ {tag} Done  "
        f"requests={total_requests}  errors={total_errors}  "
        f"elapsed={elapsed_total:.1f}s  rps={rps:.1f}"
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Overkube Traffic Simulator — generate load against cluster services",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Hit a single service
  python traffic_sim.py --target http://localhost:9001 --pattern steady --duration 600

  # Hit ALL services concurrently (requires kubectl port-forward for each)
  python traffic_sim.py --all --duration 3600

  # Override CPU/memory burn per request
  python traffic_sim.py --target http://localhost:9004 --pattern spiky \\
      --duration 300 --cpu-ms 50 --mem-kb 80
        """,
    )

    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--target", type=str, help="Base URL of a single service (e.g. http://localhost:9001)")
    mode.add_argument("--all", action="store_true", help="Hit all services concurrently via port-forward ports 9001-9010")

    p.add_argument("--pattern", type=str, default="steady",
                    choices=["steady", "spiky", "sine", "idle", "mixed"],
                    help="Traffic pattern to apply (default: steady; ignored in --all mode where each service uses its profile)")
    p.add_argument("--duration", type=int, default=300, help="How long to run in seconds (default: 300)")
    p.add_argument("--cpu-ms", type=int, default=None, help="Override base CPU burn per request (milliseconds)")
    p.add_argument("--mem-kb", type=int, default=None, help="Override base memory burn per request (KB)")

    return p.parse_args()


def main() -> None:
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    args = parse_args()

    if args.all:
        # ── Multi-service mode ──
        print(f"🌐 Overkube Traffic Sim — ALL SERVICES — duration={args.duration}s")
        print("   Make sure you have kubectl port-forward running for each service.")
        print("   See README for the one-liner to set them all up.\n")

        threads: list[threading.Thread] = []
        for svc_name, (default_pattern, base_cpu, base_mem) in SERVICE_PROFILES.items():
            port = SERVICE_PORT_MAP[svc_name]
            url = f"http://localhost:{port}"
            cpu = args.cpu_ms if args.cpu_ms is not None else base_cpu
            mem = args.mem_kb if args.mem_kb is not None else base_mem

            t = threading.Thread(
                target=run_traffic,
                args=(url, default_pattern, args.duration, cpu, mem, svc_name),
                daemon=True,
            )
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

    else:
        # ── Single-service mode ──
        base_cpu = args.cpu_ms if args.cpu_ms is not None else 10
        base_mem = args.mem_kb if args.mem_kb is not None else 0
        run_traffic(args.target, args.pattern, args.duration, base_cpu, base_mem)


if __name__ == "__main__":
    main()
