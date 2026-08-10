# Frontend Documentation

## Overview

The frontend is a React 19 + TypeScript application built with Vite. It provides the user interface for the School Operations & Governance Platform.

## Technology Stack

- **Framework**: React 19
- **Language**: TypeScript
- **Build Tool**: Vite 8
- **Routing**: React Router 7
- **Auth**: @neondatabase/auth (Neon Better Auth)
- **Database Client**: @neondatabase/neon-js

## Project Structure

```
frontend/
├── index.html                 # HTML entry point
├── package.json               # Dependencies and scripts
├── vite.config.ts             # Vite configuration
├── tsconfig.json              # TypeScript configuration
├── eslint.config.js           # ESLint configuration
├── public/
│   ├── favicon.svg            # Favicon
│   └── icons.svg              # Icons sprite
└── src/
    ├── main.tsx               # React entry point
    ├── App.tsx                # Main app with routing
    ├── App.css                # Global styles
    ├── index.css              # Base styles
    ├── assets/                # Static assets (images, SVGs)
    ├── lib/
    │   └── auth.ts            # Auth client setup
    └── components/
        ├── module-components.css  # Shared module component styles
        ├── schools/
        │   ├── SchoolList.tsx     # School list view
        │   └── SchoolForm.tsx     # School create/edit form
        ├── departments/
        │   ├── DepartmentList.tsx # Department list view
        │   └── DepartmentForm.tsx # Department create/edit form
        ├── users/
        │   ├── UserList.tsx       # User list view
        │   └── UserForm.tsx       # User create/edit form
        └── configuration/
            └── ConfigurationPanel.tsx  # Configuration management
```

## Routing

The app uses React Router 7 with routes defined in `App.tsx`:

| Route | Component | Description |
|-------|-----------|-------------|
| `/` | Home | Landing page with dashboard links |
| `/auth` | Auth | Authentication view |
| `/account` | Account | User account management |
| `/schools` | SchoolList | List all schools |
| `/schools/new` | SchoolForm | Create new school |
| `/schools/:id/edit` | SchoolForm | Edit school |
| `/departments` | DepartmentList | List all departments |
| `/departments/new` | DepartmentForm | Create new department |
| `/departments/:id/edit` | DepartmentForm | Edit department |
| `/users` | UserList | List all users |
| `/users/new` | UserForm | Create new user |
| `/users/:id/edit` | UserForm | Edit user |
| `/configuration` | ConfigurationPanel | Configuration management |

## Authentication

Authentication is handled via Neon Auth (`@neondatabase/auth`).

### Auth Client Setup (`src/lib/auth.ts`)

```
typescript
import { createAuthClient } from "@neondatabase/neon-js/auth";

export const authClient = createAuthClient(import.meta.env.VITE_NEON_AUTH_URL);
```

### Auth Components

The `@neondatabase/auth/react` package provides:
- `AuthView` - Authentication form
- `AccountView` - Account management
- `SignedIn` - Conditional rendering when signed in
- `SignedOut` - Conditional rendering when signed out
- `UserButton` - User profile button

### Token Storage

The frontend stores the auth token in `localStorage` under the key `auth_token` and includes it in API requests:

```typescript
const token = localStorage.getItem('auth_token')
const response = await fetch('/api/v1/schools', {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
})
```

## API Integration

The frontend communicates with the backend via REST API calls under the `/api/v1` prefix.

### Example: Fetching Schools (`SchoolList.tsx`)

```
typescript
const token = localStorage.getItem('auth_token')
const response = await fetch(`/api/v1/schools?page=${page}&page_size=50`, {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
})

const data: SchoolListResponse = await response.json()
setSchools(data.data)
setTotal(data.pagination.total_count)
```

### API Response Envelope

List endpoints return a standard pagination envelope:

```
typescript
interface SchoolListResponse {
  data: School[]
  pagination: {
    page: number
    page_size: number
    total_count: number
    has_next: boolean
  }
}
```

## Environment Variables

The frontend requires the following environment variables:

| Variable | Description |
|----------|-------------|
| `VITE_NEON_AUTH_URL` | Neon Auth URL for the auth client |

Create a `.env` file in the `frontend/` directory:
```
VITE_NEON_AUTH_URL=https://your-neon-auth-url
```

## Development

### Install Dependencies
```
bash
cd frontend
pnpm install
```

### Run Development Server
```bash
pnpm dev
```

The app will be available at the Vite dev server URL (typically `http://localhost:5173`).

### Build for Production
```
bash
pnpm build
```

### Lint
```
bash
pnpm lint
```

## Development Proxy

For local development, the Vite dev server should proxy API requests to the backend. Configure `vite.config.ts`:

```
typescript
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
```

> **Note**: The current `vite.config.ts` does not include a proxy configuration. This may cause issues when the frontend and backend are run separately during development. It is recommended to add the proxy configuration above so that `/api/*` requests are forwarded to the FastAPI backend.
