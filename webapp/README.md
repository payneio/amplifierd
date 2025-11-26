# Amplifier Web Application

React + TypeScript web UI for the Amplifier system.

## Tech Stack

- **React 19** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **React Router 7** - Client-side routing
- **TanStack Query** - Server state management
- **Tailwind CSS 4** - Styling
- **Lucide React** - Icons

## Development

```bash
# Install dependencies
pnpm install

# Start dev server (http://localhost:5173)
pnpm dev

# Build for production
pnpm build

# Preview production build
pnpm preview
```

## Project Structure

```
webapp/
├── src/
│   ├── api/              # API client functions
│   ├── features/         # Feature modules
│   │   ├── collections/  # Collection management
│   │   ├── directories/  # Amplified directory management
│   │   └── session/      # Session management
│   ├── components/       # React components
│   │   ├── ui/          # Reusable UI components
│   │   └── layout/      # Layout components
│   ├── lib/             # Utilities and shared code
│   ├── pages/           # Route pages
│   └── types/           # TypeScript type definitions
```

## Environment Variables

Create a `.env` file:

```
VITE_API_URL=http://localhost:8000
```

## Architecture

This application follows the modular "bricks & studs" philosophy:

- **Features** are self-contained modules with their own components, API calls, and state
- **Components** are reusable UI building blocks
- **API layer** provides typed interface to backend
- **React Query** manages server state and caching
- **React Router** handles navigation

## Current Status

**Phase 1 Complete** - Foundation setup with:
- ✅ Vite + React + TypeScript configured
- ✅ Tailwind CSS 4 styling
- ✅ React Router navigation
- ✅ React Query state management
- ✅ Directory structure established
- ✅ Path aliases (`@/`) configured
- ✅ Basic layout with sidebar

**Next: Phase 2** - Collection management UI
