import { Outlet, NavLink } from 'react-router'
import { cn } from '@/lib/utils'
import { Home, FolderOpen, Package } from 'lucide-react'

export function MainLayout() {
  return (
    <div className="flex h-screen">
      <aside className={cn(
        "w-64 border-r bg-gray-50",
        "flex flex-col"
      )}>
        <div className="p-4 border-b">
          <h1 className="text-xl font-bold">Amplifier</h1>
        </div>
        <nav className="flex-1 p-4">
          <ul className="space-y-2">
            <li>
              <NavLink
                to="/home"
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 px-3 py-2 rounded-md transition-colors",
                    isActive ? "bg-primary text-primary-foreground" : "hover:bg-gray-200"
                  )
                }
              >
                <Home className="h-4 w-4" />
                <span>Home</span>
              </NavLink>
            </li>
            <li>
              <NavLink
                to="/collections"
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 px-3 py-2 rounded-md transition-colors",
                    isActive ? "bg-primary text-primary-foreground" : "hover:bg-gray-200"
                  )
                }
              >
                <Package className="h-4 w-4" />
                <span>Collections</span>
              </NavLink>
            </li>
            <li>
              <NavLink
                to="/directories"
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 px-3 py-2 rounded-md transition-colors",
                    isActive ? "bg-primary text-primary-foreground" : "hover:bg-gray-200"
                  )
                }
              >
                <FolderOpen className="h-4 w-4" />
                <span>Directories</span>
              </NavLink>
            </li>
          </ul>
        </nav>
      </aside>

      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
