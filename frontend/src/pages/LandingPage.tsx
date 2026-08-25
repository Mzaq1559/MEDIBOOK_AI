import React from 'react';
import { Link } from 'react-router-dom';
import { Card, Button, Badge } from '../components/ui';

export const LandingPage: React.FC = () => {
  const features = [
    {
      icon: (
        <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456ZM16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423Z"
          />
        </svg>
      ),
      iconBg: 'bg-primary/10 text-primary',
      title: 'AI Symptom Triage',
      badge: 'Natural Language',
      description:
        'Interactive real-time clinical assessment that understands natural symptom descriptions, evaluates urgency, and matches you with specialized physicians.',
    },
    {
      icon: (
        <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5m-9-6h.008v.008H12v-.008ZM12 15h.008v.008H12V15Zm0 2.25h.008v.008H12v-.008ZM9.75 15h.008v.008H9.75V15Zm0 2.25h.008v.008H9.75v-.008ZM7.5 15h.008v.008H7.5V15Zm0 2.25h.008v.008H7.5v-.008Zm6.75-4.5h.008v.008h-.008v-.008Zm0 2.25h.008v.008h-.008V15Zm0 2.25h.008v.008h-.008v-.008Zm2.25-4.5h.008v.008H16.5v-.008Zm0 2.25h.008v.008H16.5V15Z"
          />
        </svg>
      ),
      iconBg: 'bg-[#62FAE3]/35 text-secondary border border-secondary/20',
      title: 'Smart Appointment Booking',
      badge: 'Instant Sync',
      description:
        'Browse verified doctor profiles, view live slot availability, book in-clinic visits or HD telehealth video consultations with zero waiting times.',
    },
    {
      icon: (
        <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a.75.75 0 0 1-.974-.94 4.053 4.053 0 0 0 .426-1.781C3.642 16.634 3 14.42 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z"
          />
        </svg>
      ),
      iconBg: 'bg-surfaceContainerHigh text-primary',
      title: 'Automated Reminders',
      badge: 'WhatsApp & SMS',
      description:
        'Smart automated notifications delivered 24 hours and 1 hour before scheduled consultations, drastically cutting clinic no-show rates.',
    },
    {
      icon: (
        <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z"
          />
        </svg>
      ),
      iconBg: 'bg-primary/10 text-primary',
      title: 'Doctor Clinical Portal',
      badge: 'Clinician Workflow',
      description:
        'A streamlined workspace for healthcare professionals to review incoming patient queues, assess triage urgency, save clinical notes, and manage daily shifts.',
    },
    {
      icon: (
        <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
          />
        </svg>
      ),
      iconBg: 'bg-errorContainer text-error border border-error/20',
      title: 'Emergency Detection',
      badge: 'Life-Saving Triage',
      description:
        'Instant pattern detection for acute conditions such as sudden chest pain or respiratory failure, immediately prompting emergency 911 dialing and ER guidance.',
    },
  ];

  return (
    <div className="space-y-16 sm:space-y-24 py-8 sm:py-12">
      {/* 1. Hero Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-8 items-center">
          {/* Left Column: Headline & CTAs */}
          <div className="lg:col-span-7 space-y-6 text-center lg:text-left">
            <div className="inline-flex items-center gap-2">
              <Badge status="primary" size="md" withDot>
                Next-Gen Healthcare AI
              </Badge>
              <Badge status="success" size="md">
                24/7 Availability
              </Badge>
            </div>

            <h1 className="font-heading font-extrabold text-4xl sm:text-5xl lg:text-6xl text-textPrimary tracking-tight leading-[1.15]">
              Your 24/7 AI Health Receptionist & Smart Clinic Platform
            </h1>

            <p className="text-base sm:text-lg text-textSecondary leading-relaxed max-w-2xl mx-auto lg:mx-0">
              Transforming patient triage and clinic appointments. Describe symptoms in plain English, match with top specialists, and manage healthcare with intelligent automation.
            </p>

            {/* Action Buttons */}
            <div className="flex flex-col sm:flex-row items-center justify-center lg:justify-start gap-3.5 pt-2">
              <Link to="/register" className="w-full sm:w-auto">
                <Button variant="primary" size="lg" className="w-full sm:w-auto justify-center px-8 text-base">
                  Get Started Free &rarr;
                </Button>
              </Link>

              <Link to="/login" className="w-full sm:w-auto">
                <Button variant="secondary" size="lg" className="w-full sm:w-auto justify-center px-8 text-base">
                  Sign In to Portal
                </Button>
              </Link>
            </div>

            {/* Trust Highlights */}
            <div className="pt-6 border-t border-surfaceContainerHigh flex flex-wrap items-center justify-center lg:justify-start gap-6 text-xs text-textSecondary font-medium">
              <div className="flex items-center gap-1.5">
                <span className="text-secondary text-sm">✓</span>
                <span>HIPAA-Compliant Architecture</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-secondary text-sm">✓</span>
                <span>Verified Board Physicians</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-secondary text-sm">✓</span>
                <span>Instant WhatsApp Reminders</span>
              </div>
            </div>
          </div>

          {/* Right Column: Hero Visual Card */}
          <div className="lg:col-span-5">
            <div className="relative">
              {/* Background ambient glow */}
              <div className="absolute -inset-2 bg-gradient-to-r from-primary/15 to-[#62FAE3]/20 rounded-3xl blur-2xl -z-10" />

              <Card
                radius="3xl"
                shadow="lg"
                className="p-6 sm:p-7 bg-white/95 backdrop-blur-md border border-surfaceContainerHigh space-y-4"
              >
                {/* Chat Mockup Header */}
                <div className="flex items-center justify-between border-b border-surfaceContainerHigh pb-3">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-xl bg-primary text-white flex items-center justify-center font-bold text-xs">
                      AI
                    </div>
                    <div>
                      <p className="font-heading font-bold text-xs text-textPrimary">MediBook Assistant</p>
                      <p className="text-[10px] text-secondary">Clinical Triage Active</p>
                    </div>
                  </div>
                  <Badge status="success" size="sm" withDot>
                    Online
                  </Badge>
                </div>

                {/* Simulated Conversation */}
                <div className="space-y-3 text-xs">
                  {/* User Bubble */}
                  <div className="flex justify-end">
                    <div className="bg-primary text-white px-3.5 py-2 rounded-2xl rounded-tr-sm max-w-[85%] shadow-soft-sm">
                      I've had a persistent cough and low fever for 3 days.
                    </div>
                  </div>

                  {/* Bot Bubble */}
                  <div className="flex justify-start">
                    <div className="bg-surfaceContainer text-textPrimary px-3.5 py-2.5 rounded-2xl rounded-tl-sm max-w-[90%] border border-surfaceContainerHigh space-y-1.5">
                      <p>I recommend scheduling a visit with a Respiratory Specialist.</p>
                      <div className="p-2.5 bg-white rounded-xl border border-surfaceContainerHigh flex items-center justify-between">
                        <div>
                          <p className="font-bold text-textPrimary">Dr. David Sterling, MD</p>
                          <p className="text-[10px] text-secondary font-medium">Pulmonologist • ★ 4.9</p>
                        </div>
                        <span className="text-[10px] font-bold text-primary bg-surfaceContainer px-2 py-0.5 rounded-full">
                          Tomorrow 10:00 AM
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Booking Notice */}
                <div className="pt-2 border-t border-surfaceContainerHigh flex items-center justify-between text-[11px] text-textSecondary">
                  <span className="flex items-center gap-1">
                    <span>📲</span> WhatsApp Notification Ready
                  </span>
                  <Link to="/register" className="font-bold text-primary hover:underline">
                    Try Live Demo &rarr;
                  </Link>
                </div>
              </Card>
            </div>
          </div>
        </div>
      </section>

      {/* 2. Feature Cards Grid */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-10">
        <div className="text-center max-w-2xl mx-auto space-y-3">
          <Badge status="primary" size="md">
            Engineered For Excellence
          </Badge>
          <h2 className="font-heading font-extrabold text-3xl sm:text-4xl text-textPrimary tracking-tight">
            Key Platform Capabilities
          </h2>
          <p className="text-sm sm:text-base text-textSecondary">
            Everything you need for seamless patient triage, appointment coordination, and clinical oversight.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, idx) => (
            <Card
              key={idx}
              radius="3xl"
              shadow="default"
              className="p-7 sm:p-8 bg-white border border-surfaceContainerHigh hover:border-primaryContainer/40 hover:shadow-soft-md transition-all duration-200 flex flex-col justify-between"
            >
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className={`w-13 h-13 rounded-2xl flex items-center justify-center shadow-soft-sm ${feature.iconBg}`}>
                    {feature.icon}
                  </div>
                  <Badge status="neutral" size="sm">
                    {feature.badge}
                  </Badge>
                </div>

                <h3 className="font-heading font-bold text-xl text-textPrimary tracking-tight">
                  {feature.title}
                </h3>

                <p className="text-sm text-textSecondary leading-relaxed">
                  {feature.description}
                </p>
              </div>

              <div className="pt-6 mt-4 border-t border-surfaceContainerHigh">
                <Link
                  to="/register"
                  className="text-xs font-semibold text-primary hover:text-primaryContainer transition-colors inline-flex items-center gap-1"
                >
                  Explore Feature <span>&rarr;</span>
                </Link>
              </div>
            </Card>
          ))}
        </div>
      </section>

      {/* 3. Bottom CTA Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <Card
          radius="3xl"
          shadow="lg"
          className="p-8 sm:p-14 bg-gradient-to-br from-primary to-primaryContainer text-white text-center space-y-6 relative overflow-hidden"
        >
          {/* Subtle background decorative shapes */}
          <div className="absolute -top-24 -right-24 w-72 h-72 rounded-full bg-white/10 blur-2xl pointer-events-none" />
          <div className="absolute -bottom-24 -left-24 w-72 h-72 rounded-full bg-[#62FAE3]/20 blur-2xl pointer-events-none" />

          <div className="relative z-10 max-w-2xl mx-auto space-y-4">
            <h2 className="font-heading font-extrabold text-3xl sm:text-4xl text-white tracking-tight">
              Ready to modernize your healthcare journey?
            </h2>
            <p className="text-white/90 text-base leading-relaxed">
              Join patients and healthcare providers experiencing faster triage, intelligent doctor appointments, and zero scheduling friction.
            </p>

            <div className="pt-4 flex flex-col sm:flex-row items-center justify-center gap-3.5">
              <Link to="/register" className="w-full sm:w-auto">
                <Button
                  size="lg"
                  className="w-full sm:w-auto bg-white text-primary hover:bg-white/90 shadow-soft-md border-none px-8 font-bold"
                >
                  Create Your Account
                </Button>
              </Link>
              <Link to="/login" className="w-full sm:w-auto">
                <Button
                  size="lg"
                  variant="secondary"
                  className="w-full sm:w-auto text-white border-white/50 hover:bg-white/10 px-8"
                >
                  Sign In
                </Button>
              </Link>
            </div>
          </div>
        </Card>
      </section>
    </div>
  );
};
