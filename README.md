# Elevate Labs Internship Projects

**Name:** PREKSHA RUHELA
**Internship:** Elevate Labs

## Projects

| # | Project | Tech | Folder |
|---|---------|------|--------|
| 8 | Open-Source Incident Management System | Flask, SQLite, Bootstrap, Docker | [incident-manager](./incident-manager) |
| 4 | CI/CD Pipeline with GitHub Actions & Docker | GitHub Actions, Docker, Docker Hub, Minikube | [04-cicd-pipeline](./04-cicd-pipeline) |

## Project 8: Incident Management System
A portal to log, assign, track and resolve incidents, with role-based access (reporter, engineer, admin), a REST API, and SMTP email notifications.

Setup and API details: [project README](./incident-manager/README.md)

## Project 4: CI/CD Pipeline
On every push, GitHub Actions runs tests, builds a Docker image and pushes it to Docker Hub. The image is then deployed on Minikube.

- Docker image: https://hub.docker.com/r/preksha227/cicd-demo
- Workflow: [cicd-04.yml](./.github/workflows/cicd-04.yml)

Setup details: [project README](./04-cicd-pipeline/README.md)
