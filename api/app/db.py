from functools import lru_cache

from .config import get_settings


@lru_cache
def get_client():
    """Supabase client (production mode only)."""
    from supabase import create_client

    s = get_settings()
    if not s.supabase_url or not s.supabase_service_role_key:
        raise RuntimeError(
            "Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY, "
            "or run in zero-setup mode with STORAGE=local."
        )
    client = create_client(s.supabase_url, s.supabase_service_role_key)
    # postgrest defaults to HTTP/2, and one shared h2 connection used from many request threads
    # breaks ("COMPRESSION_ERROR" / "Server disconnected" -> 500s). HTTP/1.1 with a thread-safe pool
    # and short keep-alive avoids both the races and stale connections.
    import httpx

    old = client.postgrest.session
    client.postgrest.session = httpx.Client(
        base_url=old.base_url,
        headers=old.headers,
        timeout=old.timeout,
        follow_redirects=True,
        http2=False,
        transport=httpx.HTTPTransport(
            retries=2,
            limits=httpx.Limits(max_connections=40, max_keepalive_connections=10, keepalive_expiry=15),
        ),
    )
    old.close()
    return client


def table(name: str):
    if get_settings().storage == "local":
        from .localdb import get_store

        return get_store().table(name)
    return get_client().table(name)


def is_local() -> bool:
    return get_settings().storage == "local"
