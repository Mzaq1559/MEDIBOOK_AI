import React from 'react';
import { cn } from '../../lib/utils';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  containerClassName?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  (
    {
      className,
      type = 'text',
      label,
      error,
      helperText,
      leftIcon,
      rightIcon,
      id,
      disabled,
      containerClassName,
      ...props
    },
    ref
  ) => {
    // Generate fallback unique ID for accessible labeling
    const generatedId = React.useId();
    const inputId = id || `input-${generatedId}`;

    return (
      <div className={cn('w-full flex flex-col gap-1.5', containerClassName)}>
        {label && (
          <label
            htmlFor={inputId}
            className="text-sm font-semibold text-textPrimary tracking-tight select-none flex items-center justify-between"
          >
            <span>{label}</span>
            {props.required && (
              <span className="text-xs text-textSecondary font-normal">Required</span>
            )}
          </label>
        )}

        <div className="relative flex items-center">
          {leftIcon && (
            <div className="absolute left-3.5 flex items-center pointer-events-none text-textSecondary">
              {leftIcon}
            </div>
          )}

          <input
            id={inputId}
            ref={ref}
            type={type}
            disabled={disabled}
            aria-invalid={error ? 'true' : 'false'}
            aria-describedby={
              error
                ? `${inputId}-error`
                : helperText
                ? `${inputId}-helper`
                : undefined
            }
            className={cn(
              // 12px rounded (rounded-xl), soft grey surface background
              'w-full rounded-xl bg-surfaceContainer text-textPrimary text-sm placeholder:text-textSecondary/60',
              'border border-outline/40 transition-all duration-200 ease-in-out',
              'h-11 px-4 py-2.5 outline-none',
              // Focus state with blue glow
              'focus:bg-white focus:border-primary focus:ring-4 focus:ring-primary/15',
              // Icon spacing
              leftIcon && 'pl-10',
              rightIcon && 'pr-10',
              // Error state
              error && 'border-error focus:border-error focus:ring-error/15 bg-errorContainer/20',
              // Disabled state
              disabled && 'opacity-60 cursor-not-allowed bg-surfaceContainerHigh/60 select-none',
              className
            )}
            {...props}
          />

          {rightIcon && (
            <div className="absolute right-3.5 flex items-center text-textSecondary">
              {rightIcon}
            </div>
          )}
        </div>

        {error ? (
          <p
            id={`${inputId}-error`}
            className="text-xs font-medium text-error flex items-center gap-1.5 animate-fadeIn"
          >
            <svg
              className="w-3.5 h-3.5 shrink-0"
              viewBox="0 0 16 16"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M8 15A7 7 0 1 0 8 1a7 7 0 0 0 0 14zm-.75-9.5a.75.75 0 0 1 1.5 0v3.5a.75.75 0 0 1-1.5 0V5.5zm.75 6.25a.875.875 0 1 1 0-1.75.875.875 0 0 1 0 1.75z"
                clipRule="evenodd"
              />
            </svg>
            <span>{error}</span>
          </p>
        ) : helperText ? (
          <p
            id={`${inputId}-helper`}
            className="text-xs text-textSecondary leading-normal"
          >
            {helperText}
          </p>
        ) : null}
      </div>
    );
  }
);

Input.displayName = 'Input';
