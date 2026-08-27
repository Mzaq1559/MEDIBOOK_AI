import React from 'react';
import { type ParsedDoctorOption, avatarBgForName } from '../../services/chat';

interface DoctorCardProps {
  doctor: ParsedDoctorOption;
  isSelected?: boolean;
  onClick: (id: string) => void;
  disabled?: boolean;
}

export const DoctorCard: React.FC<DoctorCardProps> = ({ doctor, isSelected, onClick, disabled }) => {
  const bg = avatarBgForName(doctor.name);
  
  return (
    <button
      type="button"
      onClick={() => onClick(doctor.doctor_id)}
      disabled={disabled}
      className={`w-full text-left p-4 bg-white rounded-2xl border transition-all flex flex-col justify-between
        ${isSelected ? 'border-primary shadow-soft ring-1 ring-primary/20' : 'border-surfaceContainerHigh hover:border-primary/40 shadow-soft-sm'}
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
      `}
    >
      <div>
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex items-center gap-2.5">
            <div className={`w-10 h-10 rounded-xl ${bg} flex items-center justify-center font-bold text-sm shrink-0`}>
              {doctor.name.split(' ')[1]?.charAt(0) || doctor.name.charAt(0) || 'Dr'}
            </div>
            <div>
              <h4 className="font-heading font-bold text-sm text-textPrimary">
                {doctor.name}
              </h4>
              <p className="text-[12px] text-textSecondary">{doctor.specialization}</p>
            </div>
          </div>
          {doctor.consultation_fee && (
            <span className="text-sm font-bold text-primary">
              Rs. {doctor.consultation_fee}
            </span>
          )}
        </div>

        <div className="text-[12px] text-textSecondary space-y-1 my-3 bg-surfaceContainer p-2.5 rounded-xl">
          <div className="flex items-center gap-1.5">
            <span>📍</span>
            <span className="truncate">{doctor.clinic_name}</span>
          </div>
          {doctor.rating > 0 && (
            <div className="flex items-center gap-1.5">
              <span>⭐</span>
              <span className="font-medium">{doctor.rating.toFixed(1)} Rating</span>
            </div>
          )}
        </div>
      </div>
    </button>
  );
};
