import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Card, Button, Input, ErrorBanner } from '../components/ui';
import { useAuth } from '../context/AuthContext';
import { parseApiError } from '../utils/authErrors';
import { getDashboardPath, mapRegisterRoleToUserType } from '../utils/authRouting';

type UserRole = 'Patient' | 'Doctor';

export const Register: React.FC = () => {
  const navigate = useNavigate();
  const { register } = useAuth();

  const [role, setRole] = useState<UserRole>('Patient');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const [isLoading, setIsLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [errors, setErrors] = useState<{
    fullName?: string;
    email?: string;
    phone?: string;
    password?: string;
  }>({});

  const validateForm = () => {
    const newErrors: typeof errors = {};

    if (!fullName.trim()) {
      newErrors.fullName = 'Full name is required';
    } else if (fullName.trim().length < 2) {
      newErrors.fullName = 'Please enter your real full name';
    }

    if (!email.trim()) {
      newErrors.email = 'Email address is required';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      newErrors.email = 'Please enter a valid email address';
    }

    if (!phone.trim()) {
      newErrors.phone = 'Phone number is required';
    } else {
      const digits = phone.replace(/[\s\-+()]/g, '');
      if (!/^\d{10,15}$/.test(digits)) {
        newErrors.phone = 'Phone number must contain 10–15 digits';
      }
    }

    if (!password) {
      newErrors.password = 'Password is required';
    } else if (password.length < 8) {
      newErrors.password = 'Password must be at least 8 characters';
    } else {
      const hasUppercase = /[A-Z]/.test(password);
      const hasLowercase = /[a-z]/.test(password);
      const hasNumber = /[0-9]/.test(password);
      const hasSpecial = /[^A-Za-z0-9]/.test(password);
      if (!hasUppercase || !hasLowercase || !hasNumber || !hasSpecial) {
        newErrors.password =
          'Password must include uppercase, lowercase, number, and special character';
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);

    if (!validateForm()) {
      return;
    }

    setIsLoading(true);

    try {
      const user = await register({
        email: email.trim(),
        phone: phone.trim(),
        name: fullName.trim(),
        password,
        user_type: mapRegisterRoleToUserType(role),
      });

      navigate(getDashboardPath(user.userType), { replace: true });
    } catch (error) {
      const { message } = parseApiError(error);
      setSubmitError(message);
    } finally {
      setIsLoading(false);
    }
  };

  const roles: { key: UserRole; label: string; icon: string }[] = [
    { key: 'Patient', label: 'Patient', icon: '👤' },
    { key: 'Doctor', label: 'Doctor', icon: '🩺' },
  ];

  return (
    <div className="min-h-[calc(100vh-140px)] flex items-center justify-center px-4 py-10 sm:py-16">
      <div className="w-full max-w-lg">
        <Card
          radius="3xl"
          shadow="md"
          className="p-7 sm:p-10 bg-white border border-surfaceContainerHigh"
        >
          <div className="text-center mb-7">
            <Link
              to="/"
              className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-primary to-primaryContainer text-white shadow-soft-sm hover:scale-105 transition-transform mb-4"
              aria-label="MediBook AI Home"
            >
              <svg
                className="w-7 h-7"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12 6v12m-6-6h12" />
              </svg>
            </Link>

            <h1 className="text-2xl sm:text-3xl font-extrabold text-textPrimary tracking-tight">
              Create Account
            </h1>
            <p className="text-sm text-textSecondary mt-1.5 leading-relaxed">
              Join <span className="font-semibold text-primary">MediBook AI</span> to book
              appointments, manage health records, and access care.
            </p>
          </div>

          <div className="mb-6">
            <label className="block text-xs font-bold uppercase tracking-wider text-textSecondary mb-2.5 text-center">
              Select Account Type
            </label>
            <div className="grid grid-cols-2 gap-2 p-1.5 bg-surfaceContainer rounded-pill border border-surfaceContainerHigh">
              {roles.map((r) => {
                const isSelected = role === r.key;
                return (
                  <button
                    key={r.key}
                    type="button"
                    onClick={() => setRole(r.key)}
                    className={`py-2 px-4 rounded-pill text-xs font-semibold transition-all duration-200 flex items-center justify-center gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                      isSelected
                        ? 'bg-primary text-white shadow-soft-sm scale-[1.02]'
                        : 'text-textSecondary hover:text-textPrimary hover:bg-white/60'
                    }`}
                  >
                    <span className="text-sm">{r.icon}</span>
                    <span>{r.label}</span>
                  </button>
                );
              })}
            </div>

            {role === 'Doctor' && (
              <p className="text-[11px] text-secondary bg-secondaryContainer/30 p-2.5 rounded-xl mt-2 text-center border border-secondary/20 animate-fadeIn">
                Doctor accounts are created immediately. Additional credential verification may
                be required for full portal access.
              </p>
            )}
          </div>

          {submitError && (
            <div className="mb-6 animate-fadeIn">
              <ErrorBanner
                title="Registration Error"
                message={submitError}
                onDismiss={() => setSubmitError(null)}
              />
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <Input
              label={role === 'Doctor' ? 'Full Name & Title' : 'Full Name'}
              placeholder={role === 'Doctor' ? 'e.g. Dr. Jane Sterling, MD' : 'e.g. Sarah Jenkins'}
              value={fullName}
              onChange={(e) => {
                setFullName(e.target.value);
                if (errors.fullName) setErrors((prev) => ({ ...prev, fullName: undefined }));
              }}
              error={errors.fullName}
              required
              leftIcon={
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z"
                  />
                </svg>
              }
            />

            <Input
              label="Email Address"
              type="email"
              placeholder={role === 'Doctor' ? 'doctor@clinic.com' : 'patient@example.com'}
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (errors.email) setErrors((prev) => ({ ...prev, email: undefined }));
              }}
              error={errors.email}
              required
              leftIcon={
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M21.75 6.75v10.5a2.25 2.25 0 0 1-2.25 2.25h-15a2.25 2.25 0 0 1-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25m19.5 0v.243a2.25 2.25 0 0 1-1.07 1.916l-7.5 4.615a2.25 2.25 0 0 1-2.36 0L3.32 8.91a2.25 2.25 0 0 1-1.07-1.916V6.75"
                  />
                </svg>
              }
            />

            <Input
              label="Phone Number"
              type="tel"
              placeholder="+1 (555) 019-2834"
              value={phone}
              onChange={(e) => {
                setPhone(e.target.value);
                if (errors.phone) setErrors((prev) => ({ ...prev, phone: undefined }));
              }}
              error={errors.phone}
              required
              leftIcon={
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 0 0 2.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 0 1-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 0 0-1.091-.852H4.5A2.25 2.25 0 0 0 2.25 4.5v2.25Z"
                  />
                </svg>
              }
            />

            <Input
              label="Password"
              type={showPassword ? 'text' : 'password'}
              placeholder="••••••••"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                if (errors.password) setErrors((prev) => ({ ...prev, password: undefined }));
              }}
              error={errors.password}
              helperText="Min 8 characters, uppercase, lowercase, number, and special character"
              required
              leftIcon={
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z"
                  />
                </svg>
              }
              rightIcon={
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="p-1 text-textSecondary hover:text-textPrimary transition-colors focus:outline-none"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? (
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M3.98 8.223A10.477 10.477 0 0 0 1.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.451 10.451 0 0 1 12 4.5c4.756 0 8.773 3.162 10.065 7.498a10.522 10.522 0 0 1-4.293 5.774M6.228 6.228 3 3m3.228 3.228 3.65 3.65m7.894 7.894L21 21m-3.228-3.228-3.65-3.65m0 0a3 3 0 1 0-4.243-4.243m4.242 4.242L9.88 9.88"
                      />
                    </svg>
                  ) : (
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z"
                      />
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"
                      />
                    </svg>
                  )}
                </button>
              }
            />

            <div className="pt-3">
              <Button
                type="submit"
                variant="primary"
                size="lg"
                className="w-full justify-center"
                isLoading={isLoading}
              >
                {isLoading ? 'Creating Account...' : 'Create Account'}
              </Button>
            </div>
          </form>

          <div className="mt-8 pt-6 border-t border-surfaceContainerHigh text-center">
            <p className="text-sm text-textSecondary">
              Already have an account?{' '}
              <Link
                to="/login"
                className="font-semibold text-primary hover:text-primaryContainer transition-colors inline-flex items-center gap-0.5"
              >
                Login
                <span aria-hidden="true">&rarr;</span>
              </Link>
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
};
