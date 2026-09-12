"""Explicit one-time online setup. Never imported by the runtime pipeline."""
if __name__ == "__main__":
    from sentence_transformers import SentenceTransformer
    from semantic_matcher import MODEL_NAME
    SentenceTransformer(MODEL_NAME)
    print("Model cached. Runtime now loads with local_files_only=True.")
