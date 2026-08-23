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

  if (allowedRoles && !isRoleAllowed(currentUser.userType, allowedRoles)) {
    return (
      <div className="min-h-[calc(100vh-140px)] flex items-center justify-center px-4 py-10">
        <Card radius="3xl" shadow="md" className="max-w-md w-full p-8 text-center space-y-4">
          <div className="w-14 h-14 rounded-2xl bg-errorContainer/40 text-error flex items-center justify-center mx-auto text-2xl">
            🚫
          </div>
          <div className="space-y-2">
            <h1 className="text-xl font-extrabold text-textPrimary">Access Denied</h1>
            <p className="text-sm text-textSecondary leading-relaxed">
              Your account does not have permission to view this page. You are signed in as{' '}
              <strong className="text-textPrimary">{currentUser.userType}</strong>.
            </p>
          </div>
          <Link to={getDashboardPath(currentUser.userType)}>
            <Button variant="primary" className="w-full justify-center">
              Go to My Dashboard
            </Button>
          </Link>
        </Card>
      </div>
    );
  }

  return <>{children}</>;
};
