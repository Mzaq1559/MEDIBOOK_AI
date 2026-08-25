import React, { useState, useEffect } from 'react';
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

  const fetchSchedule = async () => {
    setLoading(true);
    setError(null);
    try {
      // Get today's appointments for doctor
      const res = await listAppointments({ date: 'today' });
      setSchedule(res.appointments || []);
    } catch (err: any) {
      console.error('Failed to load doctor schedule:', err);
      setError(err?.response?.data?.detail?.message || 'Failed to load today schedule.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSchedule();
  }, []);

  const doctorName = currentUser?.userType === 'doctor' ? currentUser.name : 'Dr. Attending Physician';
  const doctorSpecialty = currentUser?.specialization || 'Clinical Specialist';

  // Format today's date nicely
  const todayFormatted = new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });

  // Calculate stats dynamically
  const totalToday = schedule.length;
  const completedCount = schedule.filter((s) => s.status.toLowerCase() === 'completed').length;
  const noShowCount = schedule.filter((s) => s.status.toLowerCase() === 'no_show' || s.status.toLowerCase() === 'no-show').length;
  const upcomingCount = schedule.filter(
    (s) => s.status.toLowerCase() === 'scheduled' || s.status.toLowerCase() === 'confirmed' || s.status.toLowerCase() === 'upcoming'
  ).length;

  const utilizationPct = totalToday > 0 ? Math.round(((completedCount + noShowCount) / totalToday) * 100) : 0;

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
            Today's Schedule
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
            <span>Total Today</span>
            <span>📋</span>
          </div>
          <div className="mt-3">
            <span className="font-heading font-extrabold text-3xl text-textPrimary">{totalToday}</span>
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
            <span>Upcoming</span>
            <span>⏳</span>
          </div>
          <div className="mt-3">
            <span className="font-heading font-extrabold text-3xl text-primary">{upcomingCount}</span>
            <p className="text-[11px] text-textSecondary mt-0.5">Remaining in queue</p>
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
            <p className="text-xs text-textSecondary font-medium">Fetching today's clinical queue...</p>
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
                  <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-5">
                    {/* Left Column: Time & Patient Info */}
                    <div className="flex items-start gap-4 sm:gap-5 flex-1">
                      {/* Time Display */}
                      <div className="w-20 sm:w-24 text-center shrink-0 p-2.5 bg-surfaceContainer rounded-2xl border border-surfaceContainerHigh">
                        <span className="block font-heading font-extrabold text-sm sm:text-base text-textPrimary">
                          {formattedTime.split(' ')[0]}
                        </span>
                        <span className="text-[10px] uppercase font-bold text-textSecondary">
                          {formattedTime.split(' ')[1] || ''}
                        </span>
                      </div>

                      {/* Patient & Symptom Details */}
                      <div className="space-y-1.5 flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2.5">
                          <h3 className="font-heading font-bold text-base sm:text-lg text-textPrimary">
                            {apt.patient_name}
                          </h3>
                          <span className="text-xs text-textSecondary">
                            • <code className="text-[10px] font-mono text-primary bg-surfaceContainer px-1.5 py-0.5 rounded">{`PT-${apt.patient_id.slice(0, 6)}`}</code>
                          </span>
                          {getUrgencyBadge(apt.urgency_level)}
                          {getStatusBadge(apt.status)}
                        </div>

                        {apt.symptoms_reported && (
                          <div className="text-xs text-textSecondary leading-relaxed pt-1">
                            <strong className="text-textPrimary">Symptoms / Reason:</strong> {apt.symptoms_reported}
                          </div>
                        )}

                        {/* Completed Notes View */}
                        {apt.doctor_notes && !isEditingNotes && (
                          <div className="mt-2.5 p-3 bg-surfaceContainer/80 rounded-xl text-xs border border-surfaceContainerHigh space-y-0.5">
                            <span className="font-bold text-secondary uppercase text-[10px] tracking-wider block">
                              Saved Clinical Notes:
                            </span>
                            <p className="text-textPrimary italic">{apt.doctor_notes}</p>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Right Column: Actions */}
                    <div className="flex flex-row lg:flex-col items-center lg:items-end justify-between lg:justify-start gap-2.5 pt-3 lg:pt-0 border-t lg:border-t-0 border-surfaceContainerHigh shrink-0">
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
            <p className="font-heading font-bold text-base text-textPrimary">No appointments scheduled for today</p>
            <p className="text-xs text-textSecondary">Your queue is currently clear.</p>
          </Card>
        )}
      </section>
    </div>
  );
};
