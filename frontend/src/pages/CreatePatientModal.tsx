import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { X } from 'lucide-react';
import { createPatient } from '../api/patients';
import type { Gender } from '../api/types';
import Spinner from '../components/Spinner';

interface Props {
  onClose: () => void;
}

export default function CreatePatientModal({ onClose }: Props) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    firstName: '',
    lastName: '',
    ehrId: '',
    age: '',
    gender: 'MALE' as Gender,
  });
  const [error, setError] = useState('');

  const mut = useMutation({
    mutationFn: () =>
      createPatient({ ...form, age: Number(form.age) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['patients'] });
      onClose();
    },
    onError: (err: any) => {
      setError(err.response?.data?.message ?? 'Failed to create patient.');
    },
  });

  const set = (field: string, value: string) =>
    setForm((f) => ({ ...f, [field]: value }));

  const valid =
    form.firstName.trim() &&
    form.lastName.trim() &&
    form.ehrId.trim() &&
    Number(form.age) > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
          <h2 className="text-base font-semibold text-gray-900">New Patient</h2>
          <button onClick={onClose} className="rounded-lg p-1 text-gray-400 hover:bg-gray-100">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form
          className="space-y-4 px-6 py-5"
          onSubmit={(e) => { e.preventDefault(); if (valid) mut.mutate(); }}
        >
          <div className="grid grid-cols-2 gap-3">
            <Field label="First Name" value={form.firstName} onChange={(v) => set('firstName', v)} />
            <Field label="Last Name" value={form.lastName} onChange={(v) => set('lastName', v)} />
          </div>
          <Field label="EHR ID" value={form.ehrId} onChange={(v) => set('ehrId', v)} placeholder="e.g. EHR-00042" mono />
          <div className="grid grid-cols-2 gap-3">
            <Field label="Age" value={form.age} onChange={(v) => set('age', v)} type="number" min={0} max={150} />
            <div>
              <label className="mb-1.5 block text-sm font-medium text-gray-700">Gender</label>
              <select
                value={form.gender}
                onChange={(e) => set('gender', e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              >
                <option value="MALE">Male</option>
                <option value="FEMALE">Female</option>
                <option value="OTHER">Other</option>
              </select>
            </div>
          </div>

          {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

          <div className="flex justify-end gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!valid || mut.isPending}
              className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {mut.isPending && <Spinner size="sm" />}
              Create
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Field({
  label, value, onChange, type = 'text', placeholder, mono, min, max,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
  mono?: boolean;
  min?: number;
  max?: number;
}) {
  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-gray-700">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        min={min}
        max={max}
        className={`w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 ${mono ? 'font-mono' : ''}`}
      />
    </div>
  );
}
