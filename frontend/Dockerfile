# syntax=docker/dockerfile:1

# ─────────────────────────────────────────────────────────────────────────
# Stage 1: build — compile the Vite/React app to static assets.
# ─────────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS build

WORKDIR /build

# Install deps first so this layer is cached as long as the lockfile
# doesn't change, independent of source edits.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# VITE_API_URL is inlined into the JS bundle at BUILD time (Vite env vars
# are not readable at container runtime), so it must be a build arg, not a
# runtime env var. Default is "" (relative paths, e.g. `/api/auth/login`):
# the nginx config in this same image proxies `/api/*` to the backend
# service, so the frontend and backend share one origin and no CORS
# configuration or rebuild-per-environment is needed. Override at build
# time (--build-arg VITE_API_URL=https://api.example.com) only if the API
# is genuinely served from a different origin than this frontend.
ARG VITE_API_URL=""
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

# ─────────────────────────────────────────────────────────────────────────
# Stage 2: runtime — nginx serving the static build + reverse-proxying /api.
# ─────────────────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime

RUN rm -f /etc/nginx/conf.d/default.conf
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=build /build/dist /usr/share/nginx/html

# nginx:alpine already runs its master process as root but worker
# processes as the unprivileged `nginx` user by default; the app dirs it
# needs to write to (cache/run) are already owned appropriately by the
# base image, so no extra chown is required here.

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:80/ >/dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
