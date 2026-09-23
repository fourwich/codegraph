# Optional runtime image with Dgraph client deps preinstalled
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir -e .
EXPOSE 8080
CMD ["codegraph", "serve", "--port", "8080", "--no-open-browser"]
