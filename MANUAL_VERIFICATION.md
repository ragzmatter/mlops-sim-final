# MANUAL_VERIFICATION.md
Run each stage by hand, in order, verifying output before moving to next. Use this to learn — not needed once orchestrated mode (KFP) works.

## 1. Feature Engineering
```bash
kubectl apply -f feature-engineering/job.yaml
kubectl wait --for=condition=complete job/feature-engineering -n mlops-data --timeout=120s
kubectl logs -n mlops-data job/feature-engineering
docker exec mlops-sim-worker ls /mnt/artifacts/   # expect features.parquet
```

## 2. Feast Materialization
```bash
kubectl wait --for=condition=complete job/feast-materialize -n mlops-data --timeout=180s
kubectl logs -n mlops-data job/feast-materialize
kubectl exec -n mlops-data deploy/redis -- redis-cli DBSIZE   # expect 50000
```

## 3. Training
```bash
kubectl apply -f training/job.yaml
kubectl wait --for=condition=complete job/model-training -n mlops-training --timeout=120s
kubectl logs -n mlops-training job/model-training
docker exec mlops-sim-worker cat /mnt/artifacts/run_id.txt
# verify in MLflow UI: http://localhost:30500 -> Experiments -> ctr-pipeline
```

## 4. Evaluation
```bash
kubectl apply -f evaluation/job.yaml
kubectl wait --for=condition=complete job/model-evaluation -n mlops-training --timeout=120s
kubectl logs -n mlops-training job/model-evaluation
docker exec mlops-sim-worker cat /mnt/artifacts/model_approved.flag
# verify in MLflow UI: Models -> ctr-model -> stage Production
```

## 5. Serving
```bash
kubectl apply -f serving/deployment_feast.yaml
kubectl rollout status deployment/model-serving -n mlops-serving --timeout=120s
curl http://localhost:30080/health
curl -X POST http://localhost:30080/predict -H 'Content-Type: application/json' -d '{"ad_id": 42}'
```

## 6. Monitoring
```bash
kubectl apply -f monitoring/prometheus.yaml
kubectl apply -f monitoring/deployment.yaml
curl -s http://localhost:30080/metrics | grep predictions_total
# http://localhost:30090/targets -> model-serving = UP
# http://localhost:30030 -> Grafana dashboard
```

## 7. Drift + Retraining
```bash
kubectl logs -n mlops-monitoring deploy/drift-monitor -f
docker exec mlops-sim-worker cat /mnt/artifacts/drift_log.json
kubectl apply -f retraining/cronjob.yaml
kubectl get jobs -n mlops-training -w
```

## 8. Argo CD GitOps
```bash
kubectl apply -f argocd/application.yaml
# https://localhost:8080 -> Applications -> mlops-sim -> Synced/Healthy
```

## 9. Kubeflow orchestrated run (compare against manual results above)
```bash
python3 kubeflow/pipeline.py
python3 << 'EOF'
import kfp
client = kfp.Client(host="http://localhost:8888")
run = client.create_run_from_pipeline_package("pipeline.yaml",
    arguments={"mlflow_uri": "http://mlflow-svc.mlops-training.svc.cluster.local:5000"})
print(run.run_id)
EOF
# http://localhost:8888 -> Runs -> confirm same artifacts produced
```
