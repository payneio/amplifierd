import { BrowserRouter, Routes, Route, Navigate } from 'react-router'
import { MainLayout } from '@/components/layout/MainLayout'
import { HomePage } from '@/pages/Home'
import { CollectionsPage } from '@/pages/Collections'
import { DirectoriesPage } from '@/pages/Directories'
import { SessionView } from '@/features/session'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<Navigate to="/home" replace />} />
          <Route path="home" element={<HomePage />} />
          <Route path="collections" element={<CollectionsPage />} />
          <Route path="directories" element={<DirectoriesPage />} />
          <Route path="directories/sessions/:sessionId" element={<SessionView />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
