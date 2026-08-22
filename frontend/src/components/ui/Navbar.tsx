import React, { useState } from 'react';
import { NavLink, Link } from 'react-router-dom';
import { cn } from '../../lib/utils';
import { Button } from './Button';

export interface NavItem {
  label: string;
  path: string;
  badge?: string;
}

export interface NavbarProps {
  logoText?: string;
  navItems?: NavItem[];
  user?: {
    name: string;
    email?: string;
    avatarUrl?: string;
    role?: string;
    specialization?: string;
  } | null;
  onLoginClick?: () => void;
  onRegisterClick?: () => void;
  onLogout?: () => void;
  className?: string;
}

const defaultAuthenticatedNavItems: NavItem[] = [
  { label: 'Dashboard', path: '/dashboard' },
  { label: 'Appointments', path: '/appointments' },
  { label: 'AI Health Chat', path: '/chat', badge: 'AI' },
  { label: 'Doctor Portal', path: '/doctor-dashboard' },
  { label: 'Admin', path: '/admin' },
];

export const Navbar: React.FC<NavbarProps> = ({
  logoText = 'MediBook AI',
  navItems = defaultAuthenticatedNavItems,
  user = null,
  onLoginClick,
  onRegisterClick,
  onLogout,
  className,
}) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Link for the logo based on login status
  const logoDestination = user
    ? user.role === 'Doctor'
      ? '/doctor-dashboard'
      : user.role === 'Admin'
      ? '/admin'
      : '/dashboard'
    : '/';

  return (
    <header
      className={cn(
        'sticky top-0 z-50 w-full bg-white/95 backdrop-blur-md border-b border-surfaceContainerHigh shadow-soft-sm transition-all duration-200',
        className
      )}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-18 py-3">
          {/* Logo (Left) */}
          <Link
            to={logoDestination}
            className="flex items-center gap-2.5 group focus:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-xl p-1"
          >
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-primary to-primaryContainer flex items-center justify-center text-white shadow-soft-sm group-hover:scale-105 transition-transform duration-200">
              <svg
                className="w-5 h-5"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12 6v12m-6-6h12" />
              </svg>
            </div>
            <div className="flex flex-col">
              <span className="font-heading font-extrabold text-xl text-textPrimary tracking-tight group-hover:text-primary transition-colors">
                {logoText.split(' ')[0]}
                <span className="text-primary ml-1">{logoText.split(' ').slice(1).join(' ')}</span>
              </span>
              <span className="text-[10px] uppercase font-semibold tracking-wider text-secondary -mt-1">
                Healthcare Platform
              </span>
            </div>
          </Link>

          {/* Navigation Links (Center) - Only shown when user is authenticated or custom links */}
          {user && (
            <nav className="hidden md:flex items-center gap-1.5 bg-surfaceContainer/70 p-1.5 rounded-pill border border-surfaceContainerHigh">
              {navItems.map((item) => (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={({ isActive }) =>
                    cn(
                      'px-3.5 py-1.5 rounded-pill text-xs font-semibold transition-all duration-150 flex items-center gap-1.5',
                      isActive
                        ? 'bg-white text-primary shadow-soft-sm'
                        : 'text-textSecondary hover:text-textPrimary hover:bg-white/60'
                    )
                  }
                >
                  <span>{item.label}</span>
                  {item.badge && (
                    <span className="bg-secondaryContainer text-[#006B5F] text-[10px] font-bold px-1.5 py-0.2 rounded-full">
                      {item.badge}
                    </span>
                  )}
                </NavLink>
              ))}
            </nav>
          )}

          {/* User Profile / Auth Actions (Right) */}
          <div className="hidden md:flex items-center gap-3">
            {user ? (
              <div className="flex items-center gap-3 pl-2">
                <div className="text-right">
                  <p className="text-sm font-semibold text-textPrimary leading-tight">
                    {user.name}
                  </p>
                  <p className="text-xs text-textSecondary font-medium">
                    {user.specialization || user.role || 'Patient'}
                  </p>
                </div>
                <div className="w-9 h-9 rounded-pill bg-surfaceContainer text-primary flex items-center justify-center font-bold border border-primary/20 shadow-soft-sm">
                  {user.avatarUrl ? (
                    <img
                      src={user.avatarUrl}
                      alt={user.name}
                      className="w-full h-full rounded-pill object-cover"
                    />
                  ) : (
                    user.name.charAt(0)
                  )}
                </div>

                {/* Working Logout Button */}
                {onLogout && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={onLogout}
                    className="text-textSecondary hover:text-error hover:bg-errorContainer/30 transition-colors ml-1"
                    title="Log out of MediBook AI"
                  >
                    Logout
                  </Button>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-2.5">
                <Link to="/login">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={onLoginClick}
                  >
                    Sign In
                  </Button>
                </Link>
                <Link to="/register">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={onRegisterClick}
                  >
                    Get Started
                  </Button>
                </Link>
              </div>
            )}
          </div>

          {/* Mobile menu button */}
          <div className="flex md:hidden items-center gap-2">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-xl text-textSecondary hover:text-textPrimary hover:bg-surfaceContainer focus:outline-none"
              aria-label="Toggle navigation menu"
            >
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                {mobileMenuOpen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>
          </div>
        </div>

        {/* Mobile Dropdown Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden py-4 border-t border-surfaceContainerHigh flex flex-col gap-2">
            {user ? (
              <>
                <div className="p-3 bg-surfaceContainer rounded-2xl flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-pill bg-primary text-white flex items-center justify-center font-bold text-xs">
                      {user.name.charAt(0)}
                    </div>
                    <div>
                      <p className="text-xs font-bold text-textPrimary">{user.name}</p>
                      <p className="text-[10px] text-textSecondary">{user.role}</p>
                    </div>
                  </div>
                  {onLogout && (
                    <button
                      onClick={() => {
                        setMobileMenuOpen(false);
                        onLogout();
                      }}
                      className="text-xs font-semibold text-error hover:underline"
                    >
                      Logout
                    </button>
                  )}
                </div>

                {navItems.map((item) => (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    onClick={() => setMobileMenuOpen(false)}
                    className={({ isActive }) =>
                      cn(
                        'px-4 py-2.5 rounded-xl text-sm font-medium transition-colors flex items-center justify-between',
                        isActive
                          ? 'bg-surfaceContainer text-primary font-semibold'
                          : 'text-textSecondary hover:bg-surfaceContainer/50'
                      )
                    }
                  >
                    <span>{item.label}</span>
                    {item.badge && (
                      <span className="bg-secondaryContainer text-[#006B5F] text-xs font-bold px-2 py-0.5 rounded-full">
                        {item.badge}
                      </span>
                    )}
                  </NavLink>
                ))}
              </>
            ) : (
              <div className="pt-2 flex flex-col gap-2">
                <Link to="/login" onClick={() => setMobileMenuOpen(false)}>
                  <Button variant="outline" className="w-full justify-center">
                    Sign In
                  </Button>
                </Link>
                <Link to="/register" onClick={() => setMobileMenuOpen(false)}>
                  <Button variant="primary" className="w-full justify-center">
                    Get Started
                  </Button>
                </Link>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
};
