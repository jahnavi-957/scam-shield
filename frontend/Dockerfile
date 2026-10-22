FROM node:22-alpine

RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

# Install dependencies first (layer caching benefit).
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

RUN mkdir -p /tmp/.vite_cache && chown -R appuser:appgroup /app /tmp/.vite_cache
USER appuser

EXPOSE 5173

# Vite dev server; `host: true` is set in vite.config.ts so it listens
# on 0.0.0.0 inside the container.
CMD ["npm", "run", "dev"]
