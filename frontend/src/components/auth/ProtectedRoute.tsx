import React from 'react';
import { Link, Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import type { UserType } from '../../types/auth';
import { getDashboardPath, isRoleAllowed } from '../../utils/authRouting';
import { Button, Card } from '../ui';

interface ProtectedRouteProps {
  children: React.ReactNode;
  allowedRoles?: UserType[];
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children, allowedRoles }) => {
  const { isAuthenticated, isLoading, currentUser } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-[calc(100vh-140px)] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-textSecondary">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <p className="text-sm font-medium">Verifying session...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated || !currentUser) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Unverified doctors are locked out of the entire system except the pending-verification page
  if (
    currentUser.userType === 'doctor' &&
    currentUser.isVerified === false &&
    location.pathname !== '/pending-verification'
  ) {
    return <Navigate to="/pending-verification" replace />;
  }

  if (allowedRoles && !isRoleAllowed(currentUser.userType, allowedRoles)) {
    return <Navigate to={getDashboardPath(currentUser.userType)} replace />;
  }

  return <>{children}</>;
};
