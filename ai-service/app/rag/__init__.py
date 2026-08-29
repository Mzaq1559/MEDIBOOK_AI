"""MediBook AI RAG module for grounded medical triage."""

__all__ = ["RAGPipeline", "get_rag_pipeline"]


def __getattr__(name: str):
    if name in __all__:
        from app.rag.pipeline import RAGPipeline, get_rag_pipeline
        return {"RAGPipeline": RAGPipeline, "get_rag_pipeline": get_rag_pipeline}[name]
    raise AttributeError(name)
