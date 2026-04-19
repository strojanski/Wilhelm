import { useMemo, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ChevronRight,
  Calendar,
  Plus,
  Trash2,
  FileText,
  ClipboardList,
  Scan,
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  HeartPulse,
  Sparkles,
} from 'lucide-react';
import { getPatient, deletePatient } from '../api/patients';
import { getVisits, createVisit, deleteVisit } from '../api/visits';
import type { Visit } from '../api/types';
import Spinner from '../components/Spinner';
import EmptyState from '../components/EmptyState';
import ConfirmDialog from '../components/ConfirmDialog';
import { format, formatDistanceToNowStrict } from 'date-fns';

const AVATAR_PALETTE = [
  'from-blue-500 to-blue-400',
  'from-emerald-500 to-emerald-400',
  'from-amber-500 to-amber-400',
  'from-rose-500 to-rose-400',
  'from-violet-500 to-violet-400',
  'from-cyan-500 to-cyan-400',
];

function avatarColor(seed: string): string {
  let h = 0;
  for (const c of seed) h = ((h << 5) - h + c.charCodeAt(0)) | 0;
  return AVATAR_PALETTE[Math.abs(h) % AVATAR_PALETTE.length];
}

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

  // Full lifetime history (unfiltered) for the stats panel
  const { data: allVisits = [] } = useQuery({
    queryKey: ['visits', ehrId, 'all'],
    queryFn: () => getVisits(ehrId!),
    enabled: !!ehrId,
  });

  const history = useMemo(() => {
    const sorted = [...allVisits].sort(
      (a, b) => new Date(a.visitDate).getTime() - new Date(b.visitDate).getTime(),
    );
    let xrayCount = 0;
    let analyzedCount = 0;
    let fractureCount = 0;
    let fractureVisits = 0;
    let lastFracture: { date: string; visitId: number; filename: string } | null = null;
    for (const v of sorted) {
      xrayCount += v.xrayFiles.length;
      const anns = Object.entries(v.xrayAnnotations ?? {});
      analyzedCount += anns.length;
      let hadFractureThisVisit = false;
      for (const [fname, ann] of anns) {
        const n = ann.segments?.length ?? 0;
        if (n > 0) {
          fractureCount += n;
          hadFractureThisVisit = true;
          if (!lastFracture || new Date(v.visitDate) >= new Date(lastFracture.date)) {
            lastFracture = { date: v.visitDate, visitId: v.id, filename: fname };
          }
        }
      }
      if (hadFractureThisVisit) fractureVisits += 1;
    }
    return {
      total: sorted.length,
      firstSeen: sorted[0]?.visitDate,
      lastSeen: sorted[sorted.length - 1]?.visitDate,
      xrayCount,
      analyzedCount,
      fractureCount,
      fractureVisits,
      lastFracture,
      timeline: [...sorted].reverse().slice(0, 5),
    };
  }, [allVisits]);

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
        <p className="text-slate-500">Patient not found.</p>
        <Link to="/patients" className="mt-4 inline-block text-sm font-medium text-blue-600 hover:underline">
          Back to patients
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-full bg-slate-50">
      {/* Full-bleed patient header */}
      <div className="relative overflow-hidden bg-slate-900 text-white">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/10 via-transparent to-transparent" />
        <div className="relative mx-auto flex w-full max-w-7xl flex-wrap items-start justify-between gap-4 px-6 py-6">
          <div className="flex items-center gap-4">
            <div
              className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-gradient-to-br ${avatarColor(
                patient.ehrId,
              )} text-lg font-semibold text-white shadow-lg ring-2 ring-slate-800`}
            >
              {patient.firstName[0]}
              {patient.lastName[0]}
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">
                {patient.lastName}, {patient.firstName}
              </h1>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                <span className="rounded-md border border-slate-700 bg-slate-800/60 px-2 py-0.5 font-mono text-slate-300">
                  {patient.ehrId}
                </span>
                <span className="rounded-md border border-slate-700 bg-slate-800/60 px-2 py-0.5 text-slate-300">
                  <span className="font-mono text-slate-500">age </span>
                  {patient.age}
                </span>
                <span
                  className={`rounded-md border px-2 py-0.5 ${
                    patient.gender === 'MALE'
                      ? 'border-blue-500/30 bg-blue-500/10 text-blue-300'
                      : patient.gender === 'FEMALE'
                      ? 'border-violet-500/30 bg-violet-500/10 text-violet-300'
                      : 'border-slate-700 bg-slate-800/60 text-slate-300'
                  }`}
                >
                  {patient.gender}
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-baseline gap-2 border-l border-slate-700 pl-4 text-right">
              <span className="text-2xl font-bold tracking-tight">{history.total}</span>
              <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
                visits
              </span>
            </div>
            <button
              onClick={() => setShowDeletePatient(true)}
              className="rounded-md p-2 text-slate-400 transition hover:bg-rose-500/10 hover:text-rose-400"
              title="Delete patient"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="mx-auto w-full max-w-7xl px-6 py-6">
        {/* Patient History / Clinical Summary */}
        <section className="mb-6">
          <div className="mb-3 flex items-baseline gap-3">
            <h2 className="flex items-center gap-2 text-lg font-bold tracking-tight text-slate-900">
              <HeartPulse className="h-4 w-4 text-rose-500" />
              Patient History
            </h2>
            <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
              Derived from electronic health record
            </span>
          </div>

          {history.total === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 bg-white px-5 py-6 text-sm text-slate-500">
              No prior visits on record. This patient has no clinical history yet.
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-[1fr_1fr]">
              {/* Lifetime stats */}
              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
                    Lifetime record
                  </span>
                  <span className="font-mono text-[10px] text-slate-400">
                    EHR · {patient.ehrId}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <Stat
                    icon={Calendar}
                    value={history.total}
                    label="Visits"
                  />
                  <Stat
                    icon={Scan}
                    value={history.xrayCount}
                    label="X-rays"
                  />
                  <Stat
                    icon={Sparkles}
                    value={history.analyzedCount}
                    label="AI analyses"
                  />
                  <Stat
                    icon={AlertTriangle}
                    value={history.fractureCount}
                    label="Fractures"
                    tone={history.fractureCount > 0 ? 'rose' : 'emerald'}
                  />
                </div>

                <div className="mt-4 grid grid-cols-1 gap-2 border-t border-slate-100 pt-3 text-xs sm:grid-cols-2">
                  <div className="flex items-center gap-2 text-slate-600">
                    <Clock className="h-3.5 w-3.5 text-slate-400" />
                    <span className="text-slate-500">Registered since</span>
                    <span className="ml-auto font-mono text-slate-900">
                      {history.firstSeen ? format(new Date(history.firstSeen), 'dd MMM yyyy') : '—'}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-slate-600">
                    <Activity className="h-3.5 w-3.5 text-slate-400" />
                    <span className="text-slate-500">Last seen</span>
                    <span className="ml-auto font-mono text-slate-900">
                      {history.lastSeen
                        ? `${formatDistanceToNowStrict(new Date(history.lastSeen))} ago`
                        : '—'}
                    </span>
                  </div>
                </div>

                {history.lastFracture && (
                  <div className="mt-3 flex items-start gap-2 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-xs">
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-rose-600" />
                    <div className="min-w-0 flex-1">
                      <p className="font-semibold text-rose-800">Prior fracture on record</p>
                      <p className="mt-0.5 truncate text-rose-700">
                        {format(new Date(history.lastFracture.date), 'dd MMM yyyy')} ·{' '}
                        <Link
                          to={`/patients/${ehrId}/visits/${history.lastFracture.visitId}/xray/${encodeURIComponent(history.lastFracture.filename)}`}
                          className="font-mono text-rose-800 underline-offset-2 hover:underline"
                        >
                          {history.lastFracture.filename}
                        </Link>
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* Recent timeline */}
              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
                    Recent activity
                  </span>
                  <span className="font-mono text-[10px] text-slate-400">
                    {Math.min(history.timeline.length, 5)} of {history.total}
                  </span>
                </div>
                <ol className="space-y-2">
                  {history.timeline.map((v) => {
                    const anns = Object.values(v.xrayAnnotations ?? {});
                    const fr = anns.reduce((a, b) => a + (b.segments?.length ?? 0), 0);
                    const tone =
                      fr > 0
                        ? 'border-rose-200 bg-rose-50 text-rose-700'
                        : v.xrayFiles.length > 0
                        ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                        : 'border-slate-200 bg-slate-50 text-slate-600';
                    return (
                      <li key={v.id}>
                        <Link
                          to={`/patients/${ehrId}/visits/${v.id}`}
                          className="group flex items-center gap-3 rounded-md px-2 py-1.5 transition hover:bg-slate-50"
                        >
                          <div className="flex h-8 w-8 shrink-0 flex-col items-center justify-center rounded-md border border-slate-200 bg-white font-mono text-[9px] leading-none text-slate-700">
                            <span className="text-[8px] font-semibold uppercase tracking-widest text-slate-400">
                              {format(new Date(v.visitDate), 'MMM')}
                            </span>
                            <span className="mt-0.5 text-[11px] font-bold text-slate-900">
                              {format(new Date(v.visitDate), 'dd')}
                            </span>
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-xs font-semibold text-slate-900">
                              {format(new Date(v.visitDate), 'EEEE, d MMM yyyy')}
                            </p>
                            <p className="mt-0.5 truncate font-mono text-[10px] text-slate-500">
                              #{v.id} · {v.xrayFiles.length} xr · {v.reportFiles.length} rpt · {v.triageFiles.length} tri
                            </p>
                          </div>
                          <span
                            className={`inline-flex shrink-0 items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] font-semibold ${tone}`}
                          >
                            {fr > 0 ? (
                              <>
                                <AlertTriangle className="h-3 w-3" />
                                Fracture ×{fr}
                              </>
                            ) : v.xrayFiles.length > 0 ? (
                              <>
                                <CheckCircle2 className="h-3 w-3" />
                                Clear
                              </>
                            ) : (
                              <>
                                <ClipboardList className="h-3 w-3" />
                                Intake
                              </>
                            )}
                          </span>
                        </Link>
                      </li>
                    );
                  })}
                </ol>
              </div>
            </div>
          )}
        </section>

        {/* Visits toolbar */}
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-baseline gap-3">
            <h2 className="text-lg font-bold tracking-tight text-slate-900">Visits</h2>
            <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
              {dateFilter ? `Filtered · ${dateFilter}` : 'All dates'}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1 rounded-full border border-slate-200 bg-white px-1 py-1">
              <input
                type="date"
                value={dateFilter}
                onChange={(e) => setDateFilter(e.target.value)}
                className="border-0 bg-transparent px-2 py-0.5 font-mono text-xs text-slate-700 focus:outline-none focus:ring-0"
              />
              {dateFilter && (
                <button
                  onClick={() => setDateFilter('')}
                  className="rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-widest text-slate-500 hover:bg-slate-100 hover:text-slate-900"
                >
                  Clear
                </button>
              )}
            </div>
            <button
              onClick={() => createVisitMut.mutate()}
              disabled={createVisitMut.isPending}
              className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm shadow-blue-500/30 hover:bg-blue-500 disabled:opacity-50"
            >
              {createVisitMut.isPending ? <Spinner size="sm" /> : <Plus className="h-3.5 w-3.5" />}
              New Visit
            </button>
          </div>
        </div>

        {loadingVisits ? (
          <div className="flex justify-center py-12"><Spinner /></div>
        ) : visits.length === 0 ? (
          <EmptyState
            icon={Calendar}
            title="No visits for this date"
            description="Clear the date filter to see all visits, or create a new one."
          />
        ) : (
          <div className="divide-y divide-slate-200 overflow-hidden rounded-xl border border-slate-200 bg-white">
            {visits.map((v) => (
              <div
                key={v.id}
                onClick={() => navigate(`/patients/${ehrId}/visits/${v.id}`)}
                className="group flex cursor-pointer items-center gap-4 px-5 py-4 transition hover:bg-slate-50"
              >
                <div className="flex h-10 w-10 shrink-0 flex-col items-center justify-center rounded-md border border-slate-200 bg-slate-50 font-mono text-xs leading-none text-slate-700">
                  <span className="text-[9px] font-semibold uppercase tracking-widest text-slate-500">
                    {format(new Date(v.visitDate), 'MMM')}
                  </span>
                  <span className="mt-0.5 text-sm font-bold text-slate-900">
                    {format(new Date(v.visitDate), 'dd')}
                  </span>
                </div>

                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-slate-900">
                    {format(new Date(v.visitDate), 'EEEE, MMMM d, yyyy')}
                  </p>
                  <p className="mt-0.5 font-mono text-[11px] text-slate-500">
                    #{v.id} · created {format(new Date(v.createdAt), 'dd MMM HH:mm')}
                  </p>
                </div>

                <div className="hidden items-center gap-1.5 sm:flex">
                  {v.xrayFiles.length > 0 && (
                    <span className="inline-flex items-center gap-1 rounded-md border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-800">
                      <Scan className="h-3 w-3" />
                      {v.xrayFiles.length} X-ray{v.xrayFiles.length !== 1 ? 's' : ''}
                    </span>
                  )}
                  {v.reportFiles.length > 0 && (
                    <span className="inline-flex items-center gap-1 rounded-md border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-800">
                      <FileText className="h-3 w-3" />
                      {v.reportFiles.length} Report{v.reportFiles.length !== 1 ? 's' : ''}
                    </span>
                  )}
                  {v.triageFiles.length > 0 && (
                    <span className="inline-flex items-center gap-1 rounded-md border border-blue-200 bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-800">
                      <ClipboardList className="h-3 w-3" />
                      {v.triageFiles.length} Triage
                    </span>
                  )}
                </div>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setVisitToDelete(v);
                  }}
                  className="rounded-md p-1.5 text-slate-300 opacity-0 transition hover:bg-rose-50 hover:text-rose-500 group-hover:opacity-100"
                  aria-label="Delete visit"
                >
                  <Trash2 className="h-4 w-4" />
                </button>

                <ChevronRight className="h-4 w-4 shrink-0 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-slate-500" />
              </div>
            ))}
          </div>
        )}
      </div>

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

function Stat({
  icon: Icon,
  value,
  label,
  tone = 'slate',
}: {
  icon: typeof Scan;
  value: number;
  label: string;
  tone?: 'slate' | 'rose' | 'emerald';
}) {
  const toneClasses = {
    slate: 'text-slate-400',
    rose: 'text-rose-500',
    emerald: 'text-emerald-500',
  }[tone];
  return (
    <div className="flex items-center gap-2 rounded-md border border-slate-100 bg-slate-50 px-3 py-2">
      <Icon className={`h-4 w-4 shrink-0 ${toneClasses}`} />
      <div className="min-w-0">
        <p className="text-lg font-bold leading-none tracking-tight text-slate-900">{value}</p>
        <p className="mt-1 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
          {label}
        </p>
      </div>
    </div>
  );
}
