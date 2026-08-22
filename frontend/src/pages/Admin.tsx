import React, { useState } from 'react';
import { Card, Button, Badge, Input } from '../components/ui';
import { useAuth } from '../context/AuthContext';

type AdminTab = 'doctors' | 'applications' | 'clinics';

interface Doctor {
  id: string;
  name: string;
  email: string;
  specialization: string;
  clinicId: string;
  clinicName: string;
  fee: number;
  rating: number;
  reviewCount: number;
  maxPatientsPerDay: number;
  status: 'Active' | 'Inactive';
}

interface DoctorApplication {
  id: string;
  name: string;
  email: string;
  phone: string;
  specialization: string;
  medicalLicense: string;
  yearsOfExperience: number;
  submittedDate: string;
  status: 'Pending';
}

interface Clinic {
  id: string;
  name: string;
  address: string;
  city: string;
  phone: string;
  email: string;
  workingHoursStart: string;
  workingHoursEnd: string;
  workingDays: string[];
  status: 'Active' | 'Inactive';
}

const initialClinics: Clinic[] = [
  {
    id: 'CLN-1',
    name: 'MediBook Central Care',
    address: '120 Broadway Ave, Suite 400',
    city: 'New York',
    phone: '+1 (212) 555-0140',
    email: 'central@medibook.com',
    workingHoursStart: '08:00 AM',
    workingHoursEnd: '06:00 PM',
    workingDays: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
    status: 'Active',
  },
  {
    id: 'CLN-2',
    name: 'Metro Health Cardiology Center',
    address: '450 Medical Center Blvd, Suite 300',
    city: 'New York',
    phone: '+1 (212) 555-0199',
    email: 'cardiology@metrohealth.com',
    workingHoursStart: '08:30 AM',
    workingHoursEnd: '05:30 PM',
    workingDays: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
    status: 'Active',
  },
  {
    id: 'CLN-3',
    name: 'Apex Respiratory & Health Clinic',
    address: '88 Park Plaza, Suite 210',
    city: 'Brooklyn',
    phone: '+1 (718) 555-0182',
    email: 'contact@apexrespiratory.com',
    workingHoursStart: '09:00 AM',
    workingHoursEnd: '05:00 PM',
    workingDays: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
    status: 'Active',
  },
];

const initialDoctors: Doctor[] = [
  {
    id: 'DOC-1',
    name: 'Dr. Marcus Vance, MD',
    email: 'marcus.vance@metrohealth.com',
    specialization: 'Cardiology & Vascular Medicine',
    clinicId: 'CLN-2',
    clinicName: 'Metro Health Cardiology Center',
    fee: 120,
    rating: 4.9,
    reviewCount: 142,
    maxPatientsPerDay: 16,
    status: 'Active',
  },
  {
    id: 'DOC-2',
    name: 'Dr. Sarah Lin, MD',
    email: 'sarah.lin@medibook.com',
    specialization: 'Internal Medicine & General Physician',
    clinicId: 'CLN-1',
    clinicName: 'MediBook Central Care',
    fee: 95,
    rating: 4.9,
    reviewCount: 198,
    maxPatientsPerDay: 20,
    status: 'Active',
  },
  {
    id: 'DOC-3',
    name: 'Dr. David Sterling, MD',
    email: 'david.sterling@apexrespiratory.com',
    specialization: 'Pulmonology & Respiratory Care',
    clinicId: 'CLN-3',
    clinicName: 'Apex Respiratory & Health Clinic',
    fee: 130,
    rating: 4.8,
    reviewCount: 88,
    maxPatientsPerDay: 14,
    status: 'Active',
  },
  {
    id: 'DOC-4',
    name: 'Dr. Emily Thorne, MD',
    email: 'emily.thorne@medibook.com',
    specialization: 'Neurology & Sleep Medicine',
    clinicId: 'CLN-1',
    clinicName: 'MediBook Central Care',
    fee: 150,
    rating: 5.0,
    reviewCount: 76,
    maxPatientsPerDay: 12,
    status: 'Active',
  },
  {
    id: 'DOC-5',
    name: 'Dr. Robert Chen, MD',
    email: 'robert.chen@medibook.com',
    specialization: 'Dermatology & Skin Surgery',
    clinicId: 'CLN-1',
    clinicName: 'MediBook Central Care',
    fee: 110,
    rating: 4.7,
    reviewCount: 104,
    maxPatientsPerDay: 18,
    status: 'Inactive',
  },
];

const initialApplications: DoctorApplication[] = [
  {
    id: 'APP-101',
    name: 'Dr. Lisa Wang, MD',
    email: 'lisa.wang@endocare.org',
    phone: '+1 (555) 928-1092',
    specialization: 'Endocrinology & Diabetes',
    medicalLicense: 'NY-MED-849201',
    yearsOfExperience: 11,
    submittedDate: 'Oct 21, 2026',
    status: 'Pending',
  },
  {
    id: 'APP-102',
    name: 'Dr. James Sterling, MD',
    email: 'james.sterling@psychiatry.com',
    phone: '+1 (555) 819-4820',
    specialization: 'Psychiatry & Behavioral Health',
    medicalLicense: 'NY-MED-772190',
    yearsOfExperience: 8,
    submittedDate: 'Oct 22, 2026',
    status: 'Pending',
  },
  {
    id: 'APP-103',
    name: 'Dr. Priya Patel, MD',
    email: 'priya.patel@oncocare.com',
    phone: '+1 (555) 672-9182',
    specialization: 'Medical Oncology & Hematology',
    medicalLicense: 'NY-MED-994102',
    yearsOfExperience: 14,
    submittedDate: 'Oct 23, 2026',
    status: 'Pending',
  },
];

const DAYS_OF_WEEK = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export const Admin: React.FC = () => {
  const { currentUser } = useAuth();

  // Active Tab
  const [activeTab, setActiveTab] = useState<AdminTab>('doctors');

  // Lists State
  const [doctors, setDoctors] = useState<Doctor[]>(initialDoctors);
  const [applications, setApplications] = useState<DoctorApplication[]>(initialApplications);
  const [clinics, setClinics] = useState<Clinic[]>(initialClinics);

  // Toast State
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Doctor Modal State
  const [isDoctorModalOpen, setIsDoctorModalOpen] = useState(false);
  const [editingDoctor, setEditingDoctor] = useState<Doctor | null>(null);
  const [doctorForm, setDoctorForm] = useState({
    name: '',
    email: '',
    specialization: '',
    fee: 100,
    clinicId: initialClinics[0]?.id || '',
    maxPatientsPerDay: 16,
  });

  // Clinic Modal State
  const [isClinicModalOpen, setIsClinicModalOpen] = useState(false);
  const [editingClinic, setEditingClinic] = useState<Clinic | null>(null);
  const [clinicForm, setClinicForm] = useState({
    name: '',
    address: '',
    city: 'New York',
    phone: '',
    email: '',
    workingHoursStart: '08:00 AM',
    workingHoursEnd: '06:00 PM',
    workingDays: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
  });

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  // --- Doctor Actions ---
  const handleOpenAddDoctor = () => {
    setEditingDoctor(null);
    setDoctorForm({
      name: '',
      email: '',
      specialization: '',
      fee: 100,
      clinicId: clinics[0]?.id || '',
      maxPatientsPerDay: 16,
    });
    setIsDoctorModalOpen(true);
  };

  const handleOpenEditDoctor = (doc: Doctor) => {
    setEditingDoctor(doc);
    setDoctorForm({
      name: doc.name,
      email: doc.email,
      specialization: doc.specialization,
      fee: doc.fee,
      clinicId: doc.clinicId,
      maxPatientsPerDay: doc.maxPatientsPerDay,
    });
    setIsDoctorModalOpen(true);
  };

  const handleSaveDoctor = (e: React.FormEvent) => {
    e.preventDefault();
    if (!doctorForm.name.trim() || !doctorForm.email.trim() || !doctorForm.specialization.trim()) {
      alert('Please fill in all required doctor fields.');
      return;
    }

    const clinicObj = clinics.find((c) => c.id === doctorForm.clinicId) || clinics[0];

    if (editingDoctor) {
      // Edit existing
      setDoctors((prev) =>
        prev.map((d) =>
          d.id === editingDoctor.id
            ? {
                ...d,
                name: doctorForm.name.trim(),
                email: doctorForm.email.trim(),
                specialization: doctorForm.specialization.trim(),
                fee: Number(doctorForm.fee),
                clinicId: clinicObj?.id || d.clinicId,
                clinicName: clinicObj?.name || d.clinicName,
                maxPatientsPerDay: Number(doctorForm.maxPatientsPerDay),
              }
            : d
        )
      );
      showToast(`Updated doctor record for ${doctorForm.name}.`);
    } else {
      // Add new
      const newDoc: Doctor = {
        id: `DOC-${Date.now().toString().slice(-4)}`,
        name: doctorForm.name.trim(),
        email: doctorForm.email.trim(),
        specialization: doctorForm.specialization.trim(),
        clinicId: clinicObj?.id || 'CLN-1',
        clinicName: clinicObj?.name || 'MediBook Central Care',
        fee: Number(doctorForm.fee),
        rating: 5.0,
        reviewCount: 0,
        maxPatientsPerDay: Number(doctorForm.maxPatientsPerDay),
        status: 'Active',
      };
      setDoctors((prev) => [newDoc, ...prev]);
      showToast(`Doctor ${newDoc.name} successfully added to clinic roster.`);
    }

    setIsDoctorModalOpen(false);
  };

  const handleToggleDoctorStatus = (id: string) => {
    setDoctors((prev) =>
      prev.map((d) => {
        if (d.id === id) {
          const newStatus = d.status === 'Active' ? 'Inactive' : 'Active';
          showToast(`Doctor ${d.name} marked as ${newStatus}.`);
          return { ...d, status: newStatus };
        }
        return d;
      })
    );
  };

  // --- Doctor Application Actions ---
  const handleApproveApplication = (app: DoctorApplication) => {
    // 1. Remove from pending list
    setApplications((prev) => prev.filter((a) => a.id !== app.id));

    // 2. Automatically create active doctor
    const newDoc: Doctor = {
      id: `DOC-${Date.now().toString().slice(-4)}`,
      name: app.name,
      email: app.email,
      specialization: app.specialization,
      clinicId: clinics[0]?.id || 'CLN-1',
      clinicName: clinics[0]?.name || 'MediBook Central Care',
      fee: 110,
      rating: 5.0,
      reviewCount: 0,
      maxPatientsPerDay: 16,
      status: 'Active',
    };
    setDoctors((prev) => [newDoc, ...prev]);

    showToast(`Doctor ${app.name} approved! Account created and added to active directory.`);
  };

  const handleRejectApplication = (app: DoctorApplication) => {
    if (window.confirm(`Are you sure you want to reject the application for ${app.name}?`)) {
      setApplications((prev) => prev.filter((a) => a.id !== app.id));
      showToast(`Application for ${app.name} rejected.`);
    }
  };

  // --- Clinic Actions ---
  const handleOpenAddClinic = () => {
    setEditingClinic(null);
    setClinicForm({
      name: '',
      address: '',
      city: 'New York',
      phone: '',
      email: '',
      workingHoursStart: '08:00 AM',
      workingHoursEnd: '06:00 PM',
      workingDays: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
    });
    setIsClinicModalOpen(true);
  };

  const handleOpenEditClinic = (clinic: Clinic) => {
    setEditingClinic(clinic);
    setClinicForm({
      name: clinic.name,
      address: clinic.address,
      city: clinic.city,
      phone: clinic.phone,
      email: clinic.email,
      workingHoursStart: clinic.workingHoursStart,
      workingHoursEnd: clinic.workingHoursEnd,
      workingDays: clinic.workingDays,
    });
    setIsClinicModalOpen(true);
  };

  const handleToggleWorkingDay = (day: string) => {
    setClinicForm((prev) => {
      const exists = prev.workingDays.includes(day);
      if (exists) {
        return { ...prev, workingDays: prev.workingDays.filter((d) => d !== day) };
      }
      return { ...prev, workingDays: [...prev.workingDays, day] };
    });
  };

  const handleSaveClinic = (e: React.FormEvent) => {
    e.preventDefault();
    if (!clinicForm.name.trim() || !clinicForm.address.trim() || !clinicForm.city.trim()) {
      alert('Please fill in clinic name, address, and city.');
      return;
    }

    if (editingClinic) {
      setClinics((prev) =>
        prev.map((c) =>
          c.id === editingClinic.id
            ? {
                ...c,
                name: clinicForm.name.trim(),
                address: clinicForm.address.trim(),
                city: clinicForm.city.trim(),
                phone: clinicForm.phone.trim(),
                email: clinicForm.email.trim(),
                workingHoursStart: clinicForm.workingHoursStart,
                workingHoursEnd: clinicForm.workingHoursEnd,
                workingDays: clinicForm.workingDays,
              }
            : c
        )
      );
      showToast(`Clinic facility "${clinicForm.name}" updated.`);
    } else {
      const newClinic: Clinic = {
        id: `CLN-${Date.now().toString().slice(-4)}`,
        name: clinicForm.name.trim(),
        address: clinicForm.address.trim(),
        city: clinicForm.city.trim(),
        phone: clinicForm.phone.trim(),
        email: clinicForm.email.trim(),
        workingHoursStart: clinicForm.workingHoursStart,
        workingHoursEnd: clinicForm.workingHoursEnd,
        workingDays: clinicForm.workingDays,
        status: 'Active',
      };
      setClinics((prev) => [...prev, newClinic]);
      showToast(`New clinic "${newClinic.name}" added successfully.`);
    }

    setIsClinicModalOpen(false);
  };

  const activeDoctorsCount = doctors.filter((d) => d.status === 'Active').length;

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-12 space-y-10">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="p-4 bg-surfaceContainer border border-primaryContainer/30 rounded-2xl shadow-soft-sm flex items-center justify-between animate-fadeIn">
          <div className="flex items-center gap-2.5">
            <span className="w-2.5 h-2.5 rounded-full bg-secondary animate-pulse" />
            <p className="text-sm font-medium text-textPrimary">{toastMessage}</p>
          </div>
          <button
            onClick={() => setToastMessage(null)}
            className="text-xs font-semibold text-textSecondary hover:text-textPrimary"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* 1. Header with Admin name */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-surfaceContainerHigh">
        <div>
          <div className="inline-flex items-center gap-2 mb-1.5">
            <Badge status="primary" size="sm" withDot>
              Admin Portal
            </Badge>
            <span className="text-xs text-textSecondary">
              Logged in as <strong>{currentUser?.name || 'Administrator'}</strong>
            </span>
          </div>
          <h1 className="font-heading font-extrabold text-3xl sm:text-4xl text-textPrimary tracking-tight">
            Admin Dashboard
          </h1>
          <p className="text-sm sm:text-base text-textSecondary mt-1">
            Manage doctors, clinics, review doctor applications, and view clinical performance metrics.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Badge status="success" size="md">
            System Online
          </Badge>
        </div>
      </div>

      {/* 2. Analytics Summary Row (4 Stat Cards) */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
        <Card radius="2xl" shadow="sm" className="p-5 bg-white border border-surfaceContainerHigh">
          <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-textSecondary">
            <span>Appointments Today</span>
            <span>📅</span>
          </div>
          <div className="mt-3">
            <span className="font-heading font-extrabold text-3xl text-textPrimary">42</span>
            <p className="text-[11px] text-textSecondary mt-0.5">+14% vs yesterday</p>
          </div>
        </Card>

        <Card radius="2xl" shadow="sm" className="p-5 bg-white border border-surfaceContainerHigh">
          <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-textSecondary">
            <span>No-show Rate %</span>
            <span>📉</span>
          </div>
          <div className="mt-3">
            <span className="font-heading font-extrabold text-3xl text-secondary">4.8%</span>
            <p className="text-[11px] text-textSecondary mt-0.5">Below 5% threshold</p>
          </div>
        </Card>

        <Card radius="2xl" shadow="sm" className="p-5 bg-white border border-surfaceContainerHigh">
          <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-textSecondary">
            <span>Average Rating</span>
            <span>⭐</span>
          </div>
          <div className="mt-3">
            <span className="font-heading font-extrabold text-3xl text-amber-500">4.9</span>
            <p className="text-[11px] text-textSecondary mt-0.5">Across 608 patient reviews</p>
          </div>
        </Card>

        <Card radius="2xl" shadow="sm" className="p-5 bg-white border border-surfaceContainerHigh">
          <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-textSecondary">
            <span>Total Active Doctors</span>
            <span>🩺</span>
          </div>
          <div className="mt-3">
            <span className="font-heading font-extrabold text-3xl text-primary">{activeDoctorsCount}</span>
            <p className="text-[11px] text-textSecondary mt-0.5">In {clinics.length} network facilities</p>
          </div>
        </Card>
      </div>

      {/* 3. Pill Tab Navigation */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-none border-b border-surfaceContainerHigh">
        <button
          type="button"
          onClick={() => setActiveTab('doctors')}
          className={`px-5 py-2.5 rounded-pill text-xs font-semibold whitespace-nowrap transition-all duration-200 focus:outline-none ${
            activeTab === 'doctors'
              ? 'bg-primary text-white shadow-soft-sm'
              : 'bg-white text-textSecondary hover:text-textPrimary hover:bg-surfaceContainer border border-surfaceContainerHigh'
          }`}
        >
          Doctors ({doctors.length})
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('applications')}
          className={`px-5 py-2.5 rounded-pill text-xs font-semibold whitespace-nowrap transition-all duration-200 focus:outline-none flex items-center gap-2 ${
            activeTab === 'applications'
              ? 'bg-primary text-white shadow-soft-sm'
              : 'bg-white text-textSecondary hover:text-textPrimary hover:bg-surfaceContainer border border-surfaceContainerHigh'
          }`}
        >
          <span>Doctor Applications</span>
          {applications.length > 0 && (
            <span
              className={`text-[10px] font-bold px-1.5 py-0.2 rounded-full ${
                activeTab === 'applications'
                  ? 'bg-white text-primary'
                  : 'bg-amber-100 text-amber-800'
              }`}
            >
              {applications.length}
            </span>
          )}
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('clinics')}
          className={`px-5 py-2.5 rounded-pill text-xs font-semibold whitespace-nowrap transition-all duration-200 focus:outline-none ${
            activeTab === 'clinics'
              ? 'bg-primary text-white shadow-soft-sm'
              : 'bg-white text-textSecondary hover:text-textPrimary hover:bg-surfaceContainer border border-surfaceContainerHigh'
          }`}
        >
          Clinics ({clinics.length})
        </button>
      </div>

      {/* 4. Tab Content */}

      {/* TAB 1: DOCTORS */}
      {activeTab === 'doctors' && (
        <section className="space-y-4 animate-fadeIn">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="font-heading font-bold text-xl text-textPrimary tracking-tight">
                Physicians & Clinical Staff
              </h2>
              <p className="text-xs text-textSecondary">
                Manage registered doctors, consultation fees, and facility assignments.
              </p>
            </div>

            <Button variant="primary" size="md" onClick={handleOpenAddDoctor}>
              + Add Doctor
            </Button>
          </div>

          <Card radius="2xl" shadow="sm" className="p-0 bg-white border border-surfaceContainerHigh overflow-hidden">
            {/* Desktop Table View */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-surfaceContainer/80 border-b border-surfaceContainerHigh text-textSecondary uppercase font-bold text-[10px] tracking-wider">
                  <tr>
                    <th className="py-3.5 px-6">Doctor</th>
                    <th className="py-3.5 px-4">Specialization</th>
                    <th className="py-3.5 px-4">Clinic Facility</th>
                    <th className="py-3.5 px-4">Fee / Slot</th>
                    <th className="py-3.5 px-4">Rating</th>
                    <th className="py-3.5 px-4">Status</th>
                    <th className="py-3.5 px-6 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surfaceContainerHigh">
                  {doctors.map((doc) => (
                    <tr key={doc.id} className="hover:bg-surfaceContainer/30 transition-colors">
                      <td className="py-4 px-6">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-xl bg-surfaceContainer text-primary border border-surfaceContainerHigh flex items-center justify-center font-bold text-xs shrink-0">
                            {doc.name.split(' ')[1]?.charAt(0) || 'Dr'}
                          </div>
                          <div>
                            <p className="font-heading font-bold text-textPrimary text-sm">{doc.name}</p>
                            <p className="text-textSecondary text-[11px]">{doc.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="py-4 px-4 text-textSecondary font-medium">
                        {doc.specialization}
                      </td>
                      <td className="py-4 px-4 text-textSecondary">
                        {doc.clinicName}
                      </td>
                      <td className="py-4 px-4 font-bold text-primary">
                        ${doc.fee}
                      </td>
                      <td className="py-4 px-4 text-amber-500 font-semibold">
                        ★ {doc.rating} <span className="text-textSecondary text-[11px] font-normal">({doc.reviewCount})</span>
                      </td>
                      <td className="py-4 px-4">
                        <Badge status={doc.status === 'Active' ? 'success' : 'neutral'} size="sm" withDot>
                          {doc.status}
                        </Badge>
                      </td>
                      <td className="py-4 px-6 text-right space-x-2">
                        <button
                          type="button"
                          onClick={() => handleOpenEditDoctor(doc)}
                          className="px-2.5 py-1 rounded-pill text-xs font-semibold text-primary hover:bg-surfaceContainer transition-colors"
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => handleToggleDoctorStatus(doc.id)}
                          className={`px-2.5 py-1 rounded-pill text-xs font-semibold transition-colors ${
                            doc.status === 'Active'
                              ? 'text-error hover:bg-errorContainer/30'
                              : 'text-secondary hover:bg-secondaryContainer/30'
                          }`}
                        >
                          {doc.status === 'Active' ? 'Deactivate' : 'Activate'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile Stacked Card View */}
            <div className="md:hidden divide-y divide-surfaceContainerHigh">
              {doctors.map((doc) => (
                <div key={doc.id} className="p-5 space-y-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2.5">
                      <div className="w-10 h-10 rounded-xl bg-surfaceContainer text-primary flex items-center justify-center font-bold text-xs shrink-0">
                        {doc.name.split(' ')[1]?.charAt(0) || 'Dr'}
                      </div>
                      <div>
                        <h4 className="font-heading font-bold text-textPrimary text-sm">{doc.name}</h4>
                        <p className="text-xs text-secondary font-medium">{doc.specialization}</p>
                      </div>
                    </div>
                    <Badge status={doc.status === 'Active' ? 'success' : 'neutral'} size="sm" withDot>
                      {doc.status}
                    </Badge>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs text-textSecondary bg-surfaceContainer p-3 rounded-xl">
                    <p>📍 {doc.clinicName}</p>
                    <p className="text-right font-bold text-primary">${doc.fee} / consultation</p>
                    <p className="text-amber-500">★ {doc.rating} ({doc.reviewCount} reviews)</p>
                    <p className="text-right">Max: {doc.maxPatientsPerDay} patients/day</p>
                  </div>

                  <div className="flex items-center justify-end gap-2 pt-1">
                    <Button size="sm" variant="ghost" onClick={() => handleOpenEditDoctor(doc)}>
                      Edit
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className={doc.status === 'Active' ? 'text-error border-error/30' : 'text-secondary border-secondary/30'}
                      onClick={() => handleToggleDoctorStatus(doc.id)}
                    >
                      {doc.status === 'Active' ? 'Deactivate' : 'Activate'}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </section>
      )}

      {/* TAB 2: DOCTOR APPLICATIONS */}
      {activeTab === 'applications' && (
        <section className="space-y-4 animate-fadeIn">
          <div>
            <h2 className="font-heading font-bold text-xl text-textPrimary tracking-tight">
              Pending Doctor Applications
            </h2>
            <p className="text-xs text-textSecondary">
              Review credential submissions from newly registered doctors awaiting verification.
            </p>
          </div>

          {applications.length > 0 ? (
            <div className="space-y-4">
              {applications.map((app) => (
                <Card
                  key={app.id}
                  radius="2xl"
                  shadow="sm"
                  className="p-6 bg-white border border-surfaceContainerHigh hover:border-amber-300 transition-all space-y-4"
                >
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div className="flex items-start gap-4">
                      <div className="w-12 h-12 rounded-2xl bg-amber-100 text-amber-800 border border-amber-200 flex items-center justify-center font-bold text-lg shrink-0">
                        🩺
                      </div>
                      <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2.5">
                          <h3 className="font-heading font-bold text-lg text-textPrimary">
                            {app.name}
                          </h3>
                          <span className="bg-amber-100 text-amber-800 border border-amber-300 text-[10px] font-bold uppercase px-2.5 py-0.5 rounded-pill">
                            Pending Review
                          </span>
                        </div>
                        <p className="text-xs font-semibold text-secondary">{app.specialization}</p>

                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-y-1 gap-x-4 pt-1 text-xs text-textSecondary">
                          <p>✉️ {app.email}</p>
                          <p>📞 {app.phone}</p>
                          <p>📅 Submitted: {app.submittedDate}</p>
                        </div>
                      </div>
                    </div>

                    {/* Approve / Reject Actions */}
                    <div className="flex items-center gap-2.5 shrink-0 pt-2 md:pt-0 border-t md:border-t-0 border-surfaceContainerHigh">
                      <button
                        type="button"
                        onClick={() => handleApproveApplication(app)}
                        className="px-4 py-2 rounded-pill text-xs font-semibold bg-[#006B5F] hover:bg-[#005249] text-white shadow-soft-sm transition-all"
                      >
                        ✓ Approve Application
                      </button>
                      <button
                        type="button"
                        onClick={() => handleRejectApplication(app)}
                        className="px-4 py-2 rounded-pill text-xs font-semibold bg-white border border-error text-error hover:bg-errorContainer transition-all"
                      >
                        ✕ Reject
                      </button>
                    </div>
                  </div>

                  <div className="p-3 bg-surfaceContainer rounded-xl text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-textSecondary">
                    <div>
                      <strong className="text-textPrimary">Medical License ID:</strong>{' '}
                      <code className="bg-white px-2 py-0.5 rounded font-mono text-primary border border-surfaceContainerHigh">
                        {app.medicalLicense}
                      </code>
                    </div>
                    <div>
                      <strong className="text-textPrimary">Clinical Experience:</strong> {app.yearsOfExperience} Years Practice
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          ) : (
            <Card radius="2xl" shadow="sm" className="p-10 text-center bg-white border border-surfaceContainerHigh space-y-3">
              <div className="w-12 h-12 rounded-2xl bg-secondaryContainer/40 text-secondary mx-auto flex items-center justify-center text-xl">
                ✓
              </div>
              <h3 className="font-heading font-bold text-base text-textPrimary">
                No Pending Applications
              </h3>
              <p className="text-xs text-textSecondary max-w-sm mx-auto">
                All submitted doctor credentials have been processed and verified.
              </p>
            </Card>
          )}
        </section>
      )}

      {/* TAB 3: CLINICS */}
      {activeTab === 'clinics' && (
        <section className="space-y-4 animate-fadeIn">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="font-heading font-bold text-xl text-textPrimary tracking-tight">
                Clinic Facilities & Network
              </h2>
              <p className="text-xs text-textSecondary">
                Manage partner hospital buildings, operating hours, and location data.
              </p>
            </div>

            <Button variant="primary" size="md" onClick={handleOpenAddClinic}>
              + Add Clinic
            </Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {clinics.map((clinic) => (
              <Card
                key={clinic.id}
                radius="2xl"
                shadow="sm"
                className="p-6 bg-white border border-surfaceContainerHigh flex flex-col justify-between space-y-4"
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="w-10 h-10 rounded-xl bg-surfaceContainer text-primary flex items-center justify-center font-bold">
                      🏥
                    </div>
                    <Badge status="success" size="sm" withDot>
                      {clinic.status}
                    </Badge>
                  </div>

                  <h3 className="font-heading font-bold text-base text-textPrimary">
                    {clinic.name}
                  </h3>
                  <p className="text-xs text-secondary font-medium mt-0.5">{clinic.city}</p>

                  <div className="space-y-1.5 text-xs text-textSecondary mt-3 pt-3 border-t border-surfaceContainerHigh">
                    <p>📍 {clinic.address}</p>
                    <p>📞 {clinic.phone}</p>
                    <p>✉️ {clinic.email}</p>
                    <p>⏰ {clinic.workingHoursStart} – {clinic.workingHoursEnd}</p>
                  </div>

                  <div className="mt-3">
                    <span className="text-[10px] uppercase font-bold tracking-wider text-textSecondary block mb-1">
                      Working Days:
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {clinic.workingDays.map((d) => (
                        <span
                          key={d}
                          className="bg-surfaceContainer text-textPrimary text-[10px] font-semibold px-2 py-0.5 rounded-md border border-surfaceContainerHigh"
                        >
                          {d}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="pt-4 border-t border-surfaceContainerHigh flex justify-end">
                  <Button size="sm" variant="secondary" onClick={() => handleOpenEditClinic(clinic)}>
                    Edit Clinic
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        </section>
      )}

      {/* --- ADD / EDIT DOCTOR MODAL --- */}
      {isDoctorModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto animate-fadeIn">
          <div className="w-full max-w-lg">
            <Card radius="3xl" shadow="lg" className="p-7 bg-white border border-surfaceContainerHigh space-y-5">
              <div className="flex items-center justify-between border-b border-surfaceContainerHigh pb-3">
                <h3 className="font-heading font-bold text-xl text-textPrimary">
                  {editingDoctor ? 'Edit Doctor Profile' : 'Add New Doctor'}
                </h3>
                <button
                  onClick={() => setIsDoctorModalOpen(false)}
                  className="p-1 rounded-pill text-textSecondary hover:text-textPrimary"
                >
                  ✕
                </button>
              </div>

              <form onSubmit={handleSaveDoctor} className="space-y-4">
                <Input
                  label="Full Name & Title"
                  placeholder="e.g. Dr. Jane Sterling, MD"
                  value={doctorForm.name}
                  onChange={(e) => setDoctorForm({ ...doctorForm, name: e.target.value })}
                  required
                />

                <Input
                  label="Email Address"
                  type="email"
                  placeholder="doctor@clinic.com"
                  value={doctorForm.email}
                  onChange={(e) => setDoctorForm({ ...doctorForm, email: e.target.value })}
                  required
                />

                <Input
                  label="Specialization"
                  placeholder="e.g. Cardiology & Vascular Medicine"
                  value={doctorForm.specialization}
                  onChange={(e) => setDoctorForm({ ...doctorForm, specialization: e.target.value })}
                  required
                />

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <Input
                    label="Consultation Fee ($)"
                    type="number"
                    min={0}
                    value={doctorForm.fee}
                    onChange={(e) => setDoctorForm({ ...doctorForm, fee: Number(e.target.value) })}
                    required
                  />

                  <Input
                    label="Max Patients / Day"
                    type="number"
                    min={1}
                    max={50}
                    value={doctorForm.maxPatientsPerDay}
                    onChange={(e) => setDoctorForm({ ...doctorForm, maxPatientsPerDay: Number(e.target.value) })}
                    required
                  />
                </div>

                {/* Clinic Facility Dropdown */}
                <div className="space-y-1.5">
                  <label className="text-sm font-semibold text-textPrimary">Assigned Clinic Facility</label>
                  <select
                    value={doctorForm.clinicId}
                    onChange={(e) => setDoctorForm({ ...doctorForm, clinicId: e.target.value })}
                    className="w-full rounded-xl bg-surfaceContainer text-textPrimary text-sm border border-outline/40 h-11 px-4 outline-none focus:bg-white focus:border-primary focus:ring-4 focus:ring-primary/15"
                  >
                    {clinics.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} ({c.city})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="pt-3 flex items-center justify-end gap-2.5">
                  <Button type="button" variant="ghost" onClick={() => setIsDoctorModalOpen(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" variant="primary">
                    {editingDoctor ? 'Save Changes' : 'Create Doctor'}
                  </Button>
                </div>
              </form>
            </Card>
          </div>
        </div>
      )}

      {/* --- ADD / EDIT CLINIC MODAL --- */}
      {isClinicModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto animate-fadeIn">
          <div className="w-full max-w-lg">
            <Card radius="3xl" shadow="lg" className="p-7 bg-white border border-surfaceContainerHigh space-y-5">
              <div className="flex items-center justify-between border-b border-surfaceContainerHigh pb-3">
                <h3 className="font-heading font-bold text-xl text-textPrimary">
                  {editingClinic ? 'Edit Clinic Facility' : 'Add New Clinic Facility'}
                </h3>
                <button
                  onClick={() => setIsClinicModalOpen(false)}
                  className="p-1 rounded-pill text-textSecondary hover:text-textPrimary"
                >
                  ✕
                </button>
              </div>

              <form onSubmit={handleSaveClinic} className="space-y-4">
                <Input
                  label="Clinic Facility Name"
                  placeholder="e.g. Eastside Medical Hub"
                  value={clinicForm.name}
                  onChange={(e) => setClinicForm({ ...clinicForm, name: e.target.value })}
                  required
                />

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <Input
                    label="Street Address"
                    placeholder="e.g. 500 Park Ave, Suite 100"
                    value={clinicForm.address}
                    onChange={(e) => setClinicForm({ ...clinicForm, address: e.target.value })}
                    required
                  />

                  <Input
                    label="City"
                    placeholder="e.g. New York"
                    value={clinicForm.city}
                    onChange={(e) => setClinicForm({ ...clinicForm, city: e.target.value })}
                    required
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <Input
                    label="Phone Number"
                    placeholder="+1 (555) 012-3456"
                    value={clinicForm.phone}
                    onChange={(e) => setClinicForm({ ...clinicForm, phone: e.target.value })}
                  />

                  <Input
                    label="Email"
                    type="email"
                    placeholder="clinic@medibook.com"
                    value={clinicForm.email}
                    onChange={(e) => setClinicForm({ ...clinicForm, email: e.target.value })}
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <Input
                    label="Opening Time"
                    placeholder="08:00 AM"
                    value={clinicForm.workingHoursStart}
                    onChange={(e) => setClinicForm({ ...clinicForm, workingHoursStart: e.target.value })}
                    required
                  />

                  <Input
                    label="Closing Time"
                    placeholder="06:00 PM"
                    value={clinicForm.workingHoursEnd}
                    onChange={(e) => setClinicForm({ ...clinicForm, workingHoursEnd: e.target.value })}
                    required
                  />
                </div>

                {/* Working Days Checkboxes */}
                <div className="space-y-1.5">
                  <label className="text-xs font-bold uppercase tracking-wider text-textSecondary block">
                    Working Days
                  </label>
                  <div className="flex flex-wrap gap-1.5">
                    {DAYS_OF_WEEK.map((day) => {
                      const isChecked = clinicForm.workingDays.includes(day);
                      return (
                        <button
                          key={day}
                          type="button"
                          onClick={() => handleToggleWorkingDay(day)}
                          className={`px-3 py-1 rounded-pill text-xs font-semibold border transition-all ${
                            isChecked
                              ? 'bg-primary text-white border-primary shadow-soft-sm'
                              : 'bg-surfaceContainer text-textSecondary border-outline/40 hover:bg-surfaceContainerHigh'
                          }`}
                        >
                          {day}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="pt-3 flex items-center justify-end gap-2.5">
                  <Button type="button" variant="ghost" onClick={() => setIsClinicModalOpen(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" variant="primary">
                    {editingClinic ? 'Save Changes' : 'Create Clinic'}
                  </Button>
                </div>
              </form>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
};
