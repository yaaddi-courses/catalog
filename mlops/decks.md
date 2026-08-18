# MLOps — deck list

Approved course structure (24 decks, fundamentals → practice → advanced).
See `.internal/mlops/progress.md` for per-deck build status.

## Foundations
1. What MLOps Actually Solves
2. The ML Lifecycle Loop
3. Reproducibility Fundamentals
4. Data Versioning

## Tracking & Registry
5. Experiment Tracking Fundamentals
6. MLflow Tracking
7. Weights & Biases
8. Model Registry & Lifecycle Stages

## Data & Features
9. Feature Store Fundamentals
10. Feast in Practice
11. Pipeline Orchestration Fundamentals

## Pipelines & CI
12. Kubeflow Pipelines
13. Airflow and Prefect for ML
14. CI for ML: Data and Model Quality Gates
15. Continuous Training and Retraining Triggers

## Serving & Rollout
16. Packaging a Model for Deployment
17. Model Serving Patterns
18. Model Serving Tools
19. Safe Rollouts: Canary and Shadow Deployment

## Monitoring & Governance
20. Monitoring ML Systems in Production
21. Data Drift and Concept Drift
22. Testing ML Systems
23. Model Governance and Model Cards
24. LLMOps: What Changes for Large Language Models

## Prerequisites this course points to instead of re-teaching
- `docker-and-containers` — containerization mechanics (deck 16 bridges here)
- `kubernetes-fundamentals` — running workloads on k8s (deck 12 bridges here)
- `harness` — general CI/CD mechanics (deck 14 bridges here)
- `opentelemetry` — general observability/tracing (deck 20 bridges here)
- `testing-in-software-engineering` — general testing vocabulary (deck 22 bridges here)
