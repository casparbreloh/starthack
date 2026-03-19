# frontend/

## Purpose

React/TypeScript UI for the Mars Greenhouse Agent System. Currently a skeleton — displays "Hello World".

## Tech

- React 19, TypeScript 5.9 (strict mode)
- Vite 8 (bundler)
- Tailwind CSS 4 (via @tailwindcss/vite plugin)

## Key Files

- `src/main.tsx` — App entry point, renders `<App />`
- `src/App.tsx` — Root component
- `src/index.css` — Tailwind imports
- `package.json` — Dependencies and scripts
- `tsconfig.json` — Strict TS config, bundler module resolution

## Commands

```bash
pnpm install  # Install dependencies
pnpm dev      # Start dev server
pnpm build    # Production build
```

## Conventions

- Strict TypeScript: no unused locals/parameters, no fallthrough cases
- ES2022 target, ESNext modules
- Base URL: `.` (relative imports from project root)
