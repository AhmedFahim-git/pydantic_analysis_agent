#!/bin/bash
set -euo pipefail

NAMESPACE="langfuse"
RELEASE="langfuse"
POSTGRESQL_CHART_VERSION="18.12.2"
LANGFUSE_CHART_VERSION="2.0.0"
CERT_MANAGER_CHART_VERSION="v1.20.2"
CLICKHOUSE_CHART_VERSION="0.0.5"

echo "Creating namespace"
kubectl apply -f ./manifests/langfuse/namespace.yaml

echo "Installing Postgresql"
helm upgrade --install postgresql \
    oci://registry-1.docker.io/bitnamicharts/postgresql \
    --version "$POSTGRESQL_CHART_VERSION" \
    --namespace postgres-helm \
    --create-namespace \
    -f ./manifests/db/secret_values.yaml \
    --wait

echo "Installing cert-manager"
helm upgrade --install cert-manager \
    oci://quay.io/jetstack/charts/cert-manager \
    --version "$CERT_MANAGER_CHART_VERSION" \
    --namespace cert-manager \
    --create-namespace \
    --set crds.enabled=true

kubectl wait \
    --for=condition=Established \
    crd/certificates.cert-manager.io \
    crd/issuers.cert-manager.io \
    --timeout=120s

echo "Installing ClickHouse operator"
helm upgrade --install clickhouse-operator \
    oci://ghcr.io/clickhouse/clickhouse-operator-helm \
    --version "$CLICKHOUSE_CHART_VERSION" \
    --namespace clickhouse-operator \
    --create-namespace \
    --wait

kubectl wait \
    --for=condition=Established \
    crd/clickhouseclusters.clickhouse.com \
    crd/keeperclusters.clickhouse.com \
    --timeout=120s

echo "Applying Langfuse secrets"
kubectl apply -f ./manifests/langfuse/secret.yaml

echo "Installing/upgrading Langfuse"
helm upgrade --install "$RELEASE" \
    oci://ghcr.io/langfuse/langfuse-k8s/charts/langfuse \
    --version "$LANGFUSE_CHART_VERSION" \
    --namespace "$NAMESPACE" \
    -f ./manifests/langfuse/values.yaml \
    -f ./manifests/langfuse/resources.yaml \
    -f ./manifests/langfuse/secret_values.yaml \
    --timeout 30m

echo "Installing Agent Sandbox CRDs"
kubectl apply -f https://github.com/kubernetes-sigs/agent-sandbox/releases/latest/download/sandbox-with-extensions.yaml

echo "Done."
