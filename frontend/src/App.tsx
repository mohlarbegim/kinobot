import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './auth'
import ProtectedRoute from './components/ProtectedRoute'
import AppLayout from './components/AppLayout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Users from './pages/Users'
import Payments from './pages/Payments'
import Movies from './pages/Movies'
import Categories from './pages/Categories'
import Channels from './pages/Channels'
import Tariffs from './pages/Tariffs'
import MessageTemplates from './pages/MessageTemplates'
import Broadcasts from './pages/Broadcasts'
import Settings from './pages/Settings'

export default function App() {
  return (
    <BrowserRouter basename="/dashboard">
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Dashboard />} />
            <Route path="users" element={<Users />} />
            <Route path="payments" element={<Payments />} />
            <Route path="movies" element={<Movies />} />
            <Route path="categories" element={<Categories />} />
            <Route path="channels" element={<Channels />} />
            <Route path="tariffs" element={<Tariffs />} />
            <Route path="messages" element={<MessageTemplates />} />
            <Route path="broadcasts" element={<Broadcasts />} />
            <Route path="settings" element={<Settings />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
