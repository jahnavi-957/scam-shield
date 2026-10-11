FROM node:22-alpine

WORKDIR /app

# Install dependencies first (layer caching benefit).
COPY package.json ./
RUN npm install

COPY . .

EXPOSE 5173

# Vite dev server; `host: true` is set in vite.config.ts so it listens
# on 0.0.0.0 inside the container.
CMD ["npm", "run", "dev"]