"""
File Parsing Utilities
Supports text extraction from PDF, Markdown, and TXT files
"""

import os
from pathlib import Path
from typing import List, Optional


def _read_text_with_fallback(file_path: str) -> str:
    """
    Read a text file, auto-detecting encoding if UTF-8 fails.

    Uses a multi-level fallback strategy:
    1. First try UTF-8 decoding
    2. Use charset_normalizer for encoding detection
    3. Fall back to chardet for encoding detection
    4. Final fallback: UTF-8 with errors='replace'

    Args:
        file_path: File path

    Returns:
        Decoded text content
    """
    data = Path(file_path).read_bytes()

    # First try UTF-8
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        pass

    # Try charset_normalizer for encoding detection
    encoding = None
    try:
        from charset_normalizer import from_bytes
        best = from_bytes(data).best()
        if best and best.encoding:
            encoding = best.encoding
    except Exception:
        pass

    # Fall back to chardet
    if not encoding:
        try:
            import chardet
            result = chardet.detect(data)
            encoding = result.get('encoding') if result else None
        except Exception:
            pass

    # Final fallback: UTF-8 with replace
    if not encoding:
        encoding = 'utf-8'

    return data.decode(encoding, errors='replace')


class FileParser:
    """File Parser"""

    SUPPORTED_EXTENSIONS = {'.pdf', '.md', '.markdown', '.txt'}

    @classmethod
    def is_supported(cls, file_path: str) -> bool:
        """
        Check whether a file is a supported format

        Args:
            file_path: File path

        Returns:
            True if the file format is supported
        """
        suffix = Path(file_path).suffix.lower()
        return suffix in cls.SUPPORTED_EXTENSIONS

    @classmethod
    def extract_text(cls, file_path: str) -> str:
        """
        Extract text from a file

        Args:
            file_path: File path

        Returns:
            Extracted text content
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        suffix = path.suffix.lower()

        if suffix not in cls.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file format: {suffix}")

        if suffix == '.pdf':
            return cls._extract_from_pdf(file_path)
        elif suffix in {'.md', '.markdown'}:
            return cls._extract_from_md(file_path)
        elif suffix == '.txt':
            return cls._extract_from_txt(file_path)

        raise ValueError(f"Cannot process file format: {suffix}")

    @staticmethod
    def _extract_from_pdf(file_path: str) -> str:
        """Extract text from PDF"""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError("PyMuPDF is required: pip install PyMuPDF")

        text_parts = []
        with fitz.open(file_path) as doc:
            for page in doc:
                text = page.get_text()
                if text.strip():
                    text_parts.append(text)

        return "\n\n".join(text_parts)

    @staticmethod
    def _extract_from_md(file_path: str) -> str:
        """Extract text from Markdown, with automatic encoding detection"""
        return _read_text_with_fallback(file_path)

    @staticmethod
    def _extract_from_txt(file_path: str) -> str:
        """Extract text from TXT, with automatic encoding detection"""
        return _read_text_with_fallback(file_path)

    @classmethod
    def extract_from_multiple(cls, file_paths: List[str]) -> str:
        """
        Extract text from multiple files and merge

        Args:
            file_paths: List of file paths

        Returns:
            Merged text
        """
        all_texts = []

        for i, file_path in enumerate(file_paths, 1):
            try:
                text = cls.extract_text(file_path)
                filename = Path(file_path).name
                all_texts.append(f"=== Document {i}: {filename} ===\n{text}")
            except Exception as e:
                all_texts.append(f"=== Document {i}: {file_path} (extraction failed: {str(e)}) ===")

        return "\n\n".join(all_texts)


def split_text_into_chunks(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50
) -> List[str]:
    """
    Split text into chunks

    Args:
        text: Original text
        chunk_size: Number of characters per chunk
        overlap: Number of overlapping characters

    Returns:
        List of text chunks
    """
    # Defensive clamping: guarantee the loop always makes forward progress
    # regardless of caller-supplied values. Without this, chunk_size <= overlap
    # (or a sentence boundary that shrinks `end` below start+overlap) makes
    # `start` stall or move backward, looping forever and exhausting memory.
    chunk_size = max(1, int(chunk_size))
    overlap = max(0, min(int(overlap), chunk_size - 1))

    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size

        # Try to split at sentence boundaries
        if end < text_len:
            # Find the nearest sentence-ending delimiter
            for sep in ['\u3002', '\uff01', '\uff1f', '.\n', '!\n', '?\n', '\n\n', '. ', '! ', '? ']:
                last_sep = text[start:end].rfind(sep)
                if last_sep != -1 and last_sep > chunk_size * 0.3:
                    end = start + last_sep + len(sep)
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= text_len:
            break

        # Next chunk starts from the overlap position, but must always advance
        # by at least one character so the loop cannot stall.
        next_start = end - overlap
        if next_start <= start:
            next_start = start + 1
        start = next_start

    return chunks
