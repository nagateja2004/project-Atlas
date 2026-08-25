# Project Atlas dashboard image.
#
# NEXT_PUBLIC_API_URL is deliberately NOT set at build time. NEXT_PUBLIC_*
# values are inlined into the browser bundle when `next build` runs, so baking
# a hostname in would force an image rebuild every time the instance's public
# address changes. Instead src/lib/api.ts falls back to "" in production, which
# makes every call same-origin - and Caddy routes the API paths to the API
# container on that same origin. The dashboard is therefore host-agnostic.

# ---------- builder ----------
FROM node:20-slim AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# ---------- runtime ----------
FROM node:20-slim AS runtime

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

WORKDIR /app

RUN useradd --create-home --uid 10002 nextjs

# output: "standalone" traces the runtime dependency set into
# .next/standalone, including a minimal server.js. static/ and public/ are not
# traced and must be copied alongside it or the page loads without CSS.
COPY --from=builder --chown=nextjs:nextjs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nextjs /app/.next/static ./.next/static

USER nextjs

ENV PORT=3000
ENV HOSTNAME=0.0.0.0
EXPOSE 3000

CMD ["node", "server.js"]
