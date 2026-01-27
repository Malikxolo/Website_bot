FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml .
COPY uv.lock* .

# Install dependencies with uv
RUN uv sync --frozen --no-dev

COPY . .

EXPOSE 8020

CMD ["uv", "run", "main.py"]