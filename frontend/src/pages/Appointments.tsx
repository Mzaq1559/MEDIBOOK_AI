import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Card, Button, Badge } from '../components/ui';
import { useAuth } from '../context/AuthContext';
import { listAppointments, getPatientAppointments, cancelAppointment, submitAppointmentFeedback } from '../services/appointments';

type AppointmentStatus = 'Upcoming' | 'Completed' | 'Cancelled' | 'No-show';
type FilterTab = 'All' | AppointmentStatus;

/* ── Doctor-view appointment (from /api/appointments) ─────────────── */
interface DoctorAppointment {
  appointment_id: string;
  clinic_id: string;
  clinic_name: string;
  clinic_address?: string;
  doctor_id: string;
  doctor_name: string;
  doctor_specialization?: string;
  patient_id: string;
  patient_name: string;
  patient_email?: string;
  patient_phone?: string;
  patient_dob?: string;
  patient_age?: number;
  patient_gender?: string;
  patient_blood_type?: string;
  patient_allergies?: string;
  patient_medical_conditions?: string;
  appointment_time: string;
  end_time?: string;
  status: string;
  symptoms_reported: string;
  urgency_level: string;
  urgency_reason?: string | null;
  appointment_type: string;
  doctor_notes?: string;
  feedback_score?: number;
  feedback_text?: string;
  feedback_submitted?: boolean;
  created_at: string;
}

/* ── Patient-view appointment (from /api/patients/{id}/appointments) ─ */
interface PatientAppointment {
  appointment_id: string;
  doctor_id?: string;
  doctor_name: string;
  doctor_specialization?: string;
  clinic_id?: string;
  clinic_name: string;
  clinic_address?: string;
  appointment_time: string;
  end_time?: string;
  status: string;
  symptoms: string;
  urgency: string;
  doctor_notes?: string;
  feedback_score?: number;
  feedback_text?: string;
  feedback_submitted?: boolean;
}

/* ══════════════════════════════════════════════════════════════════════ */
export const Appointments: React.FC = () => {
  const { currentUser } = useAuth();

  const [doctorAppts, setDoctorAppts] = useState<DoctorAppointment[]>([]);
  const [patientAppts, setPatientAppts] = useState<PatientAppointment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<FilterTab>('All');
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [ratingInputs, setRatingInputs] = useState<Record<string, { rating: number; feedback: string }>>({});
  const [toast, setToast] = useState<string | null>(null);

  const isPatient = currentUser?.userType === 'patient';
  const isAdmin = currentUser?.userType === 'admin' || currentUser?.userType === 'receptionist';
  // Doctor, admin, and receptionist all see the clinical/staff view
  const isStaffView = !isPatient;

  /* ── Fetch ─────────────────────────────────────────────────────── */
  const fetch = async () => {
    setLoading(true);
    setError(null);
    try {
      if (isPatient) {
        const data = await getPatientAppointments(currentUser!.id);
        console.log('[Appointments] Patient API response:', JSON.stringify(data, null, 2));
        setPatientAppts(Array.isArray(data) ? data : data.appointments || []);
      } else {
        // Doctor, admin, receptionist — use the role-aware list endpoint
        const res = await listAppointments();
        console.log('[Appointments] API response:', JSON.stringify(res, null, 2));
        setDoctorAppts(res.appointments || []);
      }
    } catch (err: any) {
      console.error('[Appointments] Error:', err);
      setError(err?.response?.data?.detail?.message || 'Failed to load appointments.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetch(); }, [currentUser?.id, isPatient]);

  /* ── Helpers ───────────────────────────────────────────────────── */
  const mapStatus = (s: string, appointmentTime?: string): AppointmentStatus => {
    const l = s.toLowerCase();
    if (l === 'completed') return 'Completed';
    if (l === 'cancelled') return 'Cancelled';
    if (l === 'no_show' || l === 'no-show') return 'No-show';
    // Backend stores "scheduled" for all non-terminal appointments.
    // If the appointment time has already passed (Karachi time), treat as Completed.
    if ((l === 'scheduled' || l === 'confirmed' || l === 'upcoming') && appointmentTime) {
      try {
        if (new Date(appointmentTime).getTime() < Date.now()) return 'Completed';
      } catch { /* ignore parse errors */ }
    }
    return 'Upcoming';
  };

  const badgeStatus = (s: AppointmentStatus) =>
    s === 'Upcoming' ? 'pending' : s === 'Completed' ? 'success' : s === 'Cancelled' ? 'neutral' : 'error';

  const toggleExpand = (id: string) =>
    setExpandedIds((prev) => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });

  const fmtDt = (iso: string) => {
    try {
      const d = new Date(iso);
      return {
        date: d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' }),
        time: d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
        iso: d.toISOString(),
      };
    } catch { return { date: iso, time: '', iso: '' }; }
  };

  const fmtTime = (iso: string) => {
    try { return new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }); }
    catch { return iso; }
  };

  const googleCalUrl = (title: string, startIso: string, endIso: string, details: string, location: string) => {
    const fmt = (d: string) => new Date(d).toISOString().replace(/-|\:|\.\d{3}/g, '');
    const p = new URLSearchParams({
      action: 'TEMPLATE',
      text: title,
      dates: `${fmt(startIso)}/${fmt(endIso || startIso)}`,
      details,
      location,
      ctz: 'Asia/Karachi',
    });
    return `https://calendar.google.com/calendar/render?${p.toString()}`;
  };

  const parseJsonList = (v?: string | null): string[] => {
    if (!v) return [];
    try { const a = JSON.parse(v); return Array.isArray(a) ? a : [v]; } catch { return [v]; }
  };

  /* ── Actions ───────────────────────────────────────────────────── */
  const handleCancel = async (id: string) => {
    if (!window.confirm('Cancel this appointment?')) return;
    try { await cancelAppointment(id); setToast('Appointment cancelled.'); fetch(); setTimeout(() => setToast(null), 3000); }
    catch (err: any) { alert(err?.response?.data?.detail?.message || 'Failed to cancel'); }
  };

  const handleRatingChange = (id: string, star: number) =>
    setRatingInputs((p) => ({ ...p, [id]: { ...p[id], rating: star, feedback: p[id]?.feedback || '' } }));

  const handleFeedbackText = (id: string, text: string) =>
    setRatingInputs((p) => ({ ...p, [id]: { rating: p[id]?.rating || 0, feedback: text } }));

  const handleSubmitFeedback = async (id: string) => {
    const d = ratingInputs[id];
    if (!d || d.rating === 0) { alert('Please select a star rating.'); return; }
    try {
      await submitAppointmentFeedback(id, { feedback_score: d.rating, feedback_text: d.feedback });
      setToast('Thank you! Your review has been submitted.');
      fetch();
      setTimeout(() => setToast(null), 3000);
    } catch (err: any) { alert(err?.response?.data?.detail?.message || 'Failed to submit review'); }
  };

  /* ── Status counts ─────────────────────────────────────────────── */
  const allAppts = isStaffView ? doctorAppts : patientAppts;
  const rawStatus = (a: DoctorAppointment | PatientAppointment) => a.status;
  const getApptTime = (a: DoctorAppointment | PatientAppointment) => a.appointment_time;
  const countByStatus = (s: AppointmentStatus) => allAppts.filter((a) => mapStatus(rawStatus(a), getApptTime(a)) === s).length;

  const filtered = allAppts.filter((a) => {
    if (activeTab === 'All') return true;
    return mapStatus(rawStatus(a), getApptTime(a)) === activeTab;
  });

  const filterTabs: { key: FilterTab; label: string }[] = [
    { key: 'All', label: `All (${allAppts.length})` },
    { key: 'Upcoming', label: `Upcoming (${countByStatus('Upcoming')})` },
    { key: 'Completed', label: `Completed (${countByStatus('Completed')})` },
    { key: 'Cancelled', label: `Cancelled (${countByStatus('Cancelled')})` },
    { key: 'No-show', label: `No-show (${countByStatus('No-show')})` },
  ];

  /* ── Chevron icon ──────────────────────────────────────────────── */
  const ChevronIcon = ({ open }: { open: boolean }) => (
    <svg className={`w-5 h-5 text-textSecondary transition-transform duration-200 ${open ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
    </svg>
  );

  /* ── Star rating display ───────────────────────────────────────── */
  const Stars = ({ score, size = 'sm' }: { score: number; size?: 'sm' | 'md' }) => (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((s) => (
        <span key={s} className={size === 'md' ? 'text-lg' : 'text-sm'}>
          {s <= score ? '★' : '☆'}
        </span>
      ))}
    </div>
  );

  /* ══════════════════════════════════════════════════════════════════ */
  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-12 space-y-8">
      {/* Toast */}
      {toast && (
        <div className="p-4 bg-surfaceContainer border border-primaryContainer/30 rounded-2xl shadow-soft-sm flex items-center justify-between animate-fadeIn">
          <div className="flex items-center gap-2.5">
            <span className="w-2.5 h-2.5 rounded-full bg-secondary animate-pulse" />
            <p className="text-sm font-medium text-textPrimary">{toast}</p>
          </div>
          <button onClick={() => setToast(null)} className="text-xs font-semibold text-textSecondary hover:text-textPrimary">Dismiss</button>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-surfaceContainerHigh">
        <div>
          <div className="inline-flex items-center gap-2 mb-1.5">
            <Badge status={isAdmin ? 'success' : isStaffView ? 'primary' : 'success'} size="sm">
              {isAdmin ? 'Admin Overview' : isStaffView ? 'Clinical Queue' : 'Care History'}
            </Badge>
          </div>
          <h1 className="font-heading font-extrabold text-3xl sm:text-4xl text-textPrimary tracking-tight">
            {isAdmin ? 'System-Wide Appointments' : isStaffView ? 'Patient Appointments' : 'My Appointments'}
          </h1>
          <p className="text-sm sm:text-base text-textSecondary mt-1">
            {isAdmin
              ? 'View all appointments across doctors and patients with triage urgency data.'
              : isStaffView
                ? 'View patient details, reviews, and manage your clinical schedule.'
                : 'View, manage, and review your past and upcoming clinical visits.'}
          </p>
        </div>
        {!isStaffView && (
          <Link to="/chat" className="shrink-0">
            <Button variant="primary" size="md">+ Book New Appointment</Button>
          </Link>
        )}
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-none">
        {filterTabs.map((tab) => (
          <button key={tab.key} type="button" onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 rounded-pill text-xs font-semibold whitespace-nowrap transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
              activeTab === tab.key
                ? 'bg-primary text-white shadow-soft-sm scale-[1.02]'
                : 'bg-white text-textSecondary hover:text-textPrimary hover:bg-surfaceContainer border border-surfaceContainerHigh'
            }`}>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="p-4 bg-errorContainer/30 border border-error/30 rounded-2xl flex items-center justify-between text-xs text-error">
          <p className="font-medium">⚠️ {error}</p>
          <Button size="sm" variant="ghost" onClick={fetch}>Retry</Button>
        </div>
      )}

      {/* Loading */}
      {loading ? (
        <Card radius="2xl" shadow="sm" className="p-12 text-center bg-white border border-surfaceContainerHigh">
          <div className="w-8 h-8 border-3 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-xs text-textSecondary font-medium">Fetching appointments...</p>
        </Card>
      ) : (
        <div className="space-y-5">
          {filtered.length > 0 ? filtered.map((apt) => (
            isAdmin
              ? renderAdminCard(apt as DoctorAppointment)
              : isStaffView
                ? renderDoctorCard(apt as DoctorAppointment)
                : renderPatientCard(apt as PatientAppointment)
          )) : (
            <Card radius="2xl" shadow="sm" className="p-10 text-center bg-white border border-surfaceContainerHigh space-y-4">
              <div className="w-14 h-14 rounded-2xl bg-surfaceContainer text-textSecondary mx-auto flex items-center justify-center">
                <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5" />
                </svg>
              </div>
              <h3 className="font-heading font-bold text-lg text-textPrimary">No {activeTab !== 'All' ? activeTab.toLowerCase() : ''} appointments found</h3>
              <p className="text-xs text-textSecondary">No appointments match the selected filter.</p>
              <Button size="sm" variant="secondary" onClick={() => setActiveTab('All')}>View All</Button>
            </Card>
          )}
        </div>
      )}
    </div>
  );

  /* ══════════════════════════════════════════════════════════════════
     ADMIN CARD — system-wide view: Doctor + Patient, urgency, no calendar
     ══════════════════════════════════════════════════════════════════ */
  function renderAdminCard(apt: DoctorAppointment) {
    const statusDisp = mapStatus(apt.status, apt.appointment_time);
    const isExpanded = expandedIds.has(apt.appointment_id);
    const dt = fmtDt(apt.appointment_time);
    const allergies = parseJsonList(apt.patient_allergies);
    const conditions = parseJsonList(apt.patient_medical_conditions);

    // Urgency badge — display only, derived from API urgency_level
    const urgencyNorm = (apt.urgency_level || '').toLowerCase();
    const urgencyBadge = ({
      critical: 'error' as const,
      high: 'pending' as const,
      normal: 'primary' as const,
      low: 'neutral' as const,
    } as Record<string, 'error' | 'pending' | 'primary' | 'neutral'>)[urgencyNorm] || 'neutral';
    const urgencyLabel = ({
      critical: 'Critical', high: 'High', normal: 'Normal', low: 'Low',
    } as Record<string, string>)[urgencyNorm] || 'Not assessed';

    // Display-only dictionary: translates backend reason codes to friendly text.
    // NEVER infers or determines the reason — only displays what the API provides.
    const REASON_DISPLAY: Record<string, string> = {
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
    const reasonDisplay = apt.urgency_reason
      ? REASON_DISPLAY[apt.urgency_reason] || apt.urgency_reason.replace(/_/g, ' ')
      : null;

    // Status-based left border color (light, soft tones)
    const statusNorm = (apt.status || '').toLowerCase();
    const borderColor = statusNorm === 'scheduled' ? 'border-l-violet-300'
      : statusNorm === 'completed' ? 'border-l-emerald-300'
      : statusNorm === 'no_show' ? 'border-l-red-300'
      : statusNorm === 'cancelled' ? 'border-l-gray-300'
      : urgencyNorm === 'critical' ? 'border-l-amber-300'
      : 'border-l-violet-200';

    return (
      <Card key={apt.appointment_id} radius="2xl" shadow="sm"
        className={`p-0 bg-white border border-surfaceContainerHigh border-l-4 ${borderColor} hover:border-primaryContainer/30 hover:shadow-md hover:bg-gradient-to-br hover:from-violet-50/30 hover:to-transparent transition-all duration-200 overflow-hidden`}>

        {/* ── Compact top metadata row ──────────────────────────── */}
        <div className="px-5 pt-4 pb-2.5 flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge status={badgeStatus(statusDisp)} size="sm" withDot>{statusDisp}</Badge>
            <Badge status={urgencyBadge} size="sm" withDot>{urgencyLabel}</Badge>
            {apt.appointment_type && (
              <span className="bg-surfaceContainer/80 border border-surfaceContainerHigh px-2 py-0.5 rounded-pill text-[10px] font-semibold uppercase text-textSecondary">
                {apt.appointment_type.replace('_', ' ')}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {apt.feedback_submitted && apt.feedback_score && (
              <span className="text-amber-500 text-xs"><Stars score={apt.feedback_score} /></span>
            )}
            <button onClick={() => toggleExpand(apt.appointment_id)} className="p-1.5 rounded-lg hover:bg-surfaceContainer transition-colors" aria-label="Toggle details">
              <ChevronIcon open={isExpanded} />
            </button>
          </div>
        </div>

        {/* ── Doctor → Patient profile section ──────────────────── */}
        <div className="px-5 pb-4">
          <div className="flex flex-wrap items-center gap-2.5">
            {/* Doctor pill */}
            <div className="flex items-center gap-2 bg-teal-50/80 border border-teal-200/60 rounded-xl px-3 py-2 shadow-sm">
              <div className="w-7 h-7 rounded-lg bg-teal-100 flex items-center justify-center shrink-0">
                <svg className="w-3.5 h-3.5 text-teal-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M4.26 10.147a60.438 60.438 0 0 0-.491 6.347A48.62 48.62 0 0 1 12 20.904a48.62 48.62 0 0 1 8.232-4.41 60.46 60.46 0 0 0-.491-6.347m-15.482 0a50.636 50.636 0 0 0-2.658-.813A59.906 59.906 0 0 1 12 3.493a59.903 59.903 0 0 1 10.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.717 50.717 0 0 1 12 13.489a50.702 50.702 0 0 1 7.74-3.342" /></svg>
              </div>
              <div className="flex flex-col">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-teal-600/80">Doctor</span>
                <span className="font-heading font-bold text-sm text-teal-900 leading-tight">{apt.doctor_name}</span>
              </div>
            </div>

            {/* Arrow connector */}
            <div className="flex items-center shrink-0">
              <div className="w-6 h-px bg-gray-800" />
              <svg className="w-4 h-4 text-gray-800 -ml-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" /></svg>
            </div>

            {/* Patient pill */}
            <div className="flex items-center gap-2 bg-violet-50/80 border border-violet-200/60 rounded-xl px-3 py-2 shadow-sm">
              <div className="w-7 h-7 rounded-lg bg-violet-100 flex items-center justify-center shrink-0">
                <svg className="w-3.5 h-3.5 text-violet-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" /></svg>
              </div>
              <div className="flex flex-col">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-violet-600/80">Patient</span>
                <span className="font-heading font-bold text-sm text-violet-900 leading-tight">{apt.patient_name}</span>
              </div>
            </div>

            {apt.doctor_specialization && (
              <span className="text-[10px] font-medium text-secondary bg-secondaryContainer/30 px-2 py-0.5 rounded-pill">{apt.doctor_specialization}</span>
            )}
          </div>
        </div>

        {/* ── Appointment details + Clinical info combined row ── */}
        <div className="border-t border-surfaceContainerHigh/60" />
        <div className="px-5 py-3 flex flex-wrap items-start gap-x-5 gap-y-3 text-xs">
          {/* Date/Time */}
          <span className="flex items-center gap-1.5 text-textSecondary">
            <svg className="w-3.5 h-3.5 text-primary shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5" /></svg>
            <span className="font-semibold text-textPrimary">{dt.date}</span>
            <span className="text-textSecondary">{dt.time}</span>
          </span>
          {/* Clinic */}
          <span className="flex items-center gap-1.5 text-textSecondary">
            <svg className="w-3.5 h-3.5 text-textSecondary shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" /><path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1 1 15 0Z" /></svg>
            <span className="truncate">{apt.clinic_name}</span>
          </span>
          {/* Symptoms - inline */}
          {apt.symptoms_reported && (
            <span className="flex items-start gap-1.5 text-textSecondary flex-1 min-w-[180px]">
              <span className="font-semibold text-textPrimary shrink-0">Symptoms:</span>
              <span className="leading-relaxed line-clamp-2">{apt.symptoms_reported}</span>
            </span>
          )}
        </div>

        {/* ── Triage row ─────────────────────────────────────── */}
        <div className="px-5 pb-3.5 flex items-center gap-1.5 text-xs">
          <svg className="w-3.5 h-3.5 shrink-0 text-textSecondary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" /></svg>
          {reasonDisplay ? (
            <span className="text-textSecondary" title={apt.urgency_reason || ''}>Triage: <span className="font-medium text-textPrimary">{reasonDisplay}</span></span>
          ) : (
            <span className="text-textSecondary italic">No triage data</span>
          )}
        </div>

        {/* ── Expanded: Full details ───────────────────────────── */}
        {isExpanded && (
          <div className="mt-4 pt-4 border-t border-surfaceContainerHigh animate-fadeIn space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              {/* Patient information */}
              <div className="p-3 bg-surfaceContainer/60 rounded-xl space-y-1.5">
                <h4 className="font-bold text-textPrimary uppercase text-[10px] tracking-wider">Patient Information</h4>
                <p className="text-textSecondary"><strong>Name:</strong> {apt.patient_name}</p>
                {apt.patient_gender && <p className="text-textSecondary"><strong>Gender:</strong> {apt.patient_gender === 'M' ? 'Male' : apt.patient_gender === 'F' ? 'Female' : apt.patient_gender}</p>}
                {apt.patient_age != null && <p className="text-textSecondary"><strong>Age:</strong> {apt.patient_age} years</p>}
                {apt.patient_dob && apt.patient_dob !== '1990-01-01' && <p className="text-textSecondary"><strong>DOB:</strong> {new Date(apt.patient_dob).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}</p>}
                {apt.patient_blood_type && <p className="text-textSecondary"><strong>Blood Type:</strong> <span className="font-semibold text-error">{apt.patient_blood_type}</span></p>}
                {apt.patient_email && <p className="text-textSecondary"><strong>Email:</strong> {apt.patient_email}</p>}
                {apt.patient_phone && <p className="text-textSecondary"><strong>Phone:</strong> {apt.patient_phone}</p>}
              </div>
              {/* Appointment + Doctor information */}
              <div className="p-3 bg-surfaceContainer/60 rounded-xl space-y-1.5">
                <h4 className="font-bold text-textPrimary uppercase text-[10px] tracking-wider">Appointment Details</h4>
                <p className="text-textSecondary"><strong>Doctor:</strong> {apt.doctor_name}</p>
                {apt.doctor_specialization && <p className="text-textSecondary"><strong>Specialization:</strong> {apt.doctor_specialization}</p>}
                <p className="text-textSecondary"><strong>Clinic:</strong> {apt.clinic_name}</p>
                {apt.clinic_address && <p className="text-textSecondary"><strong>Address:</strong> {apt.clinic_address}</p>}
                <p className="text-textSecondary"><strong>Type:</strong> {apt.appointment_type.replace('_', ' ')}</p>
                <p className="text-textSecondary"><strong>Urgency:</strong> {urgencyLabel}</p>
                {apt.urgency_reason && <p className="text-textSecondary"><strong>Reason:</strong> {reasonDisplay || apt.urgency_reason}</p>}
              </div>
            </div>

            {/* Medical history */}
            <div className="p-3 bg-surfaceContainer/60 rounded-xl space-y-1.5 text-xs">
              <h4 className="font-bold text-textPrimary uppercase text-[10px] tracking-wider">Medical History <span className="font-normal normal-case text-textSecondary">(patient-reported)</span></h4>
              {allergies.length > 0 ? (
                <div><strong className="text-textPrimary">Allergies:</strong><div className="flex flex-wrap gap-1 mt-1">{allergies.map((a, i) => <span key={i} className="bg-errorContainer/40 text-error text-[10px] px-2 py-0.5 rounded-pill">{a}</span>)}</div></div>
              ) : <p className="text-textSecondary italic">No allergies reported</p>}
              {conditions.length > 0 ? (
                <div className="pt-1"><strong className="text-textPrimary">Conditions:</strong><div className="flex flex-wrap gap-1 mt-1">{conditions.map((c, i) => <span key={i} className="bg-amber-100 text-amber-800 text-[10px] px-2 py-0.5 rounded-pill">{c}</span>)}</div></div>
              ) : <p className="text-textSecondary italic">No conditions reported</p>}
            </div>

            {/* Doctor notes */}
            {apt.doctor_notes && (
              <div className="p-3 bg-surfaceContainer/80 rounded-xl text-xs border border-surfaceContainerHigh">
                <span className="font-bold text-secondary uppercase text-[10px] tracking-wider block">Clinical Notes:</span>
                <p className="text-textPrimary italic mt-1">{apt.doctor_notes}</p>
              </div>
            )}

            {/* Patient review */}
            {apt.feedback_submitted && apt.feedback_score && (
              <div className="p-3 bg-surfaceContainer/40 rounded-xl space-y-2">
                <span className="text-xs font-bold text-textPrimary flex items-center gap-1.5">
                  <span>⭐</span> Patient Review
                </span>
                <div className="space-y-1">
                  <div className="flex items-center gap-1 text-amber-500 text-sm">
                    <Stars score={apt.feedback_score} size="md" />
                    <span className="text-xs text-textSecondary ml-2">({apt.feedback_score}/5)</span>
                  </div>
                  {apt.feedback_text && <p className="text-xs text-textSecondary italic">"{apt.feedback_text}"</p>}
                </div>
              </div>
            )}
          </div>
        )}
      </Card>
    );
  }

  /* ══════════════════════════════════════════════════════════════════
     DOCTOR CARD — shows patient details, expandable, reviews, calendar
     ══════════════════════════════════════════════════════════════════ */
  function renderDoctorCard(apt: DoctorAppointment) {
    const statusDisp = mapStatus(apt.status, apt.appointment_time);
    const isExpanded = expandedIds.has(apt.appointment_id);
    const dt = fmtDt(apt.appointment_time);
    const allergies = parseJsonList(apt.patient_allergies);
    const conditions = parseJsonList(apt.patient_medical_conditions);

    const calTitle = `Appointment with ${apt.patient_name}`;
    const calDetails = `Patient: ${apt.patient_name}\nSymptoms: ${apt.symptoms_reported}\nUrgency: ${apt.urgency_level}`;
    const calLocation = apt.clinic_address ? `${apt.clinic_name} — ${apt.clinic_address}` : apt.clinic_name;
    const calLink = googleCalUrl(calTitle, apt.appointment_time, apt.end_time || apt.appointment_time, calDetails, calLocation);

    return (
      <Card key={apt.appointment_id} radius="2xl" shadow="sm"
        className="p-5 sm:p-6 bg-white border border-surfaceContainerHigh hover:border-primaryContainer/30 transition-all duration-200">
        {/* ── Main row ─────────────────────────────────────────── */}
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
          {/* Left: Patient info */}
          <div className="flex items-start gap-4 flex-1 min-w-0">
            {/* Time block */}
            <div className="w-20 sm:w-24 text-center shrink-0 p-2.5 bg-surfaceContainer rounded-2xl border border-surfaceContainerHigh">
              <span className="block font-heading font-extrabold text-sm text-textPrimary">{fmtTime(apt.appointment_time).split(' ')[0]}</span>
              <span className="text-[10px] uppercase font-bold text-textSecondary">{fmtTime(apt.appointment_time).split(' ')[1] || ''}</span>
            </div>

            <div className="space-y-1.5 flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2.5">
                <h3 className="font-heading font-bold text-lg text-textPrimary">{apt.patient_name}</h3>
                <span className="text-xs text-textSecondary">
                  <code className="text-[10px] font-mono text-primary bg-surfaceContainer px-1.5 py-0.5 rounded">{`PT-${apt.patient_id.slice(0, 6)}`}</code>
                </span>
                <Badge status={badgeStatus(statusDisp)} size="sm" withDot>{statusDisp}</Badge>
                {apt.urgency_level && (
                  <Badge status={apt.urgency_level === 'critical' ? 'error' : apt.urgency_level === 'high' ? 'pending' : 'neutral'} size="sm">
                    {apt.urgency_level}
                  </Badge>
                )}
              </div>

              {apt.symptoms_reported && (
                <p className="text-xs text-textSecondary"><strong className="text-textPrimary">Symptoms:</strong> {apt.symptoms_reported}</p>
              )}

              {/* Feedback preview (if submitted) */}
              {apt.feedback_submitted && apt.feedback_score && (
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-amber-500"><Stars score={apt.feedback_score} /></span>
                  <span className="text-textSecondary font-medium">Patient Review</span>
                </div>
              )}

              <div className="flex items-center gap-3 pt-1 text-xs text-textSecondary">
                <span className="flex items-center gap-1.5">
                  <svg className="w-3.5 h-3.5 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5" /></svg>
                  {dt.date} • {dt.time}
                </span>
                <span className="flex items-center gap-1.5">
                  <svg className="w-3.5 h-3.5 text-textSecondary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" /><path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1 1 15 0Z" /></svg>
                  {apt.clinic_name}
                </span>
              </div>
            </div>
          </div>

          {/* Right: Actions */}
          <div className="flex items-center gap-2 shrink-0">
            <a href={calLink} target="_blank" rel="noopener noreferrer">
              <Button variant="outline" size="sm" className="flex items-center gap-1.5">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5" /></svg>
                Calendar
              </Button>
            </a>
            <button onClick={() => toggleExpand(apt.appointment_id)} className="p-2 rounded-xl hover:bg-surfaceContainer transition-colors" aria-label="Toggle details">
              <ChevronIcon open={isExpanded} />
            </button>
          </div>
        </div>

        {/* ── Expanded: Patient details + Review ───────────────── */}
        {isExpanded && (
          <div className="mt-4 pt-4 border-t border-surfaceContainerHigh animate-fadeIn space-y-4">
            {/* Patient medical details */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div className="p-3 bg-surfaceContainer/60 rounded-xl space-y-1.5">
                <h4 className="font-bold text-textPrimary uppercase text-[10px] tracking-wider">Patient Information</h4>
                {apt.patient_gender && <p className="text-textSecondary"><strong>Gender:</strong> {apt.patient_gender === 'M' ? 'Male' : apt.patient_gender === 'F' ? 'Female' : apt.patient_gender}</p>}
                {apt.patient_age != null && <p className="text-textSecondary"><strong>Age:</strong> {apt.patient_age} years</p>}
                {apt.patient_dob && apt.patient_dob !== '1990-01-01' && <p className="text-textSecondary"><strong>DOB:</strong> {new Date(apt.patient_dob).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}</p>}
                {apt.patient_blood_type && <p className="text-textSecondary"><strong>Blood Type:</strong> <span className="font-semibold text-error">{apt.patient_blood_type}</span></p>}
                {apt.patient_email && <p className="text-textSecondary"><strong>Email:</strong> {apt.patient_email}</p>}
                {apt.patient_phone && <p className="text-textSecondary"><strong>Phone:</strong> {apt.patient_phone}</p>}
              </div>
              <div className="p-3 bg-surfaceContainer/60 rounded-xl space-y-1.5">
                <h4 className="font-bold text-textPrimary uppercase text-[10px] tracking-wider">Medical History <span className="font-normal normal-case text-textSecondary">(patient-reported)</span></h4>
                {allergies.length > 0 ? (
                  <div><strong className="text-textPrimary">Allergies:</strong><div className="flex flex-wrap gap-1 mt-1">{allergies.map((a, i) => <span key={i} className="bg-errorContainer/40 text-error text-[10px] px-2 py-0.5 rounded-pill">{a}</span>)}</div></div>
                ) : <p className="text-textSecondary italic">No allergies reported</p>}
                {conditions.length > 0 ? (
                  <div className="pt-1"><strong className="text-textPrimary">Conditions:</strong><div className="flex flex-wrap gap-1 mt-1">{conditions.map((c, i) => <span key={i} className="bg-amber-100 text-amber-800 text-[10px] px-2 py-0.5 rounded-pill">{c}</span>)}</div></div>
                ) : <p className="text-textSecondary italic">No conditions reported</p>}
              </div>
            </div>

            {/* Doctor notes (if any) */}
            {apt.doctor_notes && (
              <div className="p-3 bg-surfaceContainer/80 rounded-xl text-xs border border-surfaceContainerHigh">
                <span className="font-bold text-secondary uppercase text-[10px] tracking-wider block">Clinical Notes:</span>
                <p className="text-textPrimary italic mt-1">{apt.doctor_notes}</p>
              </div>
            )}

            {/* Review section */}
            <div className="p-3 bg-surfaceContainer/40 rounded-xl space-y-2">
              <span className="text-xs font-bold text-textPrimary flex items-center gap-1.5">
                <span>⭐</span> Patient Review
              </span>
              {apt.feedback_submitted && apt.feedback_score ? (
                <div className="space-y-1">
                  <div className="flex items-center gap-1 text-amber-500 text-sm">
                    <Stars score={apt.feedback_score} size="md" />
                    <span className="text-xs text-textSecondary ml-2">({apt.feedback_score}/5)</span>
                  </div>
                  {apt.feedback_text && <p className="text-xs text-textSecondary italic">"{apt.feedback_text}"</p>}
                </div>
              ) : (
                <p className="text-xs text-textSecondary">No review submitted yet for this appointment.</p>
              )}
            </div>
          </div>
        )}
      </Card>
    );
  }

  /* ══════════════════════════════════════════════════════════════════
     PATIENT CARD — shows doctor details, expandable, reviews, calendar
     ══════════════════════════════════════════════════════════════════ */
  function renderPatientCard(apt: PatientAppointment) {
    const statusDisp = mapStatus(apt.status, apt.appointment_time);
    const isCompleted = statusDisp === 'Completed';
    const isUpcoming = statusDisp === 'Upcoming';
    const isExpanded = expandedIds.has(apt.appointment_id);
    const dt = fmtDt(apt.appointment_time);
    const isFeedbackSubmitted = Boolean(apt.feedback_submitted || apt.feedback_score);
    const currentRating = ratingInputs[apt.appointment_id] || { rating: apt.feedback_score || 0, feedback: apt.feedback_text || '' };

    const calTitle = `Appointment with ${apt.doctor_name}`;
    const calDetails = `Doctor: ${apt.doctor_name}${apt.doctor_specialization ? ` (${apt.doctor_specialization})` : ''}\nSymptoms: ${apt.symptoms}\nClinic: ${apt.clinic_name}`;
    const calLocation = apt.clinic_address ? `${apt.clinic_name} — ${apt.clinic_address}` : apt.clinic_name;
    const calLink = googleCalUrl(calTitle, apt.appointment_time, apt.end_time || apt.appointment_time, calDetails, calLocation);

    return (
      <Card key={apt.appointment_id} radius="2xl" shadow="sm"
        className="p-5 sm:p-6 bg-white border border-surfaceContainerHigh hover:border-primaryContainer/30 transition-all duration-200">
        {/* ── Main row ─────────────────────────────────────────── */}
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
          {/* Left: Doctor info */}
          <div className="flex items-start gap-4 flex-1 min-w-0">
            <div className="w-13 h-13 rounded-2xl bg-surfaceContainer text-primary border border-surfaceContainerHigh flex items-center justify-center font-bold text-base shrink-0 mt-0.5">
              {apt.doctor_name.split(' ').slice(1).map(n => n[0]).join('').toUpperCase().slice(0, 2) || 'Dr'}
            </div>

            <div className="space-y-1.5 flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2.5">
                <h3 className="font-heading font-bold text-lg text-textPrimary">{apt.doctor_name}</h3>
                <Badge status={badgeStatus(statusDisp)} size="sm" withDot>{statusDisp}</Badge>
              </div>
              {apt.doctor_specialization && (
                <p className="text-xs font-semibold text-secondary">{apt.doctor_specialization}</p>
              )}

              <div className="flex items-center gap-3 pt-1 text-xs text-textSecondary">
                <span className="flex items-center gap-1.5">
                  <svg className="w-4 h-4 text-primary shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5" /></svg>
                  <span className="font-semibold text-textPrimary">{dt.date} • {dt.time}</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <svg className="w-4 h-4 text-textSecondary shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" /><path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1 1 15 0Z" /></svg>
                  <span className="truncate">{apt.clinic_name}</span>
                </span>
              </div>

              {apt.doctor_notes && (
                <div className="mt-2 p-2.5 bg-surfaceContainer rounded-xl text-xs text-textSecondary border border-surfaceContainerHigh">
                  <strong className="text-textPrimary">Doctor Notes:</strong> {apt.doctor_notes}
                </div>
              )}
            </div>
          </div>

          {/* Right: Actions */}
          <div className="flex items-center gap-2 shrink-0">
            {isUpcoming && (
              <>
                <Link to="/chat">
                  <Button size="sm" variant="secondary">Reschedule</Button>
                </Link>
                <button type="button" onClick={() => handleCancel(apt.appointment_id)}
                  className="text-xs font-semibold text-error hover:underline px-3 py-1.5 rounded-pill hover:bg-errorContainer/30 transition-colors">
                  Cancel
                </button>
              </>
            )}
            <a href={calLink} target="_blank" rel="noopener noreferrer">
              <Button variant="outline" size="sm" className="flex items-center gap-1.5">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5" /></svg>
                Calendar
              </Button>
            </a>
            <button onClick={() => toggleExpand(apt.appointment_id)} className="p-2 rounded-xl hover:bg-surfaceContainer transition-colors" aria-label="Toggle details">
              <ChevronIcon open={isExpanded} />
            </button>
          </div>
        </div>

        {/* ── Expanded: Doctor details + Review ────────────────── */}
        {isExpanded && (
          <div className="mt-4 pt-4 border-t border-surfaceContainerHigh animate-fadeIn space-y-4">
            {/* Doctor details */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div className="p-3 bg-surfaceContainer/60 rounded-xl space-y-1.5">
                <h4 className="font-bold text-textPrimary uppercase text-[10px] tracking-wider">Doctor Information</h4>
                <p className="text-textSecondary"><strong>Name:</strong> {apt.doctor_name}</p>
                {apt.doctor_specialization && <p className="text-textSecondary"><strong>Specialization:</strong> {apt.doctor_specialization}</p>}
                <p className="text-textSecondary"><strong>Clinic:</strong> {apt.clinic_name}</p>
                {apt.clinic_address && <p className="text-textSecondary"><strong>Address:</strong> {apt.clinic_address}</p>}
              </div>
              <div className="p-3 bg-surfaceContainer/60 rounded-xl space-y-1.5">
                <h4 className="font-bold text-textPrimary uppercase text-[10px] tracking-wider">Appointment Details</h4>
                <p className="text-textSecondary"><strong>Date:</strong> {dt.date}</p>
                <p className="text-textSecondary"><strong>Time:</strong> {dt.time}{apt.end_time ? ` — ${fmtTime(apt.end_time)}` : ''}</p>
                <p className="text-textSecondary"><strong>Status:</strong> <Badge status={badgeStatus(statusDisp)} size="sm">{statusDisp}</Badge></p>
                {apt.symptoms && <p className="text-textSecondary"><strong>Symptoms:</strong> {apt.symptoms}</p>}
                {apt.urgency && <p className="text-textSecondary"><strong>Urgency:</strong> {apt.urgency}</p>}
              </div>
            </div>

            {/* Doctor notes */}
            {apt.doctor_notes && (
              <div className="p-3 bg-surfaceContainer/80 rounded-xl text-xs border border-surfaceContainerHigh">
                <span className="font-bold text-secondary uppercase text-[10px] tracking-wider block">Clinical Notes:</span>
                <p className="text-textPrimary italic mt-1">{apt.doctor_notes}</p>
              </div>
            )}
          </div>
        )}

        {/* ── Review section (completed appointments only) ─────── */}
        {isCompleted && (
          <div className="mt-4 pt-4 border-t border-surfaceContainerHigh bg-surfaceContainer/40 -mx-5 sm:-mx-6 -mb-5 sm:-mb-6 p-5 rounded-b-2xl">
            <div className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs font-bold text-textPrimary flex items-center gap-1.5">
                  <span>⭐</span>
                  {isFeedbackSubmitted ? 'Your Consultation Review:' : `Rate your visit with ${apt.doctor_name}:`}
                </span>
                {isFeedbackSubmitted && <Badge status="success" size="sm">Review Verified</Badge>}
              </div>

              {isFeedbackSubmitted ? (
                <div className="space-y-1">
                  <div className="flex items-center gap-1 text-amber-500 text-sm">
                    <Stars score={apt.feedback_score || currentRating.rating || 5} size="md" />
                    <span className="text-xs text-textSecondary ml-2">({apt.feedback_score || currentRating.rating || 5}/5 Stars)</span>
                  </div>
                  {(apt.feedback_text || currentRating.feedback) && (
                    <p className="text-xs text-textSecondary italic">"{apt.feedback_text || currentRating.feedback}"</p>
                  )}
                </div>
              ) : (
                <div className="space-y-3">
                  {/* Clickable stars */}
                  <div className="flex items-center gap-1.5">
                    {[1, 2, 3, 4, 5].map((star) => (
                      <button key={star} type="button" onClick={() => handleRatingChange(apt.appointment_id, star)}
                        className={`text-xl transition-transform hover:scale-125 focus:outline-none ${star <= currentRating.rating ? 'text-amber-500' : 'text-outline hover:text-amber-400'}`}
                        aria-label={`Rate ${star} star`}>
                        ★
                      </button>
                    ))}
                    <span className="text-xs font-semibold text-textSecondary ml-2">
                      {currentRating.rating > 0 ? `${currentRating.rating} of 5 stars` : 'Select stars'}
                    </span>
                  </div>
                  {/* Comment + Submit */}
                  <div className="flex flex-col sm:flex-row gap-2">
                    <input type="text" value={currentRating.feedback} onChange={(e) => handleFeedbackText(apt.appointment_id, e.target.value)}
                      placeholder="Write a brief comment (optional)..."
                      className="flex-1 text-xs bg-white rounded-xl border border-outline/40 px-3 py-2 outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary" />
                    <Button size="sm" variant="secondary" onClick={() => handleSubmitFeedback(apt.appointment_id)}>
                      Submit Review
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </Card>
    );
  }
};
