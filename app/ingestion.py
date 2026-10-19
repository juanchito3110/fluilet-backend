"""Extraction exclusively from RAM. No upload filenames or temporary files."""

import io
import unicodedata

from fastapi import HTTPException, Request

from app.config import settings


class IngestionError(ValueError):
    pass


def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    if any(unicodedata.category(char) == "Cs" for char in text):
        raise IngestionError("invalid_unicode")
    text = "".join(
        char if char in "\n\t" or unicodedata.category(char) not in {"Cc", "Cf"} else " "
        for char in text
    )
    return "\n".join(" ".join(line.split()) for line in text.split("\n")).strip()


async def read_stream(request: Request) -> bytes:
    data = bytearray()
    async for block in request.stream():
        if len(data) + len(block) > settings.MAX_BODY_BYTES:
            raise HTTPException(413, "El tamaño máximo es 5 MB.")
        data.extend(block)
    if not data:
        raise HTTPException(422, "Archivo vacío.")
    return bytes(data)


def extract_text(data: bytes, media_type: str) -> str:
    if len(data) > settings.MAX_BODY_BYTES:
        raise IngestionError("file_too_large")
    try:
        if media_type == "text/plain":
            if b"\x00" in data:
                raise IngestionError("invalid_text")
            text = data.decode("utf-8-sig", errors="strict")
        elif media_type == "application/pdf":
            if not data.startswith(b"%PDF-"):
                raise IngestionError("invalid_pdf")
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data), strict=True)
            if reader.is_encrypted or len(reader.pages) > settings.MAX_PDF_PAGES:
                raise IngestionError("unsupported_pdf")
            parts = []
            chars = 0
            for page in reader.pages:
                # Refuse excessive uncompressed page streams before text extraction.
                contents = page.get_contents()
                if contents is not None and len(contents.get_data()) > settings.MAX_BODY_BYTES:
                    raise IngestionError("pdf_page_too_large")
                part = page.extract_text() or ""
                chars += len(part)
                if chars > settings.MAX_BODY_BYTES:
                    raise IngestionError("extracted_text_too_large")
                parts.append(part)
            text = "\n\n".join(parts)
        else:
            raise IngestionError("unsupported_media")
        text = clean_text(text)
        if not text:
            raise IngestionError("no_extractable_text")
        return text
    except Exception:
        raise IngestionError("document_not_processable") from None


def _pdf_worker(connection, data):
    # PDF parsing runs in a killable process. Decompression may allocate before a
    # Python-level size check, so production Linux also enforces OS limits.
    import logging
    import os

    try:
        null = os.open(os.devnull, os.O_WRONLY)
        os.dup2(null, 1)
        os.dup2(null, 2)
        os.close(null)
        logging.disable(logging.CRITICAL)
        try:
            import resource

            resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
            if __import__("sys").platform.startswith("linux"):
                resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024, 768 * 1024 * 1024))
        except (ImportError, ValueError, OSError):
            pass
        connection.send((True, extract_text(data, "application/pdf")))
    except BaseException:
        connection.send((False, "document_not_processable"))
    finally:
        connection.close()


async def extract_safely(data: bytes, media_type: str) -> str:
    import asyncio
    import multiprocessing

    if media_type != "application/pdf":
        return await asyncio.to_thread(extract_text, data, media_type)
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=_pdf_worker, args=(child, data), daemon=True)
    process.start()
    child.close()
    try:
        async with asyncio.timeout(10):
            while not parent.poll():
                if not process.is_alive():
                    raise IngestionError("document_not_processable")
                await asyncio.sleep(0.02)
            success, result = await asyncio.to_thread(parent.recv)
            if not success:
                raise IngestionError("document_not_processable")
            return result
    except (TimeoutError, EOFError, OSError):
        raise IngestionError("document_not_processable") from None
    finally:
        if process.is_alive():
            process.terminate()
        await asyncio.to_thread(process.join, 2)
        if process.is_alive():
            process.kill()
            await asyncio.to_thread(process.join)
        parent.close()
