FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

RUN useradd --create-home --uid 1000 appuser

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY scripts ./scripts
COPY web ./web
COPY docker-entrypoint.sh ./docker-entrypoint.sh

RUN mkdir -p /srv/mlruns /srv/data && chown -R appuser:appuser /srv

# PORT and WORKERS can be set from the environment (Render sets PORT; use WORKERS=1 on small plans).
# The entrypoint starts as root only to fix disk ownership, then runs the app as appuser.
ENV PORT=8000 \
    WORKERS=2

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:%s/health' % os.environ.get('PORT','8000')).status==200 else 1)"

ENTRYPOINT ["sh", "/srv/docker-entrypoint.sh"]
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers ${WORKERS}"]
