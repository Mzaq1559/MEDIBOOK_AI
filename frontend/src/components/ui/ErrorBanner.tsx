import React from 'react';
import { cn } from '../../lib/utils';
import { Button } from './Button';

export interface ErrorBannerProps extends React.HTMLAttributes<HTMLDivElement> {
  title?: string;
  message?: React.ReactNode;
  onDismiss?: () => void;
  onRetry?: () => void;
  retryText?: string;
  variant?: 'subtle' | 'solid' | 'card';
}

export const ErrorBanner: React.FC<ErrorBannerProps> = ({
  className,
  title = 'An error occurred',
  message,
  onDismiss,
  onRetry,
  retryText = 'Try Again',
  variant = 'subtle',
  children,
  ...props
}) => {
  const variantStyles = {
    // Standard errorContainer background with soft border
    subtle: 'bg-errorContainer text-textPrimary border border-error/20',
    // Card with white background and red accent border
    card: 'bg-white text-textPrimary border-l-4 border-l-error border-y border-r border-error/20 shadow-soft-sm',
    // Solid error
    solid: 'bg-error text-white',
  };

  return (
    <div
      role="alert"
      className={cn(
        'w-full p-4 rounded-2xl transition-all duration-200 flex items-start gap-3.5',
        variantStyles[variant],
        className
      )}
      {...props}
    >
      {/* Error Icon */}
      <div
        className={cn(
          'w-9 h-9 rounded-xl flex items-center justify-center shrink-0 mt-0.5',
          variant === 'solid'
            ? 'bg-white/20 text-white'
            : 'bg-error/10 text-error'
        )}
      >
        <svg
          className="w-5 h-5"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth="2"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z"
          />
        </svg>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 pt-0.5">
        {title && (
          <h4
            className={cn(
              'text-sm font-heading font-bold tracking-tight mb-1',
              variant === 'solid' ? 'text-white' : 'text-error'
            )}
          >
            {title}
          </h4>
        )}
        <div
          className={cn(
            'text-xs leading-relaxed',
            variant === 'solid' ? 'text-white/90' : 'text-textSecondary'
          )}
        >
          {message || children}
        </div>

        {onRetry && (
          <div className="mt-3">
            <Button
              size="sm"
              variant={variant === 'solid' ? 'secondary' : 'danger'}
              onClick={onRetry}
              className={variant === 'solid' ? 'bg-white text-error hover:bg-white/90 border-none' : ''}
            >
              {retryText}
            </Button>
          </div>
        )}
      </div>

      {/* Dismiss Button */}
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss error"
          className={cn(
            'p-1.5 rounded-pill shrink-0 transition-colors',
            variant === 'solid'
              ? 'text-white/80 hover:bg-white/20'
              : 'text-textSecondary hover:bg-error/10 hover:text-error'
          )}
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      )}
    </div>
  );
};
