import React from 'react';
import { Link } from 'react-router-dom';
import { Card, Button, Badge } from '../components/ui';

export interface PlaceholderPageProps {
  title: string;
  description: string;
  path: string;
  badgeText?: string;
  icon?: React.ReactNode;
}

export const PlaceholderPage: React.FC<PlaceholderPageProps> = ({
  title,
  description,
  path,
  badgeText = 'Route Scaffolding',
  icon,
}) => {
  return (
    <div className="max-w-4xl mx-auto px-4 py-16">
      <Card
        radius="3xl"
        shadow="md"
        className="p-8 md:p-12 text-center bg-white border border-surfaceContainerHigh"
      >
        <div className="flex justify-center mb-6">
          <div className="w-16 h-16 rounded-3xl bg-surfaceContainer flex items-center justify-center text-primary border border-surfaceContainerHigh shadow-soft-sm">
            {icon || (
              <svg
                className="w-8 h-8"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth="2"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M3.75 6A2.25 2.25 0 0 1 6 3.75h2.25A2.25 2.25 0 0 1 10.5 6v2.25a2.25 2.25 0 0 1-2.25 2.25H6a2.25 2.25 0 0 1-2.25-2.25V6ZM3.75 15.75A2.25 2.25 0 0 1 6 13.5h2.25a2.25 2.25 0 0 1 2.25 2.25V18a2.25 2.25 0 0 1-2.25 2.25H6A2.25 2.25 0 0 1 3.75 18v-2.25ZM13.5 6a2.25 2.25 0 0 1 2.25-2.25H18A2.25 2.25 0 0 1 20.25 6v2.25A2.25 2.25 0 0 1 18 10.5h-2.25a2.25 2.25 0 0 1-2.25-2.25V6ZM13.5 15.75a2.25 2.25 0 0 1 2.25-2.25H18a2.25 2.25 0 0 1 2.25 2.25V18A2.25 2.25 0 0 1 18 20.25h-2.25A2.25 2.25 0 0 1 13.5 18v-2.25Z"
                />
              </svg>
            )}
          </div>
        </div>

        <div className="inline-flex mb-3">
          <Badge status="pending" size="md">
            {badgeText}
          </Badge>
        </div>

        <h1 className="text-3xl sm:text-4xl font-extrabold text-textPrimary mb-3 tracking-tight">
          {title}
        </h1>

        <p className="text-textSecondary text-base max-w-lg mx-auto mb-2 leading-relaxed">
          {description}
        </p>

        <p className="text-xs font-mono text-textSecondary/70 bg-surfaceContainer px-3 py-1 rounded-pill inline-block mb-8">
          Path: {path}
        </p>

        <div className="flex flex-wrap items-center justify-center gap-3">
          <Link to="/">
            <Button variant="primary" size="md">
              View Design System & Components
            </Button>
          </Link>
          <Link to="/dashboard">
            <Button variant="secondary" size="md">
              Go to Dashboard
            </Button>
          </Link>
        </div>
      </Card>
    </div>
  );
};
