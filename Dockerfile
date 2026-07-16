FROM node:24-bookworm-slim AS build

WORKDIR /app/server

RUN corepack enable && corepack prepare pnpm@11.13.0 --activate

COPY server/package.json server/pnpm-lock.yaml server/pnpm-workspace.yaml server/tsconfig.json ./
RUN pnpm install --frozen-lockfile

COPY server/ ./
RUN pnpm build && pnpm prune --prod

FROM node:24-bookworm-slim AS runtime

WORKDIR /app/server
ENV NODE_ENV=production
ENV PORT=3870

RUN corepack enable && corepack prepare pnpm@11.13.0 --activate

COPY --from=build /app/server/package.json ./package.json
COPY --from=build /app/server/node_modules ./node_modules
COPY --from=build /app/server/dist ./dist

USER node
EXPOSE 3870
CMD ["node", "dist/server.js"]
