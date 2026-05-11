# ── Stage 1: build deps ─────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

RUN pip install --upgrade pip setuptools wheel

COPY requirements.txt pyproject.toml ./
RUN pip install -e .
RUN pip install --no-cache-dir -r requirements.txt

COPY harness/ harness/
COPY skills/ skills/
COPY static/ static/
COPY channels/ channels/
COPY main.py ./


# ── Stage 2: runtime ────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Install poppler for pdf2image (pdf support in analyze_image tool).
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from builder.
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /build /app

RUN useradd -m -u 1000 harness && chown -R harness:harness /app
USER harness

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["python", "main.py", "--serve"]
