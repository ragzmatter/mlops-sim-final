# SELF_HOSTED_RUNNER_SETUP.md

Why: GitHub's cloud runners can't reach your laptop's `localhost:8888` (KFP UI).
A self-hosted runner runs ON your laptop instead, so `localhost:8888` just works.

## 1. Register runner with your repo
```
GitHub repo -> Settings -> Actions -> Runners -> New self-hosted runner
-> select Linux -> copy the commands shown (they include a unique token)
```

## 2. Install + configure (paste the commands GitHub shows you, e.g.)
```bash
mkdir actions-runner && cd actions-runner
curl -o actions-runner-linux-x64.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.319.1/actions-runner-linux-x64-2.319.1.tar.gz
tar xzf actions-runner-linux-x64.tar.gz
./config.sh --url https://github.com/<YOU>/mlops-sim --token <TOKEN_FROM_GITHUB>
```

## 3. Run it (keep this terminal open / or run as a service)
```bash
./run.sh
# OR install as background service:
sudo ./svc.sh install
sudo ./svc.sh start
```

## 4. Confirm it's online
```
GitHub repo -> Settings -> Actions -> Runners -> should show "Idle", green dot
```

## 5. Point ci.yaml at it
Change `runs-on: ubuntu-latest` to `runs-on: self-hosted` for the job that needs
cluster access (see updated ci.yaml below).

## Notes
- The runner process needs `kubectl`, `docker`, `kfp` python package, and your
  kubeconfig already set up on the same laptop (it just reuses your existing setup).
- Stop it anytime: `sudo ./svc.sh stop` (or Ctrl+C if running via `./run.sh`).
- This only works while your laptop is on and the runner process is running —
  acceptable for a local simulation, not how you'd do it in real cloud prod
  (real prod would use a cloud-hosted KFP, not localhost).
