# Phase 9 — Frontend scaffold + Supabase Auth

> Paste-load: read this file end-to-end, execute every section. Bypass mode is assumed active.

## Context

Phase 9 turns the frontend (already scaffolded in Phase 1 with Next.js 16 + shadcn/ui + pnpm) into an authenticated shell. By the end: users can sign up / log in / log out via Supabase Auth, hit protected routes, and see a minimal dashboard skeleton. Also sets up the typed API client that talks to the FastAPI backend.

Reference:
- `CLAUDE.md` — Stack > Frontend.
- `docs/BUILD_PLAN.md` — Phase 9 section (reference only).
- [Supabase SSR docs](https://supabase.com/docs/guides/auth/server-side/nextjs) for App Router.

## Running mode

`--dangerously-skip-permissions` active. Commit + push to main on validation success.

## Design principles (apply throughout)

- Follow shadcn/ui defaults, `base-nova` style (from Phase 1 `components.json`). NO custom CSS unless required.
- Loading states → `Skeleton` components. No spinners.
- Empty states → shadcn card + icon (`lucide-react`) + CTA button.
- Toasts via `sonner` (already installed).
- Dark mode default, accessible theme toggle (`next-themes` — install if missing).
- Every interactive element: focus rings, aria labels, keyboard navigable.

## Tasks

### 1. Supabase client helpers

`frontend/src/lib/supabase/client.ts`:
- Export `createBrowserClient` wrapped for `NEXT_PUBLIC_*` envs.

`frontend/src/lib/supabase/server.ts`:
- Export `createServerClient` that reads cookies via `next/headers`.
- Use the `@supabase/ssr` helpers (`createServerClient` + cookies adapter).

`frontend/src/lib/supabase/middleware.ts`:
- Helper that refreshes the session on every request and forwards cookies.

### 2. Route middleware

`frontend/middleware.ts` (at the **root** of frontend/, not under src/):

- Protect: `/dashboard`, `/positions`, `/risk`, `/scenarios`, `/settings` (and subpaths).
- Unauthenticated → redirect to `/login?next=<original path>`.
- Public: `/login`, `/signup`, `/api/*` (if any), static assets.

### 3. Auth pages

`frontend/src/app/(auth)/layout.tsx`: centered card layout with dark/light background.

`frontend/src/app/(auth)/login/page.tsx`:
- Form: email + password, built with `react-hook-form` + `zod` resolver.
- Submit → `supabase.auth.signInWithPassword`.
- "Sign in with magic link" button as secondary action.
- Error state under the form, success → redirect to `?next=` param or `/dashboard`.
- Link to `/signup`.

`frontend/src/app/(auth)/signup/page.tsx`:
- Same shape, calls `supabase.auth.signUp`.
- Post-signup: show "Check your email to confirm" message (no auto-login).

### 4. Dashboard shell

`frontend/src/app/(dashboard)/layout.tsx`:
- Sidebar using shadcn's `sidebar` primitive. Collapsible with `Cmd+B` hotkey.
- Sidebar nav items: Dashboard, Positions, Risk, Scenarios, Settings.
- Top bar: breadcrumbs from `pathname`, user avatar dropdown (email + Sign out), theme toggle.
- Uses `SidebarProvider`, `SidebarTrigger` from shadcn.

`frontend/src/app/(dashboard)/page.tsx`: placeholder — 4 `Card` components with zeroed KPIs.

### 5. Typed API client

- Generate OpenAPI types: run `npx openapi-typescript http://localhost:8000/api/v1/openapi.json -o frontend/src/lib/api/types.ts` (script assumes backend is running; if not, dump the spec once and commit the types).
- Add npm script `"generate:api": "openapi-typescript http://localhost:8000/api/v1/openapi.json -o src/lib/api/types.ts"`.
- `frontend/src/lib/api/fetcher.ts`:
  - Thin wrapper around `fetch` that injects `Authorization: Bearer <token>` from the current Supabase session.
  - Handles RFC 7807 error bodies: parse and surface as a `ProblemDetailsError`.
- `frontend/src/lib/api/hooks/`: one TanStack Query hook per endpoint family (e.g., `usePhysicalFrames`, `useCreateFrame`). Lazy expansion — only create the ones used in Phase 9's pages.

### 6. Global layout

`frontend/src/app/layout.tsx`:
- Wrap children in:
  - `ThemeProvider` (next-themes)
  - `QueryClientProvider` (TanStack Query)
  - `Toaster` (sonner)
- HTML lang: `pt-BR`.
- Metadata: title = "Market Risk Platform", description.

### 7. Smoke page at /debug/health

`frontend/src/app/(dashboard)/debug/health/page.tsx`:
- Authenticated page that calls `/api/v1/health` via the typed client and shows the JSON response.
- Used as a quick sanity that JWT + client + backend are wired.

## Constraints

- NO `any` types — `unknown` + narrowing or generated types.
- No global state libraries beyond Zustand (already installed) + TanStack Query.
- No custom auth — rely on Supabase Auth.
- Keep bundle size controlled: use `dynamic` imports for heavy widgets when they're added later.

## MANDATORY validation

1. `cd frontend && pnpm lint`  → 0 errors
2. `cd frontend && pnpm typecheck`  → 0 errors
3. `cd frontend && pnpm format:check`  → clean
4. `cd frontend && pnpm build`  → successful, `/login`, `/signup`, `/dashboard` routes present in build summary
5. Manual (with backend running):
   - `pnpm dev` → visit `/login` → signup a test user → receive confirmation email (or click magic link) → land on `/dashboard`
   - Cmd+B toggles sidebar
   - Dark/light theme toggle works
   - Visit `/debug/health` → shows `{"status":"ok","version":"0.1.0"}`
6. Lighthouse (chrome://lighthouse) on `/login`: Performance ≥ 90, Accessibility ≥ 95

Invariants:
- [ ] 5 protected routes redirect to `/login?next=` when unauthenticated
- [ ] Logged-in session persists across page reload (SSR cookies work)
- [ ] Theme toggle and sidebar toggle work
- [ ] Sign out clears session and redirects to `/login`
- [ ] `/debug/health` shows live backend response
- [ ] Lighthouse scores meet thresholds
- [ ] Bundle size: `/dashboard` route < 300 KB gzipped

## Commit + push

```bash
git add -A
git commit -m "feat(frontend): Phase 9 — Supabase Auth + dashboard shell + typed API client

- lib/supabase/: browser, server, middleware helpers using @supabase/ssr
- middleware.ts: protect /dashboard, /positions, /risk, /scenarios, /settings
- (auth)/login + signup pages with react-hook-form + zod
- (dashboard)/layout: shadcn Sidebar + breadcrumbs + user dropdown + theme toggle
- lib/api/: openapi-typescript generated types + fetch wrapper with JWT injection
- TanStack Query + ThemeProvider + Toaster wired at root
- /debug/health smoke page confirms JWT + backend integration

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin main
```

## COWORK HANDOFF

Standard format; include:
- Routes added
- Lighthouse scores
- Bundle sizes for each route
- Screenshot or manual confirmation that login → dashboard → logout flow works
- Any deviations from shadcn defaults
