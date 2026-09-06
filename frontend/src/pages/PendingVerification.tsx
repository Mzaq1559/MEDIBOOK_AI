import React from 'react';
import { Card, Button } from '../components/ui';
import { useAuth } from '../context/AuthContext';

export const PendingVerification: React.FC = () => {
  const { currentUser, logout } = useAuth();

  return (
    <div className="min-h-[calc(100vh-140px)] flex items-center justify-center px-4 py-10 sm:py-16">
      <div className="w-full max-w-lg">
        <Card
          radius="3xl"
          shadow="md"
          className="p-7 sm:p-10 bg-white border border-surfaceContainerHigh text-center"
        >
          <div className="mb-6">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-amber-100 text-amber-700 border border-amber-200 text-3xl mb-4">
              ⏳
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-textPrimary tracking-tight">
              Awaiting Clinical Verification
            </h1>
            <p className="text-sm text-textSecondary mt-3 leading-relaxed">
              Thank you for registering, <strong className="text-textPrimary">{currentUser?.name}</strong>.
              Your doctor account application has been submitted and is currently pending review by our administrative team.
            </p>
          </div>

          <div className="bg-secondaryContainer/30 border border-secondary/20 rounded-2xl p-5 mb-6 text-left space-y-2">
            <p className="text-xs font-bold uppercase tracking-wider text-secondary mb-2">What happens next?</p>
            <ul className="text-xs text-textSecondary space-y-1.5">
              <li className="flex items-start gap-2">
                <span className="text-secondary mt-0.5">1.</span>
                <span>Our admin team will review your submitted credentials and professional information.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-secondary mt-0.5">2.</span>
                <span>Once verified, you will be assigned a clinic facility and specialization.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-secondary mt-0.5">3.</span>
                <span>You will receive an email notification when your account is approved.</span>
              </li>
            </ul>
          </div>

          <p className="text-xs text-textSecondary mb-6">
            You will be notified via email at <strong className="text-textPrimary">{currentUser?.email}</strong> once your application has been reviewed.
          </p>

          <div className="flex justify-center">
            <Button
              variant="ghost"
              size="md"
              onClick={async () => {
                await logout();
              }}
            >
              Log Out
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
};
