"""
Registers ctr_pipeline as a KFP Recurring Run — replaces the standalone
retraining CronJob. Now retraining shows up in the same Experiments/Runs
view as every other pipeline execution, with full DAG + logs + artifacts.

Run once to register:  python3 kubeflow/recurring_run.py
"""
import kfp
from kfp.client import Client

KFP_HOST = "http://localhost:8888"
EXPERIMENT_NAME = "ctr-pipeline"
PIPELINE_PACKAGE = "pipeline.yaml"
CRON = "0 */2 * * *"   # every 2 hours (use "*/2 * * * *" for fast local demo)
MLFLOW_URI = "http://mlflow-svc.mlops-training.svc.cluster.local:5000"


def main():
    client = Client(host=KFP_HOST)
    experiment = client.create_experiment(name=EXPERIMENT_NAME)

    job = client.create_recurring_run(
        experiment_id=experiment.experiment_id,
        job_name="ctr-retraining-recurring",
        pipeline_package_path=PIPELINE_PACKAGE,
        cron_expression=CRON,
        params={"mlflow_uri": MLFLOW_URI},
        enabled=True,
    )
    print(f"Recurring run created: {job.recurring_run_id}")
    print(f"Schedule: {CRON}")
    print("View it: KFP UI -> Recurring Runs tab")


if __name__ == "__main__":
    main()
