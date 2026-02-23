# Build from repo root: docker build -t food-web -f web/Dockerfile .
FROM node:20-alpine AS base

WORKDIR /app

# Dependencies
COPY web/package.json web/package-lock.json* ./
RUN npm ci

# Source and build
COPY web/ .
RUN npm run build

EXPOSE 3000
ENV NODE_ENV=production
# BACKEND_URL is set at runtime in docker-compose for rewrite target
CMD ["npm", "start"]
