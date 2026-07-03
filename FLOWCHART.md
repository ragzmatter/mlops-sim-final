# FLOWCHART.md — Full Project, Stage by Stage

```
[GitHub Repo]
   | git push
   v
[GitHub Actions: build-test-push]  (cloud runner)
   - build + test scripts, push image to GHCR
   |
   v
[GitHub Actions: trigger-kfp]  (SELF-HOSTED RUNNER — on your laptop)
   tool: self-hosted runner (reaches localhost:8888 + :30050 directly)
   - docker build -> push to Local Registry -> kind load
   - compiles pipeline.yaml, submits KFP run via API
   OUTPUT: image in registry, KFP run triggered
   |
   v
[Local Registry]  (k8s Deployment, kube-system, NodePort 30050)
   OUTPUT: mlops-sim:latest image, pulled by all pipeline pods
   |
   v
========== KUBEFLOW PIPELINE (orchestrates everything below, ns: kubeflow) ==========
   |
   v
[Feature Engineering]  (KFP component)
   tool: pandas/sklearn (feature_engineering.py)
   INPUT:  raw_ad_data.csv
   OUTPUT: features.parquet, feature_pipeline.joblib
   |
   v
[Feast Materialize]  (KFP component — MOVED IN from standalone Job)
   tool: Feast SDK (materialize.py), talks to Redis (infra, ns: mlops-data)
   INPUT:  features.parquet
   OUTPUT: features_with_ts.parquet, registry.db, Redis keys (online store)
   |
   v
[Training]  (KFP component, logs to MLflow)
   tool: scikit-learn + MLflow (train_mlflow.py)
   INPUT:  features.parquet
   OUTPUT: model.joblib, test_split.parquet, MLflow run (params+metrics+model)
   |
   v
[Evaluation]  (KFP component, gate)
   tool: scikit-learn + MLflow Registry (evaluate_mlflow.py)
   INPUT:  model.joblib, test_split.parquet
   OUTPUT: eval_metrics.json, model_approved.flag, MLflow model -> "Production"
   | (only if approved)
   v
[Approval Gate]  -> fails pipeline if AUC below threshold (blocks everything below)
   |
   v
[Deploy Trigger]  (KFP component)
   tool: kubectl rollout restart (inside pod)
   OUTPUT: serving Deployment restarted with new model.joblib
   |
   v
[Argo CD Sync]  (Application CR, ns: argocd — infra, watches git for manifest changes)
   tool: Argo CD
   INPUT:  kustomization.yaml + all manifests
   OUTPUT: reconciled live cluster state
   |
   v
[Kubernetes Deployment]  (Deployment+Service, ns: mlops-serving)
   |
   v
[FastAPI Serving]  (app_feast.py, NodePort 30080)
   tool: FastAPI + Feast online lookup (Redis)
   INPUT:  ad_id -> Redis features -> model.joblib
   OUTPUT: click_probability response, /metrics endpoint
   |
   v
[Prometheus]  (Deployment, ns: mlops-monitoring, NodePort 30090 — infra)
   INPUT:  /metrics from serving pods
   OUTPUT: time-series metrics (predictions_total, latency, feast_hits)
   |
   v
[Grafana]  (Deployment, ns: mlops-monitoring, NodePort 30030 — infra)
   INPUT:  Prometheus queries
   OUTPUT: visual dashboards
   |
   v
[Drift Detection]  (Deployment, monitor.py, ns: mlops-monitoring — infra, always-on)
   tool: PSI calculation (numpy)
   OUTPUT: drift_log.json, retrain_trigger.flag (if PSI > 0.2)
   |
   v
[KFP Recurring Run]  (REPLACES old standalone CronJob)
   tool: kubeflow/recurring_run.py registers a scheduled run of the SAME
         ctr_pipeline DAG used above — shows up in KFP's Recurring Runs tab
   INPUT:  cron schedule (e.g. every 2 hrs)
   OUTPUT: new pipeline Run -> same DAG as above -> new model if approved
   |
   v
   (loop back to Serving — deploy_trigger_op picks up new model automatically)
```

## What changed vs earlier version
| Item | Before | Now |
|---|---|---|
| Feast materialize | standalone Job, manually applied | KFP component inside the DAG |
| Retraining | standalone CronJob (`retraining/cronjob.yaml`) | KFP Recurring Run (deprecated the CronJob file) |
| Image build/push | manual `docker build/tag/push` | automated by `trigger-kfp` job on self-hosted runner |
| CI -> KFP trigger | manual Python heredoc | automatic, runs on `git push` via self-hosted runner |


## YAML kind per stage — quick reference
| Stage | K8s Kind | File |
|---|---|---|
| Registry | Deployment + Service | registry/registry-grafana.yaml |
| Redis (infra only) | Deployment + Service | feast/redis-and-materialize-job.yaml |
| Feast materialize | KFP component (no YAML — Python in pipeline.py) | kubeflow/pipeline.py |
| Feature engineering | KFP component (was Job, now in-DAG) | kubeflow/pipeline.py |
| MLflow | Deployment + Service | mlflow/mlflow-deployment.yaml |
| Training | KFP component | kubeflow/pipeline.py |
| Evaluation | KFP component | kubeflow/pipeline.py |
| Argo CD app | Application (CRD) | argocd/application.yaml |
| Serving | Deployment + Service | serving/deployment_feast.yaml |
| Prometheus | Deployment+Service+ConfigMap | monitoring/prometheus.yaml |
| Grafana | Deployment + Service | registry/registry-grafana.yaml |
| Drift monitor | Deployment | monitoring/deployment.yaml |
| Retraining | KFP Recurring Run (was CronJob, now deprecated) | kubeflow/recurring_run.py |
| Namespaces/storage | Namespace, PV, PVC | namespaces/*.yaml |
