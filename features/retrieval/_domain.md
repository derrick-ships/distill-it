# Domain: retrieval

Everything in the pipeline between a user's question and the context fed to an LLM. Covers document loading, chunking, embedding, vector storage, and retrieval strategies.

## What belongs here

- Document loaders (PDF, web, GitHub, databases, etc.)
- Text splitters and chunking strategies
- Embedding models
- Vector stores and similarity search
- Retrieval strategies (MMR, multi-query, contextual compression)
- Full RAG (Retrieval-Augmented Generation) pipelines

## What does NOT belong here

- Orchestration of the retrieved context into an LLM call → `llm-orchestration`
- Indexing for search-as-a-product → `search`
- Adaptive scraping → `adaptive-parsing`

## Features in this domain

| Feature | From repo | Summary |
|---------|-----------|---------|
| [[rag-pipeline--from-langchain]] | langchain | Full RAG: load → split → embed → store → retrieve → generate |
