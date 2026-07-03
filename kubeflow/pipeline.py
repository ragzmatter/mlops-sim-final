"""
Kubeflow Pipeline: CTR MLOps end-to-end (KFP v2 SDK)
Stages: feature-eng -> feast materialize -> training -> evaluation -> deploy
Each component = one pod in the kubeflow namespace. KFP triggers next only on success.
"""
from kfp import dsl, compiler

IMAGE = "localhost:30050/mlops-sim:latest"
MLFLOW_URI = "http://mlflow-svc.mlops-training.svc.cluster.local:5000"


@dsl.component(base_image=IMAGE)
def feature_engineering_op():
    import subprocess
    subprocess.run(["python3", "/app/feature_engineering.py"], check=True)


@dsl.component(base_image=IMAGE, packages_to_install=["feast[redis]"])
def feast_materialize_op():
    """Reads features.parquet -> feast apply -> feast materialize -> Redis."""
    import subprocess
    subprocess.run(["python3", "/app/materialize.py"], check=True)


@dsl.component(base_image=IMAGE, packages_to_install=["mlflow"])
def training_op(mlflow_uri: str):
    import subprocess, os
    env = {**os.environ, "MLFLOW_TRACKING_URI": mlflow_uri}
    subprocess.run(["python3", "/app/train.py"], check=True, env=env)


@dsl.component(base_image=IMAGE, packages_to_install=["mlflow"])
def evaluation_op(mlflow_uri: str) -> str:
    import subprocess, os
    env = {**os.environ, "MLFLOW_TRACKING_URI": mlflow_uri}
    r = subprocess.run(["python3", "/app/evaluate.py"], env=env)
    if r.returncode != 0:
        raise RuntimeError("Evaluation gate FAILED — model not promoted")
    return "approved"


@dsl.component(base_image=IMAGE)
def deploy_trigger_op(approval: str):
    import subprocess
    if approval != "approved":
        raise RuntimeError("Skipping deploy — not approved")
    subprocess.run([
        "kubectl", "rollout", "restart",
        "deployment/model-serving", "-n", "mlops-serving"
    ], check=True)


@dsl.pipeline(name="ctr-mlops-pipeline", description="CTR end-to-end MLOps")
def ctr_pipeline(mlflow_uri: str = MLFLOW_URI):
    feat = feature_engineering_op()
    feat.set_caching_options(False)

    feast = feast_materialize_op()
    feast.after(feat)
    feast.set_caching_options(False)

    train = training_op(mlflow_uri=mlflow_uri)
    train.after(feast)
    train.set_caching_options(False)

    evl = evaluation_op(mlflow_uri=mlflow_uri)
    evl.after(train)
    evl.set_caching_options(False)

    deploy = deploy_trigger_op(approval=evl.output)
    deploy.after(evl)
    deploy.set_caching_options(False)


if __name__ == "__main__":
    compiler.Compiler().compile(ctr_pipeline, "pipeline.yaml")
    print("Compiled -> pipeline.yaml")
