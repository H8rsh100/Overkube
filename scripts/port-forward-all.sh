#!/usr/bin/env bash
# ─────────────────────────────────────────────────
# Port-forward all Overkube services to local ports
# Run this in a separate terminal before the traffic simulator
# ─────────────────────────────────────────────────

set -euo pipefail

NAMESPACE="overkube"

declare -A SERVICES=(
    ["api-gateway"]=9001
    ["user-service"]=9002
    ["inventory-service"]=9003
    ["order-processor"]=9004
    ["payment-service"]=9005
    ["search-service"]=9006
    ["auth-service"]=9007
    ["notification-service"]=9008
    ["recommendation-engine"]=9009
    ["report-generator"]=9010
)

PIDS=()

cleanup() {
    echo ""
    echo "⏹  Stopping all port-forwards..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    echo "   Done."
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "🔗 Starting port-forward for all Overkube services..."
echo ""

for svc in "${!SERVICES[@]}"; do
    port="${SERVICES[$svc]}"
    echo "  → $svc  localhost:$port → :8080"
    kubectl port-forward "svc/$svc" "${port}:8080" -n "$NAMESPACE" &
    PIDS+=($!)
done

echo ""
echo "✅ All port-forwards started. Press Ctrl+C to stop."
echo "   Run traffic simulator:  python cluster/load-gen/traffic_sim.py --all --duration 600"
echo ""

wait
