<div align="center">

# ⚡ Overkube

**Kubernetes Resource Right-Sizing & Cost Optimization Engine**

*Kubecost tells you what you're wasting. Overkube tells you what to change, grades its confidence, and opens the Pull Request to fix it.*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB.svg)](https://python.org)
[![K8s](https://img.shields.io/badge/Kubernetes-1.28+-326CE5.svg)](https://kubernetes.io)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg)](https://reactjs.org)

</div>

---

## 🎯 The Problem

In modern cloud environments, over-provisioning of Kubernetes resources is a primary driver of wasted cloud spend. Application developers often configure container `requests` and `limits` defensively to handle arbitrary peaks. This results in clusters running at 10–20% average resource utilization, while organizations pay cloud providers for 100% of the allocated capacity.

Existing solutions fall short:
1. **Silent Auto-Resizers (e.g., Kubernetes VPA)**: Dynamically resize containers but cause silent pod restarts which degrade application availability.
2. **Analysis-Only Dashboards (e.g., Kubecost, Goldilocks)**: Quantify waste but leave the operational burden of manually modifying YAML manifests and testing to the platform team.

## 💡 The Solution

**Overkube** bridges this gap. It is an end-to-end Kubernetes FinOps engine that:
1. **Collects** real-time CPU and memory metrics from your cluster.
2. **Analyzes** resource usage with percentile-based statistical models (P90/P99).
3. **Recommends** right-sized `requests` and `limits` accompanied by a rigorous **confidence score** (0–100).
4. **Quantifies** wasted spend in `$/month` using configurable cloud pricing.
5. **Closes the loop** by auto-generating a GitHub Pull Request with the optimized GitOps manifest.

---

## 🏗️ Architecture

```text
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
                    │          SQLite DB           │ (app/models.py)
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

---

## 🛠️ Tech Stack

- **Infrastructure**: Kubernetes (kind), kubectl, metrics-server, Prometheus
- **Backend**: Python 3.11, FastAPI, SQLAlchemy, PyGithub
- **Frontend**: React, Vite, Tailwind CSS v4, Recharts
- **Deployment**: Docker, docker-compose

---

## 🚀 Getting Started

To run a live demonstration of Overkube locally, you will need **Docker** and **[kind](https://kind.sigs.k8s.io/)** installed.

### 1. Spin Up the Cluster & Deploy Services
```bash
# Create local cluster
kind create cluster --config cluster/kind-config.yaml

# Deploy monitoring tools (metrics-server, prometheus)
kubectl apply -f cluster/manifests/monitoring/metrics-server.yaml
kubectl apply -f cluster/manifests/monitoring/prometheus.yaml

# Deploy 10 simulated microservices
kubectl apply -f cluster/manifests/namespace.yaml
kubectl apply -f cluster/manifests/
```

### 2. Generate Simulated Traffic
Overkube needs real data to analyze. Run the included load generator:
```bash
# Terminal 1: Start port-forwarding
.\scripts\port-forward-all.ps1  # Windows
# OR: bash scripts/port-forward-all.sh  # Linux/Mac

# Terminal 2: Generate load
cd cluster/load-gen
pip install -r requirements.txt
python traffic_sim.py --all --duration 3600
```

### 3. Start the Backend API
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env

# Seed database with 7 days of historical mock data
python -m app.backfill

# Start API
uvicorn app.main:app --reload --port 8000
```

### 4. Start the Frontend Dashboard
```bash
cd frontend
npm install
npm run dev
```
Navigate to `http://localhost:5173` to view the FinOps dashboard.

---

## 🤖 GitOps Pull Request Automation

By default, the application runs in a safe **dry-run** mode. When you click **"Apply Recommendation"** in the UI, the backend will calculate the exact diff but will not open a PR.

To enable live PR automation:
1. Create a GitHub Personal Access Token with `repo` scope.
2. Edit your `backend/.env` file:
   ```env
   GITHUB_TOKEN=ghp_your_token
   GITHUB_OWNER=your_github_username
   GITHUB_REPO=Overkube
   GITHUB_MANIFESTS_DIR=cluster/manifests
   GITHUB_DRY_RUN=false
   ```
3. Restart the backend. Click "Apply Recommendation" in the dashboard, and a branch, commit, and Pull Request will be automatically generated in your repository.

---

## 📖 Further Reading

- [**Capstone Report**](docs/capstone_report.md) - Deep dive into the P90/P99 statistical methodology and Confidence Score mathematical models.
- [**Demo Guide**](docs/running_the_demo.md) - Full step-by-step walkthrough for interview demonstrations.

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
