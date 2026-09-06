import React from 'react';
import { Card, Button } from '../components/ui';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../i18n/LanguageContext';

export const PendingVerification: React.FC = () => {
  const { currentUser, logout } = useAuth();
  const { t } = useLanguage();

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
              {t('pending.title')}
            </h1>
            <p className="text-sm text-textSecondary mt-3 leading-relaxed">
              {t('pending.subtitle', { name: currentUser?.name || '' })}
            </p>
          </div>

          <div className="bg-secondaryContainer/30 border border-secondary/20 rounded-2xl p-5 mb-6 text-left space-y-2">
            <p className="text-xs font-bold uppercase tracking-wider text-secondary mb-2">{t('pending.nextSteps')}</p>
            <ul className="text-xs text-textSecondary space-y-1.5">
              <li className="flex items-start gap-2">
                <span className="text-secondary mt-0.5">1.</span>
                <span>{t('pending.step1')}</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-secondary mt-0.5">2.</span>
                <span>{t('pending.step2')}</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-secondary mt-0.5">3.</span>
                <span>{t('pending.step3')}</span>
              </li>
            </ul>
          </div>

          <p className="text-xs text-textSecondary mb-6">
            {t('pending.notification', { email: currentUser?.email || '' })}
          </p>

          <div className="flex justify-center">
            <Button
              variant="ghost"
              size="md"
              onClick={async () => {
                await logout();
              }}
            >
              {t('pending.logout')}
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
};
