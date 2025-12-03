# Amplifier Web Application

React + TypeScript web UI for the Amplifier system, backed by the [Amplifier Daemon](../amplifierd/amplifierd/README.md).

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
## Environment Variables

Create a `.env` file:

```
VITE_API_URL=http://localhost:8421
```

