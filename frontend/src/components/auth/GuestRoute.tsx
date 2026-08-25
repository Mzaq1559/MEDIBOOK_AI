import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { getDashboardPath } from '../../utils/authRouting';

export const GuestRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading, currentUser } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-[calc(100vh-140px)] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-textSecondary">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <p className="text-sm font-medium">Loading...</p>
        </div>
      </div>
    );
  }

  if (isAuthenticated && currentUser) {
    const from = (location.state as { from?: { pathname?: string } })?.from?.pathname;
    const destination = from && from !== '/login' && from !== '/register'
      ? from
      : getDashboardPath(currentUser.userType);
    return <Navigate to={destination} replace />;
  }

  return <>{children}</>;
};
