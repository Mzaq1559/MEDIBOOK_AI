import type { UserType } from '../types/auth';
import type { NavItem } from '../components/ui/Navbar';

export function getDashboardPath(userType: UserType): string {
  switch (userType) {
    case 'doctor':
      return '/doctor-dashboard';
    case 'admin':
      return '/admin';
    case 'receptionist':
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

const ALL_NAV: NavItem[] = [
  { label: 'Dashboard', path: '/dashboard' },
  { label: 'Appointments', path: '/appointments' },
  { label: 'AI Health Chat', path: '/chat', badge: 'AI' },
  { label: 'Doctor Portal', path: '/doctor-dashboard' },
  { label: 'Admin', path: '/admin' },
];

export function getNavItemsForUserType(userType: UserType): NavItem[] {
  switch (userType) {
    case 'admin':
      return ALL_NAV;
    case 'doctor':
      return ALL_NAV.filter((item) =>
        ['/doctor-dashboard', '/appointments', '/chat'].includes(item.path)
      );
    case 'receptionist':
      return ALL_NAV.filter((item) =>
        ['/dashboard', '/appointments', '/chat'].includes(item.path)
      );
    case 'patient':
    default:
      return ALL_NAV.filter((item) =>
        ['/dashboard', '/appointments', '/chat'].includes(item.path)
      );
  }
}

export function mapRegisterRoleToUserType(role: 'Patient' | 'Doctor'): UserType {
  return role === 'Doctor' ? 'doctor' : 'patient';
}
