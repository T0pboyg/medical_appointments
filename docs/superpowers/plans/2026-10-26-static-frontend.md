# Static frontend implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Serve the built React application locally with Caddy while retaining Vite development mode.

**Architecture:** A Node build stage creates dist; the runtime image contains only Caddy, its configuration and dist. A Compose override replaces only frontend; the existing localhost:5173 origin, API and OIDC settings remain valid.

**Tech stack:** React, Vite, Docker Compose, Caddy.

**Approved design:** Separate compose.static.yaml; localhost:5173; server-only proxy secret; security headers; SPA fallback for /admin; test before switching the normal stack. Approved in the conversation on 2026-10-26.

## Constraints and review focus

- No secrets in build arguments, bundle or build context.
- Overwrite visitor-supplied proxy identity headers using the actual peer address.
- API failures must remain API responses, never the SPA document.
- Missing assets return 404; HTML revalidates, fingerprinted assets can be cached.
- Keep production data, Keycloak and stashes intact; browser tests use only the isolated database and test login.

## Tasks

- [x] Add static browser checks for HTML/assets, SPA routes, API errors, headers and spoofed forwarding headers. Observed failure on Vite: /@vite/client present.
- [x] Add frontend/Dockerfile, .dockerignore, Caddyfile and build script; add local and e2e Compose overrides.
- [x] Validate Compose and Caddy; 7 browser tests passed against static frontend; local image built.
- [x] Add CI coverage and local switching/rebuild instructions; removed isolated test containers. No commit/push.

## Review ledger

- Final independent read-only review: no blocking findings; proxy overwrite, runtime-only secret, Compose switching and localhost OIDC settings checked.
- Real Keycloak login and live Ollama conversations remain manual verification; synthetic browser tests do not substitute for those checks.
- Base compose.yaml and both old stashes remain unchanged. No changes to patient data or database schema.
