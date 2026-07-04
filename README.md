<div align="center">

# ⚡ Overkube

**Kubernetes Resource Right-Sizing & Cost Optimization Engine**

*Kubecost tells you what you're wasting. Overkube tells you what to change, how confident it is, and opens the PR to do it.*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB.svg)](https://python.org)
[![K8s](https://img.shields.io/badge/Kubernetes-1.28+-326CE5.svg)](https://kubernetes.io)

</div>

---

## 🎯 What Is This?

Overkube is an **end-to-end Kubernetes FinOps tool** that:

1. **Collects** real-time CPU and memory metrics from your cluster
2. **Analyzes** resource usage with percentile-based statistical models
3. **Recommends** right-sized `requests` and `limits` with a **confidence score** (0–100)
4. **Quantifies** wasted spend in `$/month` using configurable cloud pricing
5. **Closes the loop** by auto-generating a GitHub PR with the optimized manifest

### How It Differs from Existing Tools

| Feature | Kubernetes VPA | Goldilocks / Kubecost | **Overkube** |
|---------|---------------|----------------------|-------------|
| Recommendations | ✅ | ✅ | ✅ |
| Confidence scoring | ❌ | ❌ | ✅ **0–100 score** |
| $ waste quantification | ❌ | ✅ | ✅ |
| Auto-PR to fix manifests | ❌ | ❌ | ✅ **GitOps loop** |
| Silent pod restarts | ⚠️ Yes | ❌ | ❌ Human-reviewable |

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────┐
│                    kind cluster                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐               │
│  │ svc-01   │ │ svc-02   │ │  ...×10  │  Simulated    │
│  │ (over)   │ │ (under)  │ │          │  microservices │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘               │
│       │             │            │                     │
│  ┌────▼─────────────▼────────────▼─────┐               │
│  │       metrics-server + Prometheus    │               │
│  └────────────────┬────────────────────┘               │
└───────────────────┼────────────────────────────────────┘
                    │  K8s API / PromQL
          ┌─────────▼─────────┐
          │   Backend (FastAPI) │
          │  ┌───────────────┐ │
          │  │   Collector    │ │  → Polls every 30s
          │  │   Recommender  │ │  → P90/P99 engine
          │  │   Pricing      │ │  → $/month calculator
          │  └───────┬───────┘ │
          │          │ SQLite  │
          └──────────┼─────────┘
                     │  REST API
          ┌──────────▼─────────┐
          │  Frontend (React)   │
          │  Dashboard + Charts │
          └─────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- **Docker** (Docker Desktop or equivalent)
- **[kind](https://kind.sigs.k8s.io/)** — Kubernetes in Docker
- **kubectl**
- **Python 3.11+**

### 1. Create the Cluster

```bash
kind create cluster --config cluster/kind-config.yaml
```

This spins up a 3-node cluster (1 control-plane + 2 workers) named `overkube`.

### 2. Deploy the Monitoring Stack

```bash
# Metrics Server (enables kubectl top)
kubectl apply -f cluster/manifests/monitoring/metrics-server.yaml

# Prometheus (container-level metrics)
kubectl apply -f cluster/manifests/monitoring/prometheus.yaml
```

### 3. Deploy the Simulated Services

```bash
# Create the namespace
kubectl apply -f cluster/manifests/namespace.yaml

# Deploy all 10 microservices
kubectl apply -f cluster/manifests/service-01-api-gateway.yaml
kubectl apply -f cluster/manifests/service-02-user-service.yaml
kubectl apply -f cluster/manifests/service-03-inventory-service.yaml
kubectl apply -f cluster/manifests/service-04-order-processor.yaml
kubectl apply -f cluster/manifests/service-05-payment-service.yaml
kubectl apply -f cluster/manifests/service-06-search-service.yaml
kubectl apply -f cluster/manifests/service-07-auth-service.yaml
kubectl apply -f cluster/manifests/service-08-notification-service.yaml
kubectl apply -f cluster/manifests/service-09-recommendation-engine.yaml
kubectl apply -f cluster/manifests/service-10-report-generator.yaml
```

Verify everything is running:

```bash
kubectl get pods -n overkube
kubectl get pods -n monitoring
kubectl get pods -n kube-system | grep metrics
```

### 4. Generate Traffic

```bash
# Terminal 1: Port-forward all services
# Windows:
.\scripts\port-forward-all.ps1
# Linux/Mac:
bash scripts/port-forward-all.sh

# Terminal 2: Start the traffic simulator
pip install -r cluster/load-gen/requirements.txt
python cluster/load-gen/traffic_sim.py --all --duration 3600
```

#### Traffic Patterns

| Pattern | Description | Use Case |
|---------|-------------|----------|
| `steady` | Constant rate with slight jitter | Normal API traffic |
| `spiky` | Idle windows + intense bursts | Batch jobs, cron tasks |
| `sine` | Sine wave over the duration | Daily business-hour cycle |
| `idle` | Near-zero background noise | Off-hours / maintenance |
| `mixed` | Cycles through all patterns | Stress testing |

Single-service example:

```bash
python cluster/load-gen/traffic_sim.py \
    --target http://localhost:9001 \
    --pattern spiky \
    --duration 600 \
    --cpu-ms 30 \
    --mem-kb 50
```

---

## 📦 Service Inventory

| # | Service | Profile | Requests (CPU/Mem) | Expected Real Usage | Gap |
|---|---------|---------|-------------------|--------------------|----|
| 01 | api-gateway | 🔴 Over | 200m / 256Mi | ~50m / 64Mi | **4× over** |
| 02 | user-service | 🔴 Over | 150m / 192Mi | ~30m / 48Mi | **4× over** |
| 03 | inventory-service | 🔴 Over | 200m / 256Mi | ~40m / 50Mi | **4× over** |
| 04 | order-processor | 🟡 Under | 60m / 90Mi | ~120m / 180Mi | **50% short** |
| 05 | payment-service | 🟡 Under | 50m / 80Mi | ~100m / 160Mi | **50% short** |
| 06 | search-service | 🟡 Under | 70m / 100Mi | ~140m / 200Mi | **50% short** |
| 07 | auth-service | 🟢 Right | 50m / 64Mi | ~50m / 64Mi | **Optimal** |
| 08 | notification-service | 🟢 Right | 30m / 48Mi | ~30m / 48Mi | **Optimal** |
| 09 | recommendation-engine | 🔵 Spiky | 100m / 128Mi | Bursty 0–300m | **Variable** |
| 10 | report-generator | 🔵 Spiky | 80m / 96Mi | Sine 0–250m | **Variable** |

---

## 🛠️ Tech Stack

- **Cluster**: kind, kubectl, metrics-server, Prometheus
- **Backend**: Python 3.11, FastAPI, SQLAlchemy, NumPy
- **Frontend**: React, Vite, Recharts, Tailwind CSS
- **Infra**: Docker, docker-compose
- **CI/CD**: GitHub Actions

---

## 📁 Project Structure

```
overkube/
├── cluster/
│   ├── kind-config.yaml              # 3-node kind cluster
│   ├── manifests/
│   │   ├── namespace.yaml
│   │   ├── echo-app/                  # Lightweight burn server
│   │   ├── service-01..10-*.yaml      # 10 simulated microservices
│   │   └── monitoring/                # metrics-server + Prometheus
│   └── load-gen/
│       ├── traffic_sim.py             # Configurable traffic generator
│       └── requirements.txt
├── backend/                           # FastAPI + recommendation engine
├── frontend/                          # React dashboard
├── scripts/
│   ├── port-forward-all.ps1           # Windows helper
│   └── port-forward-all.sh            # Linux/Mac helper
├── docs/
└── README.md
```

---

## 📋 Roadmap

- [x] **Day 1** — Cluster setup, 10 service manifests, traffic simulator
- [ ] **Day 2** — Metrics collection pipeline + synthetic historical data
- [ ] **Day 3** — Recommendation engine (P90/P99 + confidence scoring)
- [ ] **Day 4** — FastAPI backend with full REST API
- [ ] **Day 5** — React dashboard with data visualization
- [ ] **Day 6** — Auto-PR generator + polish
- [ ] **Day 7** — README, demo recording, deployment

---

## 📄 License

MIT — see [LICENSE](LICENSE) for details.
