# RAG Pipeline (build spec) — distilled from langchain

## Summary

Implement a full Retrieval-Augmented Generation pipeline: load documents from a source, split them into overlapping chunks, embed each chunk into a vector, store in a vector database, then at query time retrieve the most relevant chunks and inject them as context into an LLM prompt. The pipeline is wired as an LCEL chain so streaming and async work automatically.

## Core logic (inlined)

### Document and chunk data shapes

```python
from dataclasses import dataclass, field

@dataclass
class Document:
    page_content: str
    metadata: dict = field(default_factory=dict)
    # metadata keys: source (filename/URL), page (int), chunk_index (int), etc.
```

### Stage 1: Document Loading

```python
class BaseDocumentLoader:
    def load(self) -> list[Document]:
        raise NotImplementedError

    def lazy_load(self) -> Iterator[Document]:
        """Load one-at-a-time for large sources."""
        yield from self.load()

# Text file loader (minimal reference implementation)
class TextFileLoader(BaseDocumentLoader):
    def __init__(self, path: str):
        self.path = path

    def load(self) -> list[Document]:
        with open(self.path) as f:
            return [Document(
                page_content=f.read(),
                metadata={"source": self.path}
            )]
```

### Stage 2: Text Splitting

```python
class RecursiveCharacterTextSplitter:
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: list[str] | None = None,
        length_function=len,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", " ", ""]
        self.length_function = length_function

    def split_text(self, text: str) -> list[str]:
        """Recursively split text using separators in order of preference."""
        return self._split_text(text, self.separators)

    def _split_text(self, text: str, separators: list[str]) -> list[str]:
        final_chunks = []
        sep = separators[0]

        # Try to split on the current separator
        splits = text.split(sep) if sep else list(text)

        good_splits = []  # splits that are small enough
        for s in splits:
            if self.length_function(s) < self.chunk_size:
                good_splits.append(s)
            else:
                # This split is still too large; recurse with next separator
                if good_splits:
                    final_chunks.extend(self._merge_splits(good_splits, sep))
                    good_splits = []
                if len(separators) > 1:
                    final_chunks.extend(self._split_text(s, separators[1:]))
                else:
                    final_chunks.append(s)  # no more separators; take it as-is

        if good_splits:
            final_chunks.extend(self._merge_splits(good_splits, sep))

        return final_chunks

    def _merge_splits(self, splits: list[str], separator: str) -> list[str]:
        """Merge small splits into chunks up to chunk_size, with overlap."""
        chunks = []
        current_chunk: list[str] = []
        current_len = 0

        for s in splits:
            s_len = self.length_function(s)
            if current_len + s_len > self.chunk_size and current_chunk:
                # Emit current chunk
                chunks.append(separator.join(current_chunk))
                # Keep overlap: remove from front until under chunk_overlap
                while (current_len > self.chunk_overlap and
                       current_chunk and
                       self.length_function(current_chunk[0]) < current_len - self.chunk_overlap):
                    removed = current_chunk.pop(0)
                    current_len -= self.length_function(removed) + len(separator)
            current_chunk.append(s)
            current_len += s_len + len(separator)

        if current_chunk:
            chunks.append(separator.join(current_chunk))
        return chunks

    def split_documents(self, documents: list[Document]) -> list[Document]:
        chunks = []
        for doc in documents:
            texts = self.split_text(doc.page_content)
            for i, text in enumerate(texts):
                chunks.append(Document(
                    page_content=text,
                    metadata={**doc.metadata, "chunk_index": i}
                ))
        return chunks
```

### Stage 3: Embedding

```python
class BaseEmbeddings:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

# Example: OpenAI implementation
class OpenAIEmbeddings(BaseEmbeddings):
    def __init__(self, model: str = "text-embedding-3-small", api_key: str = None):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(input=texts, model=self.model)
        return [item.embedding for item in response.data]
```

### Stage 4: Vector Store

```python
import numpy as np

class InMemoryVectorStore:
    """Simple cosine-similarity in-memory store. Use Chroma/FAISS/pgvector in prod."""

    def __init__(self, embedding_model: BaseEmbeddings):
        self.embedding_model = embedding_model
        self.documents: list[Document] = []
        self.vectors: list[list[float]] = []

    @classmethod
    def from_documents(cls, docs: list[Document], embeddings: BaseEmbeddings) -> "InMemoryVectorStore":
        store = cls(embeddings)
        texts = [d.page_content for d in docs]
        vectors = embeddings.embed_documents(texts)
        store.documents = docs
        store.vectors = vectors
        return store

    def similarity_search(self, query: str, k: int = 4) -> list[Document]:
        query_vec = self.embedding_model.embed_query(query)
        scores = [self._cosine(query_vec, v) for v in self.vectors]
        top_k = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [self.documents[i] for i in top_k]

    def _cosine(self, a: list[float], b: list[float]) -> float:
        a, b = np.array(a), np.array(b)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

    def as_retriever(self, search_type: str = "similarity",
                     search_kwargs: dict | None = None) -> "VectorStoreRetriever":
        return VectorStoreRetriever(self, search_kwargs or {"k": 4})
```

### Stage 5: Retriever

```python
class BaseRetriever:
    """Runnable: string → list[Document]"""

    def invoke(self, query: str, config=None) -> list[Document]:
        return self._get_relevant_documents(query)

    def _get_relevant_documents(self, query: str) -> list[Document]:
        raise NotImplementedError

    def __or__(self, other):
        """Support pipe composition: retriever | format_docs"""
        return RunnableSequence(steps=[self, RunnableLambda(other) if callable(other) else other])

class VectorStoreRetriever(BaseRetriever):
    def __init__(self, vectorstore: InMemoryVectorStore, search_kwargs: dict):
        self.vectorstore = vectorstore
        self.k = search_kwargs.get("k", 4)

    def _get_relevant_documents(self, query: str) -> list[Document]:
        return self.vectorstore.similarity_search(query, k=self.k)
```

### Stage 6: The RAG chain (LCEL)

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableParallel

def format_docs(docs: list[Document]) -> str:
    """Join retrieved docs into context string. Add metadata for citation."""
    parts = []
    for doc in docs:
        source = doc.metadata.get("source", "unknown")
        parts.append(f"[Source: {source}]\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)

# Build the chain
rag_prompt = ChatPromptTemplate.from_messages([
    ("system", "Answer the question using ONLY the following context. "
               "If the answer is not in the context, say 'I don't know.'\n\n"
               "Context:\n{context}"),
    ("human", "{question}")
])

def build_rag_chain(retriever: BaseRetriever, llm, output_parser=None):
    parser = output_parser or StrOutputParser()
    return (
        RunnableParallel({
            "context": retriever | format_docs,
            "question": RunnablePassthrough(),
        })
        | rag_prompt
        | llm
        | parser
    )

# Usage
chain = build_rag_chain(retriever, llm)
answer = chain.invoke("What was Q3 revenue?")
```

### Return sources alongside the answer

```python
def build_rag_chain_with_sources(retriever, llm):
    """Returns {answer: str, source_documents: list[Document]}"""
    def retrieve_and_format(question: str) -> dict:
        docs = retriever.invoke(question)
        return {
            "context": format_docs(docs),
            "question": question,
            "source_documents": docs,
        }

    return (
        RunnableLambda(retrieve_and_format)
        | {
            "answer": rag_prompt | llm | StrOutputParser(),
            "source_documents": RunnableLambda(lambda x: x["source_documents"])
          }
    )
```

## Data contracts

### Document

```python
Document(
    page_content="The full text content of this chunk...",
    metadata={
        "source": "report.pdf",       # required: where it came from
        "page": 3,                    # optional: page number
        "chunk_index": 0,             # added by splitter
        "created_at": "2026-06-01",   # optional: for time-filtered retrieval
    }
)
```

### Retriever invocation

```python
retriever.invoke("user question string") -> list[Document]  # up to k docs
```

### RAG chain I/O

```python
# Input: the user's question
rag_chain.invoke("What is X?") -> str  # the generated answer

# With sources
rag_chain_with_sources.invoke("What is X?") -> {
    "answer": str,
    "source_documents": list[Document],
}
```

## Dependencies & assumptions

- **Embeddings**: requires API key for OpenAI/Anthropic/Cohere; or local model via HuggingFace/Ollama (no key needed)
- **Vector store**: Chroma (`pip install chromadb`) for local prototyping; FAISS (`pip install faiss-cpu`) for in-memory; pgvector/Pinecone for production
- **Text splitting**: pure Python, no dependencies; `langchain-text-splitters` package or inline above
- **numpy** for cosine similarity in the reference implementation; production stores handle this internally
- LLM must be a `BaseChatModel` compatible with LCEL (`.invoke(messages)` returns `AIMessage`)

## To port this, you need:

- [ ] `Document(page_content, metadata)` data class
- [ ] At least one `DocumentLoader` for your source type (file, URL, DB, API)
- [ ] `RecursiveCharacterTextSplitter` with `chunk_size`, `chunk_overlap`, separator cascade
- [ ] `BaseEmbeddings` with `embed_documents()` and `embed_query()`
- [ ] Vector store with `from_documents()`, `similarity_search(query, k)`, `as_retriever()`
- [ ] `BaseRetriever` with `invoke(query) -> list[Document]`
- [ ] `format_docs(docs) -> str` function
- [ ] `build_rag_chain(retriever, llm)` wiring retriever → format → prompt → llm → parser
- [ ] (Optional) source return variant that keeps `list[Document]` alongside the answer

## Gotchas

**Retrieval quality is everything.** The LLM can't answer from a chunk it didn't receive. Test retrieval independently before testing the full chain: print `retriever.invoke("your question")` and check if the right content is in there.

**Chunk overlap is not optional.** Without overlap, information at chunk boundaries is lost. A sentence cut at position 1000 chars appears in neither chunk 1 nor chunk 2. Set overlap to at least 10% of chunk size (20% is safer).

**Embedding models have token limits.** `text-embedding-3-small` handles 8191 tokens per input. A 1000-character chunk is ~250 tokens — fine. A 10,000-character chunk will be silently truncated to 8191 tokens without error. Don't let chunks exceed 6000 characters.

**MMR over cosine similarity for diverse results.** Pure cosine similarity often returns 4 near-duplicate chunks. MMR (`search_type="mmr"`, `fetch_k=20`) fetches 20 candidates and picks the top-k that are both relevant AND diverse. Implement with: for each candidate, compute `λ * relevance - (1-λ) * max_similarity_to_selected`.

**Metadata filtering cuts retrieval cost.** For multi-document systems, always add a `source` metadata field and offer filter support: `vectorstore.similarity_search(query, filter={"source": "doc_a.pdf"})`. This prevents cross-contamination and makes citation straightforward.

**"Stuff" strategy has a context limit.** Joining 4 chunks of 1000 chars = 4000 chars of context. For large doc sets, consider:
- **Map-reduce**: answer per chunk, merge answers
- **Refine**: answer from chunk 1, then refine with chunk 2, 3, etc.
- **Increase k + compress**: retrieve more chunks, use an LLM to filter to only the relevant sentences

**Async and streaming.** LCEL makes `astream()` work through the chain. The LLM produces tokens as they arrive, but the retrieval step is still synchronous. For full async: use `retriever.ainvoke()` and wire via `await`.

## Origin (reference only)

- Repo: https://github.com/langchain-ai/langchain
- Retriever interface: `libs/core/langchain_core/retrievers.py`
- Text splitters: `libs/text-splitters/langchain_text_splitters/`
- Vector store interface: `libs/core/langchain_core/vectorstores/base.py`
- RAG how-to: https://python.langchain.com/docs/how_to/qa_sources/
