FROM python:3.12-slim AS dependencies
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY requirements.txt .
RUN python -m pip install --prefix=/install -r requirements.txt

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONFAULTHANDLER=1 PATH="/home/app/.local/bin:$PATH"
WORKDIR /app
RUN groupadd --system app && useradd --system --gid app --create-home app
COPY --from=dependencies /install /usr/local
COPY --chown=app:app . /app
RUN mkdir -p /app/media && chown app:app /app/media \
    && chmod 755 /app/docker-entrypoint.sh \
    && python manage.py collectstatic --noinput
USER app
EXPOSE 10000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:10000/', timeout=3)" || exit 1
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-10000} --workers 2 --access-logfile - --error-logfile -"]
