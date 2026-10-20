"""Lazy, optional local mT5. Blocking loads/generation never run on the event loop."""

import asyncio
import importlib.util
from pathlib import Path

from app.config import settings
from app.nlp.chunking import conservative_tokens


class ModelUnavailable(RuntimeError):
    pass


class MT5Runtime:
    def __init__(self):
        self._slots = asyncio.Semaphore(settings.MT5_CONCURRENCY)
        self._load_lock = asyncio.Lock()
        self._model = None
        self._tokenizer = None
        self._jobs = set()
        self.state = "not_loaded"

    @property
    def is_loaded(self):
        return self.state == "loaded" and self._model is not None and self._tokenizer is not None

    def _load_sync(self):
        if not settings.MT5_ENABLED or any(
            importlib.util.find_spec(name) is None
            for name in ("torch", "transformers", "sentencepiece")
        ):
            raise ModelUnavailable("optional_dependencies_unavailable")
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        if tuple(int(part) for part in torch.__version__.split(".")[:2]) < (2, 6):
            raise ModelUnavailable("torch_version_unsupported")
        torch.set_num_threads(2)

        checkpoint = settings.MT5_CHECKPOINT
        source = checkpoint if checkpoint and Path(checkpoint).is_dir() else settings.MT5_MODEL
        options = {"local_files_only": settings.MT5_LOCAL_FILES_ONLY, "trust_remote_code": False}
        tokenizer = AutoTokenizer.from_pretrained(source, use_fast=False, **options)
        model = AutoModelForSeq2SeqLM.from_pretrained(
            source, use_safetensors=None, weights_only=True, **options
        )
        model.eval()
        self._model, self._tokenizer = model, tokenizer
        self.state = "loaded"

    async def _prepare_locked(self):
        async with self._load_lock:
            if self._model is None:
                async with self._slots:
                    try:
                        await asyncio.to_thread(self._load_sync)
                    except Exception:
                        self.state = "unavailable"
                        raise ModelUnavailable("local_model_unavailable") from None

    async def _bounded(self, coroutine):
        # Shield the worker: a timeout must not release its semaphore while the
        # native thread is still running. Keep a task until completion, not input logs.
        task = asyncio.create_task(coroutine)
        self._jobs.add(task)

        def finished(job):
            self._jobs.discard(job)
            if not job.cancelled():
                job.exception()

        task.add_done_callback(finished)
        try:
            return await asyncio.wait_for(asyncio.shield(task), settings.MT5_TIMEOUT_SECONDS)
        except TimeoutError:
            raise ModelUnavailable("model_timeout") from None

    async def prepare(self):
        if self._model is not None:
            return
        if self.state == "unavailable":
            raise ModelUnavailable("local_model_unavailable")
        if self._jobs:
            raise ModelUnavailable("model_busy")
        await self._bounded(self._prepare_locked())

    def count_tokens(self, text: str) -> int:
        if self._tokenizer is None:
            return conservative_tokens(text)
        return len(self._tokenizer.encode(self._prompt(text), truncation=False))

    @staticmethod
    def _prompt(text):
        # The same prefix is used by the training pipeline.
        return "simplificar español: " + text

    def _generate_sync(self, text: str, attempt: int) -> str:
        import torch

        inputs = self._tokenizer(self._prompt(text), return_tensors="pt", truncation=False)
        if inputs["input_ids"].shape[-1] > settings.MT5_MAX_INPUT_TOKENS:
            raise ModelUnavailable("token_limit")
        with torch.inference_mode():
            generated = self._model.generate(
                **inputs,
                max_new_tokens=settings.MT5_MAX_NEW_TOKENS,
                num_beams=min(2 + attempt * 2, 6),
                length_penalty=1.0 - attempt * 0.15,
                do_sample=False,
                no_repeat_ngram_size=4,
                early_stopping=True,
                max_time=settings.MT5_TIMEOUT_SECONDS,
            )
        return self._tokenizer.decode(generated[0], skip_special_tokens=True).strip()

    async def _generate_locked(self, text, attempt):
        async with self._slots:
            try:
                return await asyncio.to_thread(self._generate_sync, text, attempt)
            except Exception:
                raise ModelUnavailable("generation_unavailable") from None

    async def generate(self, text: str, attempt: int) -> str:
        await self.prepare()
        if self._slots.locked() or self._jobs:
            raise ModelUnavailable("model_busy")
        return await self._bounded(self._generate_locked(text, attempt))

    async def close(self):
        if self._jobs:
            await asyncio.gather(*self._jobs, return_exceptions=True)


runtime = MT5Runtime()
