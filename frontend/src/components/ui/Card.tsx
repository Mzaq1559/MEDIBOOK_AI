import React from 'react';
import { cn } from '../../lib/utils';

export interface CardProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'title'> {
  variant?: 'default' | 'surface' | 'outline' | 'interactive';
  radius?: '2xl' | '3xl';
  shadow?: 'none' | 'sm' | 'default' | 'md' | 'lg';
  icon?: React.ReactNode;
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  description?: React.ReactNode;
  badge?: React.ReactNode;
  action?: React.ReactNode;
}

export const Card = React.forwardRef<HTMLDivElement, CardProps>(
  (
    {
      className,
      variant = 'default',
      radius = '2xl',
      shadow = 'default',
      icon,
      title,
      subtitle,
      description,
      badge,
      action,
      children,
      ...props
    },
    ref
  ) => {
    const radiusStyles = {
      '2xl': 'rounded-2xl',
      '3xl': 'rounded-3xl',
    };

    const shadowStyles = {
      none: '',
      sm: 'shadow-soft-sm',
      default: 'shadow-soft',
      md: 'shadow-soft-md',
      lg: 'shadow-soft-lg',
    };

    const variantStyles = {
      default: 'bg-white border border-surfaceContainerHigh/60',
      surface: 'bg-surfaceContainer border border-outline/30',
      outline: 'bg-transparent border border-outline',
      interactive:
        'bg-white border border-surfaceContainerHigh/60 hover:shadow-soft-md hover:border-primaryContainer/30 transition-all duration-200 cursor-pointer',
    };

    const hasHeader = icon || title || subtitle || description || badge || action;

    return (
      <div
        ref={ref}
        className={cn(
          'p-6 text-textPrimary',
          radiusStyles[radius],
          shadowStyles[shadow],
          variantStyles[variant],
          className
        )}
        {...props}
      >
        {hasHeader && (
          <div className="mb-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3.5">
                {icon && (
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-surfaceContainer text-primary border border-surfaceContainerHigh">
                    {icon}
                  </div>
                )}
                <div>
                  <div className="flex items-center gap-2">
                    {title && (
                      <h3 className="font-heading font-bold text-lg text-textPrimary tracking-tight">
                        {title}
                      </h3>
                    )}
                    {badge}
                  </div>
                  {subtitle && (
                    <p className="text-xs font-medium text-textSecondary mt-0.5">
                      {subtitle}
                    </p>
                  )}
                </div>
              </div>
              {action && <div className="shrink-0">{action}</div>}
            </div>

            {description && (
              <p className={cn('text-sm text-textSecondary leading-relaxed', icon ? 'mt-3' : 'mt-2')}>
                {description}
              </p>
            )}
          </div>
        )}

        {children}
      </div>
    );
  }
);

Card.displayName = 'Card';

export const CardHeader: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className,
  children,
  ...props
}) => (
  <div className={cn('mb-4 flex flex-col space-y-1.5', className)} {...props}>
    {children}
  </div>
);

export const CardTitle: React.FC<React.HTMLAttributes<HTMLHeadingElement>> = ({
  className,
  children,
  ...props
}) => (
  <h3
    className={cn('font-heading font-bold text-xl text-textPrimary tracking-tight', className)}
    {...props}
  >
    {children}
  </h3>
);

export const CardDescription: React.FC<React.HTMLAttributes<HTMLParagraphElement>> = ({
  className,
  children,
  ...props
}) => (
  <p className={cn('text-sm text-textSecondary leading-relaxed', className)} {...props}>
    {children}
  </p>
);

export const CardContent: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className,
  children,
  ...props
}) => (
  <div className={cn('pt-0', className)} {...props}>
    {children}
  </div>
);

export const CardFooter: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className,
  children,
  ...props
}) => (
  <div className={cn('mt-6 flex items-center pt-4 border-t border-surfaceContainerHigh', className)} {...props}>
    {children}
  </div>
);
