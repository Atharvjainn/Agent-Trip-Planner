from __future__ import annotations

import pytest

import app.kg.ingest as kg_ingest
import app.kg.reads as kg_reads


class FakeLLMBackend:
    """Implements the LLMProviderBackend protocol without any network call.

    Pass either `response_json` (a JSON string) for a successful call, or
    `raise_exc` to simulate that provider being unavailable/failing — the
    real LLMProvider.structured() retry/fallback logic still runs on top
    of this, so these tests exercise the real orchestration code."""

    def __init__(self, name: str, *, response_json: str | None = None, raise_exc: Exception | None = None):
        self.name = name
        self._response_json = response_json
        self._raise_exc = raise_exc
        self.calls = 0

    async def complete_json(self, *, prompt: str, system: str | None, timeout_seconds: float) -> str:
        self.calls += 1
        if self._raise_exc is not None:
            raise self._raise_exc
        assert self._response_json is not None
        return self._response_json


@pytest.fixture(autouse=True)
def _no_real_neo4j(monkeypatch):
    """Every test runs fully offline with respect to Neo4j: writes are
    accepted and discarded, reads return empty. This mirrors exactly what
    a real-but-unreachable Neo4j would look like from the caller's side,
    since kg/ingest.py and kg/reads.py already turn connection errors into
    this same behavior — we're just skipping the (slow) real connection
    attempt in tests. We patch at the point of use (app.kg.ingest /
    app.kg.reads each did `from app.kg.driver import run_write` /
    `run_read`, so patching app.kg.driver.run_write would not affect
    those already-bound names)."""

    async def _fake_run_write(query, params):
        return None

    async def _fake_run_read(query, params):
        return []

    monkeypatch.setattr(kg_ingest, "run_write", _fake_run_write)
    monkeypatch.setattr(kg_reads, "run_read", _fake_run_read)
