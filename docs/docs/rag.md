---
id: rag
title: Retrieval-Augmented Generation (RAG)
sidebar_label: RAG
---

# RAG Overview

The RAG pipeline enriches LLM responses with real-time retrieved documents.

## Components

1. **Vector Store** (Elasticsearch)
2. **Embeddings** (OpenAI)
3. **Retrieval**
4. **Generation**

```mermaid
flowchart LR
  TextInput -->|embed| Embeddings
  Embeddings -->|store| VectorStore
  Query -->|search| VectorStore
  Docs -->|context| LLM
  LLM -->|response| TextOutput
```
