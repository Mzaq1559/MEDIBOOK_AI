import React from 'react';
import { type ParsedSession } from '../../services/chat';

interface SessionSelectorProps {
  sessions: ParsedSession[];
  onSelect: (session: ParsedSession) => void;
  disabled?: boolean;
}

export const SessionSelector: React.FC<SessionSelectorProps> = ({ sessions, onSelect, disabled }) => {
  if (!sessions || !sessions.length) return null;

  // Group by date
  const grouped = sessions.reduce((acc, session) => {
    if (!acc[session.date]) acc[session.date] = [];
    acc[session.date].push(session);
    return acc;
  }, {} as Record<string, ParsedSession[]>);

  const formatDateLabel = (dateStr: string) => {
    try {
      const d = new Date(dateStr + 'T00:00:00');
      if (!Number.isNaN(d.getTime())) {
        return d.toLocaleDateString(undefined, {
          weekday: 'short',
          month: 'short',
          day: 'numeric',
          year: 'numeric',
        });
      }
    } catch {
      // fallback
    }
    return dateStr;
  };

  return (
    <div className="space-y-4 pt-1">
      {Object.entries(grouped).map(([date, daySessions]) => (
        <div
          key={date}
          className="bg-white p-4 rounded-2xl border border-surfaceContainerHigh shadow-soft-sm space-y-3"
        >
          <div className="flex items-center justify-between border-b border-surfaceContainerHigh pb-2">
            <span className="text-xs font-bold uppercase tracking-wider text-textSecondary px-1">
              📅 {formatDateLabel(date)}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {daySessions.map((s) => {
              const isMorning = s.session.toLowerCase() === 'morning';
              const isAvailable = s.available && s.remaining > 0;
              const isSelectable = !disabled && isAvailable;

              return (
                <button
                  key={`${s.date}-${s.session}`}
                  type="button"
                  disabled={!isSelectable}
                  onClick={() => isSelectable && onSelect(s)}
                  className={`flex flex-col p-4 rounded-xl border text-left transition-all duration-200 relative overflow-hidden ${
                    !isSelectable
                      ? 'opacity-60 cursor-not-allowed bg-surfaceContainer/50 border-surfaceContainerHigh text-textSecondary'
                      : 'bg-surfaceContainer/20 hover:bg-white border-surfaceContainerHigh hover:border-primary hover:shadow-soft-md cursor-pointer group focus:outline-none focus:ring-2 focus:ring-primary/20'
                  }`}
                >
                  <div className="flex items-center justify-between w-full mb-2">
                    <span className="text-sm font-bold text-textPrimary flex items-center gap-1.5">
                      {isMorning ? '🌅 Morning' : '🌙 Evening'}
                    </span>
                    <span
                      className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${
                        isAvailable
                          ? 'bg-primary/10 text-primary'
                          : 'bg-errorContainer text-error'
                      }`}
                    >
                      {s.booked} / {s.capacity} booked
                    </span>
                  </div>

                  <div className="mt-1">
                    {isAvailable ? (
                      <span className="text-xs font-semibold text-success flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-success inline-block"></span>
                        {s.remaining} {s.remaining === 1 ? 'spot' : 'spots'} remaining
                      </span>
                    ) : (
                      <span className="text-xs font-semibold text-error flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-error inline-block"></span>
                        Fully booked
                      </span>
                    )}
                  </div>

                  {isSelectable && (
                    <div className="mt-3 pt-2 border-t border-surfaceContainerHigh/60 flex items-center justify-between text-xs text-primary font-semibold group-hover:translate-x-0.5 transition-transform">
                      <span>Select session</span>
                      <span>→</span>
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
};
