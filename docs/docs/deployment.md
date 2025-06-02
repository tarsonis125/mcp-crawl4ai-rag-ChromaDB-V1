---
id: deployment
title: Deployment
sidebar_label: Deployment
---

# Deployment

## Docker Compose

```yaml
version: '3.8'
services:
  server:
    build: .
    ports:
      - 3838:3838
  ui:
    build: archon-ui-main
    ports:
      - 3000:3000
  es:
    image: elasticsearch:7.17.0
```

## Environment Variables

- `OPENAI_API_KEY`
- `ES_HOST`
