"""Gemini key rotation: a key that hits its quota is skipped, then the next key answers."""
from types import SimpleNamespace

import app.agents.engine as eng


class _Chunk:
    def __init__(self, text):
        self.content = text


class _FakeModel:
    def __init__(self, key, dead):
        self.key, self.dead = key, dead

    def stream(self, messages):
        if self.key in self.dead:
            raise RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded")
        yield _Chunk(f"answer from {self.key}")

    def invoke(self, messages, *a, **k):
        return list(self.stream(messages))[0]

    def bind_tools(self, tools):
        return self


def _setup(monkeypatch, dead, keys="k2,k3", main="k1"):
    s = SimpleNamespace(llm_provider="google_genai", llm_model="m", llm_fast_model="f", llm_fallback_models="",
                        llm_max_retries=1, llm_temperature=None, google_api_key=main, google_api_keys=keys)
    monkeypatch.setattr(eng, "get_settings", lambda: s)
    monkeypatch.setattr(eng, "init_chat_model", lambda name, model_provider, **kw: _FakeModel(kw["google_api_key"], dead))
    eng._cooldown.clear()


def _text(llm):
    return "".join(c.content for c in llm.stream("hi"))


def test_keys_are_deduped_and_main_first():
    s = SimpleNamespace(google_api_key="a", google_api_keys=" b, a ,c,,")
    assert eng._gemini_keys(s) == ["a", "b", "c"]


def test_second_key_answers_when_first_is_out_of_quota(monkeypatch):
    _setup(monkeypatch, dead={"k1"})
    assert _text(eng.get_llm()) == "answer from k2"


def test_third_key_when_two_are_out(monkeypatch):
    _setup(monkeypatch, dead={"k1", "k2"})
    assert _text(eng.get_llm()) == "answer from k3"


def test_exhausted_key_is_skipped_on_the_next_request(monkeypatch):
    _setup(monkeypatch, dead={"k1"})
    _text(eng.get_llm())                     # k1 fails, k2 answers, k1 goes on cooldown
    llm = eng.get_llm()
    assert [t[0] for t in llm.tags] == ["k2", "k3", "k1"]
    assert _text(llm) == "answer from k2"


def test_tools_binding_keeps_rotation(monkeypatch):
    _setup(monkeypatch, dead={"k1"})
    assert _text(eng.get_llm().bind_tools([])) == "answer from k2"
