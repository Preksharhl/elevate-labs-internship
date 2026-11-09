# Project 4 - CI/CD Pipeline with GitHub Actions & Docker

Push to `main` -> GitHub Actions lints + tests -> builds Docker image -> pushes to Docker Hub -> pulled and run on Minikube.

## Run locally
    docker compose up --build        # http://localhost:8000

## Pipeline (`.github/workflows/cicd-04.yml`)
1. **test**: flake8 + pytest
2. **build-and-push**: Docker Buildx, tags `latest` and the commit SHA

Required repo secrets: `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`.

## Deploy on Minikube
    minikube start
    # edit k8s/deployment.yaml: set YOUR_DOCKERHUB_USERNAME
    kubectl apply -f k8s/
    kubectl get pods
    minikube service cicd-demo --url

Docker image: https://hub.docker.com/r/YOUR_DOCKERHUB_USERNAME/cicd-demo
