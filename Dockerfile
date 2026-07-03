FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    pandas numpy scikit-learn joblib pyarrow \
    fastapi uvicorn prometheus_client pydantic \
    mlflow feast[redis]

COPY data/generate_dataset.py                   /app/generate_dataset.py
COPY feature-engineering/feature_engineering.py /app/feature_engineering.py
COPY training/train_mlflow.py                   /app/train.py
COPY evaluation/evaluate_mlflow.py              /app/evaluate.py
COPY serving/app_feast.py                       /app/serving_app.py
COPY monitoring/monitor.py                      /app/monitor.py
COPY retraining/retrain.py                      /app/retrain.py
COPY feast/materialize.py                       /app/materialize.py
COPY feast/feature_repo/                        /app/feature_repo/

ENV ARTIFACT_DIR=/mnt/artifacts
ENV FEAST_REPO=/app/feature_repo

CMD ["python3", "--version"]
