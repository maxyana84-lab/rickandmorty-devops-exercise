# Rick and Morty: alive humans from Earth

![ci](https://github.com/maxyana84-lab/rickandmorty-devops-exercise/actions/workflows/ci.yml/badge.svg)

A script and a small REST service that query the [Rick and Morty API](https://rickandmortyapi.com/documentation/#rest),
keep the characters that are **Human**, **Alive** and from **Earth**, and return `Name`, `Location` and `Image`
as a CSV file (script) or as JSON (service).

```
Name,Location,Image
Rick Sanchez,Citadel of Ricks,https://rickandmortyapi.com/api/character/avatar/1.jpeg
```

## Example result
The first run of the workflow ([run #1](https://github.com/maxyana84-lab/rickandmorty-devops-exercise/actions/runs/42401638396),
7 November 2026) found **104** characters in the live API. The first rows of the CSV (the whole file is attached to the
run as the `characters-csv` artifact):

```
Name,Location,Image
Rick Sanchez,Citadel of Ricks,https://rickandmortyapi.com/api/character/avatar/1.jpeg
Summer Smith,Earth (Replacement Dimension),https://rickandmortyapi.com/api/character/avatar/3.jpeg
Beth Smith,Earth (Replacement Dimension),https://rickandmortyapi.com/api/character/avatar/4.jpeg
Jerry Smith,Earth (Replacement Dimension),https://rickandmortyapi.com/api/character/avatar/5.jpeg
```
In the same run both deployments (plain manifests and Helm chart) reached 2/2 ready pods on a kind cluster, and
`scripts/smoke_test.sh` passed against each of them (`/healthcheck`, `/characters` and `/characters.csv` returned 104
characters, an unknown path returned `404`). The numbers can change when the public API data changes.

Note that the character with id 2, Morty Smith, is not in the result: the API gives him the origin `unknown`, not Earth. The list does contain other characters that are also called Morty Smith (versions from other dimensions, with an Earth origin): names are not unique in this API, the image URL (it contains the character id) is.

## Contents
- [How the filtering works](#how-the-filtering-works)
- [1. The script](#1-the-script)
- [2. The REST service](#2-the-rest-service)
- [3. Docker](#3-docker)
- [4. Kubernetes manifests (`yamls/`)](#4-kubernetes-manifests-yamls)
- [5. Helm chart (`helm/`)](#5-helm-chart-helm)
- [6. GitHub Actions workflow](#6-github-actions-workflow)
- [Tests](#tests)
- [Project layout](#project-layout)

## How the filtering works
- The API filters `species` and `status`, but only by substring (`species=Human` can also return `Humanoid`) and it
  has **no origin filter**. The code therefore asks the API for `species=Human&status=Alive`, follows the pagination
  (`info.next`) and checks all three conditions again on every character.
- **Origin is Earth** means the origin is `Earth` or one of the numbered Earths such as `Earth (C-137)` or
  `Earth (Replacement Dimension)`. Pass `--origin-match exact` to the script to accept only the plain `Earth`.
- **Location** is the character's current location (`location.name`).
- The API answers `404` when nothing matches; this is treated as an empty result. Network errors and `5xx` answers are
  retried with a back-off, then reported as an error.

## 1. The script
Python 3.10+.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.export --output characters.csv        # add --origin-match exact for the strict reading
```
It prints `wrote N characters to characters.csv` and exits with code 1 if the API is unreachable.

## 2. The REST service
```bash
gunicorn --bind 0.0.0.0:8000 "app.api:create_app()"        # or: flask --app app.api:create_app run --port 8000
```

| Endpoint | Description |
|---|---|
| `GET /characters` | `{"count": N, "characters": [{"name", "location", "image"}, ...]}` (JSON) |
| `GET /characters.csv` | the same data as a CSV download (`Name,Location,Image`) |
| `GET /healthcheck` | `{"status": "ok"}`. Liveness only, it does not call the public API |

```bash
curl http://localhost:8000/healthcheck
curl http://localhost:8000/characters
curl http://localhost:8000/characters.csv
```
The result is cached in memory for `CACHE_TTL_SECONDS` (default 300) so that requests do not hit the public API each
time. If the Rick and Morty API is down, `/characters` answers `502` with `{"error": "..."}`.

Configuration (environment variables): `PORT` (8000), `CACHE_TTL_SECONDS` (300), `RICKANDMORTY_API_URL`
(`https://rickandmortyapi.com/api`), `HTTP_TIMEOUT_SECONDS` (10).

## 3. Docker
```bash
docker build -t rickandmorty-api:1.0.0 .
docker run --rm -p 8000:8000 rickandmorty-api:1.0.0
curl http://localhost:8000/characters
```
The image is `python:3.12-slim`, runs gunicorn as a non-root user (uid 10001) and has a `HEALTHCHECK` on `/healthcheck`
(`docker ps` shows `healthy`). The CSV script can run in the same image:
`docker run --rm -v "$PWD:/out" rickandmorty-api:1.0.0 python -m app.export --output /out/characters.csv`.

## 4. Kubernetes manifests (`yamls/`)
`Deployment.yaml` (2 replicas, readiness and liveness probes on `/healthcheck`, resource limits, read-only root
filesystem), `Service.yaml` (ClusterIP, port 80) and `Ingress.yaml` (nginx, host `rickandmorty.local`).

Local cluster with minikube:
```bash
minikube start
minikube addons enable ingress
minikube image build -t rickandmorty-api:1.0.0 .     # builds the image inside the cluster
# alternative: docker build -t rickandmorty-api:1.0.0 . && minikube image load rickandmorty-api:1.0.0

kubectl apply -f yamls/
kubectl rollout status deployment/rickandmorty-api
```
Reach it, either through the Ingress:
```bash
echo "$(minikube ip) rickandmorty.local" | sudo tee -a /etc/hosts      # with the Docker driver use: minikube tunnel, and 127.0.0.1
curl http://rickandmorty.local/characters
```
or directly:
```bash
kubectl port-forward svc/rickandmorty-api 8080:80
curl http://localhost:8080/characters
```
microk8s works the same way (`microk8s enable ingress`, `microk8s ctr image import`, `microk8s kubectl apply -f yamls/`).
Remove everything with `kubectl delete -f yamls/`.

## 5. Helm chart (`helm/`)
`helm/rickandmorty` renders a Deployment, a Service and an optional Ingress. Everything configurable is in
`values.yaml` (replicas, image, service, ingress, resources, environment variables).
```bash
helm lint helm/rickandmorty
helm install rickandmorty helm/rickandmorty            # image rickandmorty-api:1.0.0 must be available in the cluster
kubectl port-forward svc/rickandmorty 8080:80
curl http://localhost:8080/characters

helm upgrade rickandmorty helm/rickandmorty --set replicaCount=3 --set ingress.host=rm.example.local
helm uninstall rickandmorty
```
Use `--set ingress.enabled=false` on a cluster without an ingress controller.

## 6. GitHub Actions workflow
`.github/workflows/ci.yml` runs on every push to `main`, on pull requests and manually (**Actions -> ci -> Run workflow**).

| Job | Steps |
|---|---|
| `test` | check out, set up Python 3.12, install dependencies, run the unit tests, run the script against the **real** API and upload `characters.csv` as the build artifact `characters-csv` |
| `kubernetes` (after `test`) | build the Docker image; start a small Kubernetes cluster on the runner with `helm/kind-action` (kind); load the image into it; `kubectl apply -f yamls/` and wait for the rollout; run `scripts/smoke_test.sh` through a port-forward; delete the manifests; `helm lint` and `helm install` the chart; run the same smoke tests against the Helm release; print pod descriptions and logs if anything failed |

`scripts/smoke_test.sh <base-url>` checks `/healthcheck`, the shape and content of `/characters`, the header and rows of
`/characters.csv`, and that an unknown path returns `404`.

## Tests
```bash
pip install -r requirements-dev.txt
pytest -q
```
The unit tests mock the Rick and Morty API (pagination, the three conditions, `Humanoid`, the origin variants, `404`
as empty result, upstream errors, CSV quoting) and exercise the Flask endpoints, the health check and the cache.

## Project layout
```
app/rickandmorty.py   API client, filtering, CSV
app/export.py         command line script
app/api.py            Flask service
tests/                unit tests
scripts/smoke_test.sh smoke tests used by the workflow
Dockerfile
yamls/                Deployment.yaml, Service.yaml, Ingress.yaml
helm/rickandmorty/    Helm chart
.github/workflows/ci.yml
```
