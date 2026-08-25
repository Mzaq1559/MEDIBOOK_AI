import React, { createContext, useContext, useState, useEffect } from 'react';

export interface User {
  id: string;
  name: string;
  email: string;
  role: 'Patient' | 'Doctor' | 'Admin';
  phone?: string;
  specialization?: string;
  avatarUrl?: string;
}

interface AuthContextType {
  isLoggedIn: boolean;
  currentUser: User | null;
  login: (email: string, role?: 'Patient' | 'Doctor' | 'Admin', name?: string) => void;
  logout: () => void;
  register: (user: User) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isLoggedIn, setIsLoggedIn] = useState<boolean>(() => {
    return localStorage.getItem('medibook_isLoggedIn') === 'true';
  });

  const [currentUser, setCurrentUser] = useState<User | null>(() => {
    const saved = localStorage.getItem('medibook_currentUser');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {
        return null;
      }
    }
    return null;
  });

  useEffect(() => {
    localStorage.setItem('medibook_isLoggedIn', String(isLoggedIn));
    if (currentUser) {
      localStorage.setItem('medibook_currentUser', JSON.stringify(currentUser));
    } else {
      localStorage.removeItem('medibook_currentUser');
    }
  }, [isLoggedIn, currentUser]);

  const login = (email: string, role: 'Patient' | 'Doctor' | 'Admin' = 'Patient', name?: string) => {
    const isDoctor = role === 'Doctor' || email.toLowerCase().includes('dr') || email.toLowerCase().includes('doctor');
    const assignedRole = isDoctor ? 'Doctor' : role;

    const mockUser: User = {
      id: isDoctor ? 'DOC-4921' : 'PT-89420',
      name: name || (isDoctor ? 'Dr. Ahmed Khan, MD' : (email.split('@')[0] ? email.split('@')[0].replace('.', ' ').replace(/\b\w/g, (c) => c.toUpperCase()) : 'Sarah Jenkins')),
      email: email,
      role: assignedRole,
      phone: '+1 (555) 019-2834',
      specialization: isDoctor ? 'Cardiology Specialist' : undefined,
    };

    setCurrentUser(mockUser);
    setIsLoggedIn(true);
  };

  const register = (user: User) => {
    setCurrentUser(user);
    setIsLoggedIn(true);
  };

  const logout = () => {
    setIsLoggedIn(false);
    setCurrentUser(null);
    localStorage.removeItem('medibook_isLoggedIn');
    localStorage.removeItem('medibook_currentUser');
  };

  return (
    <AuthContext.Provider value={{ isLoggedIn, currentUser, login, logout, register }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
