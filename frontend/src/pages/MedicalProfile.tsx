import React, { useState, useEffect, useCallback } from 'react';
import { Card, Button, Badge, Input } from '../components/ui';
import { useAuth } from '../context/AuthContext';
import {
  getMyPatientProfile,
  updateMyPatientProfile,
  type PatientProfile,
  type PatientProfileUpdatePayload,
} from '../services/patient';
import { useLanguage } from '../i18n/LanguageContext';
import { translateDate } from '../i18n/translations';

const BLOOD_TYPES = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'];
const GENDER_OPTIONS = [
  { value: 'M', enLabel: 'Male', urLabel: 'مرد' },
  { value: 'F', enLabel: 'Female', urLabel: 'عورت' },
  { value: 'Other', enLabel: 'Other', urLabel: 'دیگر' },
];

export const MedicalProfile: React.FC = () => {
  const { currentUser } = useAuth();
  const { t, lang } = useLanguage();

  const [profile, setProfile] = useState<PatientProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  // Form state
  const [dob, setDob] = useState('');
  const [gender, setGender] = useState('');
  const [bloodType, setBloodType] = useState('');
  const [allergiesText, setAllergiesText] = useState('');
  const [conditionsText, setConditionsText] = useState('');
  const [ecName, setEcName] = useState('');
  const [ecPhone, setEcPhone] = useState('');
  const [ecRelation, setEcRelation] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  const fetchProfile = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getMyPatientProfile();
      setProfile(data);
      populateForm(data);
    } catch (err: any) {
      console.error('[MedicalProfile] Failed to load profile:', err);
      setError(err?.response?.data?.detail?.message || 'Failed to load medical profile.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  function populateForm(p: PatientProfile) {
    setDob(p.date_of_birth || '');
    setGender(p.gender || '');
    setBloodType(p.blood_type || '');
    setAllergiesText((p.allergies || []).join(', '));
    setConditionsText((p.medical_conditions || []).join(', '));
    setEcName(p.emergency_contact_name || '');
    setEcPhone(p.emergency_contact_phone || '');
    setEcRelation(p.emergency_contact_relation || '');
  }

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 4000);
  };

  const parseList = (text: string): string[] =>
    text
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);

  const handleSave = async () => {
    setFormError(null);

    // Basic validation
    if (dob) {
      const parsed = new Date(dob);
      if (isNaN(parsed.getTime())) {
        setFormError(t('profile.invalidDob'));
        return;
      }
      if (parsed > new Date()) {
        setFormError(t('profile.futureDob'));
        return;
      }
    }

    const payload: PatientProfileUpdatePayload = {
      date_of_birth: dob || null,
      gender: gender || null,
      blood_type: bloodType || null,
      allergies: parseList(allergiesText),
      medical_conditions: parseList(conditionsText),
      emergency_contact_name: ecName || null,
      emergency_contact_phone: ecPhone || null,
      emergency_contact_relation: ecRelation || null,
    };

    setSaving(true);
    try {
      const updated = await updateMyPatientProfile(payload);
      setProfile(updated);
      setEditing(false);
      showToast(t('profile.success'));
    } catch (err: any) {
      console.error('[MedicalProfile] Save failed:', err);
      const detail = err?.response?.data?.detail;
      if (Array.isArray(detail)) {
        setFormError(detail.map((d: any) => d.msg || d.message || JSON.stringify(d)).join('; '));
      } else if (typeof detail === 'object' && detail?.message) {
        setFormError(detail.message);
      } else {
        setFormError(t('common.error'));
      }
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    if (profile) populateForm(profile);
    setEditing(false);
    setFormError(null);
  };

  const genderLabel = (g?: string | null) => {
    if (!g) return null;
    const found = GENDER_OPTIONS.find((o) => o.value === g);
    if (!found) return g;
    return lang === 'ur' ? found.urLabel : found.enLabel;
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-12 space-y-8">
      {/* Toast */}
      {toast && (
        <div className="p-4 bg-surfaceContainer border border-primaryContainer/30 rounded-2xl shadow-soft-sm flex items-center justify-between animate-fadeIn">
          <div className="flex items-center gap-2.5">
            <span className="w-2.5 h-2.5 rounded-full bg-secondary animate-pulse" />
            <p className="text-sm font-medium text-textPrimary">{toast}</p>
          </div>
          <button onClick={() => setToast(null)} className="text-xs font-semibold text-textSecondary hover:text-textPrimary">
            {t('common.dismiss')}
          </button>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-surfaceContainerHigh">
        <div>
          <div className="inline-flex items-center gap-2 mb-1.5">
            <Badge status={profile?.profile_completed ? 'success' : 'pending'} size="sm" withDot>
              {profile?.profile_completed ? t('profile.complete') : t('profile.incomplete')}
            </Badge>
          </div>
          <h1 className="font-heading font-extrabold text-3xl sm:text-4xl text-textPrimary tracking-tight">
            {t('profile.title')}
          </h1>
          <p className="text-sm sm:text-base text-textSecondary mt-8">
            {t('profile.subtitle')}
          </p>
        </div>
        {!editing && !loading && (
          <Button variant="primary" size="md" onClick={() => setEditing(true)}>
            {t('profile.edit')}
          </Button>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="p-4 bg-errorContainer/30 border border-error/30 rounded-2xl flex items-center justify-between text-xs text-error">
          <p className="font-medium">⚠️ {error}</p>
          <Button size="sm" variant="ghost" onClick={fetchProfile}>
            {t('common.retry')}
          </Button>
        </div>
      )}

      {/* Loading */}
      {loading ? (
        <Card radius="2xl" shadow="sm" className="p-12 text-center bg-white border border-surfaceContainerHigh">
          <div className="w-8 h-8 border-3 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-xs text-textSecondary font-medium">{t('profile.loading')}</p>
        </Card>
      ) : editing ? (
        /* ── Edit Form ──────────────────────────────────────────── */
        <form
          className="space-y-6"
          onSubmit={(e) => {
            e.preventDefault();
            handleSave();
          }}
        >
          {formError && (
            <div className="p-4 bg-errorContainer/30 border border-error/30 rounded-2xl text-xs text-error">
              <p className="font-medium">⚠️ {formError}</p>
            </div>
          )}

          {/* Demographics */}
          <Card radius="2xl" shadow="sm" className="p-6 bg-white border border-surfaceContainerHigh space-y-5">
            <h2 className="font-heading font-bold text-lg text-textPrimary flex items-center gap-2">
              <svg className="w-5 h-5 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" />
              </svg>
              {t('profile.demographics')}
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                id="dob"
                name="dob"
                label={t('profile.dob')}
                type="date"
                value={dob}
                onChange={(e) => setDob(e.target.value)}
              />
              <div className="flex flex-col gap-1.5">
                <label htmlFor="gender" className="text-sm font-semibold text-textPrimary tracking-tight select-none">{t('profile.gender')}</label>
                <select
                  id="gender"
                  name="gender"
                  value={gender}
                  onChange={(e) => setGender(e.target.value)}
                  className="w-full rounded-xl bg-surfaceContainer text-textPrimary text-sm border border-outline/40 h-11 px-4 outline-none focus:bg-white focus:border-primary focus:ring-4 focus:ring-primary/15 transition-all duration-200"
                >
                  <option value="">{t('profile.notSpecified')}</option>
                  {GENDER_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {lang === 'ur' ? o.urLabel : o.enLabel}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-1.5">
                <label htmlFor="blood-type" className="text-sm font-semibold text-textPrimary tracking-tight select-none">{t('profile.bloodType')}</label>
                <select
                  id="blood-type"
                  name="blood_type"
                  value={bloodType}
                  onChange={(e) => setBloodType(e.target.value)}
                  className="w-full rounded-xl bg-surfaceContainer text-textPrimary text-sm border border-outline/40 h-11 px-4 outline-none focus:bg-white focus:border-primary focus:ring-4 focus:ring-primary/15 transition-all duration-200"
                >
                  <option value="">{t('profile.notSpecified')}</option>
                  {BLOOD_TYPES.map((bt) => (
                    <option key={bt} value={bt}>
                      {bt}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </Card>

          {/* Medical History */}
          <Card radius="2xl" shadow="sm" className="p-6 bg-white border border-surfaceContainerHigh space-y-5">
            <h2 className="font-heading font-bold text-lg text-textPrimary flex items-center gap-2">
              <svg className="w-5 h-5 text-error" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" />
              </svg>
              {t('profile.medicalHistory')}
            </h2>
            <Input
              id="allergies"
              name="allergies"
              label={t('profile.allergies')}
              value={allergiesText}
              onChange={(e) => setAllergiesText(e.target.value)}
              placeholder={t('profile.allergiesPlaceholder')}
              helperText={t('profile.commaSeparated')}
            />
            <Input
              id="conditions"
              name="medical_conditions"
              label={t('profile.conditions')}
              value={conditionsText}
              onChange={(e) => setConditionsText(e.target.value)}
              placeholder={t('profile.conditionsPlaceholder')}
              helperText={t('profile.commaSeparated')}
            />
          </Card>

          {/* Emergency Contact */}
          <Card radius="2xl" shadow="sm" className="p-6 bg-white border border-surfaceContainerHigh space-y-5">
            <h2 className="font-heading font-bold text-lg text-textPrimary flex items-center gap-2">
              <svg className="w-5 h-5 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 0 0 2.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.59-.147-1.17-.375-1.694-.693l-.368-.221a.75.75 0 0 0-.991.242l-.606.908a1.125 1.125 0 0 1-1.593.28l-.15-.135a9.02 9.02 0 0 1-2.558-3.727l-.064-.156a.75.75 0 0 0-.866-.494l-1.17.293a.75.75 0 0 1-.933-.729V6.75Z" />
              </svg>
              {t('profile.emergencyContact')}
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                id="ec-name"
                name="emergency_contact_name"
                label={t('profile.contactName')}
                value={ecName}
                onChange={(e) => setEcName(e.target.value)}
                placeholder={t('profile.contactName')}
                autoComplete="name"
              />
              <Input
                id="ec-phone"
                name="emergency_contact_phone"
                label={t('profile.contactPhone')}
                value={ecPhone}
                onChange={(e) => setEcPhone(e.target.value)}
                placeholder={t('profile.contactPhone')}
                autoComplete="tel"
              />
              <div className="sm:col-span-2">
                <Input
                  id="ec-relation"
                  name="emergency_contact_relation"
                  label={t('profile.relation')}
                  value={ecRelation}
                  onChange={(e) => setEcRelation(e.target.value)}
                  placeholder={t('profile.relationPlaceholder')}
                />
              </div>
            </div>
          </Card>

          {/* Action buttons */}
          <div className="flex items-center justify-end gap-3 pt-2">
            <Button type="button" variant="ghost" size="md" onClick={handleCancel} disabled={saving}>
              {t('profile.cancel')}
            </Button>
            <Button type="submit" variant="primary" size="md" disabled={saving}>
              {saving ? (
                <span className="flex items-center gap-2">
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  {t('profile.saving')}
                </span>
              ) : (
                t('profile.save')
              )}
            </Button>
          </div>
        </form>
      ) : (
        /* ── View Mode ──────────────────────────────────────────── */
        <div className="space-y-6">
          {/* Profile incomplete banner */}
          {profile && !profile.profile_completed && (
            <Card radius="2xl" shadow="sm" className="p-5 bg-amber-50 border border-amber-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-start gap-3">
                <span className="text-amber-600 text-xl mt-0.5">⚠️</span>
                <div>
                  <p className="font-heading font-bold text-sm text-amber-900">{t('profile.completeBanner')}</p>
                  <p className="text-xs text-amber-700 mt-0.5">
                    {t('profile.completeBannerDesc')}
                  </p>
                </div>
              </div>
              <Button variant="secondary" size="sm" onClick={() => setEditing(true)} className="shrink-0">
                {t('profile.completeNow')}
              </Button>
            </Card>
          )}

          {/* Demographics */}
          <Card radius="2xl" shadow="sm" className="p-6 bg-white border border-surfaceContainerHigh">
            <h2 className="font-heading font-bold text-lg text-textPrimary mb-4 flex items-center gap-2">
              <svg className="w-5 h-5 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" />
              </svg>
              {t('profile.demographics')}
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-textSecondary">{t('profile.name')}</span>
                <p className="text-textPrimary font-medium mt-0.5">{profile?.name || '—'}</p>
              </div>
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-textSecondary">{t('profile.email')}</span>
                <p className="text-textPrimary font-medium mt-0.5">{profile?.email || '—'}</p>
              </div>
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-textSecondary">{t('profile.phone')}</span>
                <p className="text-textPrimary font-medium mt-0.5">{profile?.phone || '—'}</p>
              </div>
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-textSecondary">{t('profile.dob')}</span>
                <p className="text-textPrimary font-medium mt-0.5">
                  {profile?.date_of_birth
                    ? translateDate(new Date(profile.date_of_birth).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }), lang)
                    : t('profile.notSpecified')}
                </p>
              </div>
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-textSecondary">{t('profile.age')}</span>
                <p className="text-textPrimary font-medium mt-0.5">
                  {profile?.age != null ? `${profile.age} ${t('appts.years')}` : '—'}
                </p>
              </div>
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-textSecondary">{t('profile.gender')}</span>
                <p className="text-textPrimary font-medium mt-0.5">{genderLabel(profile?.gender) || t('profile.notSpecified')}</p>
              </div>
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-textSecondary">{t('profile.bloodType')}</span>
                <p className="text-textPrimary font-medium mt-0.5">
                  {profile?.blood_type ? (
                    <span className="font-semibold text-error">{profile.blood_type}</span>
                  ) : (
                    t('profile.notSpecified')
                  )}
                </p>
              </div>
            </div>
          </Card>

          {/* Medical History */}
          <Card radius="2xl" shadow="sm" className="p-6 bg-white border border-surfaceContainerHigh">
            <h2 className="font-heading font-bold text-lg text-textPrimary mb-4 flex items-center gap-2">
              <svg className="w-5 h-5 text-error" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" />
              </svg>
              {t('profile.medicalHistory')}
            </h2>
            <div className="space-y-4">
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-textSecondary">{t('profile.allergies')}</span>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {(profile?.allergies || []).length > 0 ? (
                    profile!.allergies.map((a, i) => (
                      <span key={i} className="bg-errorContainer/40 text-error text-xs px-2.5 py-1 rounded-pill font-medium">
                        {a}
                      </span>
                    ))
                  ) : (
                    <p className="text-textSecondary text-sm">{t('profile.noAllergies')}</p>
                  )}
                </div>
              </div>
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-textSecondary">{t('profile.conditions')}</span>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {(profile?.medical_conditions || []).length > 0 ? (
                    profile!.medical_conditions.map((c, i) => (
                      <span key={i} className="bg-amber-100 text-amber-800 text-xs px-2.5 py-1 rounded-pill font-medium">
                        {c}
                      </span>
                    ))
                  ) : (
                    <p className="text-textSecondary text-sm">{t('profile.noConditions')}</p>
                  )}
                </div>
              </div>
            </div>
          </Card>

          {/* Emergency Contact */}
          <Card radius="2xl" shadow="sm" className="p-6 bg-white border border-surfaceContainerHigh">
            <h2 className="font-heading font-bold text-lg text-textPrimary mb-4 flex items-center gap-2">
              <svg className="w-5 h-5 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 0 0 2.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.59-.147-1.17-.375-1.694-.693l-.368-.221a.75.75 0 0 0-.991.242l-.606.908a1.125 1.125 0 0 1-1.593.28l-.15-.135a9.02 9.02 0 0 1-2.558-3.727l-.064-.156a.75.75 0 0 0-.866-.494l-1.17.293a.75.75 0 0 1-.933-.729V6.75Z" />
              </svg>
              {t('profile.emergencyContact')}
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-textSecondary">{t('profile.name')}</span>
                <p className="text-textPrimary font-medium mt-0.5">{profile?.emergency_contact_name || t('profile.notSpecified')}</p>
              </div>
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-textSecondary">{t('profile.phone')}</span>
                <p className="text-textPrimary font-medium mt-0.5">{profile?.emergency_contact_phone || t('profile.notSpecified')}</p>
              </div>
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-textSecondary">{t('profile.relation')}</span>
                <p className="text-textPrimary font-medium mt-0.5">{profile?.emergency_contact_relation || t('profile.notSpecified')}</p>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};
