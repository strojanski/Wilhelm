import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Plus, Search, Trash2, Users, ChevronLeft, ChevronRight } from 'lucide-react';
import { getPatients, deletePatient } from '../api/patients';
import type { Patient } from '../api/types';
import Spinner from '../components/Spinner';
import EmptyState from '../components/EmptyState';
import ConfirmDialog from '../components/ConfirmDialog';
import CreatePatientModal from './CreatePatientModal';


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
    <div className="mx-auto w-full max-w-7xl px-6 py-6">
      {/* Header row */}
      <div className="mb-5 flex items-baseline justify-between">
        <div className="flex items-baseline gap-3">
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Patients</h1>
          {data && (
            <span className="font-mono text-xs text-slate-500">
              {data.totalElements} total
            </span>
          )}
        </div>
        <div className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
          Ward directory
        </div>
      </div>

      {/* Search bar */}
      <div className="relative mb-4">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          autoFocus
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by name or EHR ID…"
          className="h-10 w-full rounded-lg border border-slate-200 bg-white pl-10 pr-3 text-sm text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
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
                className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500"
              >
                <Plus className="h-4 w-4" /> New Patient
              </button>
            ) : undefined
          }
        />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {filtered.map((p) => (
              <div
                key={p.id}
                onClick={() => navigate(`/patients/${p.ehrId}`)}
                className="group relative flex cursor-pointer items-center gap-3 overflow-hidden rounded-lg border border-slate-200 bg-white px-3 py-2.5 transition-all duration-150 hover:-translate-y-0.5 hover:border-slate-800 hover:shadow-md hover:shadow-slate-900/10"
              >
                <div className="pointer-events-none absolute inset-y-0 left-0 w-1 bg-slate-800 opacity-0 transition-opacity group-hover:opacity-100" />

                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-800 text-[13px] font-semibold text-slate-100 ring-1 ring-slate-900/5">
                  {p.firstName[0]}
                  {p.lastName[0]}
                </div>

                <div className="min-w-0 flex-1">
                  <h3 className="truncate text-sm font-semibold tracking-tight text-slate-900">
                    {p.lastName}, {p.firstName}
                  </h3>
                  <p className="mt-0.5 truncate font-mono text-[11px] text-slate-500">
                    {p.ehrId} · {p.age}y {p.gender[0]}
                  </p>
                </div>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setToDelete(p);
                  }}
                  className="rounded-md p-1 text-slate-300 opacity-0 transition hover:bg-rose-50 hover:text-rose-600 group-hover:opacity-100"
                  aria-label="Delete patient"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>

          {data && data.totalPages > 1 && !search && (
            <div className="mt-6 flex items-center justify-end gap-3">
              <p className="font-mono text-xs text-slate-500">
                Page {data.number + 1} of {data.totalPages}
              </p>
              <div className="flex gap-1">
                <button
                  disabled={data.number === 0}
                  onClick={() => setPage((p) => p - 1)}
                  className="rounded-md border border-slate-200 bg-white p-1.5 text-slate-600 transition hover:border-slate-300 hover:bg-slate-50 disabled:opacity-40"
                  aria-label="Previous page"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <button
                  disabled={data.number + 1 >= data.totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded-md border border-slate-200 bg-white p-1.5 text-slate-600 transition hover:border-slate-300 hover:bg-slate-50 disabled:opacity-40"
                  aria-label="Next page"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Floating action button */}
      <button
        onClick={() => setShowCreate(true)}
        className="fixed bottom-6 right-6 flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-blue-600 to-blue-500 text-white shadow-xl shadow-blue-500/40 transition hover:scale-105 hover:shadow-blue-500/60 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2"
        aria-label="New patient"
        title="New patient"
      >
        <Plus className="h-6 w-6" />
      </button>

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
