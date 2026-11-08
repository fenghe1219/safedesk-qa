FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /qa

COPY pyproject.toml ./
COPY qa ./qa
RUN pip install --no-cache-dir ".[dev]"

COPY tests ./tests
COPY datasets ./datasets
COPY scripts ./scripts

CMD ["python", "-m", "pytest", "tests/unit", "tests/api", "tests/eval", "-q"]
