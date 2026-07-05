"""
Overkube — Metrics Collector
==============================
Background service that polls the Kubernetes metrics-server API every
COLLECTOR_INTERVAL seconds and writes resource usage rows to the DB.

Architecture
------------
  CollectorService.run()          ← called once at app startup (asyncio task)
      └─ _collect_once()          ← one full scrape cycle
            ├─ _fetch_pod_metrics()   ← hits metrics.k8s.io/v1beta1/pods
            ├─ _fetch_deployment_spec()  ← reads Deployment resource envelopes
            ├─ _upsert_service()     ← ensures Service row exists
            └─ _write_sample()       ← inserts UsageSample row

The collector is intentionally fault-tolerant:
  - If the K8s API is unreachable, it logs the error and waits for the next tick.
  - Individual service failures are caught so a bad pod never drops the whole run.
  - Runs in an asyncio.sleep loop so it doesn't block the FastAPI event loop.

Units
-----
  CPU:    millicores  (1 vCPU = 1000 millicores)
  Memory: MiB         (1 MiB = 1024 * 1024 bytes)
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Service, SessionLocal, UsageSample, create_tables

logger = logging.getLogger(__name__)


# ── Unit Conversion Helpers ───────────────────────────────────────────────────

def _parse_cpu(cpu_str: Optional[str]) -> Optional[int]:
    """
    Convert a K8s CPU string to millicores (int).
    Examples: "250m" → 250,  "1" → 1000,  "0.5" → 500
    Returns None if the string is absent or unparseable.
    """
    if not cpu_str:
        return None
    cpu_str = cpu_str.strip()
    if cpu_str.endswith("m"):
        return int(cpu_str[:-1])
    try:
        return int(float(cpu_str) * 1000)
    except ValueError:
        logger.warning("Cannot parse CPU string: %r", cpu_str)
        return None


def _parse_mem(mem_str: Optional[str]) -> Optional[float]:
    """
    Convert a K8s memory string to MiB (float).
    Handles: Ki, Mi, Gi, K, M, G, and bare bytes.
    Returns None if the string is absent or unparseable.
    """
    if not mem_str:
        return None
    mem_str = mem_str.strip()
    units = {
        "Ki": 1 / 1024,
        "Mi": 1.0,
        "Gi": 1024.0,
        "K":  1 / 1.024 / 1024,  # 1000 bytes → MiB
        "M":  1000 / 1024,
        "G":  1000 * 1000 / 1024 / 1024,
    }
    for suffix, factor in units.items():
        if mem_str.endswith(suffix):
            try:
                return float(mem_str[: -len(suffix)]) * factor
            except ValueError:
                break
    try:
        return float(mem_str) / (1024 * 1024)  # bare bytes
    except ValueError:
        logger.warning("Cannot parse memory string: %r", mem_str)
        return None


# ── Kubernetes Client Factory ─────────────────────────────────────────────────

def _make_k8s_clients():
    """
    Return (CoreV1Api, AppsV1Api, CustomObjectsApi) loaded from the
    kubeconfig context named in settings.
    Raises if the kubeconfig / context is missing.
    """
    try:
        from kubernetes import client as k8s_client, config as k8s_config
    except ImportError as exc:
        raise RuntimeError(
            "The 'kubernetes' package is required.  pip install kubernetes"
        ) from exc

    try:
        k8s_config.load_kube_config(context=settings.kube_context)
    except k8s_config.ConfigException:
        # Running inside a pod — fall back to in-cluster config
        logger.info("kubeconfig not found, falling back to in-cluster config")
        k8s_config.load_incluster_config()

    return (
        k8s_client.CoreV1Api(),
        k8s_client.AppsV1Api(),
        k8s_client.CustomObjectsApi(),
    )


# ── Collector ─────────────────────────────────────────────────────────────────

class CollectorService:
    """
    Long-running async service.  Call ``await CollectorService().run()``
    from an asyncio task and it will loop indefinitely.
    """

    def __init__(self) -> None:
        self._core_v1: Any = None
        self._apps_v1: Any = None
        self._custom: Any = None
        self._k8s_ready = False

    def _init_k8s(self) -> bool:
        """Lazily initialise K8s clients (cluster may not be up at startup)."""
        if self._k8s_ready:
            return True
        try:
            self._core_v1, self._apps_v1, self._custom = _make_k8s_clients()
            self._k8s_ready = True
            logger.info(
                "K8s clients initialised (context=%s, namespace=%s)",
                settings.kube_context,
                settings.overkube_namespace,
            )
            return True
        except Exception as exc:
            logger.error("Failed to initialise K8s clients: %s", exc)
            return False

    # ── Public API ────────────────────────────────────────────────────────────

    async def run(self) -> None:
        """
        Entry point — polls indefinitely at COLLECTOR_INTERVAL seconds.
        Designed to be launched as an asyncio.Task from the FastAPI lifespan.
        """
        logger.info(
            "Collector starting (interval=%ds, namespace=%s)",
            settings.collector_interval,
            settings.overkube_namespace,
        )
        create_tables()

        while True:
            try:
                await self._collect_once()
            except Exception as exc:
                # Never let a bug crash the collector loop
                logger.exception("Unexpected error in collector: %s", exc)

            await asyncio.sleep(settings.collector_interval)

    # ── Private Helpers ───────────────────────────────────────────────────────

    async def _collect_once(self) -> None:
        """One full scrape cycle across all pods in the target namespace."""
        if not self._init_k8s():
            logger.warning("K8s not available — skipping collect cycle")
            return

        loop = asyncio.get_event_loop()
        namespace = settings.overkube_namespace

        # Run blocking K8s calls in a thread pool so we don't block the event loop
        try:
            pod_metrics = await loop.run_in_executor(
                None, self._fetch_pod_metrics, namespace
            )
            deployments = await loop.run_in_executor(
                None, self._fetch_deployments, namespace
            )
        except Exception as exc:
            logger.error("K8s API error during collect: %s", exc)
            return

        # Build a lookup: deployment_name → resource spec
        deploy_specs: dict[str, dict] = {
            d.metadata.name: self._extract_resource_spec(d)
            for d in deployments.items
        }

        # Build a lookup: pod_label_app → aggregated metrics
        # Pods for the same deployment share the app label
        agg_metrics = self._aggregate_pod_metrics(pod_metrics)

        ts = time.time()
        db: Session = SessionLocal()
        saved = 0

        try:
            for svc_name, spec in deploy_specs.items():
                metrics = agg_metrics.get(svc_name, {})

                try:
                    self._upsert_service(db, svc_name, namespace, spec)
                    self._write_sample(db, svc_name, namespace, ts, metrics, spec)
                    saved += 1
                except Exception as exc:
                    logger.error("Error saving sample for %s: %s", svc_name, exc)
                    db.rollback()
                    continue

            db.commit()
            logger.debug("Collected %d samples at ts=%.0f", saved, ts)

        finally:
            db.close()

    def _fetch_pod_metrics(self, namespace: str) -> list[dict]:
        """
        Call the metrics.k8s.io API (metrics-server) to get per-pod CPU/mem.
        Returns the raw items list.
        """
        resp = self._custom.list_namespaced_custom_object(
            group="metrics.k8s.io",
            version="v1beta1",
            namespace=namespace,
            plural="pods",
        )
        return resp.get("items", [])

    def _fetch_deployments(self, namespace: str):
        """List all Deployments in the namespace."""
        return self._apps_v1.list_namespaced_deployment(namespace=namespace)

    def _extract_resource_spec(self, deployment) -> dict:
        """
        Pull requests/limits from the first container of a Deployment.
        Returns a dict with keys: cpu_request, cpu_limit, mem_request, mem_limit.
        All values are in millicores / MiB (or None if unset).
        """
        containers = deployment.spec.template.spec.containers
        if not containers:
            return {}
        resources = containers[0].resources or {}

        requests = resources.requests or {}
        limits = resources.limits or {}

        return {
            "cpu_request": _parse_cpu(requests.get("cpu")),
            "cpu_limit":   _parse_cpu(limits.get("cpu")),
            "mem_request": _parse_mem(requests.get("memory")),
            "mem_limit":   _parse_mem(limits.get("memory")),
            "waste_profile": (
                deployment.metadata.labels or {}
            ).get("waste-profile"),
        }

    def _aggregate_pod_metrics(self, pod_metrics: list[dict]) -> dict[str, dict]:
        """
        Sum CPU and memory across all pods belonging to the same Deployment
        (identified by the 'app' label).
        Returns: {app_label: {cpu_usage_millicores, mem_usage_mb}}
        """
        agg: dict[str, dict] = {}

        for pod in pod_metrics:
            labels = pod.get("metadata", {}).get("labels", {})
            app_label = labels.get("app")
            if not app_label:
                continue

            cpu_total = 0
            mem_total = 0.0

            for container in pod.get("containers", []):
                usage = container.get("usage", {})
                cpu_total += _parse_cpu(usage.get("cpu")) or 0
                mem_total += _parse_mem(usage.get("memory")) or 0.0

            if app_label not in agg:
                agg[app_label] = {"cpu_usage_millicores": 0, "mem_usage_mb": 0.0}

            agg[app_label]["cpu_usage_millicores"] += cpu_total
            agg[app_label]["mem_usage_mb"] += mem_total

        return agg

    def _upsert_service(
        self,
        db: Session,
        name: str,
        namespace: str,
        spec: dict,
    ) -> None:
        """Insert or update the Service registry row."""
        svc = db.query(Service).filter_by(service_name=name, namespace=namespace).first()
        if svc is None:
            svc = Service(service_name=name, namespace=namespace)
            db.add(svc)

        svc.last_seen = time.time()
        svc.waste_profile = spec.get("waste_profile")
        svc.cpu_request = spec.get("cpu_request")
        svc.cpu_limit = spec.get("cpu_limit")
        svc.mem_request = spec.get("mem_request")
        svc.mem_limit = spec.get("mem_limit")

    def _write_sample(
        self,
        db: Session,
        name: str,
        namespace: str,
        ts: float,
        metrics: dict,
        spec: dict,
    ) -> None:
        """Insert a new UsageSample row."""
        sample = UsageSample(
            service_name=name,
            namespace=namespace,
            timestamp=ts,
            cpu_usage_millicores=metrics.get("cpu_usage_millicores"),
            mem_usage_mb=metrics.get("mem_usage_mb"),
            cpu_request=spec.get("cpu_request"),
            cpu_limit=spec.get("cpu_limit"),
            mem_request=spec.get("mem_request"),
            mem_limit=spec.get("mem_limit"),
        )
        db.add(sample)


# ── Singleton ─────────────────────────────────────────────────────────────────
collector = CollectorService()
