"""
Text chunking for ingestion pipeline.

Uses LangChain's RecursiveCharacterTextSplitter with settings tuned for
personal documents (short-to-medium length, conversational and structured text).
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter


_DEFAULT_CHUNK_SIZE = 800
_DEFAULT_CHUNK_OVERLAP = 100


def chunk_texts(
    sections: list[str],
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = _DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """
    Split a list of text sections into overlapping chunks.

    Joins sections into a single document first, then splits, so that
    paragraph boundaries don't artificially limit chunk context.

    Returns list of chunk strings.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    full_text = "\n\n".join(sections)
    return splitter.split_text(full_text)
