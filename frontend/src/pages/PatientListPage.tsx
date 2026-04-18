import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Plus, Search, Trash2, Users, ChevronLeft, ChevronRight } from 'lucide-react';
import { getPatients, deletePatient } from '../api/patients';
import type { Patient } from '../api/types';
import Spinner from '../components/Spinner';
import Badge from '../components/Badge';
import EmptyState from '../components/EmptyState';
import ConfirmDialog from '../components/ConfirmDialog';
import CreatePatientModal from './CreatePatientModal';

const genderColor = { MALE: 'blue', FEMALE: 'purple', OTHER: 'gray' } as const;

export default function PatientListPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [toDelete, setToDelete] = useState<Patient | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['patients', page],
    queryFn: () => getPatients(page, 20),
  });

  const deleteMut = useMutation({
    mutationFn: (ehrId: string) => deletePatient(ehrId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['patients'] });
      setToDelete(null);
    },
  });

  const patients = data?.content ?? [];
  const filtered = search
    ? patients.filter(
        (p) =>
          `${p.firstName} ${p.lastName}`.toLowerCase().includes(search.toLowerCase()) ||
          p.ehrId.toLowerCase().includes(search.toLowerCase()),
      )
    : patients;

  return (
    <div>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Patients</h1>
          {data && (
            <p className="mt-0.5 text-sm text-gray-500">{data.totalElements} total</p>
          )}
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-brand-700"
        >
          <Plus className="h-4 w-4" />
          New Patient
        </button>
      </div>

      <div className="mb-4 flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-3 py-2 shadow-sm">
        <Search className="h-4 w-4 shrink-0 text-gray-400" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by name or EHR ID…"
          className="w-full bg-transparent text-sm outline-none placeholder:text-gray-400"
        />
      </div>

      {isLoading ? (
        <div className="flex justify-center py-20">
          <Spinner />
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Users}
          title="No patients found"
          description={search ? 'Try a different search term.' : 'Create your first patient to get started.'}
          action={
            !search ? (
              <button
                onClick={() => setShowCreate(true)}
                className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
              >
                <Plus className="h-4 w-4" /> New Patient
              </button>
            ) : undefined
          }
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Patient</th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">EHR ID</th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Age</th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Gender</th>
                <th className="relative px-6 py-3"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filtered.map((p) => (
                <tr
                  key={p.id}
                  onClick={() => navigate(`/patients/${p.ehrId}`)}
                  className="cursor-pointer transition-colors hover:bg-brand-50"
                >
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-100 text-sm font-bold text-brand-700">
                        {p.firstName[0]}{p.lastName[0]}
                      </div>
                      <span className="font-medium text-gray-900">{p.firstName} {p.lastName}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 font-mono text-sm text-gray-600">{p.ehrId}</td>
                  <td className="px-6 py-4 text-sm text-gray-600">{p.age}</td>
                  <td className="px-6 py-4">
                    <Badge label={p.gender} color={genderColor[p.gender]} />
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button
                      onClick={(e) => { e.stopPropagation(); setToDelete(p); }}
                      className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-600"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {data && data.totalPages > 1 && !search && (
            <div className="flex items-center justify-between border-t border-gray-200 px-6 py-3">
              <p className="text-sm text-gray-500">
                Page {data.number + 1} of {data.totalPages}
              </p>
              <div className="flex gap-2">
                <button
                  disabled={data.number === 0}
                  onClick={() => setPage((p) => p - 1)}
                  className="rounded-lg border border-gray-300 p-1.5 text-gray-600 hover:bg-gray-50 disabled:opacity-40"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <button
                  disabled={data.number + 1 >= data.totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded-lg border border-gray-300 p-1.5 text-gray-600 hover:bg-gray-50 disabled:opacity-40"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {showCreate && <CreatePatientModal onClose={() => setShowCreate(false)} />}

      {toDelete && (
        <ConfirmDialog
          title="Delete patient"
          message={`Are you sure you want to delete ${toDelete.firstName} ${toDelete.lastName}? All visits and documents will be permanently removed.`}
          loading={deleteMut.isPending}
          onConfirm={() => deleteMut.mutate(toDelete.ehrId)}
          onCancel={() => setToDelete(null)}
        />
      )}
    </div>
  );
}
