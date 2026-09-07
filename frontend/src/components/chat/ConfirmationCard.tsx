import React, { useState } from 'react';
import { Button, Badge } from '../ui';
import { type ParsedBookingSummary } from '../../services/chat';
import { useLanguage } from '../../i18n/LanguageContext';

export function formatSessionDisplay(
  rawSlot?: string,
  session?: string | null,
  date?: string | null
): string {
  let sessionName = '';
  if (session) {
    sessionName = session.toLowerCase() === 'morning' ? 'Morning Session' : 'Evening Session';
  } else if (rawSlot && /morning/i.test(rawSlot)) {
    sessionName = 'Morning Session';
  } else if (rawSlot && /evening/i.test(rawSlot)) {
    sessionName = 'Evening Session';
  }

  let dateObj: Date | null = null;
  if (date) {
    const d = new Date(date + (date.includes('T') ? '' : 'T00:00:00'));
    if (!Number.isNaN(d.getTime())) dateObj = d;
  }
  if (!dateObj && rawSlot) {
    const match = rawSlot.match(/(\d{4}-\d{2}-\d{2})/);
    if (match) {
      const d = new Date(match[1] + 'T00:00:00');
      if (!Number.isNaN(d.getTime())) dateObj = d;
    } else {
      const parsed = new Date(rawSlot);
      if (!Number.isNaN(parsed.getTime())) dateObj = parsed;
    }
  }

  if (!sessionName && rawSlot) {
    const hourMatch = rawSlot.match(/(\d{1,2}):\d{2}/);
    if (hourMatch) {
      const hr = parseInt(hourMatch[1], 10);
      const isPm = /pm/i.test(rawSlot);
      const effHr = isPm && hr < 12 ? hr + 12 : hr;
      sessionName = effHr < 14 ? 'Morning Session' : 'Evening Session';
    } else {
      sessionName = 'Morning Session';
    }
  }

  if (!sessionName) {
    sessionName = 'Morning Session';
  }

  if (dateObj) {
    const formattedDate = dateObj.toLocaleDateString('en-US', {
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    });
    return `${sessionName} — ${formattedDate}`;
  }

  return sessionName;
}

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
  disabled,
}) => {
  // Prevent double-submission: once clicked, the button stays disabled for the
  // lifetime of this card (the message is immutable once in the chat history).
  const [hasConfirmed, setHasConfirmed] = useState(false);
  const { t } = useLanguage();

  // Derive display state strictly from the backend-authoritative `status` field.
  // Fall back to the legacy `isConfirmed` boolean only when `status` is absent
  // so that older messages rendered before this change still look correct.
  const status = booking.status ?? (booking.isConfirmed ? 'executed' : 'pending');

  const isExpired = status === 'expired';
  const isFailed = status === 'failed';
  const isExecuted = status === 'executed';
  const isPending = status === 'pending';

  const badgeStatus = isExecuted
    ? 'success'
    : isExpired || isFailed
    ? 'error'
    : 'pending';

  const badgeLabel = isExecuted
    ? t('confirm.verified')
    : isExpired
    ? t('confirm.expired')
    : isFailed
    ? t('confirm.failed')
    : t('confirm.pending');

  const headingLabel = isExecuted
    ? t('confirm.bookingConfirmed')
    : isExpired
    ? t('confirm.requestExpired')
    : isFailed
    ? t('confirm.bookingFailed')
    : t('confirm.appointmentReview');

  const handleConfirm = () => {
    setHasConfirmed(true);
    onConfirm();
  };

  const displaySession = formatSessionDisplay(
    booking.selectedSlot,
    booking.session,
    booking.date
  );

  return (
    <div className="p-5 bg-white rounded-2xl border-2 border-primary/20 shadow-soft-md space-y-4 animate-fadeIn">
      <div className="flex items-center justify-between border-b border-surfaceContainerHigh pb-3">
        <div className="flex items-center gap-2">
          <span
            className={`w-2.5 h-2.5 rounded-full ${
              isExecuted
                ? 'bg-success'
                : isExpired || isFailed
                ? 'bg-error'
                : 'bg-primary'
            }`}
          />
          <h4 className="font-heading font-bold text-sm text-textPrimary">
            {headingLabel}
          </h4>
        </div>
        <Badge status={badgeStatus} size="sm">
          {badgeLabel}
        </Badge>
      </div>

      {/* Expired / Failed notice */}
      {(isExpired || isFailed) && (
        <div className="flex items-start gap-2 p-3 bg-errorContainer rounded-xl border border-error/20 text-xs text-error">
          <span className="text-base leading-none mt-0.5">⚠️</span>
          <p className="leading-relaxed">
            {isExpired
              ? t('confirm.expiredMsg')
              : t('confirm.failedMsg')}
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
        <div className="p-3 bg-surfaceContainer rounded-xl">
          <span className="text-[10px] text-textSecondary uppercase font-bold block mb-0.5">{t('confirm.doctor')}</span>
          <span className="font-bold text-textPrimary text-sm block">
            {booking.doctor.name}
          </span>
          {booking.doctor.specialization && (
            <span className="text-textSecondary text-[11px] block">{booking.doctor.specialization}</span>
          )}
        </div>

        <div className="p-3 bg-surfaceContainer rounded-xl">
          <span className="text-[10px] text-textSecondary uppercase font-bold block mb-0.5">Session</span>
          <span className="font-bold text-textPrimary text-sm block text-primary">
            {displaySession}
          </span>
        </div>

        {(booking.doctor.clinic_name || booking.doctor.consultation_fee) && (
          <div className="p-3 bg-surfaceContainer rounded-xl sm:col-span-2 flex items-center justify-between">
            {booking.doctor.clinic_name && (
              <div>
                <span className="text-[10px] text-textSecondary uppercase font-bold block mb-0.5">{t('confirm.location')}</span>
                <span className="font-semibold text-textPrimary text-xs block">
                  {booking.doctor.clinic_name}
                </span>
                {booking.doctor.clinic_address && (
                  <span className="text-textSecondary text-[11px] block mt-0.5 max-w-[200px] truncate">
                    {booking.doctor.clinic_address}
                  </span>
                )}
              </div>
            )}
            {booking.doctor.consultation_fee && (
              <div className="text-right">
                <span className="text-[10px] text-textSecondary uppercase font-bold block mb-0.5">{t('confirm.fee')}</span>
                <span className="font-bold text-primary text-sm">Rs. {booking.doctor.consultation_fee}</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Action buttons — only shown for a live pending proposal */}
      {isPending && (
        <div className="flex flex-col sm:flex-row items-center gap-3 pt-2">
          <Button
            variant="primary"
            size="md"
            className="w-full sm:flex-1 justify-center shadow-soft"
            isLoading={isLoading}
            // Disabled once clicked (hasConfirmed) OR while the bot is responding,
            // to prevent double-submission.
            disabled={disabled || hasConfirmed}
            onClick={handleConfirm}
          >
            {isLoading ? t('confirm.confirming') : t('confirm.booking')}
          </Button>
          <Button
            variant="secondary"
            size="md"
            className="w-full sm:w-auto"
            disabled={disabled || isLoading || hasConfirmed}
            onClick={onChange}
          >
            {t('confirm.change')}
          </Button>
        </div>
      )}
    </div>
  );
};
