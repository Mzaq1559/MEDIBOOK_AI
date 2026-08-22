import React, { useState } from 'react';
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
  Input,
  Badge,
  Chip,
  LoadingSpinner,
  ErrorBanner,
} from '../components/ui';

export const ComponentShowcase: React.FC = () => {
  // State for interactive component demos
  const [showErrorBanner, setShowErrorBanner] = useState(true);
  const [buttonLoading, setButtonLoading] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [inputError, setInputError] = useState('');
  const [dismissedChips, setDismissedChips] = useState<string[]>([]);

  const colors = [
    { name: 'primary', hex: '#0058BC', text: 'text-white', bg: 'bg-primary', role: 'Main Brand Blue' },
    { name: 'primaryContainer', hex: '#0070EB', text: 'text-white', bg: 'bg-primaryContainer', role: 'Action Glow / Accent' },
    { name: 'secondary', hex: '#006B5F', text: 'text-white', bg: 'bg-secondary', role: 'Teal Brand Accent' },
    { name: 'secondaryContainer', hex: '#62FAE3', text: 'text-secondary', bg: 'bg-secondaryContainer', role: 'Success / Highlight' },
    { name: 'error', hex: '#BA1A1A', text: 'text-white', bg: 'bg-error', role: 'Error Alert' },
    { name: 'errorContainer', hex: '#FFDAD6', text: 'text-error', bg: 'bg-errorContainer', role: 'Error Surface' },
    { name: 'background', hex: '#F8F9FF', text: 'text-textPrimary', bg: 'bg-background', role: 'Page Background', border: true },
    { name: 'surfaceContainer', hex: '#EFF4FF', text: 'text-textPrimary', bg: 'bg-surfaceContainer', role: 'Input & Soft Surface' },
    { name: 'surfaceContainerHigh', hex: '#E6EEFF', text: 'text-textPrimary', bg: 'bg-surfaceContainerHigh', role: 'Card & Hover Surface' },
    { name: 'textPrimary', hex: '#0D1C2E', text: 'text-white', bg: 'bg-textPrimary', role: 'Primary Typography' },
    { name: 'textSecondary', hex: '#414755', text: 'text-white', bg: 'bg-textSecondary', role: 'Secondary Typography' },
    { name: 'outline', hex: '#C1C6D7', text: 'text-textPrimary', bg: 'bg-outline', role: 'Subtle Borders' },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-16">
      {/* Hero Header */}
      <section className="text-center max-w-3xl mx-auto pt-4 pb-2">
        <div className="inline-flex items-center gap-2 mb-4">
          <Badge status="primary" size="md" withDot>
            Design System Active
          </Badge>
          <Badge status="success" size="md">
            Vite + React + Tailwind
          </Badge>
        </div>
        <h1 className="text-4xl sm:text-5xl font-extrabold text-textPrimary tracking-tight mb-4">
          MediBook AI Design System
        </h1>
        <p className="text-base sm:text-lg text-textSecondary leading-relaxed">
          A clean, calm, and modern healthcare UI library built with soft blue-tinted shadows,
          pill-shaped interactive elements, rounded soft curves, and generous whitespace.
        </p>
      </section>

      {/* 1. Design Tokens: Colors & Typography */}
      <section className="space-y-6">
        <div className="flex items-center justify-between border-b border-surfaceContainerHigh pb-3">
          <div>
            <h2 className="text-2xl font-bold text-textPrimary">Design System Tokens</h2>
            <p className="text-sm text-textSecondary">Color palette, typography, and elevation</p>
          </div>
          <span className="text-xs font-mono text-textSecondary bg-surfaceContainer px-3 py-1 rounded-pill">
            tailwind.config.js
          </span>
        </div>

        {/* Color Palette Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3.5">
          {colors.map((c) => (
            <div
              key={c.name}
              className="bg-white rounded-2xl p-3 border border-surfaceContainerHigh shadow-soft-sm flex flex-col justify-between h-28"
            >
              <div
                className={`w-full h-10 rounded-xl ${c.bg} ${c.border ? 'border border-outline/40' : ''} shadow-inner`}
              />
              <div className="mt-2">
                <p className="text-xs font-bold text-textPrimary font-mono truncate">{c.name}</p>
                <p className="text-[11px] text-textSecondary font-mono">{c.hex}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Typography & Radii Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
          {/* Typography */}
          <Card radius="2xl" shadow="sm" className="space-y-3">
            <h3 className="text-lg font-bold text-textPrimary">Typography (Google Fonts)</h3>
            <div className="space-y-3 pt-2">
              <div className="p-3.5 bg-surfaceContainer rounded-xl">
                <span className="text-xs font-semibold text-primary uppercase tracking-wider block mb-1">
                  Headings: Manrope (Weight 700)
                </span>
                <p className="font-heading font-bold text-xl text-textPrimary">
                  Intelligent Patient Healthcare & Triage
                </p>
              </div>
              <div className="p-3.5 bg-surfaceContainer rounded-xl">
                <span className="text-xs font-semibold text-secondary uppercase tracking-wider block mb-1">
                  Body & Labels: Inter (Weight 400 - 600)
                </span>
                <p className="font-sans text-sm text-textSecondary leading-relaxed">
                  The quick brown fox jumps over the lazy dog. Inter provides clean legibility for medical data and clinical summaries.
                </p>
              </div>
            </div>
          </Card>

          {/* Border Radii & Soft Blue Shadows */}
          <Card radius="2xl" shadow="sm" className="space-y-3">
            <h3 className="text-lg font-bold text-textPrimary">Radii & Soft Blue Shadows</h3>
            <div className="grid grid-cols-2 gap-3 pt-2">
              <div className="p-4 bg-white rounded-xl border border-surfaceContainerHigh shadow-soft text-center">
                <p className="text-xs font-bold text-textPrimary font-mono">rounded-xl (12px)</p>
                <p className="text-[11px] text-textSecondary mt-1">Form inputs & icons</p>
              </div>
              <div className="p-4 bg-white rounded-2xl border border-surfaceContainerHigh shadow-soft text-center">
                <p className="text-xs font-bold text-textPrimary font-mono">rounded-2xl (16px)</p>
                <p className="text-[11px] text-textSecondary mt-1">Standard cards & banners</p>
              </div>
              <div className="p-4 bg-white rounded-3xl border border-surfaceContainerHigh shadow-soft-md text-center">
                <p className="text-xs font-bold text-textPrimary font-mono">rounded-3xl (24px)</p>
                <p className="text-[11px] text-textSecondary mt-1">Hero cards & dialogs</p>
              </div>
              <div className="p-4 bg-white rounded-pill border border-surfaceContainerHigh shadow-soft-sm text-center flex flex-col justify-center">
                <p className="text-xs font-bold text-textPrimary font-mono">rounded-pill (full)</p>
                <p className="text-[11px] text-textSecondary mt-0.5">Buttons & Badges</p>
              </div>
            </div>
          </Card>
        </div>
      </section>

      {/* 2. Button Component */}
      <section className="space-y-6">
        <div className="flex items-center justify-between border-b border-surfaceContainerHigh pb-3">
          <div>
            <h2 className="text-2xl font-bold text-textPrimary">1. Button Component</h2>
            <p className="text-sm text-textSecondary">
              Pill-shaped with primary (solid blue), secondary (transparent blue border), and danger variants
            </p>
          </div>
          <Badge status="pending">Button.tsx</Badge>
        </div>

        <Card radius="2xl" shadow="sm" className="space-y-6">
          {/* Variants */}
          <div>
            <h4 className="text-xs font-bold text-textSecondary uppercase tracking-wider mb-3">Variants</h4>
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="primary">Primary Button</Button>
              <Button variant="secondary">Secondary Button</Button>
              <Button variant="danger">Danger Action</Button>
              <Button variant="ghost">Ghost Button</Button>
              <Button variant="outline">Outline Button</Button>
            </div>
          </div>

          {/* Sizes */}
          <div>
            <h4 className="text-xs font-bold text-textSecondary uppercase tracking-wider mb-3">Sizes</h4>
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="primary" size="sm">
                Small (sm)
              </Button>
              <Button variant="primary" size="md">
                Medium (md) - Default
              </Button>
              <Button variant="primary" size="lg">
                Large (lg)
              </Button>
            </div>
          </div>

          {/* Interactive Loading & Icons */}
          <div>
            <h4 className="text-xs font-bold text-textSecondary uppercase tracking-wider mb-3">
              Icons & Interactive Loading State
            </h4>
            <div className="flex flex-wrap items-center gap-3">
              <Button
                variant="primary"
                isLoading={buttonLoading}
                onClick={() => {
                  setButtonLoading(true);
                  setTimeout(() => setButtonLoading(false), 2000);
                }}
                leftIcon={
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                  </svg>
                }
              >
                {buttonLoading ? 'Booking...' : 'Book Appointment (Click Me)'}
              </Button>

              <Button
                variant="secondary"
                rightIcon={
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
                  </svg>
                }
              >
                View Records
              </Button>

              <Button variant="danger" disabled>
                Disabled Button
              </Button>
            </div>
          </div>
        </Card>
      </section>

      {/* 3. Card Component */}
      <section className="space-y-6">
        <div className="flex items-center justify-between border-b border-surfaceContainerHigh pb-3">
          <div>
            <h2 className="text-2xl font-bold text-textPrimary">2. Card Component</h2>
            <p className="text-sm text-textSecondary">
              rounded-2xl / rounded-3xl with soft blue-tinted shadows, icon, title, description, and subcomponents
            </p>
          </div>
          <Badge status="pending">Card.tsx</Badge>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Card 1: Default Card with Header props */}
          <Card
            radius="2xl"
            shadow="default"
            icon={
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
              </svg>
            }
            title="Next Consultation"
            subtitle="Dr. Emily Thorne, MD"
            badge={<Badge status="success" size="sm">Confirmed</Badge>}
            description="Tomorrow at 10:30 AM via HD Telehealth Video."
          >
            <div className="pt-2 flex items-center justify-between">
              <span className="text-xs text-textSecondary">Cardiology Clinic</span>
              <Button size="sm" variant="secondary">
                Join Room
              </Button>
            </div>
          </Card>

          {/* Card 2: Interactive Hover Card */}
          <Card
            variant="interactive"
            radius="2xl"
            shadow="sm"
            icon={
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456ZM16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423Z" />
              </svg>
            }
            title="AI Health Assistant"
            subtitle="24/7 Symptom Triage"
            badge={<Badge status="pending" size="sm">Active</Badge>}
            description="Hover to see dynamic soft blue elevation and border tint."
          >
            <div className="pt-2 flex items-center justify-between">
              <span className="text-xs font-semibold text-primary">Start Chat &rarr;</span>
            </div>
          </Card>

          {/* Card 3: Composable with Subcomponents */}
          <Card radius="3xl" shadow="md" className="flex flex-col justify-between">
            <div>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <Badge status="error" size="sm" withDot>
                    Prescription Refill
                  </Badge>
                  <span className="text-xs text-textSecondary">Due in 2 days</span>
                </div>
                <CardTitle className="text-lg mt-2">Amoxicillin 500mg</CardTitle>
                <CardDescription>
                  Take 1 capsule every 8 hours with food. 6 capsules remaining.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="p-3 bg-surfaceContainer rounded-xl text-xs text-textSecondary">
                  Prescribed by Dr. Robert Chen on Aug 18
                </div>
              </CardContent>
            </div>
            <CardFooter className="justify-between">
              <span className="text-xs font-semibold text-textSecondary">Pharmacy: CVS #4821</span>
              <Button size="sm" variant="primary">
                Refill
              </Button>
            </CardFooter>
          </Card>
        </div>
      </section>

      {/* 4. Input Component */}
      <section className="space-y-6">
        <div className="flex items-center justify-between border-b border-surfaceContainerHigh pb-3">
          <div>
            <h2 className="text-2xl font-bold text-textPrimary">3. Input Component</h2>
            <p className="text-sm text-textSecondary">
              Soft grey background, 12px rounded (rounded-xl), label + error support, blue glow on focus
            </p>
          </div>
          <Badge status="pending">Input.tsx</Badge>
        </div>

        <Card radius="2xl" shadow="sm">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* Standard Input */}
            <Input
              label="Full Name"
              placeholder="e.g. Sarah Jenkins"
              helperText="Enter your name as it appears on medical records"
              required
            />

            {/* Input with Icons & Blue Glow */}
            <Input
              label="Email Address"
              placeholder="patient@example.com"
              type="email"
              helperText="We'll send appointment confirmations here"
              leftIcon={
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 0 1-2.25 2.25h-15a2.25 2.25 0 0 1-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25m19.5 0v.243a2.25 2.25 0 0 1-1.07 1.916l-7.5 4.615a2.25 2.25 0 0 1-2.36 0L3.32 8.91a2.25 2.25 0 0 1-1.07-1.916V6.75" />
                </svg>
              }
            />

            {/* Interactive Error State Test */}
            <Input
              label="Insurance Member ID"
              placeholder="e.g. MED-89410-X"
              value={inputValue}
              onChange={(e) => {
                const val = e.target.value;
                setInputValue(val);
                if (val && val.length < 5) {
                  setInputError('Member ID must be at least 5 characters');
                } else {
                  setInputError('');
                }
              }}
              error={inputError || (inputValue === '' ? 'Insurance Member ID is required' : undefined)}
              leftIcon={
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-3.75 3h15a2.25 2.25 0 0 0 2.25-2.25V6.75A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25v10.5A2.25 2.25 0 0 0 4.5 19.5Z" />
                </svg>
              }
            />
          </div>
        </Card>
      </section>

      {/* 5. Badge / Chip Component */}
      <section className="space-y-6">
        <div className="flex items-center justify-between border-b border-surfaceContainerHigh pb-3">
          <div>
            <h2 className="text-2xl font-bold text-textPrimary">4. Badge / Chip Component</h2>
            <p className="text-sm text-textSecondary">
              Pill-shaped, colored background tint based on status (success=teal, error=red, pending=blue)
            </p>
          </div>
          <Badge status="pending">Badge.tsx</Badge>
        </div>

        <Card radius="2xl" shadow="sm" className="space-y-6">
          {/* Status Badges */}
          <div>
            <h4 className="text-xs font-bold text-textSecondary uppercase tracking-wider mb-3">Status Badges</h4>
            <div className="flex flex-wrap items-center gap-3">
              <Badge status="success">Success / Verified (Teal)</Badge>
              <Badge status="pending">Pending / Scheduled (Blue)</Badge>
              <Badge status="error">Error / Urgent (Red)</Badge>
              <Badge status="primary">Primary Brand</Badge>
              <Badge status="neutral">Neutral Status</Badge>
            </div>
          </div>

          {/* With Live Pulse Dots */}
          <div>
            <h4 className="text-xs font-bold text-textSecondary uppercase tracking-wider mb-3">With Indicator Dot</h4>
            <div className="flex flex-wrap items-center gap-3">
              <Badge status="success" withDot>
                Online Doctor
              </Badge>
              <Badge status="pending" withDot>
                Awaiting Lab Results
              </Badge>
              <Badge status="error" withDot>
                Payment Overdue
              </Badge>
              <Badge status="primary" withDot>
                AI Diagnosing
              </Badge>
            </div>
          </div>

          {/* Dismissible Chips */}
          <div>
            <h4 className="text-xs font-bold text-textSecondary uppercase tracking-wider mb-3">Dismissible Chips</h4>
            <div className="flex flex-wrap items-center gap-2">
              {['Cardiology', 'Neurology', 'Pediatrics', 'Telehealth', 'Orthopedics']
                .filter((chip) => !dismissedChips.includes(chip))
                .map((chip) => (
                  <Chip
                    key={chip}
                    status="neutral"
                    onRemove={() => setDismissedChips([...dismissedChips, chip])}
                  >
                    {chip}
                  </Chip>
                ))}
              {dismissedChips.length > 0 && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setDismissedChips([])}
                  className="text-xs text-primary underline"
                >
                  Reset Filter Chips
                </Button>
              )}
            </div>
          </div>
        </Card>
      </section>

      {/* 6. LoadingSpinner & 7. ErrorBanner Components */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* LoadingSpinner */}
        <section className="space-y-6">
          <div className="flex items-center justify-between border-b border-surfaceContainerHigh pb-3">
            <div>
              <h2 className="text-2xl font-bold text-textPrimary">6. LoadingSpinner</h2>
              <p className="text-sm text-textSecondary">Clean animated SVG with size and color variants</p>
            </div>
            <Badge status="pending">LoadingSpinner.tsx</Badge>
          </div>

          <Card radius="2xl" shadow="sm" className="p-6">
            <div className="flex items-center justify-around py-4">
              <div className="text-center space-y-2">
                <LoadingSpinner size="sm" color="primary" />
                <p className="text-xs text-textSecondary font-mono">sm (primary)</p>
              </div>
              <div className="text-center space-y-2">
                <LoadingSpinner size="md" color="secondary" />
                <p className="text-xs text-textSecondary font-mono">md (secondary)</p>
              </div>
              <div className="text-center space-y-2">
                <LoadingSpinner size="lg" color="primary" />
                <p className="text-xs text-textSecondary font-mono">lg (primary)</p>
              </div>
              <div className="text-center space-y-2">
                <LoadingSpinner size="xl" color="error" />
                <p className="text-xs text-textSecondary font-mono">xl (error)</p>
              </div>
            </div>
          </Card>
        </section>

        {/* ErrorBanner */}
        <section className="space-y-6">
          <div className="flex items-center justify-between border-b border-surfaceContainerHigh pb-3">
            <div>
              <h2 className="text-2xl font-bold text-textPrimary">7. ErrorBanner</h2>
              <p className="text-sm text-textSecondary">
                errorContainer background, error icon, dismiss and retry support
              </p>
            </div>
            <Badge status="pending">ErrorBanner.tsx</Badge>
          </div>

          <div className="space-y-4">
            {showErrorBanner ? (
              <ErrorBanner
                title="Failed to sync clinical records"
                message="Unable to connect to the hospital EHR server. Please check your network connection and retry."
                onRetry={() => alert('Retrying EHR connection...')}
                onDismiss={() => setShowErrorBanner(false)}
              />
            ) : (
              <div className="p-4 bg-surfaceContainer rounded-2xl text-center">
                <p className="text-xs text-textSecondary mb-2">Error banner dismissed</p>
                <Button size="sm" variant="secondary" onClick={() => setShowErrorBanner(true)}>
                  Show Error Banner Again
                </Button>
              </div>
            )}
          </div>
        </section>
      </div>

      {/* React Router Placeholder Routes Quick Navigation */}
      <section className="space-y-6 pt-4">
        <div className="flex items-center justify-between border-b border-surfaceContainerHigh pb-3">
          <div>
            <h2 className="text-2xl font-bold text-textPrimary">React Router Placeholder Routes</h2>
            <p className="text-sm text-textSecondary">
              Empty placeholder routes configured with React Router v6/v7
            </p>
          </div>
          <Badge status="success">7 Routes Ready</Badge>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {[
            { path: '/login', name: 'Login', badge: 'Auth' },
            { path: '/register', name: 'Register', badge: 'Auth' },
            { path: '/dashboard', name: 'Dashboard', badge: 'Patient' },
            { path: '/chat', name: 'AI Chat', badge: 'AI Assistant' },
            { path: '/appointments', name: 'Appointments', badge: 'Booking' },
            { path: '/doctor-dashboard', name: 'Doctor Dashboard', badge: 'Clinician' },
            { path: '/admin', name: 'Admin', badge: 'Management' },
          ].map((route) => (
            <a
              key={route.path}
              href={route.path}
              className="p-4 bg-white rounded-2xl border border-surfaceContainerHigh hover:border-primary/40 hover:shadow-soft transition-all duration-200 group flex items-center justify-between"
            >
              <div>
                <p className="font-heading font-bold text-sm text-textPrimary group-hover:text-primary transition-colors">
                  {route.name}
                </p>
                <p className="text-xs font-mono text-textSecondary mt-0.5">{route.path}</p>
              </div>
              <Badge status="pending" size="sm">
                {route.badge}
              </Badge>
            </a>
          ))}
        </div>
      </section>
    </div>
  );
};
