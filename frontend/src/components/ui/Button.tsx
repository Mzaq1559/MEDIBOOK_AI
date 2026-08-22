import React from 'react';
import { cn } from '../../lib/utils';
import { LoadingSpinner } from './LoadingSpinner';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'outline';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = 'primary',
      size = 'md',
      isLoading = false,
      leftIcon,
      rightIcon,
      children,
      disabled,
      ...props
    },
    ref
  ) => {
    // Base styles: pill-shaped, smooth transitions, font weight 600
    const baseStyles =
      'inline-flex items-center justify-center font-medium rounded-pill transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none disabled:cursor-not-allowed select-none';

    // Variants according to design system
    const variantStyles = {
      primary:
        'bg-primary text-white hover:bg-primaryContainer shadow-soft-sm hover:shadow-soft active:bg-primary',
      secondary:
        'bg-transparent border-2 border-primary text-primary hover:bg-surfaceContainer active:bg-surfaceContainerHigh',
      danger:
        'bg-error text-white hover:bg-[#a01616] shadow-soft-sm hover:shadow-soft active:bg-error',
      ghost:
        'bg-transparent text-textSecondary hover:text-textPrimary hover:bg-surfaceContainer',
      outline:
        'bg-transparent border border-outline text-textPrimary hover:bg-surfaceContainer',
    };

    // Sizes
    const sizeStyles = {
      sm: 'text-xs px-4 py-1.5 gap-1.5 min-h-[32px]',
      md: 'text-sm px-5 py-2.5 gap-2 min-h-[42px]',
      lg: 'text-base px-7 py-3 gap-2.5 min-h-[50px] font-semibold',
    };

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn(
          baseStyles,
          variantStyles[variant],
          sizeStyles[size],
          className
        )}
        {...props}
      >
        {isLoading ? (
          <>
            <LoadingSpinner
              size={size === 'sm' ? 'sm' : 'sm'}
              color={variant === 'secondary' || variant === 'ghost' || variant === 'outline' ? 'primary' : 'white'}
            />
            <span>{children}</span>
          </>
        ) : (
          <>
            {leftIcon && <span className="inline-flex shrink-0 items-center">{leftIcon}</span>}
            <span>{children}</span>
            {rightIcon && <span className="inline-flex shrink-0 items-center">{rightIcon}</span>}
          </>
        )}
      </button>
    );
  }
);

Button.displayName = 'Button';
