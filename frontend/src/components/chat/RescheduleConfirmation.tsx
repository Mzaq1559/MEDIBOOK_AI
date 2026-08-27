import React from 'react';
import { Button } from '../ui';
import { type ParsedRescheduleSummary } from '../../services/chat';

interface RescheduleConfirmationProps {
  reschedule: ParsedRescheduleSummary;
  onConfirm: () => void;
  onChange: () => void;
  isLoading: boolean;
  disabled: boolean;
}

export const RescheduleConfirmation: React.FC<RescheduleConfirmationProps> = ({
  reschedule,
  onConfirm,
  onChange,
  isLoading,
  disabled
}) => {
  return (
    <div className="p-5 bg-white rounded-2xl border-2 border-secondary/20 shadow-soft-md space-y-4 animate-fadeIn">
      <div className="flex items-center gap-2 border-b border-surfaceContainerHigh pb-3">
        <span className="text-lg">📅</span>
        <h4 className="font-heading font-bold text-sm text-textPrimary">
          Confirm Reschedule
        </h4>
      </div>

      <div className="text-xs space-y-1 mb-2">
        <span className="text-textSecondary">Doctor: </span>
        <span className="font-bold text-textPrimary">{reschedule.doctor?.name || 'Your Doctor'}</span>
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs relative">
        {/* Arrow connector */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-6 h-6 bg-white rounded-full border border-surfaceContainerHigh flex items-center justify-center z-10 text-textSecondary">
          →
        </div>

        <div className="p-3 bg-surfaceContainer rounded-xl opacity-70">
          <span className="text-[10px] text-error uppercase font-bold block mb-0.5">Old Time</span>
          <span className="font-semibold text-textSecondary text-xs block line-through">
            {reschedule.oldSlot}
          </span>
        </div>

        <div className="p-3 bg-primary/10 rounded-xl border border-primary/20">
          <span className="text-[10px] text-primary uppercase font-bold block mb-0.5">New Time</span>
          <span className="font-bold text-primary text-xs block">
            {reschedule.newSlot}
          </span>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row items-center gap-3 pt-2">
        <Button
          variant="primary"
          size="md"
          className="w-full sm:flex-1 justify-center shadow-soft"
          isLoading={isLoading}
          disabled={disabled}
          onClick={onConfirm}
        >
          {isLoading ? 'Rescheduling...' : 'Confirm Reschedule'}
        </Button>
        <Button
          variant="secondary"
          size="md"
          className="w-full sm:w-auto"
          disabled={disabled || isLoading}
          onClick={onChange}
        >
          Change Time
        </Button>
      </div>
    </div>
  );
};
