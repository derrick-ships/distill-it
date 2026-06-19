# RAG Pipeline — from [langchain](https://github.com/langchain-ai/langchain)

> Domain: [[_domain]] · Source: https://github.com/langchain-ai/langchain · NotebookLM:

## What it does

RAG (Retrieval-Augmented Generation) lets an LLM answer questions about documents it has never seen in training — your private PDFs, your company wiki, your customer support transcripts. The key move: at question time, find the most relevant chunks from your document collection and inject them into the prompt. The model reasons over *that* context, not its training weights. LangChain gives you a full toolkit for every step of this pipeline.

## Why it exists

Fine-tuning a model on your private data is expensive, slow, and goes stale the moment your documents change. RAG solves this differently: keep documents in a fast vector database, and retrieve on demand. The model stays the same; only the context changes. This means:
- Your "knowledge base" updates the moment you re-index a document
- You can show the user exactly which sources the answer came from
- You can handle documents much larger than any context window by searching instead of stuffing

## How it actually works

A full RAG pipeline has six stages. LangChain has components for each.

### Stage 1 — Load

`DocumentLoader` classes turn raw sources into `Document` objects. A `Document` has two fields: `page_content` (the text) and `metadata` (a dict — source filename, URL, page number, timestamp, etc.).

```python
from langchain_community.document_loaders import PyPDFLoader, WebBaseLoader
docs = PyPDFLoader("report.pdf").load()
# or
docs = WebBaseLoader("https://example.com/article").load()
```

There are 100+ loaders for: PDF (via pdfplumber/PyMuPDF), DOCX, HTML, YouTube transcripts, GitHub repos, Slack exports, SQL databases, Notion pages, and more.

### Stage 2 — Split

Raw documents are too large to fit in context (and too general to match specific questions). `TextSplitter` classes cut them into overlapping chunks.

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,      # target characters per chunk
    chunk_overlap=200,    # overlap between consecutive chunks
    separators=["\n\n", "\n", " ", ""]  # try splitting on these in order
)
chunks = splitter.split_documents(docs)
```

`RecursiveCharacterTextSplitter` tries to split on paragraph breaks first (`\n\n`), then line breaks, then spaces, then characters — falling to a harder separator only if the current chunk is still too large. This preserves semantic units (paragraphs > sentences > words).

The `chunk_overlap` is crucial: without it, a sentence that spans a chunk boundary is cut in half and may never be retrieved in full context.

### Stage 3 — Embed

Each chunk is converted to a dense vector (an array of floats) that encodes its semantic meaning. Questions are embedded the same way, and the similarity between question-vector and chunk-vectors determines relevance.

```python
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
# embeddings.embed_documents(["text1", "text2"]) -> list[list[float]]
# embeddings.embed_query("question") -> list[float]
```

Any `Embeddings` subclass works here — Anthropic, Cohere, HuggingFace local models, Ollama, etc.

### Stage 4 — Store

Chunks + their vectors go into a vector store. The store handles similarity search at query time.

```python
from langchain_chroma import Chroma

vectorstore = Chroma.from_documents(chunks, embeddings)
# Later: vectorstore.similarity_search("my question", k=4)
```

Common options: **Chroma** (local, zero-config, SQLite-backed), **FAISS** (local, in-memory, fast for prototyping), **Pinecone** (managed, production scale), **pgvector** (Postgres extension, good if you're already on Postgres).

### Stage 5 — Retrieve

A `retriever` wraps the vector store and turns it into a `BaseRetriever` — a Runnable that takes a question string and returns `list[Document]`.

```python
retriever = vectorstore.as_retriever(
    search_type="mmr",          # maximal marginal relevance (reduces redundancy)
    search_kwargs={"k": 4}      # return top 4 chunks
)
```

Advanced retriever variants:
- **MultiQueryRetriever** — generates 3-5 variations of the query, retrieves for each, deduplicates. Gets more coverage for ambiguous questions.
- **ContextualCompressionRetriever** — uses an LLM to filter/compress each retrieved document to only the relevant sentences before returning.
- **ParentDocumentRetriever** — stores small chunks for retrieval precision but returns their parent (larger) chunks for context richness.

### Stage 6 — Generate

The retriever slots into an LCEL chain as the `context` input to the prompt:

```python
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

def format_docs(docs: list[Document]) -> str:
    return "\n\n".join(doc.page_content for doc in docs)

prompt = ChatPromptTemplate.from_messages([
    ("system", "Answer using only this context:\n\n{context}"),
    ("human", "{question}")
])

rag_chain = (
    {
        "context": retriever | format_docs,
        "question": RunnablePassthrough()
    }
    | prompt
    | llm
    | StrOutputParser()
)

answer = rag_chain.invoke("What does the report say about Q3 revenue?")
```

The `{"context": retriever | format_docs, "question": RunnablePassthrough()}` is a `RunnableParallel` — it runs both branches on the same input (the question string) simultaneously: retriever converts it to documents which are formatted to a string, and passthrough keeps the question itself. The dict of results feeds the prompt template.

`create_retrieval_chain(retriever, combine_docs_chain)` is a convenience wrapper that returns `{input: str} -> {input: str, context: list[Document], answer: str}` — useful when you want to return the source documents alongside the answer.

## The non-obvious parts

**The retriever is the bottleneck, not the model.** The quality of the final answer is only as good as the retrieved chunks. If the right chunk isn't retrieved, the model can't answer correctly — no matter how capable it is. Invest heavily in retrieval: chunk size, overlap, embedding model choice, and retrieval strategy matter more than which LLM you use.

**MMR (Maximal Marginal Relevance)** is almost always better than plain similarity search. Pure similarity can return 4 near-identical chunks all saying the same thing. MMR balances relevance with diversity — each new result must be relevant AND different from what's already in the result set.

**Metadata filtering is underused.** The vector store can filter by metadata before doing similarity search: `search_kwargs={"filter": {"source": "Q3-report.pdf"}}`. This is much cheaper than retrieving everything and hoping the right source comes up. For multi-document systems, always add source metadata.

**Chunk size is a dial with real tradeoffs.** Small chunks (256 chars) = precise retrieval but no context. Large chunks (2000 chars) = lots of context but retrieval is less precise and costs more tokens. 512–1000 chars with 10–20% overlap is a reasonable starting point; tune from there.

**The `format_docs` function is deceptively important.** How you join documents — with what separator, whether you include metadata headers, whether you truncate long docs — affects comprehension quality. A common improvement: `f"Source: {doc.metadata['source']}\n{doc.page_content}"` lets the model cite sources.

**Embedding models have their own context limit.** `text-embedding-3-small` has a 8191 token limit per document. If your chunks exceed this, the embedding silently truncates. Keep chunks under ~6000 chars to be safe.

## Related

- [[lcel-runnable-protocol--from-langchain]] (RAG chains are written in LCEL; the retriever is a Runnable)
- [[tool-calling-agent--from-langchain]] (retrieval is often a tool the agent calls rather than a fixed pipeline step)
- [[schema-driven-extraction--from-llm-scraper]] (structured extraction from retrieved documents as a follow-up step)
- [[multi-source-research-engine--from-last30days-skill]] (fan-out research vs single-retriever RAG — contrasting patterns)
