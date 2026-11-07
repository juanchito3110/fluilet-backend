"""A completed PDF worker may exit just before its parent observes the pipe."""

import multiprocessing
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.ingestion import IngestionError, extract_safely


@pytest.mark.parametrize("sent", [True, False], ids=["completed-result", "crashed-without-result"])
async def test_pdf_child_exit_checks_for_a_buffered_result(monkeypatch, sent):
    class Pipe:
        ready = False
        closed = False

        def poll(self):
            return self.ready

        def recv(self):
            assert self.ready
            return True, "La lectura llegó completa desde el proceso PDF."

        def close(self):
            self.closed = True

    parent = Pipe()
    child = Mock()

    def exited():
        # Simulate a scheduler switch: the worker sends and exits after the
        # initial empty poll, before the parent checks whether it is alive.
        parent.ready = sent
        return False

    process = Mock(is_alive=exited)
    context = SimpleNamespace(
        Pipe=lambda **kwargs: (parent, child), Process=lambda **kwargs: process
    )
    monkeypatch.setattr(multiprocessing, "get_context", lambda method: context)
    if sent:
        assert await extract_safely(b"%PDF-test", "application/pdf") == (
            "La lectura llegó completa desde el proceso PDF."
        )
    else:
        with pytest.raises(IngestionError, match="document_not_processable"):
            await extract_safely(b"%PDF-test", "application/pdf")
    assert parent.closed
    child.close.assert_called_once()
    process.start.assert_called_once()
    process.join.assert_called_once_with(2)
    process.terminate.assert_not_called()
    process.kill.assert_not_called()
