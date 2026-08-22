import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, Button, Badge } from '../components/ui';

type AppointmentStatus = 'Upcoming' | 'Completed' | 'Cancelled' | 'No-show';
type FilterTab = 'All' | AppointmentStatus;

interface AppointmentRecord {
  id: string;
  doctorName: string;
  doctorRole: string;
  specialization: string;
  clinicName: string;
  clinicAddress: string;
  date: string;
  time: string;
  type: 'In-Clinic Visit' | 'Telehealth Video';
  status: AppointmentStatus;
  fee: string;
  notes?: string;
  rating?: number;
  feedback?: string;
  feedbackSubmitted?: boolean;
}

const initialAppointments: AppointmentRecord[] = [
  {
    id: 'APT-1092',
    doctorName: 'Dr. Marcus Vance, MD',
    doctorRole: 'Senior Cardiologist',
    specialization: 'Cardiology & Vascular Medicine',
    clinicName: 'Metro Health Cardiology Clinic',
    clinicAddress: '450 Medical Center Blvd, Suite 300, New York, NY',
    date: 'Oct 24, 2026',
    time: '10:30 AM - 11:15 AM',
    type: 'In-Clinic Visit',
    status: 'Upcoming',
    fee: '$120',
  },
  {
    id: 'APT-1088',
    doctorName: 'Dr. Sarah Lin, MD',
    doctorRole: 'General Physician',
    specialization: 'Internal Medicine & Primary Care',
    clinicName: 'MediBook Central Care',
    clinicAddress: '120 Broadway Ave, Suite 400, New York, NY',
    date: 'Nov 02, 2026',
    time: '02:00 PM - 02:30 PM',
    type: 'Telehealth Video',
    status: 'Upcoming',
    fee: '$95',
  },
  {
    id: 'APT-1045',
    doctorName: 'Dr. Emily Thorne, MD',
    doctorRole: 'Clinical Neurologist',
    specialization: 'Neurology & Sleep Medicine',
    clinicName: 'Downtown Neurological Center',
    clinicAddress: '72 Fifth Ave, Suite 610, New York, NY',
    date: 'Sep 18, 2026',
    time: '11:00 AM - 11:45 AM',
    type: 'In-Clinic Visit',
    status: 'Completed',
    fee: '$150',
    notes: 'Prescribed migraine prophylaxis. Follow up in 3 months.',
    rating: 5,
    feedback: 'Dr. Thorne was very attentive and explained everything clearly.',
    feedbackSubmitted: true,
  },
  {
    id: 'APT-1021',
    doctorName: 'Dr. Robert Chen, MD',
    doctorRole: 'Dermatologist',
    specialization: 'Dermatology & Skin Surgery',
    clinicName: 'Midtown Dermatology Associates',
    clinicAddress: '310 Lexington Ave, Suite 120, New York, NY',
    date: 'Aug 04, 2026',
    time: '03:15 PM - 03:45 PM',
    type: 'In-Clinic Visit',
    status: 'Completed',
    fee: '$110',
    notes: 'Routine skin check. All clear.',
    rating: 0,
    feedback: '',
    feedbackSubmitted: false,
  },
  {
    id: 'APT-0982',
    doctorName: 'Dr. David Sterling, MD',
    doctorRole: 'Pulmonologist',
    specialization: 'Pulmonology & Respiratory Care',
    clinicName: 'Apex Respiratory Clinic',
    clinicAddress: '88 Park Plaza, Suite 210, New York, NY',
    date: 'Jun 12, 2026',
    time: '09:30 AM - 10:00 AM',
    type: 'Telehealth Video',
    status: 'Cancelled',
    fee: '$130',
  },
  {
    id: 'APT-0950',
    doctorName: 'Dr. Michael Chang, MD',
    doctorRole: 'Orthopedic Surgeon',
    specialization: 'Orthopedics & Joint Care',
    clinicName: 'Empire Orthopedic Group',
    clinicAddress: '150 East 42nd St, Suite 800, New York, NY',
    date: 'May 08, 2026',
    time: '01:00 PM - 01:30 PM',
    type: 'In-Clinic Visit',
    status: 'No-show',
    fee: '$140',
  },
];

export const Appointments: React.FC = () => {
  const [appointments, setAppointments] = useState<AppointmentRecord[]>(initialAppointments);
  const [activeTab, setActiveTab] = useState<FilterTab>('All');
  const [ratingInputs, setRatingInputs] = useState<Record<string, { rating: number; feedback: string }>>({});
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Status mapping to design tokens
  const getBadgeStatus = (status: AppointmentStatus) => {
    switch (status) {
      case 'Upcoming':
        return 'pending'; // blue
      case 'Completed':
        return 'success'; // teal
      case 'Cancelled':
        return 'neutral'; // grey
      case 'No-show':
        return 'error'; // red
    }
  };

  const handleCancel = (id: string) => {
    if (window.confirm('Are you sure you want to cancel this appointment?')) {
      setAppointments((prev) =>
        prev.map((apt) => (apt.id === id ? { ...apt, status: 'Cancelled' } : apt))
      );
      setToastMessage('Appointment has been cancelled.');
      setTimeout(() => setToastMessage(null), 3000);
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

  const handleSubmitFeedback = (id: string) => {
    const data = ratingInputs[id];
    if (!data || data.rating === 0) {
      alert('Please select a star rating (1 to 5 stars) before submitting.');
      return;
    }

    setAppointments((prev) =>
      prev.map((apt) =>
        apt.id === id
          ? {
              ...apt,
              rating: data.rating,
              feedback: data.feedback,
              feedbackSubmitted: true,
            }
          : apt
      )
    );

    setToastMessage('Thank you! Your feedback has been submitted ⭐');
    setTimeout(() => setToastMessage(null), 3000);
  };

  const filteredAppointments = appointments.filter((apt) => {
    if (activeTab === 'All') return true;
    return apt.status === activeTab;
  });

  const filterTabs: { key: FilterTab; label: string }[] = [
    { key: 'All', label: `All (${appointments.length})` },
    { key: 'Upcoming', label: `Upcoming (${appointments.filter((a) => a.status === 'Upcoming').length})` },
    { key: 'Completed', label: `Completed (${appointments.filter((a) => a.status === 'Completed').length})` },
    { key: 'Cancelled', label: `Cancelled (${appointments.filter((a) => a.status === 'Cancelled').length})` },
    { key: 'No-show', label: `No-show (${appointments.filter((a) => a.status === 'No-show').length})` },
  ];

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

      {/* 3. Appointment Cards List */}
      <div className="space-y-5">
        {filteredAppointments.length > 0 ? (
          filteredAppointments.map((apt) => {
            const isCompleted = apt.status === 'Completed';
            const isUpcoming = apt.status === 'Upcoming';
            const currentRatingState = ratingInputs[apt.id] || { rating: apt.rating || 0, feedback: apt.feedback || '' };

            return (
              <Card
                key={apt.id}
                radius="2xl"
                shadow="sm"
                className="p-6 sm:p-7 bg-white border border-surfaceContainerHigh hover:border-primaryContainer/30 transition-all duration-200"
              >
                <div className="flex flex-col md:flex-row md:items-start justify-between gap-5">
                  {/* Doctor & Clinic Info */}
                  <div className="flex items-start gap-4 flex-1">
                    <div className="w-13 h-13 rounded-2xl bg-surfaceContainer text-primary border border-surfaceContainerHigh flex items-center justify-center font-bold text-base shrink-0 mt-0.5">
                      {apt.doctorName.split(' ')[1]?.charAt(0) || 'Dr'}
                    </div>

                    <div className="space-y-1.5 flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2.5">
                        <h3 className="font-heading font-bold text-lg text-textPrimary">
                          {apt.doctorName}
                        </h3>
                        <Badge status={getBadgeStatus(apt.status)} size="sm" withDot>
                          {apt.status}
                        </Badge>
                        <Badge status="neutral" size="sm">
                          {apt.type}
                        </Badge>
                      </div>

                      <p className="text-xs font-semibold text-secondary">
                        {apt.specialization}
                      </p>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-y-1 gap-x-4 pt-2 text-xs text-textSecondary">
                        <div className="flex items-center gap-2">
                          <svg className="w-4 h-4 text-primary shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5" />
                          </svg>
                          <span className="font-semibold text-textPrimary">{apt.date} • {apt.time}</span>
                        </div>

                        <div className="flex items-center gap-2">
                          <svg className="w-4 h-4 text-textSecondary shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
                            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1 1 15 0Z" />
                          </svg>
                          <span className="truncate">{apt.clinicName}</span>
                        </div>
                      </div>

                      {apt.notes && (
                        <div className="mt-2.5 p-2.5 bg-surfaceContainer rounded-xl text-xs text-textSecondary border border-surfaceContainerHigh">
                          <strong className="text-textPrimary">Doctor Note:</strong> {apt.notes}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Actions for Scheduled Appointments */}
                  {isUpcoming && (
                    <div className="flex flex-row md:flex-col items-center md:items-end justify-between md:justify-start gap-2.5 pt-3 md:pt-0 border-t md:border-t-0 border-surfaceContainerHigh shrink-0">
                      <Link to="/chat">
                        <Button size="sm" variant="secondary">
                          Reschedule
                        </Button>
                      </Link>
                      <button
                        type="button"
                        onClick={() => handleCancel(apt.id)}
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
                          {apt.feedbackSubmitted ? 'Your Consultation Review:' : 'Rate your visit with ' + apt.doctorName + ':'}
                        </span>

                        {apt.feedbackSubmitted && (
                          <Badge status="success" size="sm">
                            Review Verified
                          </Badge>
                        )}
                      </div>

                      {apt.feedbackSubmitted ? (
                        <div className="space-y-1">
                          <div className="flex items-center gap-1 text-amber-500 text-sm">
                            {[1, 2, 3, 4, 5].map((star) => (
                              <span key={star}>
                                {star <= (apt.rating || 5) ? '★' : '☆'}
                              </span>
                            ))}
                            <span className="text-xs text-textSecondary ml-2">
                              ({apt.rating || 5}/5 Stars)
                            </span>
                          </div>
                          {apt.feedback && (
                            <p className="text-xs text-textSecondary italic">
                              "{apt.feedback}"
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
                                  onClick={() => handleRatingChange(apt.id, star)}
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
                              onChange={(e) => handleFeedbackTextChange(apt.id, e.target.value)}
                              placeholder="Write a brief comment (optional)..."
                              className="flex-1 text-xs bg-white rounded-xl border border-outline/40 px-3 py-2 outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
                            />
                            <Button
                              size="sm"
                              variant="secondary"
                              onClick={() => handleSubmitFeedback(apt.id)}
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
    </div>
  );
};
