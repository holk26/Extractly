FROM python:3.12-slim

# Prevent .pyc files and force unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Store Playwright browsers outside the user home so a non-root user can reach them
    PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers

WORKDIR /app

# Install Python deps + Playwright Chromium in one layer to minimise image size.
# `playwright install chromium --with-deps` handles all OS-level browser dependencies
# automatically and cleans up the apt cache.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install chromium --with-deps \
    && rm -rf /var/lib/apt/lists/*

# Copy application source (separate layer so source changes don't re-install deps)
COPY . .

# Run as an unprivileged user for defence-in-depth
RUN useradd --no-create-home --shell /bin/false appuser \
    && chown -R appuser:appuser /app /opt/pw-browsers

USER appuser

EXPOSE 8000

# Lightweight liveness probe – succeeds once the root route responds
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

