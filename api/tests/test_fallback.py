import pytest

from app.agents.engine import FallbackLLM, _should_fallback


class Chunk:
    def __init__(self, text):
        self.content = text


class Model:
    def __init__(self, name, chunks=(), fail=None, fail_after=0):
        self.name, self.chunks, self.fail, self.fail_after = name, list(chunks), fail, fail_after
        self.calls = 0

    def bind_tools(self, tools):
        return self

    def stream(self, messages):
        self.calls += 1
        for i, c in enumerate(self.chunks):
            if self.fail and i == self.fail_after:
                raise self.fail
            yield Chunk(c)
        if self.fail and self.fail_after >= len(self.chunks):
            raise self.fail

    def invoke(self, messages, *a, **k):
        self.calls += 1
        if self.fail:
            raise self.fail
        return Chunk("".join(self.chunks))


def text(it):
    return "".join(c.content for c in it)


def test_falls_over_on_quota_error():
    a = Model("a", fail=RuntimeError("429 RESOURCE_EXHAUSTED quota"))
    b = Model("b", ["hello"])
    assert text(FallbackLLM([a, b]).stream("x")) == "hello"
    assert a.calls == 1 and b.calls == 1


def test_falls_over_on_503_and_not_found_for_invoke():
    a = Model("a", fail=RuntimeError("503 UNAVAILABLE high demand"))
    b = Model("b", fail=RuntimeError("404 NOT_FOUND no longer available"))
    c = Model("c", ["ok"])
    assert FallbackLLM([a, b, c]).invoke("x").content == "ok"


def test_no_fallback_after_output_started():
    a = Model("a", ["par", "tial"], fail=RuntimeError("503 UNAVAILABLE"), fail_after=1)
    b = Model("b", ["other"])
    out = []
    with pytest.raises(RuntimeError):
        for c in FallbackLLM([a, b]).stream("x"):
            out.append(c.content)
    assert out == ["par"] and b.calls == 0


def test_real_errors_are_not_swallowed():
    a = Model("a", fail=ValueError("bad request: tools schema invalid"))
    b = Model("b", ["x"])
    with pytest.raises(ValueError):
        list(FallbackLLM([a, b]).stream("x"))
    assert b.calls == 0


def test_last_model_error_is_raised():
    a = Model("a", fail=RuntimeError("429 quota"))
    b = Model("b", fail=RuntimeError("503 unavailable"))
    with pytest.raises(RuntimeError, match="503"):
        list(FallbackLLM([a, b]).stream("x"))


def test_bind_tools_keeps_fallbacks():
    a, b = Model("a", ["1"]), Model("b", ["2"])
    assert isinstance(FallbackLLM([a, b]).bind_tools([]), FallbackLLM)


def test_should_fallback_classifier():
    assert _should_fallback(RuntimeError("GoogleRateLimitError: RESOURCE_EXHAUSTED"))
    assert not _should_fallback(ValueError("Invalid SQL syntax"))
