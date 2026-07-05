"""
Overkube — Synthetic Historical Data Backfill
==============================================
Generates 7 days of realistic usage_samples at 5-minute intervals so the
recommendation engine and dashboard have meaningful depth from day one,
even before the real collector has run for long.

The synthetic usage is derived from the same traffic profiles defined in
``cluster/load-gen/traffic_sim.py`` so the data is internally consistent:
  - Over-provisioned services show flat, low usage well below their requests
  - Under-provisioned services show usage that frequently exceeds their requests
  - Right-sized services show usage close to requests
  - Spiky services show a bursty / sine-wave pattern with high variance

Usage
-----
    # Backfill 7 days (default)
    python -m backend.app.backfill

    # Backfill a custom number of days
    python -m backend.app.backfill --days 14

    # Wipe existing synthetic data and re-generate
    python -m backend.app.backfill --days 7 --reset

    # Dry-run: print stats without writing to DB
    python -m backend.app.backfill --dry-run
"""

from __future__ import annotations

import argparse
import logging
import math
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Allow running as a script directly from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.config import settings
from app.models import Service, SessionLocal, UsageSample, create_tables

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Service Profile Definitions ───────────────────────────────────────────────
# Each profile drives the synthetic generator.
# (cpu_request_m, cpu_limit_m, mem_request_mib, mem_limit_mib,
#  base_cpu_pct, noise_pct, pattern, waste_profile)
#
# base_cpu_pct = typical usage as a fraction of cpu_request
# noise_pct    = ± random noise applied to base
# pattern      = "steady" | "spiky" | "sine" | "idle"

@dataclass
class ServiceProfile:
    service_name: str
    cpu_request:  int    # millicores
    cpu_limit:    int    # millicores
    mem_request:  int    # MiB
    mem_limit:    int    # MiB
    base_cpu_pct: float  # fraction of cpu_request used on average
    base_mem_pct: float  # fraction of mem_request used on average
    noise_pct:    float  # ± random noise (fraction)
    pattern:      str    # traffic shape
    waste_profile: str


SERVICE_PROFILES: list[ServiceProfile] = [
    # ── Over-provisioned (usage ≈ 25% of request) ─────────────────────────────
    ServiceProfile("api-gateway",           200, 500, 256, 512,  0.25, 0.25, 0.08, "steady",  "over-provisioned"),
    ServiceProfile("user-service",          150, 400, 192, 384,  0.22, 0.22, 0.07, "steady",  "over-provisioned"),
    ServiceProfile("inventory-service",     200, 500, 256, 512,  0.23, 0.20, 0.06, "steady",  "over-provisioned"),
    # ── Under-provisioned (usage > request → throttling risk) ─────────────────
    ServiceProfile("order-processor",        60, 100,  90, 128,  1.80, 1.70, 0.15, "steady",  "under-provisioned"),
    ServiceProfile("payment-service",        50,  80,  80, 120,  1.75, 1.65, 0.12, "steady",  "under-provisioned"),
    ServiceProfile("search-service",         70, 120, 100, 150,  1.85, 1.80, 0.18, "steady",  "under-provisioned"),
    # ── Right-sized (usage ≈ request) ─────────────────────────────────────────
    ServiceProfile("auth-service",           50,  80,  64,  96,  0.90, 0.88, 0.10, "steady",  "right-sized"),
    ServiceProfile("notification-service",   30,  50,  48,  72,  0.88, 0.85, 0.08, "steady",  "right-sized"),
    # ── Spiky (high variance) ─────────────────────────────────────────────────
    ServiceProfile("recommendation-engine", 100, 300, 128, 256,  0.60, 0.55, 0.40, "spiky",   "spiky"),
    ServiceProfile("report-generator",       80, 250,  96, 200,  0.55, 0.50, 0.35, "sine",    "spiky"),
]


# ── Usage Generators ──────────────────────────────────────────────────────────

def _steady_cpu(profile: ServiceProfile, _elapsed_frac: float) -> float:
    """Flat usage with Gaussian noise."""
    base = profile.cpu_request * profile.base_cpu_pct
    noise = base * profile.noise_pct * random.gauss(0, 1)
    return max(1.0, base + noise)


def _spiky_cpu(profile: ServiceProfile, elapsed_frac: float) -> float:
    """
    Bursty pattern: long idle windows + short intense bursts.
    Cycle length: 1/8 of the total duration.
    """
    cycle = elapsed_frac * 8.0
    cycle_pos = cycle % 1.0
    base = profile.cpu_request * profile.base_cpu_pct

    if cycle_pos < 0.65:
        # Idle window (65% of cycle)
        return max(1.0, base * 0.05 + random.gauss(0, base * 0.02))
    else:
        # Burst window (35% of cycle)
        burst = base * 2.8 * profile.base_cpu_pct
        return max(1.0, burst + random.gauss(0, burst * 0.20))


def _sine_cpu(profile: ServiceProfile, elapsed_frac: float) -> float:
    """
    Sine wave over the full duration, simulating daily business-hour cycle.
    Peak at 60% of the elapsed window, trough at the start/end.
    """
    phase = 2 * math.pi * elapsed_frac
    multiplier = 0.15 + 0.85 * (0.5 + 0.5 * math.sin(phase - math.pi / 2))
    base = profile.cpu_request * profile.base_cpu_pct
    val = base * multiplier
    noise = val * profile.noise_pct * random.gauss(0, 0.5)
    return max(1.0, val + noise)


def _generate_cpu(profile: ServiceProfile, elapsed_frac: float) -> int:
    """Dispatch to the correct pattern generator."""
    if profile.pattern == "spiky":
        raw = _spiky_cpu(profile, elapsed_frac)
    elif profile.pattern == "sine":
        raw = _sine_cpu(profile, elapsed_frac)
    else:
        raw = _steady_cpu(profile, elapsed_frac)
    return max(1, round(raw))


def _generate_mem(profile: ServiceProfile, elapsed_frac: float) -> float:
    """
    Memory usage: follows the same pattern as CPU but with less variance
    (memory tends to be more stable than CPU).
    Slow drift upward over time, then occasional GC drops.
    """
    base = profile.mem_request * profile.base_mem_pct
    drift = base * 0.10 * elapsed_frac           # gradual growth
    gc_drop = -drift if random.random() < 0.03 else 0.0  # 3% chance of GC
    noise = base * profile.noise_pct * 0.4 * random.gauss(0, 1)
    return max(1.0, base + drift + gc_drop + noise)


# ── Backfill Core ─────────────────────────────────────────────────────────────

def generate_backfill(
    days: int = 7,
    interval_seconds: int = 300,   # 5 minutes
) -> list[dict]:
    """
    Generate synthetic usage_samples for all SERVICE_PROFILES.
    Returns a list of row dicts — does NOT write to the DB.
    """
    now = time.time()
    start = now - days * 86400
    total_seconds = days * 86400
    steps = total_seconds // interval_seconds

    rows: list[dict] = []

    for profile in SERVICE_PROFILES:
        logger.info(
            "  Generating %d samples for %s (pattern=%s)",
            steps, profile.service_name, profile.pattern,
        )
        for i in range(steps):
            ts = start + i * interval_seconds
            elapsed_frac = i / max(steps - 1, 1)   # 0.0 → 1.0

            cpu = _generate_cpu(profile, elapsed_frac)
            mem = _generate_mem(profile, elapsed_frac)

            rows.append({
                "service_name":        profile.service_name,
                "namespace":           settings.overkube_namespace,
                "timestamp":           ts,
                "cpu_usage_millicores": cpu,
                "mem_usage_mb":        round(mem, 2),
                "cpu_request":         profile.cpu_request,
                "cpu_limit":           profile.cpu_limit,
                "mem_request":         profile.mem_request,
                "mem_limit":           profile.mem_limit,
            })

    return rows


def run_backfill(
    days: int = 7,
    interval_seconds: int = 300,
    reset: bool = False,
    dry_run: bool = False,
) -> None:
    """
    Orchestrate the full backfill: generate rows and optionally write to DB.
    """
    logger.info("=" * 60)
    logger.info("Overkube Synthetic Backfill")
    logger.info("  Days        : %d", days)
    logger.info("  Interval    : %ds", interval_seconds)
    logger.info("  Services    : %d", len(SERVICE_PROFILES))
    logger.info("  DB          : %s", settings.database_url)
    logger.info("=" * 60)

    create_tables()

    if reset and not dry_run:
        db = SessionLocal()
        try:
            deleted = db.query(UsageSample).delete()
            svc_deleted = db.query(Service).delete()
            db.commit()
            logger.info("Reset: deleted %d samples + %d service rows", deleted, svc_deleted)
        finally:
            db.close()

    rows = generate_backfill(days=days, interval_seconds=interval_seconds)
    total = len(rows)
    logger.info("Generated %d total rows", total)

    # Print a quick stats summary per service
    from collections import defaultdict
    import statistics

    by_service: dict[str, list] = defaultdict(list)
    for r in rows:
        by_service[r["service_name"]].append(r["cpu_usage_millicores"])

    logger.info("\n%-30s  %6s  %6s  %6s  %6s  %s",
                "Service", "P50", "P90", "P99", "Max", "Profile")
    logger.info("-" * 80)
    for profile in SERVICE_PROFILES:
        vals = sorted(by_service[profile.service_name])
        n = len(vals)
        p50 = vals[int(n * 0.50)]
        p90 = vals[int(n * 0.90)]
        p99 = vals[int(n * 0.99)]
        mx  = vals[-1]
        logger.info(
            "%-30s  %5dm  %5dm  %5dm  %5dm  req=%dm",
            profile.service_name, p50, p90, p99, mx, profile.cpu_request,
        )

    if dry_run:
        logger.info("\nDry-run mode — nothing written to DB.")
        return

    # Upsert Service rows
    db = SessionLocal()
    try:
        for profile in SERVICE_PROFILES:
            svc = db.query(Service).filter_by(
                service_name=profile.service_name,
                namespace=settings.overkube_namespace,
            ).first()
            if svc is None:
                svc = Service(
                    service_name=profile.service_name,
                    namespace=settings.overkube_namespace,
                )
                db.add(svc)

            svc.waste_profile = profile.waste_profile
            svc.last_seen = time.time()
            svc.cpu_request = profile.cpu_request
            svc.cpu_limit = profile.cpu_limit
            svc.mem_request = profile.mem_request
            svc.mem_limit = profile.mem_limit

        db.commit()
        logger.info("Upserted %d Service rows", len(SERVICE_PROFILES))
    finally:
        db.close()

    # Bulk-insert samples in batches of 1000
    BATCH = 1000
    db = SessionLocal()
    try:
        written = 0
        for i in range(0, total, BATCH):
            batch = rows[i : i + BATCH]
            db.bulk_insert_mappings(UsageSample, batch)
            db.commit()
            written += len(batch)
            if written % 10_000 == 0:
                logger.info("  Inserted %d / %d rows...", written, total)

        logger.info("✅ Backfill complete: %d samples written.", written)
    finally:
        db.close()


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Overkube synthetic data backfill",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--days", type=int, default=7,
                   help="How many days of history to generate (default: 7)")
    p.add_argument("--interval", type=int, default=300,
                   help="Sample interval in seconds (default: 300 = 5 min)")
    p.add_argument("--reset", action="store_true",
                   help="Delete existing synthetic data before inserting")
    p.add_argument("--dry-run", action="store_true",
                   help="Print stats but do not write to DB")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_backfill(
        days=args.days,
        interval_seconds=args.interval,
        reset=args.reset,
        dry_run=args.dry_run,
    )
