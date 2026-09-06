import React from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { Navbar } from '../ui/Navbar';
import { useAuth } from '../../context/AuthContext';
import { getNavItemsForUserType, getUserTypeLabel } from '../../utils/authRouting';

export const Layout: React.FC = () => {
  const { currentUser, logout, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  const navbarUser = currentUser
    ? {
        name: currentUser.name || 'User',
        email: currentUser.email,
        avatarUrl: currentUser.avatarUrl,
        role: getUserTypeLabel(currentUser.userType),
        isPatient: currentUser.userType === 'patient',
      }
    : null;

  const navItems = currentUser ? getNavItemsForUserType(currentUser.userType) : undefined;

  return (
    <div className="min-h-screen bg-background text-textPrimary flex flex-col font-sans selection:bg-primaryContainer/20 selection:text-primary">
      <Navbar
        user={isAuthenticated ? navbarUser : null}
        navItems={navItems}
        onLogout={isAuthenticated ? handleLogout : undefined}
      />
      <main className="flex-1 w-full">
        <Outlet />
      </main>
      <footer className="mt-auto border-t border-surfaceContainerHigh bg-white/70 py-6 text-center">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-3">
          <p className="text-xs text-textSecondary">
            © {new Date().getFullYear()} MediBook AI. All rights reserved. Design System & Healthcare Platform.
          </p>
          <div className="flex items-center gap-4 text-xs font-medium text-textSecondary">
            <span className="inline-flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-secondary"></span>
              Design System Active
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
};
