import React, { useState, useEffect } from 'react';
import { Navigate } from 'react-router-dom';
import { Card, Button, Badge } from '../components/ui';
import { useAuth } from '../context/AuthContext';
import { listAppointments, completeAppointment, markNoShow } from '../services/appointments';

type UrgencyLevel = 'low' | 'normal' | 'high' | 'critical';

interface BackendDoctorAppointment {
  appointment_id: string;
  patient_id: string;
  patient_name: string;
  doctor_id: string;
  doctor_name: string;
  appointment_time: string;
  end_time: string;
  status: string;
  urgency_level?: string;
  urgency_reason?: string | null;
  symptoms_reported?: string;
  doctor_notes?: string;
}

export const DoctorDashboard: React.FC = () => {
  const { currentUser } = useAuth();
  const [schedule, setSchedule] = useState<BackendDoctorAppointment[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [activeNotesId, setActiveNotesId] = useState<string | null>(null);
  const [notesText, setNotesText] = useState<string>('');
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Redirect unverified doctors to pending verification page
  if (currentUser?.userType === 'doctor' && currentUser.isVerified === false) {
    return <Navigate to="/pending-verification" replace />;
  }

  const fetchSchedule = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listAppointments({ status: 'scheduled' });
      console.log('[DoctorDashboard] API response:', JSON.stringify(res, null, 2));
      const appts = res.appointments || [];
      console.log(`[DoctorDashboard] Got ${appts.length} appointments`);
      if (appts.length > 0) {
        console.log('[DoctorDashboard] First appointment sample:', JSON.stringify(appts[0], null, 2));
      }
      setSchedule(appts);
    } catch (err: any) {
      console.error('[DoctorDashboard] Failed to load schedule:', err);
      console.error('[DoctorDashboard] Error response:', JSON.stringify(err?.response?.data, null, 2));
      setError(err?.response?.data?.detail?.message || 'Failed to load upcoming schedule.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSchedule();
  }, []);

  const doctorName = currentUser?.userType === 'doctor' ? currentUser.name : 'Dr. Attending Physician';
  const doctorSpecialty = 'Clinical Specialist';

  // Format today's date nicely
  const todayFormatted = new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });

  // Calculate stats dynamically
  const totalUpcoming = schedule.length;
  const completedCount = schedule.filter((s) => s.status.toLowerCase() === 'completed').length;
  const noShowCount = schedule.filter((s) => s.status.toLowerCase() === 'no_show' || s.status.toLowerCase() === 'no-show').length;
  // "Upcoming" stat = today's appointments only
  const todayStr = new Date().toDateString();
  const todayCount = schedule.filter((s) => {
    try { return new Date(s.appointment_time).toDateString() === todayStr; } catch { return false; }
  }).length;

  const utilizationPct = totalUpcoming > 0 ? Math.round(((completedCount + noShowCount) / totalUpcoming) * 100) : 0;

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  // Urgency badge styling
  const getUrgencyBadge = (urgency?: string) => {
    const norm = (urgency || 'normal').toLowerCase();
    switch (norm) {
      case 'critical':
        return (
          <span className="inline-flex items-center gap-1 bg-errorContainer text-error border border-error/30 text-[10px] font-extrabold uppercase px-2.5 py-0.5 rounded-pill animate-pulse">
            🚨 Critical
          </span>
        );
      case 'high':
        return (
          <span className="inline-flex items-center gap-1 bg-amber-100 text-amber-800 border border-amber-300 text-[10px] font-bold uppercase px-2.5 py-0.5 rounded-pill">
            ⚠️ High
          </span>
        );
      case 'low':
        return (
          <Badge status="neutral" size="sm">
            Low
          </Badge>
        );
      default:
        return (
          <Badge status="pending" size="sm">
            Normal
          </Badge>
        );
    }
  };

  const getStatusBadge = (statusStr: string) => {
    const s = statusStr.toLowerCase();
    if (s === 'completed') {
      return (
        <Badge status="success" size="sm" withDot>
          Completed
        </Badge>
      );
    }
    if (s === 'no_show' || s === 'no-show') {
      return (
        <Badge status="error" size="sm">
          No-show
        </Badge>
      );
    }
    if (s === 'cancelled') {
      return (
        <Badge status="neutral" size="sm">
          Cancelled
        </Badge>
      );
    }
    return (
      <Badge status="pending" size="sm">
        Scheduled
      </Badge>
    );
  };

  const handleStartComplete = (apt: BackendDoctorAppointment) => {
    setActiveNotesId(apt.appointment_id);
    setNotesText(apt.doctor_notes || '');
  };

  const handleSaveNotesAndFinalize = async (id: string) => {
    if (!notesText.trim()) {
      alert('Please enter clinical consultation notes before completing the appointment.');
      return;
    }

    try {
      await completeAppointment(id, { notes: notesText.trim() });
      setActiveNotesId(null);
      setNotesText('');
      showToast('Appointment marked as Completed with clinical notes saved.');
      fetchSchedule();
    } catch (err: any) {
      alert(err?.response?.data?.detail?.message || 'Failed to complete appointment');
    }
  };

  const handleMarkNoShowAction = async (id: string) => {
    if (window.confirm('Are you sure you want to mark this patient as No-show?')) {
      try {
        await markNoShow(id);
        showToast('Patient marked as No-show.');
        fetchSchedule();
      } catch (err: any) {
        alert(err?.response?.data?.detail?.message || 'Failed to mark appointment as no-show');
      }
    }
  };

  const formatTime = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-12 space-y-10">
      {/* Toast */}
      {toastMessage && (
        <div className="p-4 bg-surfaceContainer border border-primaryContainer/30 rounded-2xl shadow-soft-sm flex items-center justify-between animate-fadeIn">
          <div className="flex items-center gap-2.5">
            <span className="w-2.5 h-2.5 rounded-full bg-secondary animate-pulse" />
            <p className="text-sm font-medium text-textPrimary">{toastMessage}</p>
          </div>
          <button
            onClick={() => setToastMessage(null)}
            className="text-xs font-semibold text-textSecondary hover:text-textPrimary"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* 1. Header with Doctor info & Today's Schedule */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-surfaceContainerHigh">
        <div>
          <div className="inline-flex items-center gap-2 mb-2">
            <Badge status="primary" size="sm" withDot>
              Doctor Clinical Portal
            </Badge>
            <span className="text-xs text-secondary font-semibold">{doctorSpecialty}</span>
          </div>
          <h1 className="font-heading font-extrabold text-3xl sm:text-4xl text-textPrimary tracking-tight">
            Upcoming Schedule
          </h1>
          <p className="text-sm sm:text-base text-textSecondary mt-1 flex items-center gap-2">
            <span>📅 {todayFormatted}</span>
            <span>•</span>
            <span>Attending: <strong>{doctorName}</strong></span>
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Badge status="success" size="md">
            Clinic Open
          </Badge>
        </div>
      </div>

      {/* 2. Stats Row (4 Stat Cards) */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
        <Card radius="2xl" shadow="sm" className="p-5 bg-white border border-surfaceContainerHigh">
          <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-textSecondary">
            <span>Total Upcoming</span>
            <span>📋</span>
          </div>
          <div className="mt-3">
            <span className="font-heading font-extrabold text-3xl text-textPrimary">{totalUpcoming}</span>
            <p className="text-[11px] text-textSecondary mt-0.5">Patients booked</p>
          </div>
        </Card>

        <Card radius="2xl" shadow="sm" className="p-5 bg-white border border-surfaceContainerHigh">
          <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-textSecondary">
            <span>Completed</span>
            <span>✅</span>
          </div>
          <div className="mt-3">
            <span className="font-heading font-extrabold text-3xl text-secondary">{completedCount}</span>
            <p className="text-[11px] text-textSecondary mt-0.5">Visits documented</p>
          </div>
        </Card>

        <Card radius="2xl" shadow="sm" className="p-5 bg-white border border-surfaceContainerHigh">
          <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-textSecondary">
            <span>Today</span>
            <span>📌</span>
          </div>
          <div className="mt-3">
            <span className="font-heading font-extrabold text-3xl text-primary">{todayCount}</span>
            <p className="text-[11px] text-textSecondary mt-0.5">Today's appointments</p>
          </div>
        </Card>

        <Card radius="2xl" shadow="sm" className="p-5 bg-white border border-surfaceContainerHigh">
          <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-textSecondary">
            <span>Utilization %</span>
            <span>📊</span>
          </div>
          <div className="mt-3">
            <span className="font-heading font-extrabold text-3xl text-textPrimary">{utilizationPct}%</span>
            <p className="text-[11px] text-textSecondary mt-0.5">Shift completion</p>
          </div>
        </Card>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="p-4 bg-errorContainer/30 border border-error/30 rounded-2xl flex items-center justify-between text-xs text-error">
          <p className="font-medium">⚠️ {error}</p>
          <Button size="sm" variant="ghost" onClick={fetchSchedule}>
            Retry
          </Button>
        </div>
      )}

      {/* 3. Appointment List (Rows/Cards) */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-heading font-bold text-xl text-textPrimary tracking-tight">
            Patient Appointments Queue
          </h2>
          <span className="text-xs font-mono text-textSecondary bg-surfaceContainer px-3 py-1 rounded-pill">
            Live Clinical List
          </span>
        </div>

        {loading ? (
          <Card radius="2xl" shadow="sm" className="p-12 text-center bg-white border border-surfaceContainerHigh">
            <div className="w-8 h-8 border-3 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-xs text-textSecondary font-medium">Fetching upcoming clinical queue...</p>
          </Card>
        ) : schedule.length > 0 ? (
          <div className="space-y-4">
            {schedule.map((apt) => {
              const statusLower = apt.status.toLowerCase();
              const isCompleted = statusLower === 'completed';
              const isNoShow = statusLower === 'no_show' || statusLower === 'no-show';
              const isPending = statusLower === 'scheduled' || statusLower === 'confirmed' || statusLower === 'upcoming';
              const isEditingNotes = activeNotesId === apt.appointment_id;
              const isCritical = apt.urgency_level?.toLowerCase() === 'critical';

              const formattedTime = formatTime(apt.appointment_time);

              return (
                <Card
                  key={apt.appointment_id}
                  radius="2xl"
                  shadow="sm"
                  className={`p-5 sm:p-6 bg-white border transition-all duration-200 ${
                    isCritical && isPending
                      ? 'border-error/50 shadow-soft-md ring-2 ring-error/15'
                      : 'border-surfaceContainerHigh hover:border-primaryContainer/30'
                  }`}
                >
                  <div className="space-y-3">
                    {/* Top: Patient name + Date/Time + Badges */}
                    <div className="flex flex-wrap items-center gap-2.5">
                      <div className="flex items-center gap-2 bg-primary/5 border border-primary/20 rounded-xl px-3 py-1.5">
                        <svg className="w-4 h-4 text-primary shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" /></svg>
                        <h3 className="font-heading font-bold text-sm text-textPrimary">
                          {apt.patient_name}
                        </h3>
                      </div>
                      <code className="text-[10px] font-mono text-primary bg-surfaceContainer px-1.5 py-0.5 rounded">{`PT-${apt.patient_id.slice(0, 6)}`}</code>
                      {getUrgencyBadge(apt.urgency_level)}
                      {getStatusBadge(apt.status)}
                    </div>

                    {/* Date + Time inline */}
                    <div className="flex flex-wrap items-center gap-3 text-xs text-textSecondary">
                      <span className="flex items-center gap-1.5">
                        <svg className="w-3.5 h-3.5 text-primary shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5" /></svg>
                        {new Date(apt.appointment_time).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
                        <span className="text-textPrimary font-semibold">{formattedTime}</span>
                      </span>
                    </div>

                    {/* Triage + Symptoms clinical section */}
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
                      <span className="flex items-center gap-1.5">
                        <svg className="w-3.5 h-3.5 shrink-0 text-textSecondary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" /></svg>
                        {(() => {
                          const RD: Record<string, string> = {
                            chest_pain_with_breathing_distress: 'Chest pain with breathing distress',
                            chest_pain_radiating: 'Chest pain radiating',
                            worsening_chest_pain: 'Worsening chest pain',
                            severe_bleeding: 'Severe bleeding',
                            serious_trauma: 'Serious trauma',
                            head_injury_red_flag: 'Head injury red flag',
                            anaphylaxis_red_flag: 'Anaphylaxis red flag',
                            severe_abdominal_pain: 'Severe abdominal pain',
                            meningitis_red_flag: 'Meningitis red flag',
                            diabetic_red_flag: 'Diabetic red flag',
                            severe_asthma: 'Severe asthma',
                            child_high_fever: 'Child high fever',
                            pregnancy_emergency: 'Pregnancy emergency',
                            standalone_emergency_pattern: 'Emergency pattern detected',
                            high_urgency_marker: 'High urgency marker',
                            cardiology_route: 'Cardiology route',
                            specialty_route: 'Specialty route',
                            insufficient_detail: 'Insufficient detail',
                          };
                          const display = apt.urgency_reason ? RD[apt.urgency_reason] || apt.urgency_reason.replace(/_/g, ' ') : null;
                          return display
                            ? <span className="text-textSecondary">Triage: <span className="font-medium text-textPrimary">{display}</span></span>
                            : <span className="text-textSecondary italic">No triage data</span>;
                        })()}
                      </span>
                    </div>

                    {/* Symptoms */}
                    {apt.symptoms_reported && (
                      <div className="text-xs text-textSecondary leading-relaxed">
                        <strong className="text-textPrimary">Symptoms:</strong> {apt.symptoms_reported}
                      </div>
                    )}

                    {/* Completed Notes View */}
                    {apt.doctor_notes && !isEditingNotes && (
                      <div className="mt-1 p-3 bg-surfaceContainer/80 rounded-xl text-xs border border-surfaceContainerHigh space-y-0.5">
                        <span className="font-bold text-secondary uppercase text-[10px] tracking-wider block">
                          Saved Clinical Notes:
                        </span>
                        <p className="text-textPrimary italic">{apt.doctor_notes}</p>
                      </div>
                    )}

                    {/* Actions row */}
                    <div className="flex flex-wrap items-center gap-2.5 pt-1">
                      {isPending && !isEditingNotes && (
                        <div className="flex items-center gap-2">
                          <Button
                            variant="primary"
                            size="sm"
                            onClick={() => handleStartComplete(apt)}
                          >
                            Mark Complete
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            className="hover:border-error hover:text-error"
                            onClick={() => handleMarkNoShowAction(apt.appointment_id)}
                          >
                            Mark No-show
                          </Button>
                        </div>
                      )}

                      {isCompleted && (
                        <div className="flex items-center gap-2 text-xs font-semibold text-secondary bg-secondaryContainer/30 px-3 py-1.5 rounded-pill border border-secondary/20">
                          <span>✓ Record Finalized</span>
                        </div>
                      )}

                      {isNoShow && (
                        <div className="flex items-center gap-2 text-xs font-semibold text-error bg-errorContainer/40 px-3 py-1.5 rounded-pill border border-error/20">
                          <span>✗ Marked No-Show</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Inline Notes Expansion when Mark Complete is clicked */}
                  {isEditingNotes && (
                    <div className="mt-4 pt-4 border-t border-surfaceContainerHigh bg-surfaceContainer/50 -mx-5 sm:-mx-6 -mb-5 sm:-mb-6 p-5 rounded-b-2xl animate-fadeIn space-y-3">
                      <label className="block text-xs font-bold text-textPrimary">
                        Add Clinical Notes & Prescription for {apt.patient_name}:
                      </label>
                      <textarea
                        rows={3}
                        value={notesText}
                        onChange={(e) => setNotesText(e.target.value)}
                        placeholder="Enter clinical findings, vital interpretations, prescriptions, and follow-up instructions..."
                        className="w-full text-xs bg-white rounded-xl border border-outline/40 p-3 outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary placeholder:text-textSecondary/60"
                      />
                      <div className="flex items-center justify-end gap-2.5">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            setActiveNotesId(null);
                            setNotesText('');
                          }}
                        >
                          Cancel
                        </Button>
                        <Button
                          size="sm"
                          variant="primary"
                          onClick={() => handleSaveNotesAndFinalize(apt.appointment_id)}
                        >
                          Save Notes & Finalize
                        </Button>
                      </div>
                    </div>
                  )}
                </Card>
              );
            })}
          </div>
        ) : (
          <Card radius="2xl" shadow="sm" className="p-10 text-center bg-white border border-surfaceContainerHigh space-y-2">
            <p className="font-heading font-bold text-base text-textPrimary">No upcoming scheduled appointments</p>
            <p className="text-xs text-textSecondary">Your queue is currently clear.</p>
          </Card>
        )}
      </section>
    </div>
  );
};
