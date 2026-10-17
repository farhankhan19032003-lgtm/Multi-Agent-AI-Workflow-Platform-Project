"""First page load fires several requests at once; the local tenant must be created exactly once."""
import threading
import time

import app.identity as identity


class _Query:
    def __init__(self, store, name):
        self.store, self.name, self.op = store, name, "select"

    def select(self, *_):
        return self

    def eq(self, *_):
        return self

    def limit(self, *_):
        return self

    def insert(self, row):
        self.op, self.row = "insert", row
        return self

    def execute(self):
        if self.op == "select":
            time.sleep(0.05)  # widen the window in which every thread sees "no tenant yet"
            return type("R", (), {"data": list(self.store["rows"])})()
        if self.store["rows"]:
            raise RuntimeError("UNIQUE constraint failed: tenants.id")
        self.store["rows"].append(self.row)
        self.store["inserts"] += 1
        return type("R", (), {"data": [self.row]})()


def test_local_tenant_created_once_under_concurrency(monkeypatch):
    store = {"rows": [], "inserts": 0}
    monkeypatch.setattr(identity.db, "table", lambda name: _Query(store, name))
    monkeypatch.setattr(identity, "_local_ready", False)
    errors = []

    def call():
        try:
            identity._ensure_local_tenant()
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=call) for _ in range(12)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors
    assert store["inserts"] == 1
