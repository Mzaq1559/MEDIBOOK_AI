import type { UserType } from '../types/auth';
import type { NavItem } from '../components/ui/Navbar';
import type { Lang } from '../i18n/translations';
import { dictionaries } from '../i18n/translations';

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

export function getUserTypeLabel(userType: UserType, lang: Lang = 'en'): string {
  const t = dictionaries[lang];
  switch (userType) {
    case 'doctor':
      return t['register.doctor'];
    case 'admin':
      return t['common.administrator'];
    case 'receptionist':
      return lang === 'en' ? 'Receptionist' : 'ریسیپشنسٹ';
    case 'patient':
    default:
      return t['common.patient'];
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

export function getNavItemsForUserType(userType: UserType, lang: Lang = 'en'): NavItem[] {
  const t = dictionaries[lang];
  const sharedItems: NavItem[] = [
    { label: t['nav.appointments'], path: '/appointments' },
    { label: t['nav.chat'], path: '/chat', badge: 'AI' },
  ];

  switch (userType) {
    case 'admin':
      return [{ label: t['nav.adminPortal'], path: '/admin' }, ...sharedItems];
    case 'doctor':
      return [{ label: t['nav.doctorPortal'], path: '/doctor-dashboard' }, ...sharedItems];
    case 'receptionist':
      return [{ label: t['nav.receptionistPortal'], path: '/receptionist-dashboard' }, ...sharedItems];
    case 'patient':
    default:
      return [
        { label: t['nav.dashboard'], path: '/dashboard' },
        ...sharedItems,
      ];
  }
}

export function mapRegisterRoleToUserType(role: 'Patient' | 'Doctor'): UserType {
  return role === 'Doctor' ? 'doctor' : 'patient';
}

