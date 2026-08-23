import React, { useState } from 'react';
import { Card, Button, Badge } from '../components/ui';
import { useAuth } from '../context/AuthContext';

type UrgencyLevel = 'low' | 'normal' | 'high' | 'critical';
type DoctorAppointmentStatus = 'Upcoming' | 'In-Progress' | 'Completed' | 'No-show';

interface DoctorAppointment {
  id: string;
  time: string;
  patientName: string;
  patientAge: number;
  patientGender: string;
  patientId: string;
  symptoms: string;
  urgency: UrgencyLevel;
  status: DoctorAppointmentStatus;
  notes?: string;
  type: 'In-Clinic' | 'Telehealth Video';
}

const initialDoctorSchedule: DoctorAppointment[] = [
  {
    id: 'D-101',
    time: '08:30 AM',
    patientName: 'Arthur Pendelton',
    patientAge: 62,
    patientGender: 'Male',
    patientId: 'PT-1082',
    symptoms: 'Post-CABG surgery routine follow-up, reports occasional dizziness.',
    urgency: 'high',
    status: 'Completed',
    notes: 'ECG normal sinus rhythm. Adjusted Beta-blocker dosage to 25mg daily. Scheduled echo in 4 weeks.',
    type: 'In-Clinic',
  },
  {
    id: 'D-102',
    time: '09:15 AM',
    patientName: 'Emma Watson',
    patientAge: 34,
    patientGender: 'Female',
    patientId: 'PT-9421',
    symptoms: 'Mild chest tightness upon moderate treadmill exertion, no radiation to arm.',
    urgency: 'high',
    status: 'Completed',
    notes: 'Vitals stable. Ordered stress echocardiogram and lipid profile.',
    type: 'In-Clinic',
  },
  {
    id: 'D-103',
    time: '10:00 AM',
    patientName: 'Michael Chang',
    patientAge: 48,
    patientGender: 'Male',
    patientId: 'PT-8821',
    symptoms: 'Severe palpitations with resting heart rate > 120 bpm, shortness of breath.',
    urgency: 'critical',
    status: 'Upcoming',
    type: 'In-Clinic',
  },
  {
    id: 'D-104',
    time: '10:45 AM',
    patientName: 'Sarah Jenkins',
    patientAge: 29,
    patientGender: 'Female',
    patientId: 'PT-89420',
    symptoms: 'Annual cardiovascular wellness check, family history of hyperlipidemia.',
    urgency: 'normal',
    status: 'Upcoming',
    type: 'In-Clinic',
  },
  {
    id: 'D-105',
    time: '11:30 AM',
    patientName: 'Lucas Vance',
    patientAge: 19,
    patientGender: 'Male',
    patientId: 'PT-7640',
    symptoms: 'Pre-athletic collegiate clearance examination.',
    urgency: 'low',
    status: 'Upcoming',
    type: 'In-Clinic',
  },
  {
    id: 'D-106',
    time: '01:15 PM',
    patientName: 'Eleanor Davis',
    patientAge: 71,
    patientGender: 'Female',
    patientId: 'PT-6523',
    symptoms: 'Hypertension management, home systolic readings averaging 145-155.',
    urgency: 'normal',
    status: 'Upcoming',
    type: 'Telehealth Video',
  },
  {
    id: 'D-107',
    time: '02:00 PM',
    patientName: 'David K. Miller',
    patientAge: 53,
    patientGender: 'Male',
    patientId: 'PT-5120',
    symptoms: 'Did not answer scheduled teleconsultation call.',
    urgency: 'low',
    status: 'No-show',
    type: 'Telehealth Video',
  },
  {
    id: 'D-108',
    time: '03:00 PM',
    patientName: 'Rachel Green',
    patientAge: 42,
    patientGender: 'Female',
    patientId: 'PT-4981',
    symptoms: 'Follow-up on 24-hr Holter monitor findings for PVCs.',
    urgency: 'normal',
    status: 'Upcoming',
    type: 'In-Clinic',
  },
];

export const DoctorDashboard: React.FC = () => {
  const { currentUser } = useAuth();
  const [schedule, setSchedule] = useState<DoctorAppointment[]>(initialDoctorSchedule);
  const [activeNotesId, setActiveNotesId] = useState<string | null>(null);
  const [notesText, setNotesText] = useState<string>('');
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const doctorName = currentUser?.userType === 'doctor' ? currentUser.name : 'Dr. Ahmed Khan, MD';
  const doctorSpecialty = currentUser?.specialization || 'Senior Cardiologist & Vascular Specialist';

  // Format today's date nicely
  const todayFormatted = new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });

  // Calculate stats dynamically
  const totalToday = schedule.length;
  const completedCount = schedule.filter((s) => s.status === 'Completed').length;
  const upcomingCount = schedule.filter((s) => s.status === 'Upcoming').length;
  const noShowCount = schedule.filter((s) => s.status === 'No-show').length;
  const utilizationPct = Math.round(((completedCount + noShowCount) / totalToday) * 100);

  // Urgency badge styling
  const getUrgencyBadge = (urgency: UrgencyLevel) => {
    switch (urgency) {
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
      case 'normal':
        return (
          <Badge status="pending" size="sm">
            Normal
          </Badge>
        );
      case 'low':
        return (
          <Badge status="neutral" size="sm">
            Low
          </Badge>
        );
    }
  };

  const getStatusBadge = (status: DoctorAppointmentStatus) => {
    switch (status) {
      case 'Completed':
        return (
          <Badge status="success" size="sm" withDot>
            Completed
          </Badge>
        );
      case 'No-show':
        return (
          <Badge status="error" size="sm">
            No-show
          </Badge>
        );
      case 'In-Progress':
        return (
          <Badge status="primary" size="sm" withDot>
            In-Progress
          </Badge>
        );
      case 'Upcoming':
        return (
          <Badge status="pending" size="sm">
            Scheduled
          </Badge>
        );
    }
  };

  const handleStartComplete = (apt: DoctorAppointment) => {
    setActiveNotesId(apt.id);
    setNotesText(apt.notes || '');
  };

  const handleSaveNotesAndFinalize = (id: string) => {
    if (!notesText.trim()) {
      alert('Please enter clinical consultation notes before completing the appointment.');
      return;
    }

    setSchedule((prev) =>
      prev.map((apt) =>
        apt.id === id
          ? {
              ...apt,
              status: 'Completed',
              notes: notesText.trim(),
            }
          : apt
      )
    );

    setActiveNotesId(null);
    setNotesText('');
    setToastMessage('Appointment marked as Completed with clinical notes saved.');
    setTimeout(() => setToastMessage(null), 3500);
  };

  const handleMarkNoShow = (id: string) => {
    if (window.confirm('Are you sure you want to mark this patient as No-show?')) {
      setSchedule((prev) =>
        prev.map((apt) => (apt.id === id ? { ...apt, status: 'No-show' } : apt))
      );
      setToastMessage('Patient marked as No-show.');
      setTimeout(() => setToastMessage(null), 3000);
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
        {/* Stat 1 */}
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

        {/* Stat 2 */}
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

        {/* Stat 3 */}
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

        {/* Stat 4 */}
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

        <div className="space-y-4">
          {schedule.map((apt) => {
            const isCompleted = apt.status === 'Completed';
            const isNoShow = apt.status === 'No-show';
            const isPending = apt.status === 'Upcoming';
            const isEditingNotes = activeNotesId === apt.id;
            const isCritical = apt.urgency === 'critical';

            return (
              <Card
                key={apt.id}
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
                        {apt.time.split(' ')[0]}
                      </span>
                      <span className="text-[10px] uppercase font-bold text-textSecondary">
                        {apt.time.split(' ')[1]}
                      </span>
                      <span className="block text-[9px] font-semibold text-primary mt-0.5">
                        {apt.type === 'Telehealth Video' ? 'Video' : 'In-Person'}
                      </span>
                    </div>

                    {/* Patient & Symptom Details */}
                    <div className="space-y-1.5 flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2.5">
                        <h3 className="font-heading font-bold text-base sm:text-lg text-textPrimary">
                          {apt.patientName}
                        </h3>
                        <span className="text-xs text-textSecondary">
                          ({apt.patientAge}y, {apt.patientGender}) • <code className="text-[10px] font-mono text-primary bg-surfaceContainer px-1.5 py-0.5 rounded">{apt.patientId}</code>
                        </span>
                        {getUrgencyBadge(apt.urgency)}
                        {getStatusBadge(apt.status)}
                      </div>

                      <div className="text-xs text-textSecondary leading-relaxed pt-1">
                        <strong className="text-textPrimary">Symptoms / Reason:</strong> {apt.symptoms}
                      </div>

                      {/* Completed Notes View */}
                      {apt.notes && !isEditingNotes && (
                        <div className="mt-2.5 p-3 bg-surfaceContainer/80 rounded-xl text-xs border border-surfaceContainerHigh space-y-0.5">
                          <span className="font-bold text-secondary uppercase text-[10px] tracking-wider block">
                            Saved Clinical Notes:
                          </span>
                          <p className="text-textPrimary italic">{apt.notes}</p>
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
                          onClick={() => handleMarkNoShow(apt.id)}
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
                      Add Clinical Notes & Prescription for {apt.patientName}:
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
                        onClick={() => handleSaveNotesAndFinalize(apt.id)}
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
      </section>
    </div>
  );
};
