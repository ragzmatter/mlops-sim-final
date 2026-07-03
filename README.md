# mlops-sim — Master Project (Final)

Start here. This is the up-to-date, consolidated version of everything built
across the whole session.

### Read in this order
1. **ORCHESTRATED_SETUP.md** — the real/production-style path. Install infra
   once, then `git push` does everything (includes self-hosted runner setup).
2. **MANUAL_VERIFICATION.md** — optional, stage-by-stage manual walkthrough
   for learning. Not needed once orchestrated mode works.
3. **FLOWCHART.md** — full visual flow, every stage's tool + YAML kind + I/O.
4. **SELF_HOSTED_RUNNER_SETUP.md** — detailed runner install (referenced by
   Stage 6 of ORCHESTRATED_SETUP.md).
5. **PIPELINE_STEPS_V2.md** — earlier, very granular 20-phase reference
   (still accurate for command syntax; superseded in structure by the 3 files
   above, kept for depth/troubleshooting detail).

### Folder map
```
mlops-sim/
├── README.md                      <- you are here
├── ORCHESTRATED_SETUP.md
├── MANUAL_VERIFICATION.md
├── FLOWCHART.md
├── SELF_HOSTED_RUNNER_SETUP.md
├── PIPELINE_STEPS_V2.md
├── Dockerfile                     <- bakes in CURRENT scripts only (mlflow+feast versions)
├── requirements.txt
├── kustomization.yaml
├── run_pipeline.sh                <- manual-path runner (see MANUAL_VERIFICATION.md)
├── kind/kind-config.yaml          <- ALL NodePorts: 30080/30090/30500/30050/30030
├── namespaces/                    <- namespaces.yaml, shared-storage.yaml
├── data/generate_dataset.py
├── feature-engineering/
│   ├── feature_engineering.py     <- active, used by KFP component
│   └── job.yaml                   <- manual-path only (see MANUAL_VERIFICATION.md)
├── feast/
│   ├── feature_repo/              <- feature_store.yaml, features.py
│   ├── materialize.py             <- active, now a KFP component (not standalone Job)
│   └── redis-and-materialize-job.yaml  <- Redis infra ONLY (materialize Job removed)
├── training/
│   ├── train_mlflow.py            <- ACTIVE (MLflow logging + registry)
│   └── job.yaml                   <- manual-path only, runs the mlflow version inside image
├── evaluation/
│   ├── evaluate_mlflow.py         <- ACTIVE (MLflow promotion to Production)
│   └── job.yaml                   <- manual-path only
├── mlflow/mlflow-deployment.yaml  <- infra, NodePort 30500
├── serving/
│   ├── app_feast.py               <- ACTIVE (Feast/Redis online lookup)
│   └── deployment_feast.yaml      <- ACTIVE
├── monitoring/
│   ├── monitor.py                 <- drift detection, always-on Deployment
│   ├── deployment.yaml
│   └── prometheus.yaml
├── registry/registry-grafana.yaml <- local registry (30050) + Grafana (30030)
├── kubeflow/
│   ├── pipeline.py                <- ACTIVE full DAG: feature-eng->feast->train->eval->deploy
│   └── recurring_run.py           <- ACTIVE, replaces old retraining CronJob
├── argocd/application.yaml
├── .github/workflows/ci.yaml      <- build-test-push (cloud) + trigger-kfp (self-hosted)
└── _deprecated/                   <- OLD files, not used anywhere, kept for reference only
    └── README.md                  <- explains what each old file was replaced by
```

## What's genuinely deprecated (do not use)
See `_deprecated/README.md` for the full table. Short version: anything in
`_deprecated/` was replaced by an MLflow-aware, Feast-aware, or
recurring-run-aware version sitting in the normal folders.

## What's still "manual path" on purpose (not deprecated, just optional)
`feature-engineering/job.yaml`, `training/job.yaml`, `evaluation/job.yaml`,
and `run_pipeline.sh` are intentionally kept — they're the hands-on learning
path described in MANUAL_VERIFICATION.md. They run the SAME current scripts
(via the Docker image), just triggered by you instead of by KFP. Safe to use
for debugging a single stage in isolation.
