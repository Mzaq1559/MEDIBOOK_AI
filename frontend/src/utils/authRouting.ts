import type { UserType } from '../types/auth';
import type { NavItem } from '../components/ui/Navbar';

export function getDashboardPath(userType: UserType): string {
  switch (userType) {
    case 'doctor':
      return '/doctor-dashboard';
    case 'admin':
      return '/admin';
    case 'receptionist':
      return '/receptionist-dashboard';
    case 'patient':
    default:
      return '/dashboard';
  }
}

export function getUserTypeLabel(userType: UserType): string {
  switch (userType) {
    case 'doctor':
      return 'Doctor';
    case 'admin':
      return 'Administrator';
    case 'receptionist':
      return 'Receptionist';
    case 'patient':
    default:
      return 'Patient';
  }
}

export function isRoleAllowed(userType: UserType, allowedRoles: UserType[]): boolean {
  return allowedRoles.includes(userType);
}

const ROUTE_ROLE_MAP: Record<string, UserType[]> = {
  '/dashboard': ['patient'],
  '/doctor-dashboard': ['doctor'],
  '/admin': ['admin'],
  '/receptionist-dashboard': ['receptionist'],
};

export function isPathAllowedForUserType(path: string, userType: UserType): boolean {
  const allowedRoles = ROUTE_ROLE_MAP[path];
  if (!allowedRoles) {
    return true;
  }
  return allowedRoles.includes(userType);
}

export function getNavItemsForUserType(userType: UserType): NavItem[] {
  const sharedItems: NavItem[] = [
    { label: 'Appointments', path: '/appointments' },
    { label: 'AI Health Chat', path: '/chat', badge: 'AI' },
  ];

  switch (userType) {
    case 'admin':
      return [{ label: 'Admin Portal', path: '/admin' }, ...sharedItems];
    case 'doctor':
      return [{ label: 'Doctor Portal', path: '/doctor-dashboard' }, ...sharedItems];
    case 'receptionist':
      return [{ label: 'Receptionist Portal', path: '/receptionist-dashboard' }, ...sharedItems];
    case 'patient':
    default:
      return [{ label: 'Dashboard', path: '/dashboard' }, ...sharedItems];
  }
}

export function mapRegisterRoleToUserType(role: 'Patient' | 'Doctor'): UserType {
  return role === 'Doctor' ? 'doctor' : 'patient';
}

