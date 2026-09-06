import React, { useState, useEffect } from 'react';
import { Navigate } from 'react-router-dom';
import { Card, Button, Badge } from '../components/ui';
import { useAuth } from '../context/AuthContext';
import { listAppointments, completeAppointment, markNoShow } from '../services/appointments';
import { useLanguage } from '../i18n/LanguageContext';
import { translateUrgency, translateStatus, translateReason, translateDate, translateTime } from '../i18n/translations';
import { getDashboardMetrics } from '../services/analytics';

type UrgencyLevel = 'low' | 'normal' | 'high' | 'critical';

interface BackendDoctorAppointment {
  appointment_id: string;
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
  const { t, lang } = useLanguage();
  const [schedule, setSchedule] = useState<BackendDoctorAppointment[]>([]);
  const [dashboard, setDashboard] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [activeNotesId, setActiveNotesId] = useState<string | null>(null);
  const [notesText, setNotesText] = useState<string>('');
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

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
      // Also fetch dashboard metrics for completed count and other stats
      const dashRes = await getDashboardMetrics();
      setDashboard(dashRes);
      setSchedule(appts);
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
  // Use dashboard metrics for completed and no-show counts
  const completedCount = dashboard?.completed_today ?? 0;
  const noShowCount = dashboard?.no_show_today ?? 0;
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

  const toggleExpand = (id: string) =>
    setExpandedIds((prev) => {
      const n = new Set(prev);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });

  const parseJsonList = (v?: string | null): string[] => {
    if (!v) return [];
    try { const a = JSON.parse(v); return Array.isArray(a) ? a : [v]; } catch { return [v]; }
  };

  // Urgency badge styling
  const getUrgencyBadge = (urgency?: string) => {
    const norm = (urgency || 'normal').toLowerCase();
    switch (norm) {
      case 'critical':
        return (
          <span className="inline-flex items-center gap-1 bg-errorContainer text-error border border-error/30 text-[10px] font-extrabold uppercase px-2.5 py-0.5 rounded-pill animate-pulse">
            🚨 {translateUrgency('critical', lang)}
          </span>
        );
      case 'high':
        return (
          <span className="inline-flex items-center gap-1 bg-amber-100 text-amber-800 border border-amber-300 text-[10px] font-bold uppercase px-2.5 py-0.5 rounded-pill">
            ⚠️ {translateUrgency('high', lang)}
          </span>
        );
      case 'low':
        return (
          <Badge status="neutral" size="sm">
            {translateUrgency('low', lang)}
          </Badge>
        );
      default:
        return (
          <Badge status="pending" size="sm">
            {translateUrgency('normal', lang)}
          </Badge>
        );
    }
  };

  const getStatusBadge = (statusStr: string) => {
    const s = statusStr.toLowerCase();
    if (s === 'completed') {
      return (
        <Badge status="success" size="sm" withDot>
          {translateStatus('completed', lang)}
        </Badge>
      );
    }
    if (s === 'no_show' || s === 'no-show') {
      return (
        <Badge status="error" size="sm">
          {translateStatus('no_show', lang)}
        </Badge>
      );
    }
    if (s === 'cancelled') {
      return (
        <Badge status="neutral" size="sm">
          {translateStatus('cancelled', lang)}
        </Badge>
      );
    }
    return (
      <Badge status="pending" size="sm">
        {translateStatus('scheduled', lang)}
      </Badge>
    );
  };

  const handleStartComplete = (apt: BackendDoctorAppointment) => {
    setActiveNotesId(apt.appointment_id);
    setNotesText(apt.doctor_notes || '');
  };

  const handleSaveNotesAndFinalize = async (id: string) => {
    if (!notesText.trim()) {
      alert(t('doctor.completeNotesRequired'));
      return;
    }

    try {
      await completeAppointment(id, { notes: notesText.trim() });
      setActiveNotesId(null);
      setNotesText('');
      showToast(t('doctor.completeSuccess'));
      // Refresh both schedule and dashboard metrics
      fetchSchedule();
    } catch (err: any) {
      alert(err?.response?.data?.detail?.message || t('admin.saveChanges'));
    }
  };

  const handleMarkNoShowAction = async (id: string) => {
    if (window.confirm(t('doctor.noShowConfirm'))) {
      try {
        await markNoShow(id);
        showToast(t('doctor.noShowSuccess'));
        // Refresh both schedule and dashboard metrics
        fetchSchedule();
      } catch (err: any) {
        alert(err?.response?.data?.detail?.message || t('doctor.markNoShow'));
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
            {t('common.dismiss')}
          </button>
        </div>
      )}

      {/* 1. Header with Doctor info & Today's Schedule */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-surfaceContainerHigh">
        <div>
          <div className="inline-flex items-center gap-2 mb-2">
            <Badge status="primary" size="sm" withDot>
              {t('doctor.portal')}
            </Badge>
            <span className="text-xs text-secondary font-semibold">{t('doctor.specialist')}</span>
          </div>
          <h1 className="font-heading font-extrabold text-3xl sm:text-4xl text-textPrimary tracking-tight">
            {t('doctor.upcomingSchedule')}
          </h1>
          <p className="text-sm sm:text-base text-textSecondary mt-3 flex items-center gap-2">
            <span>📅 {translateDate(new Date().toISOString(), lang, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}</span>
            <span>•</span>
            <span>{t('doctor.attending')} <strong>{doctorName}</strong></span>
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Badge status="success" size="md">
            {t('doctor.clinicOpen')}
          </Badge>
        </div>
      </div>

      {/* 2. Stats Row (4 Stat Cards) */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
        <Card radius="2xl" shadow="sm" className="p-5 bg-white border border-surfaceContainerHigh">
          <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-textSecondary">
            <span>{t('doctor.totalUpcoming')}</span>
            <span>📋</span>
          </div>
          <div className="mt-3">
            <span className="font-heading font-extrabold text-3xl text-textPrimary">{totalUpcoming}</span>
            <p className="text-[11px] text-textSecondary mt-0.5">{t('doctor.patientsBooked')}</p>
          </div>
        </Card>

        <Card radius="2xl" shadow="sm" className="p-5 bg-white border border-surfaceContainerHigh">
          <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-textSecondary">
            <span>{t('doctor.completed')}</span>
            <span>✅</span>
          </div>
          <div className="mt-3">
            <span className="font-heading font-extrabold text-3xl text-secondary">{completedCount}</span>
            <p className="text-[11px] text-textSecondary mt-0.5">{t('doctor.visitsDocumented')}</p>
          </div>
        </Card>

        <Card radius="2xl" shadow="sm" className="p-5 bg-white border border-surfaceContainerHigh">
          <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-textSecondary">
            <span>{t('doctor.today')}</span>
            <span>📌</span>
          </div>
          <div className="mt-3">
            <span className="font-heading font-extrabold text-3xl text-primary">{todayCount}</span>
            <p className="text-[11px] text-textSecondary mt-0.5">{t('doctor.todaysAppts')}</p>
          </div>
        </Card>

        <Card radius="2xl" shadow="sm" className="p-5 bg-white border border-surfaceContainerHigh">
          <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-textSecondary">
            <span>{t('doctor.utilization')}</span>
            <span>📊</span>
          </div>
          <div className="mt-3">
            <span className="font-heading font-extrabold text-3xl text-textPrimary">{utilizationPct}%</span>
            <p className="text-[11px] text-textSecondary mt-0.5">{t('doctor.shiftCompletion')}</p>
          </div>
        </Card>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="p-4 bg-errorContainer/30 border border-error/30 rounded-2xl flex items-center justify-between text-xs text-error">
          <p className="font-medium">⚠️ {error}</p>
          <Button size="sm" variant="ghost" onClick={fetchSchedule}>
            {t('doctor.retry')}
          </Button>
        </div>
      )}

      {/* 3. Appointment List (Rows/Cards) */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-heading font-bold text-xl text-textPrimary tracking-tight">
            {t('doctor.patientQueue')}
          </h2>
          <span className="text-xs font-mono text-textSecondary bg-surfaceContainer px-3 py-1 rounded-pill">
            {t('doctor.liveList')}
          </span>
        </div>

        {loading ? (
          <Card radius="2xl" shadow="sm" className="p-12 text-center bg-white border border-surfaceContainerHigh">
            <div className="w-8 h-8 border-3 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-xs text-textSecondary font-medium">{t('doctor.fetching')}</p>
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
              // Determine if the appointment time has already passed
              const isPast = new Date(apt.appointment_time) <= new Date();

              const formattedTime = formatTime(apt.appointment_time);

              return (
                <Card
                  key={apt.appointment_id}
                  radius="2xl"
                  shadow="sm"
                  className={`p-5 sm:p-6 bg-white border transition-all duration-200 ${isCritical && isPending
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
                          const display = translateReason(apt.urgency_reason, lang);
                          return display
                            ? <span className="text-textSecondary">{t('appts.triage')} <span className="font-medium text-textPrimary">{display}</span></span>
                            : <span className="text-textSecondary italic">{t('appts.noTriageData')}</span>;
                        })()}
                      </span>
                    </div>

                    {/* Symptoms */}
                    {apt.symptoms_reported && (
                      <div className="text-xs text-textSecondary leading-relaxed">
                        <strong className="text-textPrimary">{t('appts.symptoms')}</strong> {apt.symptoms_reported}
                      </div>
                    )}

                    {/* Completed Notes View */}
                    {apt.doctor_notes && !isEditingNotes && (
                      <div className="mt-1 p-3 bg-surfaceContainer/80 rounded-xl text-xs border border-surfaceContainerHigh space-y-0.5">
                        <span className="font-bold text-secondary uppercase text-[10px] tracking-wider block">
                          {t('appts.clinicalNotes')}
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
                            {t('doctor.markComplete')}
                          </Button>
                          {isPending && isPast && (
                            <Button
                              variant="outline"
                              size="sm"
                              className="hover:border-error hover:text-error"
                              onClick={() => handleMarkNoShowAction(apt.appointment_id)}
                            >
                              {t('doctor.markNoShow')}
                            </Button>
                          )}
                        </div>
                      )}

                      {isCompleted && (
                        <div className="flex items-center gap-2 text-xs font-semibold text-secondary bg-secondaryContainer/30 px-3 py-1.5 rounded-pill border border-secondary/20">
                          <span>{t('appts.recordFinalized')}</span>
                        </div>
                      )}

                      {isNoShow && (
                        <div className="flex items-center gap-2 text-xs font-semibold text-error bg-errorContainer/40 px-3 py-1.5 rounded-pill border border-error/20">
                          <span>{t('appts.markedNoShow')}</span>
                        </div>
                      )}

                      <button
                        onClick={() => toggleExpand(apt.appointment_id)}
                        className="ml-auto p-1.5 rounded-lg hover:bg-surfaceContainer transition-colors text-textSecondary"
                        aria-label="Toggle patient details"
                      >
                        <svg className={`w-5 h-5 transition-transform duration-200 ${expandedIds.has(apt.appointment_id) ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                        </svg>
                      </button>
                    </div>
                  </div>

                  {/* Inline Notes Expansion when Mark Complete is clicked */}
                  {isEditingNotes && (
                    <div className="mt-4 pt-4 border-t border-surfaceContainerHigh bg-surfaceContainer/50 -mx-5 sm:-mx-6 -mb-5 sm:-mb-6 p-5 rounded-b-2xl animate-fadeIn space-y-3">
                      <label className="block text-xs font-bold text-textPrimary">
                        {t('doctor.addNotes', { name: apt.patient_name })}
                      </label>
                      <textarea
                        rows={3}
                        value={notesText}
                        onChange={(e) => setNotesText(e.target.value)}
                        placeholder={t('doctor.notesPlaceholder')}
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
                          {t('doctor.cancel')}
                        </Button>
                        <Button
                          size="sm"
                          variant="primary"
                          onClick={() => handleSaveNotesAndFinalize(apt.appointment_id)}
                        >
                          {t('doctor.saveFinalize')}
                        </Button>
                      </div>
                    </div>
                  )}

                  {/* Expanded: Patient medical details */}
                  {expandedIds.has(apt.appointment_id) && !isEditingNotes && (
                    <div className="mt-4 pt-4 border-t border-surfaceContainerHigh animate-fadeIn">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                        <div className="p-3 bg-surfaceContainer/60 rounded-xl space-y-1.5">
                          <h4 className="font-bold text-textPrimary uppercase text-[10px] tracking-wider">{t('doctor.patientInfo')}</h4>
                          {apt.patient_gender && <p className="text-textSecondary"><strong>{t('appts.gender')}</strong> {apt.patient_gender === 'M' ? t('appts.male') : apt.patient_gender === 'F' ? t('appts.female') : apt.patient_gender}</p>}
                          {apt.patient_age != null && <p className="text-textSecondary"><strong>{t('appts.age')}</strong> {apt.patient_age} {t('appts.years')}</p>}
                          {apt.patient_dob && apt.patient_dob !== '1990-01-01' && <p className="text-textSecondary"><strong>{t('appts.dob')}</strong> {translateDate(new Date(apt.patient_dob).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }), lang)}</p>}
                          {apt.patient_blood_type && <p className="text-textSecondary"><strong>{t('appts.bloodType')}</strong> <span className="font-semibold text-error">{apt.patient_blood_type}</span></p>}
                          {apt.patient_email && <p className="text-textSecondary"><strong>{t('appts.email')}</strong> {apt.patient_email}</p>}
                          {apt.patient_phone && <p className="text-textSecondary"><strong>{t('appts.phone')}</strong> {apt.patient_phone}</p>}
                        </div>
                        <div className="p-3 bg-surfaceContainer/60 rounded-xl space-y-1.5">
                          <h4 className="font-bold text-textPrimary uppercase text-[10px] tracking-wider">{t('doctor.medicalHistory')} <span className="font-normal normal-case text-textSecondary">{t('doctor.patientReported')}</span></h4>
                          {(() => {
                            const allergies = parseJsonList(apt.patient_allergies);
                            const conditions = parseJsonList(apt.patient_medical_conditions);
                            return (
                              <>
                                {allergies.length > 0 ? (
                                  <div><strong className="text-textPrimary">Allergies:</strong><div className="flex flex-wrap gap-1 mt-1">{allergies.map((a, i) => <span key={i} className="bg-errorContainer/40 text-error text-[10px] px-2 py-0.5 rounded-pill">{a}</span>)}</div></div>
                                ) : <p className="text-textSecondary italic">{t('appts.noAllergies')}</p>}
                                {conditions.length > 0 ? (
                                  <div className="pt-1"><strong className="text-textPrimary">{t('appts.conditions')}</strong><div className="flex flex-wrap gap-1 mt-1">{conditions.map((c, i) => <span key={i} className="bg-amber-100 text-amber-800 text-[10px] px-2 py-0.5 rounded-pill">{c}</span>)}</div></div>
                                ) : <p className="text-textSecondary italic">{t('appts.noConditions')}</p>}
                              </>
                            );
                          })()}
                        </div>
                      </div>
                    </div>
                  )}
                </Card>
              );
            })}
          </div>
        ) : (
          <Card radius="2xl" shadow="sm" className="p-10 text-center bg-white border border-surfaceContainerHigh space-y-2">
            <p className="font-heading font-bold text-base text-textPrimary">{t('doctor.noUpcoming')}</p>
            <p className="text-xs text-textSecondary">{t('doctor.queueClear')}</p>
          </Card>
        )}
      </section>
    </div>
  );
};
