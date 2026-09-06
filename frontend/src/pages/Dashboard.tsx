import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Card, Button, Badge } from '../components/ui';
import { useAuth } from '../context/AuthContext';
import { getPatientAppointments, cancelAppointment } from '../services/appointments';
import { getMyPatientProfile, type PatientProfile } from '../services/patient';

interface BackendAppointment {
  appointment_id: string;
  doctor_id: string;
  doctor_name: string;
  doctor_specialization: string;
  clinic_id: string;
  clinic_name: string;
  clinic_address: string;
  appointment_time: string;
  end_time: string;
  status: string;
  urgency_level?: string;
  urgency_reason?: string | null;
  symptoms_reported?: string;
  doctor_notes?: string;
}

export const Dashboard: React.FC = () => {
  const { currentUser } = useAuth();

  const [appointments, setAppointments] = useState<BackendAppointment[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [notification, setNotification] = useState<string | null>(null);
  const [profile, setProfile] = useState<PatientProfile | null>(null);

  const fetchAppointments = async () => {
    if (!currentUser?.id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getPatientAppointments(currentUser.id);
      setAppointments(Array.isArray(data) ? data : data.appointments || []);
    } catch (err: any) {
      console.error('Failed to load patient appointments:', err);
      setError(err?.response?.data?.detail?.message || 'Failed to load your appointments. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const fetchProfile = async () => {
    try {
      const data = await getMyPatientProfile();
      setProfile(data);
    } catch {
      // Non-critical; profile banner just won't show
    }
  };

  useEffect(() => {
    fetchAppointments();
    fetchProfile();
  }, [currentUser?.id]);

  const patient = {
    name: currentUser?.name || 'Patient',
    initials: currentUser?.name
      ? currentUser.name
          .split(' ')
          .map((n) => n[0])
          .join('')
          .toUpperCase()
          .slice(0, 2)
      : 'PT',
    id: currentUser?.id ? `PT-${currentUser.id.slice(0, 6)}` : 'PT-00000',
  };

  // Find upcoming scheduled appointment
  const scheduledList = appointments
    .filter((a) => a.status.toLowerCase() === 'scheduled' || a.status.toLowerCase() === 'confirmed')
    .sort((a, b) => new Date(a.appointment_time).getTime() - new Date(b.appointment_time).getTime());

  const upcomingAppointment = scheduledList[0] || null;

  const totalAppointments = appointments.length;
  const completedVisits = appointments.filter((a) => a.status.toLowerCase() === 'completed').length;
  const upcomingVisits = scheduledList.length;

  const handleCancelAppointment = async (id: string) => {
    if (window.confirm('Are you sure you want to cancel this appointment?')) {
      try {
        await cancelAppointment(id);
        setNotification('Appointment was successfully cancelled.');
        fetchAppointments();
        setTimeout(() => setNotification(null), 4000);
      } catch (err: any) {
        alert(err?.response?.data?.detail?.message || 'Failed to cancel appointment');
      }
    }
  };

  const formatDateTime = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return {
        date: d.toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric', year: 'numeric' }),
        time: d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
      };
    } catch {
      return { date: isoString, time: '' };
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-12 space-y-12">
      {/* Notification Toast */}
      {notification && (
        <div className="p-4 bg-surfaceContainer border border-primaryContainer/30 rounded-2xl shadow-soft-sm flex items-center justify-between animate-fadeIn">
          <div className="flex items-center gap-3">
            <span className="w-2.5 h-2.5 rounded-full bg-primary animate-pulse" />
            <p className="text-sm font-medium text-textPrimary">{notification}</p>
          </div>
          <button
            onClick={() => setNotification(null)}
            className="text-xs font-semibold text-textSecondary hover:text-textPrimary"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* 1. Welcome Header */}
      <section className="pb-2">
        <div className="inline-flex items-center gap-2 mb-2">
          <Badge status="success" size="sm" withDot>
            Patient Portal
          </Badge>
          <span className="text-xs text-textSecondary font-mono">ID: {patient.id}</span>
        </div>
        <h1 className="font-heading font-extrabold text-3xl sm:text-4xl text-textPrimary tracking-tight">
          Welcome back, {patient.name}
        </h1>
        <p className="text-base text-textSecondary mt-1 leading-relaxed">
          Here's what's happening with your health and upcoming care schedule.
        </p>
      </section>

      {/* Error Alert */}
      {error && (
        <div className="p-4 bg-errorContainer/30 border border-error/30 rounded-2xl flex items-center justify-between text-xs text-error">
          <p className="font-medium">⚠️ {error}</p>
          <Button size="sm" variant="ghost" onClick={fetchAppointments}>
            Retry
          </Button>
        </div>
      )}

      {/* Loading Spinner */}
      {loading ? (
        <Card radius="3xl" shadow="sm" className="p-12 text-center bg-white border border-surfaceContainerHigh">
          <div className="w-8 h-8 border-3 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-xs text-textSecondary font-medium">Fetching your appointment schedule from server...</p>
        </Card>
      ) : (
        <>
          {/* 2. Profile Completion Banner */}
          {profile && !profile.profile_completed && (
            <section>
              <Card
                radius="3xl"
                shadow="md"
                className="p-6 bg-gradient-to-r from-amber-50 to-amber-100/50 border border-amber-200 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
              >
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-2xl bg-amber-200/60 flex items-center justify-center shrink-0">
                    <svg className="w-5 h-5 text-amber-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="font-heading font-bold text-base text-amber-900">Complete Your Medical Profile</h3>
                    <p className="text-sm text-amber-700 mt-0.5">
                      Please provide your medical history and emergency contact information for safer care.
                    </p>
                  </div>
                </div>
                <Link to="/medical-profile">
                  <Button variant="secondary" size="md" className="shrink-0">
                    Complete Now
                  </Button>
                </Link>
              </Card>
            </section>
          )}

          {/* 3. Upcoming Appointment Card */}
          <section className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-heading font-bold text-xl text-textPrimary tracking-tight">
                Upcoming Appointment
              </h2>
            </div>

            {upcomingAppointment ? (
              <Card
                radius="3xl"
                shadow="md"
                className="p-6 sm:p-8 bg-white border border-surfaceContainerHigh transition-all hover:shadow-soft-lg"
              >
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
                  {/* Doctor Details & Date */}
                  <div className="flex items-start gap-4 sm:gap-5">
                    <div className="w-14 h-14 sm:w-16 sm:h-16 rounded-2xl bg-gradient-to-br from-primary/15 to-primaryContainer/20 border border-primary/20 flex items-center justify-center text-primary shrink-0">
                      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z"
                        />
                      </svg>
                    </div>

                    <div className="space-y-1.5">
                      <div className="flex flex-wrap items-center gap-2.5">
                        <h3 className="font-heading font-bold text-xl text-textPrimary">
                          {upcomingAppointment.doctor_name}
                        </h3>
                        <Badge status="success" size="sm" withDot>
                          {upcomingAppointment.status}
                        </Badge>
                        {upcomingAppointment.urgency_level && (
                          <Badge status="pending" size="sm">
                            {upcomingAppointment.urgency_level} urgency
                          </Badge>
                        )}
                        {upcomingAppointment.urgency_reason && (
                          <span className="text-[10px] text-textSecondary italic" title={upcomingAppointment.urgency_reason}>
                            {upcomingAppointment.urgency_reason.replace(/_/g, ' ')}
                          </span>
                        )}
                      </div>

                      <p className="text-sm font-medium text-secondary">
                        {upcomingAppointment.doctor_specialization}
                      </p>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-y-1 gap-x-6 pt-2 text-xs text-textSecondary">
                        <div className="flex items-center gap-2">
                          <svg className="w-4 h-4 text-primary shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5" />
                          </svg>
                          <span className="font-semibold text-textPrimary">
                            {formatDateTime(upcomingAppointment.appointment_time).date}
                          </span>
                        </div>

                        <div className="flex items-center gap-2">
                          <svg className="w-4 h-4 text-primary shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
                          </svg>
                          <span className="font-semibold text-textPrimary">
                            {formatDateTime(upcomingAppointment.appointment_time).time}
                          </span>
                        </div>

                        <div className="flex items-center gap-2 sm:col-span-2 pt-1">
                          <svg className="w-4 h-4 text-textSecondary shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
                            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1 1 15 0Z" />
                          </svg>
                          <span>
                            <strong className="text-textPrimary">{upcomingAppointment.clinic_name}</strong> — {upcomingAppointment.clinic_address}
                          </span>
                        </div>

                        {upcomingAppointment.symptoms_reported && (
                          <div className="sm:col-span-2 mt-2 p-2.5 bg-surfaceContainer rounded-xl text-xs text-textSecondary">
                            <strong className="text-textPrimary">Symptoms Reported:</strong> {upcomingAppointment.symptoms_reported}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="flex flex-row lg:flex-col items-center lg:items-end justify-between sm:justify-end gap-3 pt-4 lg:pt-0 border-t lg:border-t-0 border-surfaceContainerHigh">
                    <Link to="/chat">
                      <Button variant="secondary" size="md">
                        Reschedule
                      </Button>
                    </Link>
                    <button
                      type="button"
                      onClick={() => handleCancelAppointment(upcomingAppointment.appointment_id)}
                      className="text-xs font-semibold text-error hover:underline px-3 py-1.5 rounded-pill hover:bg-errorContainer/30 transition-colors"
                    >
                      Cancel Appointment
                    </button>
                  </div>
                </div>
              </Card>
            ) : (
              /* Empty State Card */
              <Card
                radius="3xl"
                shadow="sm"
                className="p-8 sm:p-12 text-center bg-white border border-surfaceContainerHigh"
              >
                <div className="w-14 h-14 rounded-2xl bg-surfaceContainer text-textSecondary mx-auto flex items-center justify-center mb-4">
                  <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5" />
                  </svg>
                </div>
                <h3 className="font-heading font-bold text-lg text-textPrimary mb-1">
                  No upcoming appointments
                </h3>
                <p className="text-sm text-textSecondary max-w-md mx-auto mb-6">
                  You are all caught up! Need medical advice or a routine specialist checkup?
                </p>
                <Link to="/chat">
                  <Button variant="primary" size="md">
                    Book Now with AI Assistant
                  </Button>
                </Link>
              </Card>
            )}
          </section>

          {/* 3. Action Cards Side by Side */}
          <section className="space-y-4">
            <h2 className="font-heading font-bold text-xl text-textPrimary tracking-tight">
              Quick Health Actions
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Action Card 1: Book New Appointment */}
              <Link to="/chat" className="group block focus:outline-none">
                <Card
                  variant="interactive"
                  radius="3xl"
                  shadow="default"
                  className="p-7 sm:p-8 h-full flex flex-col justify-between bg-gradient-to-br from-white to-surfaceContainer/50 border border-surfaceContainerHigh group-hover:border-primary/40 group-hover:shadow-soft-md transition-all duration-200"
                >
                  <div>
                    <div className="flex items-center justify-between mb-5">
                      <div className="w-13 h-13 rounded-2xl bg-gradient-to-br from-primary to-primaryContainer text-white flex items-center justify-center shadow-soft-sm group-hover:scale-105 transition-transform">
                        <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456ZM16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423Z"
                          />
                        </svg>
                      </div>
                      <Badge status="primary" size="sm">
                        AI Guided
                      </Badge>
                    </div>

                    <h3 className="font-heading font-bold text-2xl text-textPrimary mb-2 group-hover:text-primary transition-colors">
                      Book New Appointment
                    </h3>
                    <p className="text-sm text-textSecondary leading-relaxed">
                      Describe symptoms to our intelligent AI assistant to triage severity, match with specialized doctors, and book instant time slots.
                    </p>
                  </div>

                  <div className="pt-6 flex items-center justify-between">
                    <span className="text-xs font-semibold text-primary group-hover:translate-x-1 transition-transform inline-flex items-center gap-1.5">
                      Launch Health Chat <span>&rarr;</span>
                    </span>
                    <Button size="sm" variant="primary">
                      Start Triage
                    </Button>
                  </div>
                </Card>
              </Link>

              {/* Action Card 2: View History */}
              <Link to="/medical-profile" className="group block focus:outline-none">
                <Card
                  variant="interactive"
                  radius="3xl"
                  shadow="default"
                  className="p-7 sm:p-8 h-full flex flex-col justify-between bg-gradient-to-br from-white to-surfaceContainer/50 border border-surfaceContainerHigh group-hover:border-secondary/40 group-hover:shadow-soft-md transition-all duration-200"
                >
                  <div>
                    <div className="flex items-center justify-between mb-5">
                      <div className="w-13 h-13 rounded-2xl bg-[#62FAE3]/40 text-secondary border border-secondary/20 flex items-center justify-center shadow-soft-sm group-hover:scale-105 transition-transform">
                        <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 0 0 2.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 0 0-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75 2.25 2.25 0 0 0-.1-.664m-5.8 0A2.251 2.251 0 0 1 13.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25ZM6.75 12h.008v.008H6.75V12Zm0 3h.008v.008H6.75V15Zm0 3h.008v.008H6.75V18Z"
                          />
                        </svg>
                      </div>
                      <Badge status="success" size="sm">
                        Medical History
                      </Badge>
                    </div>

                    <h3 className="font-heading font-bold text-2xl text-textPrimary mb-2 group-hover:text-secondary transition-colors">
                      Medical Profile
                    </h3>
                    <p className="text-sm text-textSecondary leading-relaxed">
                      View and manage your allergies, medical conditions, demographics, and emergency contact information.
                    </p>
                  </div>

                  <div className="pt-6 flex items-center justify-between">
                    <span className="text-xs font-semibold text-secondary group-hover:translate-x-1 transition-transform inline-flex items-center gap-1.5">
                      Manage Profile <span>&rarr;</span>
                    </span>
                    <Button size="sm" variant="secondary">
                      Open Profile
                    </Button>
                  </div>
                </Card>
              </Link>
            </div>
          </section>

          {/* 4. Real Stats Row */}
          <section className="space-y-4">
            <h2 className="font-heading font-bold text-xl text-textPrimary tracking-tight">
              Care Summary
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
              {/* Stat 1 */}
              <Card radius="2xl" shadow="sm" className="p-6 bg-white border border-surfaceContainerHigh">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-textSecondary">
                    Total Appointments
                  </span>
                  <div className="w-8 h-8 rounded-xl bg-surfaceContainer text-primary flex items-center justify-center">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 0 1 6 3.75h2.25A2.25 2.25 0 0 1 10.5 6v2.25a2.25 2.25 0 0 1-2.25 2.25H6a2.25 2.25 0 0 1-2.25-2.25V6ZM3.75 15.75A2.25 2.25 0 0 1 6 13.5h2.25a2.25 2.25 0 0 1 2.25 2.25V18a2.25 2.25 0 0 1-2.25 2.25H6A2.25 2.25 0 0 1 3.75 18v-2.25Z" />
                    </svg>
                  </div>
                </div>
                <div className="mt-3">
                  <span className="font-heading font-extrabold text-3xl sm:text-4xl text-textPrimary">
                    {totalAppointments}
                  </span>
                  <p className="text-xs text-textSecondary mt-1">Recorded in your profile</p>
                </div>
              </Card>

              {/* Stat 2 */}
              <Card radius="2xl" shadow="sm" className="p-6 bg-white border border-surfaceContainerHigh">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-textSecondary">
                    Completed Visits
                  </span>
                  <div className="w-8 h-8 rounded-xl bg-[#62FAE3]/30 text-secondary flex items-center justify-center">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
                    </svg>
                  </div>
                </div>
                <div className="mt-3">
                  <span className="font-heading font-extrabold text-3xl sm:text-4xl text-secondary">
                    {completedVisits}
                  </span>
                  <p className="text-xs text-textSecondary mt-1">Documented medical visits</p>
                </div>
              </Card>

              {/* Stat 3 */}
              <Card radius="2xl" shadow="sm" className="p-6 bg-white border border-surfaceContainerHigh">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-textSecondary">
                    Upcoming
                  </span>
                  <div className="w-8 h-8 rounded-xl bg-surfaceContainerHigh text-primary flex items-center justify-center">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
                    </svg>
                  </div>
                </div>
                <div className="mt-3">
                  <span className="font-heading font-extrabold text-3xl sm:text-4xl text-primary">
                    {upcomingVisits}
                  </span>
                  <p className="text-xs text-textSecondary mt-1">
                    {upcomingVisits > 0 ? 'Active scheduled visits' : 'No pending sessions'}
                  </p>
                </div>
              </Card>
            </div>
          </section>
        </>
      )}
    </div>
  );
};
