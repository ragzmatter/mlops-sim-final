"""
Stage: Automated Retraining (placeholder)
Will be triggered by the KFP Recurring Run once drift/PSI thresholds are exceeded.
TODO: implement retraining trigger logic - pull latest features, retrain, log to MLflow.
"""
import os

ART_DIR = os.environ.get("ARTIFACT_DIR", "/mnt/artifacts")

def main():
    print(f"[retrain] placeholder invoked, ARTIFACT_DIR={ART_DIR}")
    print("[retrain] TODO: implement retraining pipeline logic")

if __name__ == "__main__":
    main()
