# Build from the repository root:  docker build -f packages/server/Dockerfile -t tonedown-server .
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages ./packages
RUN uv sync --all-packages --no-dev --frozen
ENV PATH="/app/.venv/bin:$PATH" TONEDOWN_HOST=0.0.0.0 TONEDOWN_PORT=8080
EXPOSE 8080
CMD ["tonedown-server"]
