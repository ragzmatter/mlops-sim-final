# ORCHESTRATED_SETUP.md
Production-style flow: install infra once (Category A), let KFP own all pipeline
work (Category B). After setup, every future run = `git push`. Nothing manual.

## Stage 0 — Core Infra
```bash
docker ps
brew install kind kubectl
kind create cluster --name mlops-sim --config kind/kind-config.yaml
kubectl apply -f namespaces/namespaces.yaml
kubectl apply -f namespaces/shared-storage.yaml
```

## Stage 1 — Local Registry (infra)
```bash
kubectl apply -f registry/registry-grafana.yaml
```
(no manual docker build/push needed anymore — CI's `trigger-kfp` job does this, see Stage 6)

## Stage 2 — Redis (infra — Feast's online store backend)
```bash
kubectl apply -f feast/redis-and-materialize-job.yaml
```
Note: this file now contains ONLY Redis (Deployment+Service). The materialize
step itself moved into the pipeline as `feast_materialize_op()` — it's pipeline
work, not infra, so KFP creates/destroys that pod per run.

## Stage 3 — MLflow (infra)
```bash
kubectl apply -f mlflow/mlflow-deployment.yaml
kubectl rollout status deployment/mlflow -n mlops-training
kubectl port-forward svc/mlflow-svc -n mlops-training 30500:5000 &
```

## Stage 4 — Kubeflow Pipelines (the orchestrator itself — infra)
```bash

export PIPELINE_VERSION=2.16.1

kubectl apply -k "github.com/kubeflow/pipelines/manifests/kustomize/cluster-scoped-resources?ref=$PIPELINE_VERSION"
kubectl wait --for condition=established --timeout=60s crd/applications.app.k8s.io
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.18.2/cert-manager.yaml
kubectl wait --for=condition=Ready pod -l app.kubernetes.io/instance=cert-manager -n cert-manager --timeout=300s
kubectl apply -k "github.com/kubeflow/pipelines/manifests/kustomize/env/cert-manager/platform-agnostic-k8s-native?ref=$PIPELINE_VERSION"

kubectl port-forward svc/ml-pipeline-ui -n kubeflow 8888:80

# Alternatively, for multi-user environments with multiple teams or users requiring isolation and RBAC controls on who can access which pipelines (still not production-ready like the community distribution), you can use the multi-user Kubernetes native mode (requires Istio to be installed, so we strongly recommend using the community distribution instead):
# kubectl apply -k "github.com/kubeflow/pipelines/manifests/kustomize/env/cert-manager/platform-agnostic-multi-user-k8s-native?ref=$PIPELINE_VERSION"

```


## Stage 5 — Argo CD (infra)
```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl apply -f argocd/application.yaml
```

## Stage 6 — Self-Hosted GitHub Actions Runner (infra — closes CI -> KFP loop)
```bash
mkdir actions-runner && cd actions-runner
curl -o actions-runner-linux-x64.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.319.1/actions-runner-linux-x64-2.319.1.tar.gz
tar xzf actions-runner-linux-x64.tar.gz
./config.sh --url https://github.com/<YOU>/mlops-sim --token <TOKEN_FROM_GITHUB>
sudo ./svc.sh install && sudo ./svc.sh start
```
Full detail: SELF_HOSTED_RUNNER_SETUP.md. This runner lives on your laptop, so
it can reach `localhost:8888` (KFP) and `localhost:30050` (registry) directly —
that's the entire reason it's needed instead of GitHub's cloud runners.

## Stage 7 — Monitoring (infra)
```bash
kubectl apply -f monitoring/prometheus.yaml
kubectl apply -f monitoring/deployment.yaml     # drift monitor
kubectl port-forward svc/grafana-svc -n mlops-monitoring 30030:3000 &
```

## Stage 8 — Register the Recurring Run (one-time, replaces old CronJob)
```bash
python3 kubeflow/pipeline.py            # compile pipeline.yaml
python3 kubeflow/recurring_run.py       # registers scheduled retraining in KFP
```
This replaces `retraining/cronjob.yaml` (now deprecated — do not apply it).
Retraining now appears in KFP's "Recurring Runs" tab, same DAG as the main run.

## Stage 9 — Trigger (the only manual action ever again)
```bash
git push origin main
```
`ci.yaml` runs:
1. `build-test-push` (GitHub cloud) — build, smoke-test, push image to GHCR
2. `trigger-kfp` (self-hosted runner, on your laptop) — loads image into kind,
   compiles pipeline.yaml, submits a KFP run

KFP then runs: feature-eng -> feast materialize -> training (MLflow log)
-> evaluation (MLflow registry promote) -> deploy trigger -> Argo CD reconciles
serving if manifests changed. Drift monitor + recurring run handle retraining
continuously in the background, no further action from you.

## One-time installs summary
1. Docker, kind, kubectl
2. Local registry (manifest)
3. Redis (manifest)
4. MLflow (manifest)
5. Kubeflow Pipelines + kfp SDK
6. Argo CD
7. Self-hosted GitHub Actions runner
8. Prometheus + Grafana (manifests)
9. Register recurring run (one Python script, once)

After this: **every future run = `git push`.**
