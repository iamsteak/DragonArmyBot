FROM node:22-alpine AS build
WORKDIR /app
COPY package.json pnpm-lock.yaml* ./
RUN corepack enable && pnpm install --frozen-lockfile=false
COPY tsconfig.json ./
COPY src ./src
RUN pnpm exec tsc -p tsconfig.json

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
COPY package.json pnpm-lock.yaml* ./
RUN corepack enable && pnpm install --prod --frozen-lockfile=false
COPY --from=build /app/dist ./dist
RUN mkdir -p /app/data
CMD ["node", "dist/index.js"]
