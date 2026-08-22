import React from 'react';
import { cn } from '../../lib/utils';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  status?: 'success' | 'error' | 'pending' | 'neutral' | 'primary';
  size?: 'sm' | 'md' | 'lg';
  withDot?: boolean;
  icon?: React.ReactNode;
  onRemove?: () => void;
}

export const Badge: React.FC<BadgeProps> = ({
  className,
  status = 'neutral',
  size = 'md',
  withDot = false,
  icon,
  onRemove,
  children,
  ...props
}) => {
  // Status color mappings based on design system
  const statusStyles = {
    // Success: teal tint using secondary & secondaryContainer
    success: 'bg-[#62FAE3]/35 text-secondary border-[#006B5F]/20 hover:bg-[#62FAE3]/50',
    // Error: red tint using error & errorContainer
    error: 'bg-errorContainer text-error border-error/20 hover:bg-[#ffc9c2]',
    // Pending: blue tint using primaryContainer/surfaceContainerHigh
    pending: 'bg-surfaceContainerHigh text-primary border-primary/25 hover:bg-[#d8e5ff]',
    // Primary: full primary tint
    primary: 'bg-primary/10 text-primary border-primary/20 hover:bg-primary/15',
    // Neutral: surface container
    neutral: 'bg-surfaceContainer text-textSecondary border-outline/40 hover:bg-surfaceContainerHigh',
  };

  const dotColors = {
    success: 'bg-secondary',
    error: 'bg-error',
    pending: 'bg-primary',
    primary: 'bg-primary',
    neutral: 'bg-textSecondary',
  };

  const sizeStyles = {
    sm: 'text-[11px] px-2.5 py-0.5 gap-1.5 font-medium',
    md: 'text-xs px-3 py-1 gap-1.5 font-semibold',
    lg: 'text-sm px-3.5 py-1.5 gap-2 font-semibold',
  };

  return (
    <span
      className={cn(
        // Pill-shaped, soft borders, clean typography
        'inline-flex items-center rounded-pill border transition-colors select-none tracking-tight',
        statusStyles[status],
        sizeStyles[size],
        className
      )}
      {...props}
    >
      {withDot && (
        <span
          className={cn('w-1.5 h-1.5 rounded-full shrink-0 animate-pulse', dotColors[status])}
          aria-hidden="true"
        />
      )}
      {icon && <span className="inline-flex shrink-0 items-center">{icon}</span>}
      <span>{children}</span>
      {onRemove && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          className="ml-0.5 -mr-1 p-0.5 rounded-full hover:bg-black/10 transition-colors inline-flex items-center justify-center"
          aria-label="Remove badge"
        >
          <svg className="w-3 h-3" viewBox="0 0 16 16" fill="currentColor">
            <path d="M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708z" />
          </svg>
        </button>
      )}
    </span>
  );
};

// Also export as Chip alias
export const Chip = Badge;
