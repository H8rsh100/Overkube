# ⚡ Overkube Capstone Report

## 1. Executive Summary & Problem Statement
In modern cloud environments, over-provisioning of Kubernetes resources is a primary driver of wasted cloud spend. Application developers often configure container `requests` and `limits` defensively to handle arbitrary peaks, or simply rely on default values. This results in clusters running at 10–20% average resource utilization, while organizations pay cloud providers for 100% of the allocated capacity.

Existing solutions fall into two main categories:
1. **Silent Auto-Resizers (e.g. Kubernetes VPA)**: Dynamically resize containers, but cause silent pod restarts which can degrade application availability and disrupt critical transactions.
2. **Analysis-Only Dashboards (e.g. Kubecost, Goldilocks)**: Quantify waste and display cost recommendations but do not close the loop. They leave the operational burden of manually modifying YAML manifests, testing, and opening GitOps pull requests to already overburdened platform engineering teams.

**Overkube** bridges this gap. It is an end-to-end Kubernetes FinOps engine that continuously collects actual CPU and memory usage, computes right-sized resource recommendations with statistical confidence scoring, and closes the GitOps loop by automatically opening Pull Requests targeting the manifest repository.

---

## 2. Technical Architecture & Component Breakdown

```
                    ┌──────────────────────────────┐
                    │       Kubernetes Cluster     │
                    │   (Simulated Microservices)  │
                    └──────────────┬───────────────┘
                                   │ K8s Metrics API
                                   ▼
                    ┌──────────────────────────────┐
                    │      Background Collector    │ (app/collector.py)
                    └──────────────┬───────────────┘
                                   │ SQLAlchemy WAL-mode
                                   ▼
                    ┌──────────────────────────────┐
                    │      SQLite/Postgres DB      │ (app/models.py)
                    └──────────────┬───────────────┘
                                   │ Query metrics
                                   ▼
                    ┌──────────────────────────────┐
                    │    Recommendation Engine     │ (app/recommender.py)
                    └──────────────┬───────────────┘
                                   │ FastAPI Routers
                                   ▼
                    ┌──────────────────────────────┐
                    │         FastAPI REST         │ (app/main.py)
                    └──────────────┬───────────────┘
                                   │ JSON HTTP
                                   ▼
                    ┌──────────────────────────────┐
                    │       React Dashboard        │ (Vite + Recharts)
                    └──────────────────────────────┘
```

- **Metrics Pipeline**: A background asyncio task polls the Kubernetes Metrics API (via the standard Python K8s client) every 30 seconds.
- **Persistent Storage**: Aggregated usage data, requests, and limits are written to a SQLite table `usage_samples`. Write-Ahead Logging (WAL) is enabled to support concurrent read/write transactions without database locks.
- **Statistical Recommender**: Computes optimal CPU and memory configurations based on historical usage samples using a P90 request and P99 limit methodology.
- **GitOps PR Engine**: Patches YAML manifests in GitOps repositories and automatically opens Pull Requests on GitHub using the PyGitHub library, with a dry-run fallback.

---

## 3. Recommendation Methodology & Math

Overkube uses a statistical approach to determine resource recommendations:

### CPU Request & Limit
- **CPU Request** = **90th Percentile (P90)** of all CPU usage samples. This handles 90% of observed loads, allowing the Kubernetes scheduler to place pods based on real usage patterns.
- **CPU Limit** = **max(P99 of CPU usage, 1.2 × CPU Request)**. This provides headroom for spiky workloads. Since exceeding a CPU limit results in throttling (performance degradation) rather than termination, we optimize for density while allowing burst capacity.

### Memory Request & Limit
- **Memory Request** = **90th Percentile (P90)** of memory usage samples.
- **Memory Limit** = **P99 of memory usage + 32 MiB safety margin**. Because memory is non-compressible, exceeding memory limits results in immediate Out-Of-Memory (OOM) kills. We bias on the side of safety and stability for memory allocations.

### Multi-Dimensional Confidence Score
A confidence score (0–100) is calculated for each recommendation to ensure teams can trust the GitOps changes:
1. **Sample Count (30%)**: Scores resource stability based on how many metrics points have been captured (maximum score at 2,016 samples, equivalent to 7 days of 5-minute intervals).
2. **Predictability / Volatility (50%)**: Measured using the Coefficient of Variation ($CV = \sigma / \mu$). Workloads with stable usage have low variance and high predictability, yielding a higher confidence score.
3. **Data Recency (20%)**: Stale historical samples degrade confidence linearly over a 7-day period.

---

## 4. Cost Estimation Formula
Cost impact is computed using standard AWS EC2 general-purpose instances blended on-demand rates, customizable via `pricing_config.json`:
- **vCPU Rate**: $0.04 per vCPU-hour
- **Memory Rate**: $0.005 per GB-hour

$$\text{Monthly Cost} = \left( \frac{\text{CPU Request (m)}}{1000} \times 0.04 + \frac{\text{Memory Request (MiB)}}{1024} \times 0.005 \right) \times 730 \text{ hours}$$

---

## 5. Future Work
- **PromQL Integration**: Add support for scraping metrics directly from Prometheus using PromQL queries for finer granularity.
- **Slack/Discord Webhooks**: Broadcast right-sizing recommendations directly to developer chat channels.
- **Machine Learning Forecasts**: Integrate predictive models (e.g. Prophet or LSTM) to forecast cyclical peaks and automatically adjust recommendations prior to predictable traffic surges.
