FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AGENTIC_API_HOST=0.0.0.0 \
    AGENTIC_API_PORT=8080

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

USER 65532:65532
EXPOSE 8080
CMD ["uvicorn", "agentic_api.main:app", "--host", "0.0.0.0", "--port", "8080"]

