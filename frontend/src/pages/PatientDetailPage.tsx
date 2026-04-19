import { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ChevronRight, Calendar, Plus, Trash2, Users } from 'lucide-react';
import { getPatient, deletePatient } from '../api/patients';
import { getVisits, createVisit, deleteVisit } from '../api/visits';
import type { Visit } from '../api/types';
import Spinner from '../components/Spinner';
import Badge from '../components/Badge';
import EmptyState from '../components/EmptyState';
import ConfirmDialog from '../components/ConfirmDialog';
import { format } from 'date-fns';

const genderColor = { MALE: 'blue', FEMALE: 'purple', OTHER: 'gray' } as const;

export default function PatientDetailPage() {
  const { ehrId } = useParams<{ ehrId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [showDeletePatient, setShowDeletePatient] = useState(false);
  const [visitToDelete, setVisitToDelete] = useState<Visit | null>(null);
  const [dateFilter, setDateFilter] = useState(format(new Date(), 'yyyy-MM-dd'));

  const { data: patient, isLoading: loadingPatient } = useQuery({
    queryKey: ['patient', ehrId],
    queryFn: () => getPatient(ehrId!),
    enabled: !!ehrId,
  });

  const { data: visits = [], isLoading: loadingVisits } = useQuery({
    queryKey: ['visits', ehrId, dateFilter],
    queryFn: () => getVisits(ehrId!, dateFilter || undefined),
    enabled: !!ehrId,
  });

  const deletePatientMut = useMutation({
    mutationFn: () => deletePatient(ehrId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['patients'] });
      navigate('/patients');
    },
  });

  const createVisitMut = useMutation({
    mutationFn: () => createVisit(ehrId!, { visitDate: format(new Date(), 'yyyy-MM-dd') }),
    onSuccess: (visit) => {
      qc.invalidateQueries({ queryKey: ['visits', ehrId] });
      navigate(`/patients/${ehrId}/visits/${visit.id}`);
    },
  });

  const deleteVisitMut = useMutation({
    mutationFn: (visitId: number) => deleteVisit(ehrId!, visitId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['visits', ehrId] });
      setVisitToDelete(null);
    },
  });

  if (loadingPatient) {
    return <div className="flex justify-center py-20"><Spinner /></div>;
  }

  if (!patient) {
    return (
      <div className="py-20 text-center">
        <p className="text-gray-500">Patient not found.</p>
        <Link to="/patients" className="mt-4 inline-block text-sm font-medium text-brand-600 hover:underline">
          Back to patients
        </Link>
      </div>
    );
  }

  return (
    <div>
      {/* Breadcrumb */}
      <nav className="mb-6 flex items-center gap-1 text-sm text-gray-500">
        <Link to="/patients" className="flex items-center gap-1 hover:text-brand-600">
          <Users className="h-3.5 w-3.5" /> Patients
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <span className="font-medium text-gray-900">{patient.firstName} {patient.lastName}</span>
      </nav>

      {/* Patient header card */}
      <div className="mb-6 overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
        <div className="flex flex-col gap-4 p-6 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-brand-100 text-xl font-bold text-brand-700">
              {patient.firstName[0]}{patient.lastName[0]}
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                {patient.firstName} {patient.lastName}
              </h1>
              <p className="mt-0.5 font-mono text-sm text-gray-500">{patient.ehrId}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex gap-4 text-sm text-gray-600">
              <span><span className="font-medium">Age:</span> {patient.age}</span>
              <Badge label={patient.gender} color={genderColor[patient.gender]} />
            </div>
            <button
              onClick={() => setShowDeletePatient(true)}
              className="ml-2 rounded-lg p-2 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-600"
              title="Delete patient"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Visits */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Visits</h2>
        <div className="flex items-center gap-3">
          <input
            type="date"
            value={dateFilter}
            onChange={(e) => setDateFilter(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
          {dateFilter && (
            <button onClick={() => setDateFilter('')} className="text-sm text-gray-500 hover:text-gray-900">
              Clear
            </button>
          )}
          <button
            onClick={() => createVisitMut.mutate()}
            disabled={createVisitMut.isPending}
            className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {createVisitMut.isPending ? <Spinner size="sm" /> : <Plus className="h-4 w-4" />}
            New Visit
          </button>
        </div>
      </div>

      {loadingVisits ? (
        <div className="flex justify-center py-12"><Spinner /></div>
      ) : visits.length === 0 ? (
        <EmptyState
          icon={Calendar}
          title="No visits yet"
          description="Create a new visit to start uploading documents."
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {visits.map((v) => (
            <div
              key={v.id}
              onClick={() => navigate(`/patients/${ehrId}/visits/${v.id}`)}
              className="group cursor-pointer rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md hover:border-brand-300"
            >
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-base font-semibold text-gray-900">
                    {format(new Date(v.visitDate), 'MMM d, yyyy')}
                  </p>
                  <p className="mt-0.5 text-xs text-gray-400">
                    Created {format(new Date(v.createdAt), 'MMM d, HH:mm')}
                  </p>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); setVisitToDelete(v); }}
                  className="rounded-lg p-1.5 text-gray-300 transition-colors hover:bg-red-50 hover:text-red-500"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
              <div className="mt-4 flex gap-3 text-xs text-gray-500">
                <span className="flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full bg-blue-400" />
                  {v.triageFiles.length} triage
                </span>
                <span className="flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full bg-green-400" />
                  {v.reportFiles.length} reports
                </span>
                <span className="flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full bg-amber-400" />
                  {v.xrayFiles.length} x-rays
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {showDeletePatient && (
        <ConfirmDialog
          title="Delete patient"
          message={`Delete ${patient.firstName} ${patient.lastName}? All visits and documents will be permanently removed.`}
          loading={deletePatientMut.isPending}
          onConfirm={() => deletePatientMut.mutate()}
          onCancel={() => setShowDeletePatient(false)}
        />
      )}

      {visitToDelete && (
        <ConfirmDialog
          title="Delete visit"
          message={`Delete visit from ${format(new Date(visitToDelete.visitDate), 'MMM d, yyyy')}? All documents in this visit will be permanently removed.`}
          loading={deleteVisitMut.isPending}
          onConfirm={() => deleteVisitMut.mutate(visitToDelete.id)}
          onCancel={() => setVisitToDelete(null)}
        />
      )}
    </div>
  );
}
