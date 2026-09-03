import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Layout } from './components/layout/Layout';
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import { GuestRoute } from './components/auth/GuestRoute';
import { LandingPage } from './pages/LandingPage';
import { ComponentShowcase } from './pages/ComponentShowcase';
import { Login } from './pages/Login';
import { Register } from './pages/Register';
import { Dashboard } from './pages/Dashboard';
import { Chat } from './pages/Chat';
import { Appointments } from './pages/Appointments';
import { DoctorDashboard } from './pages/DoctorDashboard';
import { Admin } from './pages/Admin';
import { PlaceholderPage } from './pages/PlaceholderPage';
import { getDashboardPath } from './utils/authRouting';

/**
 * Top-level error boundary: catches unhandled render errors
 * and shows a friendly fallback instead of a white screen.
 */
class AppErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('AppErrorBoundary caught:', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50 p-6">
          <div className="max-w-md w-full bg-white rounded-2xl shadow-lg p-8 text-center space-y-4">
            <div className="w-14 h-14 mx-auto rounded-full bg-red-100 flex items-center justify-center">
              <span className="text-2xl">!</span>
            </div>
            <h2 className="text-xl font-bold text-gray-900">Something went wrong</h2>
            <p className="text-sm text-gray-600">
              An unexpected error occurred. Please refresh the page to continue.
            </p>
            <button
              onClick={() => window.location.reload()}
              className="px-6 py-2.5 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 transition-colors"
            >
              Refresh Page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

const RootIndexRoute: React.FC = () => {
  const { isAuthenticated, isLoading, currentUser } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-[calc(100vh-140px)] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (isAuthenticated && currentUser) {
    return <Navigate to={getDashboardPath(currentUser.userType)} replace />;
  }

  return <LandingPage />;
};

export function App() {
  return (
    <AppErrorBoundary>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
            <Route path="/" element={<RootIndexRoute />} />

            <Route
              path="/login"
              element={
                <GuestRoute>
                  <Login />
                </GuestRoute>
              }
            />
            <Route
              path="/register"
              element={
                <GuestRoute>
                  <Register />
                </GuestRoute>
              }
            />

            <Route path="/showcase" element={<ComponentShowcase />} />

            <Route
              path="/dashboard"
              element={
                <ProtectedRoute allowedRoles={['patient']}>
                  <Dashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/chat"
              element={
                <ProtectedRoute>
                  <Chat />
                </ProtectedRoute>
              }
            />
            <Route
              path="/appointments"
              element={
                <ProtectedRoute>
                  <Appointments />
                </ProtectedRoute>
              }
            />
            <Route
              path="/doctor-dashboard"
              element={
                <ProtectedRoute allowedRoles={['doctor']}>
                  <DoctorDashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin"
              element={
                <ProtectedRoute allowedRoles={['admin']}>
                  <Admin />
                </ProtectedRoute>
              }
            />
            <Route
              path="/receptionist-dashboard"
              element={
                <ProtectedRoute allowedRoles={['receptionist']}>
                  <PlaceholderPage
                    title="Receptionist Dashboard"
                    description="Manage patient check-ins, desk scheduling, and appointment queues."
                    path="/receptionist-dashboard"
                  />
                </ProtectedRoute>
              }
            />

            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
    </AppErrorBoundary>
  );
}

export default App;
