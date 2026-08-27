import React from 'react';
import { type ParsedAppointment } from '../../services/chat';
import { Badge } from '../ui';

interface AppointmentCardProps {
  appointment: ParsedAppointment;
  onSelect?: (id: string) => void;
  disabled?: boolean;
}

export const AppointmentCard: React.FC<AppointmentCardProps> = ({ appointment, onSelect, disabled }) => {
  // Format datetime
  let timeStr = appointment.appointment_time;
  try {
    const d = new Date(appointment.appointment_time);
    if (!isNaN(d.getTime())) {
      timeStr = d.toLocaleString(undefined, {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit'
      });
    }
  } catch (e) {}

  return (
    <button
      type="button"
      onClick={() => onSelect && onSelect(appointment.appointment_id)}
      disabled={disabled || !onSelect}
      className={`w-full text-left p-4 bg-white rounded-2xl border transition-all flex flex-col gap-2
        ${onSelect ? 'hover:border-primary/40 cursor-pointer shadow-soft-sm' : 'cursor-default shadow-sm'}
        ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
        border-surfaceContainerHigh
      `}
    >
      <div className="flex justify-between items-start w-full">
        <h4 className="font-bold text-sm text-textPrimary">
          {appointment.doctor_name}
        </h4>
        <Badge status={appointment.status === 'scheduled' ? 'success' : 'neutral'} size="sm">
          {appointment.status}
        </Badge>
      </div>
      
      {appointment.doctor_specialization && (
        <span className="text-[11px] text-textSecondary -mt-1 block">
          {appointment.doctor_specialization}
        </span>
      )}

      <div className="bg-surfaceContainer/50 rounded-xl p-2.5 mt-1 space-y-1">
        <div className="flex items-center gap-2 text-xs text-textPrimary font-semibold">
          <span>🕒</span>
          <span>{timeStr}</span>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-textSecondary">
          <span>📍</span>
          <span className="truncate">{appointment.clinic_name}</span>
        </div>
      </div>
    </button>
  );
};
