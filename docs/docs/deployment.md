# Deployment

Instructions for production deployment.

## Docker Compose

```bash
docker-compose -f docker-compose.yml up --build -d
```

## Environment Variables

Use `.env.example` as a template.

## CI/CD Pipeline

- Build Docker images
- Run Tests
- Push to registry
- Deploy to Kubernetes or Docker Swarm

```mermaid
graph LR
  BuildCI-->Test
  Test-->PushRegistry
  PushRegistry-->Deploy
```
