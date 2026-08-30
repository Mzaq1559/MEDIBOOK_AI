import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Card, Button, Badge } from '../components/ui';
import { useAuth } from '../context/AuthContext';
import { getPatientAppointments, cancelAppointment, submitAppointmentFeedback } from '../services/appointments';
import { generateGoogleCalendarUrl } from '../lib/utils';

type AppointmentStatus = 'Upcoming' | 'Completed' | 'Cancelled' | 'No-show';
type FilterTab = 'All' | AppointmentStatus;

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
  symptoms_reported?: string;
  doctor_notes?: string;
  feedback_score?: number;
  feedback_text?: string;
  feedback_submitted?: boolean;
}

export const Appointments: React.FC = () => {
  const { currentUser } = useAuth();
  const [appointments, setAppointments] = useState<BackendAppointment[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<FilterTab>('All');
  const [ratingInputs, setRatingInputs] = useState<Record<string, { rating: number; feedback: string }>>({});
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const fetchAppointments = async () => {
    if (!currentUser?.id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getPatientAppointments(currentUser.id);
      setAppointments(Array.isArray(data) ? data : data.appointments || []);
    } catch (err: any) {
      console.error('Failed to load appointments history:', err);
      setError(err?.response?.data?.detail?.message || 'Failed to load your appointments history.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAppointments();
  }, [currentUser?.id]);

  const mapStatus = (statusStr: string): AppointmentStatus => {
    const s = statusStr.toLowerCase();
    if (s === 'completed') return 'Completed';
    if (s === 'cancelled') return 'Cancelled';
    if (s === 'no_show' || s === 'no-show') return 'No-show';
    return 'Upcoming';
  };

  const getBadgeStatus = (status: AppointmentStatus) => {
    switch (status) {
      case 'Upcoming':
        return 'pending';
      case 'Completed':
        return 'success';
      case 'Cancelled':
        return 'neutral';
      case 'No-show':
        return 'error';
    }
  };

  const handleCancel = async (id: string) => {
    if (window.confirm('Are you sure you want to cancel this appointment?')) {
      try {
        await cancelAppointment(id);
        setToastMessage('Appointment has been cancelled.');
        fetchAppointments();
        setTimeout(() => setToastMessage(null), 3000);
      } catch (err: any) {
        alert(err?.response?.data?.detail?.message || 'Failed to cancel appointment');
      }
    }
  };

  const handleRatingChange = (id: string, star: number) => {
    setRatingInputs((prev) => ({
      ...prev,
      [id]: {
        ...prev[id],
        rating: star,
        feedback: prev[id]?.feedback || '',
      },
    }));
  };

  const handleFeedbackTextChange = (id: string, text: string) => {
    setRatingInputs((prev) => ({
      ...prev,
      [id]: {
        rating: prev[id]?.rating || 0,
        feedback: text,
      },
    }));
  };

  const handleSubmitFeedback = async (id: string) => {
    const data = ratingInputs[id];
    if (!data || data.rating === 0) {
      alert('Please select a star rating (1 to 5 stars) before submitting.');
      return;
    }

    try {
      await submitAppointmentFeedback(id, {
        feedback_score: data.rating,
        feedback_text: data.feedback,
      });
      setToastMessage('Thank you! Your feedback has been submitted ⭐');
      fetchAppointments();
      setTimeout(() => setToastMessage(null), 3000);
    } catch (err: any) {
      alert(err?.response?.data?.detail?.message || 'Failed to submit feedback');
    }
  };

  const filteredAppointments = appointments.filter((apt) => {
    const mapped = mapStatus(apt.status);
    if (activeTab === 'All') return true;
    return mapped === activeTab;
  });

  const filterTabs: { key: FilterTab; label: string }[] = [
    { key: 'All', label: `All (${appointments.length})` },
    { key: 'Upcoming', label: `Upcoming (${appointments.filter((a) => mapStatus(a.status) === 'Upcoming').length})` },
    { key: 'Completed', label: `Completed (${appointments.filter((a) => mapStatus(a.status) === 'Completed').length})` },
    { key: 'Cancelled', label: `Cancelled (${appointments.filter((a) => mapStatus(a.status) === 'Cancelled').length})` },
    { key: 'No-show', label: `No-show (${appointments.filter((a) => mapStatus(a.status) === 'No-show').length})` },
  ];

  const formatDateTime = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return {
        date: d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }),
        time: d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
      };
    } catch {
      return { date: isoString, time: '' };
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-12 space-y-8">
      {/* Toast Notice */}
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

      {/* 1. Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-surfaceContainerHigh">
        <div>
          <div className="inline-flex items-center gap-2 mb-1.5">
            <Badge status="primary" size="sm">
              Care History
            </Badge>
          </div>
          <h1 className="font-heading font-extrabold text-3xl sm:text-4xl text-textPrimary tracking-tight">
            My Appointments
          </h1>
          <p className="text-sm sm:text-base text-textSecondary mt-1">
            View, reschedule, cancel, and review your past and upcoming clinical visits.
          </p>
        </div>

        <Link to="/chat" className="shrink-0">
          <Button variant="primary" size="md">
            + Book New Appointment
          </Button>
        </Link>
      </div>

      {/* 2. Filter Tabs / Pills Row */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-none">
        {filterTabs.map((tab) => {
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2 rounded-pill text-xs font-semibold whitespace-nowrap transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                isActive
                  ? 'bg-primary text-white shadow-soft-sm scale-[1.02]'
                  : 'bg-white text-textSecondary hover:text-textPrimary hover:bg-surfaceContainer border border-surfaceContainerHigh'
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Error Alert */}
      {error && (
        <div className="p-4 bg-errorContainer/30 border border-error/30 rounded-2xl flex items-center justify-between text-xs text-error">
          <p className="font-medium">⚠️ {error}</p>
          <Button size="sm" variant="ghost" onClick={fetchAppointments}>
            Retry
          </Button>
        </div>
      )}

      {/* 3. Appointment Cards List */}
      {loading ? (
        <Card radius="2xl" shadow="sm" className="p-12 text-center bg-white border border-surfaceContainerHigh">
          <div className="w-8 h-8 border-3 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-xs text-textSecondary font-medium">Fetching appointment history...</p>
        </Card>
      ) : (
        <div className="space-y-5">
          {filteredAppointments.length > 0 ? (
            filteredAppointments.map((apt) => {
              const statusDisplay = mapStatus(apt.status);
              const isCompleted = statusDisplay === 'Completed';
              const isUpcoming = statusDisplay === 'Upcoming';
              const currentRatingState = ratingInputs[apt.appointment_id] || {
                rating: apt.feedback_score || 0,
                feedback: apt.feedback_text || '',
              };
              const isFeedbackSubmitted = Boolean(apt.feedback_submitted || apt.feedback_score);
              const dt = formatDateTime(apt.appointment_time);

              return (
                <Card
                  key={apt.appointment_id}
                  radius="2xl"
                  shadow="sm"
                  className="p-6 sm:p-7 bg-white border border-surfaceContainerHigh hover:border-primaryContainer/30 transition-all duration-200"
                >
                  <div className="flex flex-col md:flex-row md:items-start justify-between gap-5">
                    {/* Doctor & Clinic Info */}
                    <div className="flex items-start gap-4 flex-1">
                      <div className="w-13 h-13 rounded-2xl bg-surfaceContainer text-primary border border-surfaceContainerHigh flex items-center justify-center font-bold text-base shrink-0 mt-0.5">
                        {apt.doctor_name.split(' ')[1]?.charAt(0) || 'Dr'}
                      </div>

                      <div className="space-y-1.5 flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2.5">
                          <h3 className="font-heading font-bold text-lg text-textPrimary">
                            {apt.doctor_name}
                          </h3>
                          <Badge status={getBadgeStatus(statusDisplay)} size="sm" withDot>
                            {statusDisplay}
                          </Badge>
                        </div>

                        <p className="text-xs font-semibold text-secondary">
                          {apt.doctor_specialization}
                        </p>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-y-1 gap-x-4 pt-2 text-xs text-textSecondary">
                          <div className="flex items-center gap-2">
                            <svg className="w-4 h-4 text-primary shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5" />
                            </svg>
                            <span className="font-semibold text-textPrimary">{dt.date} • {dt.time}</span>
                          </div>

                          <div className="flex items-center gap-2">
                            <svg className="w-4 h-4 text-textSecondary shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
                              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1 1 15 0Z" />
                            </svg>
                            <span className="truncate">{apt.clinic_name}</span>
                          </div>
                        </div>

                        {apt.doctor_notes && (
                          <div className="mt-2.5 p-2.5 bg-surfaceContainer rounded-xl text-xs text-textSecondary border border-surfaceContainerHigh">
                            <strong className="text-textPrimary">Doctor Note:</strong> {apt.doctor_notes}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Actions for Scheduled Appointments */}
                    {isUpcoming && (
                      <div className="flex flex-wrap md:flex-col items-center md:items-end justify-between md:justify-start gap-2.5 pt-3 md:pt-0 border-t md:border-t-0 border-surfaceContainerHigh shrink-0">
                        <a
                          href={generateGoogleCalendarUrl({
                            title: `MediBook: Dr. ${apt.doctor_name}`,
                            startTime: apt.appointment_time,
                            description: `Doctor: Dr. ${apt.doctor_name} (${apt.doctor_specialization})\nClinic: ${apt.clinic_name}\nAddress: ${apt.clinic_address}`,
                            location: `${apt.clinic_name}, ${apt.clinic_address}`,
                          })}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-surfaceContainer hover:bg-surfaceContainerHigh border border-surfaceContainerHigh text-primary text-xs font-semibold rounded-pill transition-all"
                        >
                          <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.11 0-1.99.9-1.99 2L3 20c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V9h14v11zM7 11h5v5H7z" />
                          </svg>
                          <span>Add to Calendar</span>
                        </a>
                        <Link to="/chat">
                          <Button size="sm" variant="secondary">
                            Reschedule
                          </Button>
                        </Link>
                        <button
                          type="button"
                          onClick={() => handleCancel(apt.appointment_id)}
                          className="text-xs font-semibold text-error hover:underline px-3 py-1.5 rounded-pill hover:bg-errorContainer/30 transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    )}
                  </div>

                  {/* 4. For Completed Appointments Only: Interactive Star Rating & Feedback */}
                  {isCompleted && (
                    <div className="mt-5 pt-4 border-t border-surfaceContainerHigh bg-surfaceContainer/40 -mx-6 sm:-mx-7 -mb-6 sm:-mb-7 p-5 rounded-b-2xl">
                      <div className="space-y-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="text-xs font-bold text-textPrimary flex items-center gap-1.5">
                            <span>⭐</span>
                            {isFeedbackSubmitted ? 'Your Consultation Review:' : 'Rate your visit with ' + apt.doctor_name + ':'}
                          </span>

                          {isFeedbackSubmitted && (
                            <Badge status="success" size="sm">
                              Review Verified
                            </Badge>
                          )}
                        </div>

                        {isFeedbackSubmitted ? (
                          <div className="space-y-1">
                            <div className="flex items-center gap-1 text-amber-500 text-sm">
                              {[1, 2, 3, 4, 5].map((star) => (
                                <span key={star}>
                                  {star <= (apt.feedback_score || currentRatingState.rating || 5) ? '★' : '☆'}
                                </span>
                              ))}
                              <span className="text-xs text-textSecondary ml-2">
                                ({apt.feedback_score || currentRatingState.rating || 5}/5 Stars)
                              </span>
                            </div>
                            {(apt.feedback_text || currentRatingState.feedback) && (
                              <p className="text-xs text-textSecondary italic">
                                "{apt.feedback_text || currentRatingState.feedback}"
                              </p>
                            )}
                          </div>
                        ) : (
                          <div className="space-y-3">
                            {/* 5 Clickable Stars */}
                            <div className="flex items-center gap-1.5">
                              {[1, 2, 3, 4, 5].map((star) => {
                                const isFilled = star <= currentRatingState.rating;
                                return (
                                  <button
                                    key={star}
                                    type="button"
                                    onClick={() => handleRatingChange(apt.appointment_id, star)}
                                    className={`text-xl transition-transform hover:scale-125 focus:outline-none ${
                                      isFilled ? 'text-amber-500' : 'text-outline hover:text-amber-400'
                                    }`}
                                    aria-label={`Rate ${star} star`}
                                  >
                                    ★
                                  </button>
                                );
                              })}
                              <span className="text-xs font-semibold text-textSecondary ml-2">
                                {currentRatingState.rating > 0
                                  ? `${currentRatingState.rating} of 5 stars`
                                  : 'Select stars'}
                              </span>
                            </div>

                            {/* Optional Comment Input */}
                            <div className="flex flex-col sm:flex-row gap-2">
                              <input
                                type="text"
                                value={currentRatingState.feedback}
                                onChange={(e) => handleFeedbackTextChange(apt.appointment_id, e.target.value)}
                                placeholder="Write a brief comment (optional)..."
                                className="flex-1 text-xs bg-white rounded-xl border border-outline/40 px-3 py-2 outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
                              />
                              <Button
                                size="sm"
                                variant="secondary"
                                onClick={() => handleSubmitFeedback(apt.appointment_id)}
                              >
                                Submit Feedback
                              </Button>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </Card>
              );
            })
          ) : (
            /* Empty State */
            <Card
              radius="2xl"
              shadow="sm"
              className="p-10 text-center bg-white border border-surfaceContainerHigh space-y-4"
            >
              <div className="w-14 h-14 rounded-2xl bg-surfaceContainer text-textSecondary mx-auto flex items-center justify-center">
                <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5" />
                </svg>
              </div>
              <div className="space-y-1">
                <h3 className="font-heading font-bold text-lg text-textPrimary">
                  No {activeTab !== 'All' ? activeTab.toLowerCase() : ''} appointments found
                </h3>
                <p className="text-xs text-textSecondary max-w-sm mx-auto">
                  {activeTab !== 'All'
                    ? `You have no appointments currently marked as "${activeTab}".`
                    : 'You have not booked any appointments yet.'}
                </p>
              </div>
              <div className="pt-2">
                <Button size="sm" variant="secondary" onClick={() => setActiveTab('All')}>
                  View All Appointments
                </Button>
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
};
