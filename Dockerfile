FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Run as an unprivileged user
RUN useradd --system --uid 10001 --no-create-home appuser
USER 10001

EXPOSE 8000

# python:slim has no curl, so the health check uses the standard library
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthcheck' % os.environ.get('PORT','8000'), timeout=2)"

# --worker-tmp-dir /dev/shm: gunicorn then needs no writable /tmp, so the container also runs with
# readOnlyRootFilesystem (see yamls/Deployment.yaml)
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --workers 2 --worker-tmp-dir /dev/shm --access-logfile - 'app.api:create_app()'"]
