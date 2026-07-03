# _deprecated/
These files are NOT used anywhere in the current setup. Kept only for
reference/comparison so you can see what changed and why. Do not apply or
import any of these.

| File | Why deprecated |
|---|---|
| train.py.OLD_pre-mlflow | Superseded by training/train_mlflow.py (adds MLflow logging + registry) |
| evaluate.py.OLD_pre-mlflow | Superseded by evaluation/evaluate_mlflow.py (adds MLflow promotion to Production) |
| app.py.OLD_pre-feast | Superseded by serving/app_feast.py (reads features from Feast/Redis online store instead of raw request body) |
| deployment.yaml.OLD_pre-feast | Superseded by serving/deployment_feast.yaml (points to app_feast.py) |
| cronjob.yaml.OLD_superseded-by-recurring-run | Superseded by kubeflow/recurring_run.py (retraining now runs as a KFP Recurring Run, same DAG/UI as the main pipeline) |
| retrain.py.OLD_superseded-by-recurring-run | Was the CronJob's entrypoint; no longer needed since kubeflow/pipeline.py is reused directly by the recurring run |

Current, active files are in their normal folders (training/train_mlflow.py,
evaluation/evaluate_mlflow.py, serving/app_feast.py, serving/deployment_feast.yaml,
kubeflow/recurring_run.py). The Dockerfile already only COPYs the active versions.
