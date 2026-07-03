# MLOps Full Pipeline — Start to End Steps

## Architecture
```
Git Push → GitHub Actions → Docker Build → Local Registry → Kubeflow Pipeline
  → Feature Job → Training Job → MLflow Log → Evaluation Job → MLflow Registry
  → Approval Gate → Argo CD Sync → Serving Deployment → Prometheus → Grafana
  → Drift Detection → Retraining CronJob
```

## Port Map (localhost)
| Service        | Port  |
|----------------|-------|
| Model API      | 30080 |
| MLflow UI      | 30500 |
| Prometheus     | 30090 |
| Grafana        | 30030 |
| Local Registry | 30050 |

---

## Phase 1 — One-time cluster setup

```bash
# 1. Create kind cluster
kind create cluster --name mlops-sim --config kind/kind-config.yaml
kubectl get nodes   # confirm Ready

# 2. Namespaces + storage
kubectl apply -f namespaces/namespaces.yaml
kubectl apply -f namespaces/shared-storage.yaml

# 3. Local registry
kubectl apply -f registry/registry-grafana.yaml

# 4. MLflow tracking server
kubectl apply -f mlflow/mlflow-deployment.yaml
kubectl rollout status deployment/mlflow -n mlops-training

# 5. Monitoring stack
kubectl apply -f monitoring/prometheus.yaml
kubectl apply -f monitoring/deployment.yaml
# Grafana already applied in step 3

# 6. Install Argo CD
kubectl create namespace argocd
kubectl apply -n argocd -f \
  https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl rollout status deployment/argocd-server -n argocd --timeout=180s

# 7. Install Kubeflow Pipelines (standalone)
kubectl apply -k "github.com/kubeflow/pipelines/manifests/kustomize/cluster-scoped-resources?ref=2.0.0"
kubectl apply -k "github.com/kubeflow/pipelines/manifests/kustomize/env/platform-agnostic-pns?ref=2.0.0"
kubectl rollout status deployment/ml-pipeline -n kubeflow --timeout=300s
# KFP UI: kubectl port-forward svc/ml-pipeline-ui -n kubeflow 8888:80
```

---

## Phase 2 — GitHub + CI setup (one-time)

```bash
# 8. Push repo to GitHub
git init && git add . && git commit -m "initial"
git branch -M main
git remote add origin https://github.com/<YOU>/mlops-sim.git
git push -u origin main
# GitHub Actions CI triggers automatically on push (see .github/workflows/ci.yaml)
# It builds, tests, and pushes image to ghcr.io/<YOU>/mlops-sim:latest
```

---

## Phase 3 — Build and load image

```bash
# 9. Build image locally (or let CI do it, then pull)
docker build -t mlops-sim:local .

# 10. Tag and push to local in-cluster registry
docker tag mlops-sim:local localhost:30050/mlops-sim:latest
docker push localhost:30050/mlops-sim:latest

# 11. Load directly into kind nodes (avoids pull in air-gapped setup)
kind load docker-image mlops-sim:local --name mlops-sim
```

---

## Phase 4 — Run Kubeflow Pipeline

```bash
# 12. Compile pipeline
pip install kfp
python3 kubeflow/pipeline.py   # produces pipeline.yaml

# 13. Submit pipeline
kubectl port-forward svc/ml-pipeline-ui -n kubeflow 8888:80 &
# Open http://localhost:8888 -> Upload pipeline.yaml -> Create Run
# OR via CLI:
pip install kfp
python3 - <<'EOF'
import kfp
client = kfp.Client(host="http://localhost:8888")
client.create_run_from_pipeline_package(
    "pipeline.yaml",
    arguments={"mlflow_uri": "http://localhost:30500"}
)
EOF
```

KFP automatically runs each stage pod and only triggers the next when the
previous pod exits 0 (success). This is the orchestration DAG.

---

## Phase 5 — Watch the pipeline run

```bash
# 14. KFP UI: http://localhost:8888  — see DAG execution, pod logs per stage

# 15. MLflow UI: http://localhost:30500
#     Experiments -> ctr-pipeline -> see run, params, metrics, model artifact
#     Models -> ctr-model -> version promoted to "Production" after eval passes

# 16. Check artifacts on shared store
ls /tmp/mlops-artifacts/
# raw_ad_data.csv, features.parquet, model.joblib, eval_metrics.json,
# model_approved.flag, run_id.txt, mlflow/, mlflow-artifacts/
```

---

## Phase 6 — ArgoCD GitOps sync

```bash
# 17. Register app with Argo CD (after editing repoURL in application.yaml)
kubectl apply -f argocd/application.yaml

# 18. Get Argo CD admin password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d; echo

# 19. Port-forward and log in
kubectl port-forward svc/argocd-server -n argocd 8080:443
# https://localhost:8080  admin / <password>

# Argo CD watches your git repo. When manifests change it auto-applies them.
# Test selfHeal: kubectl edit deployment/model-serving -n mlops-serving
# Argo CD reverts it within ~30s
```

---

## Phase 7 — Serving + observability

```bash
# 20. Apply serving deployment (if not already via ArgoCD)
kubectl apply -f serving/deployment.yaml
kubectl rollout status deployment/model-serving -n mlops-serving

# 21. Predict
curl -X POST http://localhost:30080/predict \
  -H 'Content-Type: application/json' \
  -d '{"num_1":55,"num_2":1.2,"num_3":40,
       "cat_1":"device_1","cat_2":"site_3",
       "cat_3":"campaign_2","cat_4":"geo_1"}'
# returns: {"click_probability": 0.3X}

# 22. Raw Prometheus metrics
curl http://localhost:30080/metrics

# 23. Prometheus UI: http://localhost:30090
#     Query: predictions_total, prediction_latency_seconds_bucket

# 24. Grafana: http://localhost:30030  (admin/admin)
#     Add data source -> Prometheus -> URL: http://prometheus-svc:9090
#     Create dashboard panels: predictions_total, latency p99, prediction_score
```

---

## Phase 8 — Drift + retraining

```bash
# 25. Watch drift monitor
kubectl logs -n mlops-monitoring deploy/drift-monitor -f
# PSI climbs every 30s. Once > 0.2, flag is written.

# 26. Check flag
cat /tmp/mlops-artifacts/drift_log.json
cat /tmp/mlops-artifacts/retrain_trigger.flag  # appears after drift

# 27. CronJob fires every 2 min, checks flag, reruns full pipeline in-pod
kubectl get jobs -n mlops-training
kubectl logs -n mlops-training job/<retraining-cronjob-xxxxx>
# If new model passes eval gate: flag cleared, model.joblib updated
# Serving pod picks up new model on next rollout restart

# 28. Trigger rollout to pick up new model
kubectl rollout restart deployment/model-serving -n mlops-serving
```

---

## Phase 9 — Full CI/CD loop test (everything stitched)

```bash
# 29. Make a code change (e.g. change AUC_THRESHOLD in evaluate.py to 0.50)
git add . && git commit -m "lower eval threshold"
git push origin main
# -> GitHub Actions fires: build -> test -> push image to ghcr.io
# -> Locally: docker build + kind load + kubectl rollout restart
# -> Argo CD sees no manifest change (only code changed), stays Synced
# -> For a manifest change: edit retraining/cronjob.yaml schedule, push
#    -> Argo CD auto-applies the new CronJob schedule
```

---

## Teardown
```bash
kind delete cluster --name mlops-sim
rm -rf /tmp/mlops-artifacts
```

---

## What each tool does in one line
| Tool | Role |
|---|---|
| **kind** | Local Kubernetes cluster on your laptop |
| **GitHub Actions** | CI — builds, tests, pushes Docker image on every commit |
| **Local Registry** | Stores built images inside the cluster (no DockerHub needed) |
| **Kubeflow Pipelines** | Orchestrates stage Jobs in a DAG — each stage triggers the next only on success |
| **MLflow** | Logs params/metrics per run; Model Registry promotes approved models to "Production" |
| **Argo CD** | GitOps — reconciles K8s cluster state to match your git repo manifests |
| **FastAPI** | Serves predictions + exposes /metrics endpoint |
| **Prometheus** | Scrapes /metrics from serving pods |
| **Grafana** | Visualises Prometheus metrics as dashboards |
| **Drift monitor** | PSI-based check every 30s; writes trigger flag when drift detected |
| **CronJob** | Scheduled retraining pod that checks the flag and reruns pipeline if set |

## Time estimate
| Phase | Time |
|---|---|
| Cluster + all infra up (Phases 1–3) | 3–4 hrs |
| Kubeflow pipeline running end-to-end (Phase 4–5) | 2–3 hrs |
| Argo CD + GitOps loop working (Phase 6) | 1–2 hrs |
| Serving + Grafana dashboard live (Phase 7) | 1 hr |
| Drift + retraining observed (Phase 8) | 1 hr |
| Full CI/CD loop test (Phase 9) | 1 hr |
| **Total** | **~10–12 hrs** |

---

## Feast Commands — Feature Engineering Stage

```bash
# 1. Install feast with redis support
pip install "feast[redis]"

# 2. After feature_engineering.py writes features.parquet, run materialize.py
#    which does the following internally — shown here as raw commands too:

# 2a. Apply feature definitions to registry
feast -c feast/feature_repo apply
# Creates/updates registry.db, validates feature_store.yaml + features.py

# 2b. Materialize offline -> online (Redis) up to now
feast -c feast/feature_repo materialize-incremental $(date -u +"%Y-%m-%dT%H:%M:%S")
# Reads features_with_ts.parquet, pushes all rows into Redis keyed by ad_id

# 2c. Verify what's in the registry
feast -c feast/feature_repo feature-views list
feast -c feast/feature_repo entities list

# 2d. Spot-check a feature value in Redis directly
redis-cli -h localhost GET "ad_features:ad_id:42"

# In Kubernetes (after feast-materialize Job completes):
kubectl logs -n mlops-data job/feast-materialize
kubectl exec -n mlops-data deploy/redis -- redis-cli KEYS "*" | head -20
kubectl exec -n mlops-data deploy/redis -- redis-cli DBSIZE
# Should show N keys = number of rows materialized
```

---

## Feast Commands — Model Serving Stage

```bash
# Serving pod uses Feast SDK inline (app_feast.py). Equivalent raw commands:

# 1. Fetch features for a single entity from online store (Redis)
python3 - << 'PYEOF'
from feast import FeatureStore
store = FeatureStore(repo_path="feast/feature_repo")
fv = store.get_online_features(
    features=[
        "ad_features:num_1", "ad_features:num_2", "ad_features:num_3",
        "ad_features:cat_1", "ad_features:cat_2", "ad_features:cat_3",
        "ad_features:cat_4",
    ],
    entity_rows=[{"ad_id": 42}]
).to_dict()
print(fv)
PYEOF

# 2. Batch fetch from offline store (for retraining / evaluation, not serving)
python3 - << 'PYEOF'
import pandas as pd
from datetime import datetime, timezone
from feast import FeatureStore
store = FeatureStore(repo_path="feast/feature_repo")
entity_df = pd.DataFrame({"ad_id": [0,1,2,3,4],
                           "event_timestamp": [datetime.now(timezone.utc)]*5})
training_df = store.get_historical_features(
    entity_df=entity_df,
    features=["ad_features:num_1","ad_features:num_2","ad_features:num_3",
              "ad_features:cat_1","ad_features:cat_2","ad_features:cat_3","ad_features:cat_4"]
).to_df()
print(training_df.head())
PYEOF

# 3. Hit the serving endpoint using Feast online path
curl -X POST http://localhost:30080/predict \
  -H 'Content-Type: application/json' \
  -d '{"ad_id": 42}'

# 4. Confirm Feast hit counter in Prometheus
curl -s http://localhost:30080/metrics | grep feast_online_hits_total

# In Kubernetes — verify serving pod can reach Redis:
kubectl exec -n mlops-serving deploy/model-serving -- \
  python3 -c "
import redis, os
r = redis.Redis(host='redis-svc.mlops-data.svc.cluster.local', port=6379)
print('Redis ping:', r.ping())
print('Keys in store:', r.dbsize())
"

# Check serving logs for Feast lookups
kubectl logs -n mlops-serving deploy/model-serving -f
```

---

## Feast Full Flow Sequence (both stages together)

```
[feature_engineering.py]
  writes → /mnt/artifacts/features.parquet

[materialize.py  /  feast-materialize Job]
  reads  → features.parquet
  adds   → ad_id (entity key), event_timestamp
  writes → features_with_ts.parquet  (offline store source)
  runs   → feast apply          (registers schema in registry.db)
  runs   → feast materialize    (pushes rows to Redis online store)
  result → Redis: ad_id:0 → {num_1, num_2, ..., cat_4}
                  ad_id:1 → {num_1, num_2, ..., cat_4}
                  ... N rows

[app_feast.py  /  model-serving Deployment]
  receives → POST /predict  {ad_id: 42}
  calls    → store.get_online_features([ad_id:42])  → Redis lookup ~1ms
  runs     → model.predict_proba(features)
  returns  → {click_probability: 0.34}
```
