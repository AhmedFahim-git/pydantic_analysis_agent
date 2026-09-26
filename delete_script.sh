#!/bin/bash
set -euo pipefail

NAMESPACE="langfuse"
RELEASE="langfuse"

echo "Deleting Agent Sandbox CRDs"
kubectl delete -f https://github.com/kubernetes-sigs/agent-sandbox/releases/latest/download/sandbox-with-extensions.yaml

# echo "Uninstalling Langfuse Chart"
# helm uninstall "$RELEASE" --namespace "$NAMESPACE" --wait

echo "Deleting Langfuse secrets"
kubectl delete -f ./manifests/langfuse/secret.yaml

echo "Uninstalling Clickhouse Operator Chart"
helm uninstall clickhouse-operator --namespace clickhouse-operator

echo "Uninstalling Cert Manager Chart"
helm uninstall cert-manager --namespace cert-manager

echo "Uninstalling Postgresql Chart"
helm uninstall postgresql --namespace postgres-helm

echo "Deleting namespace"
kubectl delete -f ./manifests/langfuse/namespace.yaml
