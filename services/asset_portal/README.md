# Game Asset Portal (SPA)

This package bootstraps the React single-page application for the studio asset management portal. The goal is to provide a responsive, accessible control center for artists, reviewers, producers, and operations teams on top of the existing FastAPI + PostgreSQL stack.

## Features

- React + TypeScript powered by Vite for fast iteration
- Chakra UI design system with automatic light/dark theming
- React Router layout with landing, dashboard, discovery, workflow, operations, and settings views
- React Query client and Axios ready for REST/OpenAPI integration
- Localization scaffold via `react-i18next`
- Testing setup with Vitest and Testing Library

## Getting Started

```bash
cd services/asset_portal
npm install
npm run dev
```

The development server will be available at http://localhost:5173.

### Build & Test

```bash
npm run lint
npm run test
npm run build
```

## Next Steps

- Connect to the FastAPI OpenAPI spec to generate the typed API client
- Replace mocked dashboard data with live analytics endpoints
- Implement OAuth2/SAML SSO auth guard and role-aware navigation filters
- Expand asset detail views with previews, comments, annotations, and merge readiness flows
