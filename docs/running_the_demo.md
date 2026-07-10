# ⚡ How to Practically Use & Demo Overkube

This guide walks you through a live demonstration of Overkube from scratch. It is designed to help you verify everything is running, test the auto-PR loop locally, and walk recruiters or interviewers through the project structure.

---

## 🏗️ Step 1: Spin Up the Cluster

Ensure you have Docker and `kind` installed, then create the cluster:

```bash
kind create cluster --config cluster/kind-config.yaml
```

Verify your cluster has three nodes:
```bash
kubectl get nodes
# Expected output:
# overkube-control-plane   Ready    control-plane   ...
# overkube-worker          Ready    <none>          ...
# overkube-worker2         Ready    <none>          ...
```

---

## 📈 Step 2: Deploy Monitoring & Simulated Services

Apply all monitoring manifests:
```bash
# Metrics Server (enables cpu/memory tracking)
kubectl apply -f cluster/manifests/monitoring/metrics-server.yaml

# Prometheus (stores metric logs)
kubectl apply -f cluster/manifests/monitoring/prometheus.yaml
```

Wait 30 seconds for the metrics server to start collecting stats, then check:
```bash
kubectl top nodes
```

Next, deploy the 10 microservices with varying provision gaps (over-provisioned, under-provisioned, spiky, and optimal):
```bash
# Create the namespace
kubectl apply -f cluster/manifests/namespace.yaml

# Apply all microservice manifests
kubectl apply -f cluster/manifests/
```

Confirm all pods are running:
```bash
kubectl get pods -n overkube
```

---

## 🚦 Step 3: Run Port-Forwarding & Traffic Generator

To let the traffic generator hit the microservices, start port-forwarding:

- **Windows (PowerShell)**:
  ```powershell
  .\scripts\port-forward-all.ps1
  ```
- **Linux/Mac**:
  ```bash
  bash scripts/port-forward-all.sh
  ```

In a new terminal window, start the traffic simulator to load the services and generate real usage:
```bash
cd cluster/load-gen
pip install -r requirements.txt
python traffic_sim.py --all --duration 3600
```
This runs a 1-hour load test simulating steady loads, spiky workloads, and sine waves matching each service's target profile.

---

## 💻 Step 4: Run the Backend API & Backfill Data

To see the recommender engine in action immediately without waiting 7 days for historical metrics, run the historical backfill script to populate 7 days of realistic usage samples:

```bash
# Move to backend folder and set up environment
cd backend
pip install -r requirements.txt
copy .env.example .env

# Populate SQLite with 7 days of historical samples
python -m app.backfill
```

Now, start the FastAPI API server:
```bash
uvicorn app.main:app --reload --port 8000
```
Check that the interactive API docs are live at `http://localhost:8000/docs`.

---

## 🎨 Step 5: Start the React Frontend

Open a new terminal window, move to the frontend folder, install dependencies, and start the development server:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser. You will be greeted by the **Overkube Dark HUD Dashboard**:
- **Recoverable Spend**: Highlights the animated count-up of potential monthly savings.
- **Service Grid**: Shows all 10 services and their resource status.
- **Service Drawer**: Click any service (e.g. `api-gateway`) to slide in the drawer. Switch between the **CPU** and **MEM** views to inspect actual usage lines vs configured requests and limits.
- **Info Panel**: Click **"How it works"** in the top navigation to view the methodology panel.

---

## 🔄 Step 6: Test the GitOps Auto-PR Loop (Dry-Run vs Real PR)

By default, the application runs in **dry-run** mode. When you click **"Apply Recommendation"** in the drawer:
1. The backend simulates the GitOps process.
2. It returns a local diff (e.g., `200m → 40m CPU`) and displays a success toast message in the UI.

### To Enable Live GitHub Pull Requests:
1. Create a Personal Access Token (classic) on GitHub with `repo` scopes.
2. Fork the `Overkube` repository to your personal GitHub account.
3. Edit your `backend/.env` file with your credentials:
   ```env
   GITHUB_TOKEN=ghp_your_actual_token_here
   GITHUB_OWNER=your_github_username
   GITHUB_REPO=Overkube
   GITHUB_MANIFESTS_DIR=cluster/manifests
   GITHUB_DRY_RUN=false
   ```
4. Restart your backend (`uvicorn app.main:app --reload`).
5. Open the frontend, choose `api-gateway`, and click **"Apply Recommendation"**.
6. Check your GitHub account — you will see a newly opened Pull Request patching `cluster/manifests/service-01-api-gateway.yaml` with the right-sized resource values!
