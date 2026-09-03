import React from 'react';
import { Button, Badge } from '../ui';
import { type ParsedBookingSummary } from '../../services/chat';
import { generateGoogleCalendarUrl } from '../../lib/utils';

interface ConfirmationCardProps {
  booking: ParsedBookingSummary;
  onConfirm: () => void;
  onChange: () => void;
  isLoading: boolean;
  disabled: boolean;
}

export const ConfirmationCard: React.FC<ConfirmationCardProps> = ({ 
  booking, 
  onConfirm, 
  onChange, 
  isLoading, 
  disabled 
}) => {
  // Guard: if booking data is incomplete, show a safe fallback
  const doctor = booking?.doctor;
  if (!doctor?.name) {
    return (
      <div className="p-5 bg-white rounded-2xl border-2 border-error/20 shadow-soft-md animate-fadeIn">
        <p className="text-sm text-textPrimary">
          {booking?.isConfirmed
            ? 'Your appointment was booked but we could not load the details. Please check your appointments page.'
            : 'Something went wrong loading the booking details. Please try again.'}
        </p>
        {!booking?.isConfirmed && (
          <div className="pt-3">
            <Button variant="secondary" size="sm" onClick={onChange} disabled={disabled}>
              Start Over
            </Button>
          </div>
        )}
      </div>
    );
  }

  const doctorName = doctor.name.replace(/^Dr\.\s*/i, '');
  const displayDoctorName = `Dr. ${doctorName}`;
  const gcalUrl = generateGoogleCalendarUrl({
    title: `MediBook: ${displayDoctorName}`,
    startTime: booking.selectedSlot || undefined,
    description: `Doctor: ${displayDoctorName} (${doctor.specialization || 'Consultant'})\nClinic: ${doctor.clinic_name || 'Clinic'}\nAddress: ${doctor.clinic_address || 'Clinic address unavailable'}`,
    location: `${doctor.clinic_name || ''}, ${doctor.clinic_address || ''}`.trim().replace(/,\s*$/, ''),
  });

  return (
    <div className="p-5 bg-white rounded-2xl border-2 border-primary/20 shadow-soft-md space-y-4 animate-fadeIn">
      <div className="flex items-center justify-between border-b border-surfaceContainerHigh pb-3">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-primary" />
          <h4 className="font-heading font-bold text-sm text-textPrimary">
            {booking.isConfirmed ? 'Booking Confirmed' : 'Appointment Review'}
          </h4>
        </div>
        <Badge status={booking.isConfirmed ? 'success' : 'pending'} size="sm">
          {booking.isConfirmed ? 'Verified & Saved' : 'Pending Confirmation'}
        </Badge>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
        <div className="p-3 bg-surfaceContainer rounded-xl">
          <span className="text-[10px] text-textSecondary uppercase font-bold block mb-0.5">Doctor</span>
          <span className="font-bold text-textPrimary text-sm block">
            {doctor.name}
          </span>
          {doctor.specialization && (
            <span className="text-textSecondary text-[11px] block">{doctor.specialization}</span>
          )}
        </div>

        <div className="p-3 bg-surfaceContainer rounded-xl">
          <span className="text-[10px] text-textSecondary uppercase font-bold block mb-0.5">Date & Time</span>
          <span className="font-bold text-textPrimary text-sm block text-primary">
            {booking.selectedSlot}
          </span>
        </div>

        {(doctor.clinic_name || doctor.consultation_fee) && (
          <div className="p-3 bg-surfaceContainer rounded-xl sm:col-span-2 flex items-center justify-between">
            {doctor.clinic_name && (
              <div>
                <span className="text-[10px] text-textSecondary uppercase font-bold block mb-0.5">Location</span>
                <span className="font-semibold text-textPrimary text-xs block">
                  {doctor.clinic_name}
                </span>
                {doctor.clinic_address && (
                  <span className="text-textSecondary text-[11px] block mt-0.5 max-w-[200px] truncate">
                    {doctor.clinic_address}
                  </span>
                )}
              </div>
            )}
            {doctor.consultation_fee && (
              <div className="text-right">
                <span className="text-[10px] text-textSecondary uppercase font-bold block mb-0.5">Consultation Fee</span>
                <span className="font-bold text-primary text-sm">Rs. {doctor.consultation_fee}</span>
              </div>
            )}
          </div>
        )}
      </div>

      {!booking.isConfirmed ? (
        <div className="flex flex-col sm:flex-row items-center gap-3 pt-2">
          <Button
            variant="primary"
            size="md"
            className="w-full sm:flex-1 justify-center shadow-soft"
            isLoading={isLoading}
            disabled={disabled}
            onClick={onConfirm}
          >
            {isLoading ? 'Confirming...' : 'Confirm Booking'}
          </Button>
          <Button
            variant="secondary"
            size="md"
            className="w-full sm:w-auto"
            disabled={disabled || isLoading}
            onClick={onChange}
          >
            Change
          </Button>
        </div>
      ) : (
        <div className="pt-1">
          <a
            href={gcalUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="w-full flex items-center justify-center gap-2 py-2.5 px-4 bg-surfaceContainer hover:bg-surfaceContainerHigh border border-surfaceContainerHigh hover:border-primary/40 text-textPrimary font-semibold text-xs rounded-xl shadow-soft-sm transition-all duration-200"
          >
            <svg className="w-4 h-4 text-primary shrink-0" fill="currentColor" viewBox="0 0 24 24">
              <path d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.11 0-1.99.9-1.99 2L3 20c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V9h14v11zM7 11h5v5H7z" />
            </svg>
            <span>Add to Google Calendar</span>
          </a>
        </div>
      )}
    </div>
  );
};
