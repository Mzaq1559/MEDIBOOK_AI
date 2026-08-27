import React from 'react';
import { type ParsedSlot } from '../../services/chat';

interface TimeSlotGridProps {
  slots: ParsedSlot[];
  onSelect: (timestamp: string) => void;
  disabled?: boolean;
}

export const TimeSlotGrid: React.FC<TimeSlotGridProps> = ({ slots, onSelect, disabled }) => {
  if (!slots.length) return null;

  // Group by date
  const grouped = slots.reduce((acc, slot) => {
    if (!acc[slot.date]) acc[slot.date] = [];
    acc[slot.date].push(slot);
    return acc;
  }, {} as Record<string, ParsedSlot[]>);

  return (
    <div className="space-y-4">
      {Object.entries(grouped).map(([date, daySlots]) => (
        <div key={date} className="bg-white p-3 rounded-2xl border border-surfaceContainerHigh shadow-soft-sm">
          <span className="text-[11px] font-bold uppercase tracking-wider text-textSecondary block mb-2 px-1">
            {date}
          </span>
          <div className="flex flex-wrap gap-2">
            {daySlots.map((slot) => (
              <button
                key={slot.timestamp}
                type="button"
                onClick={() => onSelect(slot.timestamp)}
                disabled={disabled}
                className={`text-xs font-semibold px-3 py-2 rounded-xl border transition-all
                  ${disabled 
                    ? 'opacity-50 cursor-not-allowed bg-surfaceContainer text-textSecondary border-surfaceContainerHigh' 
                    : 'bg-surfaceContainer hover:bg-primary hover:text-white text-textPrimary border-surfaceContainerHigh hover:border-primary focus:ring-2 focus:ring-primary/20'}
                `}
              >
                {slot.time}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};
