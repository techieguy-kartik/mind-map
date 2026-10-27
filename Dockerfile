FROM node:20-bookworm-slim AS frontend
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY index.html tsconfig.json vite.config.ts ./
COPY public public
COPY src src
RUN npm run build

FROM python:3.14-slim
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY server server
COPY --from=frontend /app/dist dist
RUN useradd --create-home atlas && mkdir /app/var && chown atlas:atlas /app/var
USER atlas
ENV ATLAS_HOST=0.0.0.0 ATLAS_PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"]
CMD ["python", "-m", "server.start"]
