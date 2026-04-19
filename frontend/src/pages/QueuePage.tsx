import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueries, useQuery } from '@tanstack/react-query';
import {
  Activity,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  FileText,
  Scan,
  Search,
  Siren,
  Users,
} from 'lucide-react';
import { getPatients } from '../api/patients';
import { getVisits } from '../api/visits';
import type { Patient, Visit } from '../api/types';
import Spinner from '../components/Spinner';
import { format, formatDistanceToNowStrict } from 'date-fns';

type Priority = 'urgent' | 'review' | 'clear' | 'pending';

interface QueueRow {
  visit: Visit;
  patient: Patient;
  priority: Priority;
  fractureCount: number;
  analyzedCount: number;
}

function classifyVisit(visit: Visit): { priority: Priority; fractureCount: number; analyzedCount: number } {
  const anns = Object.values(visit.xrayAnnotations ?? {});
  const analyzedCount = anns.length;
  const fractureCount = anns.reduce((acc, a) => acc + (a.segments?.length ?? 0), 0);
  if (fractureCount > 0) return { priority: 'urgent', fractureCount, analyzedCount };
  if (visit.xrayFiles.length > 0 && analyzedCount < visit.xrayFiles.length) {
    return { priority: 'pending', fractureCount, analyzedCount };
  }
  if (visit.xrayFiles.length > 0 && fractureCount === 0 && analyzedCount === visit.xrayFiles.length) {
    return { priority: 'clear', fractureCount, analyzedCount };
  }
  return { priority: 'review', fractureCount, analyzedCount };
}

const PRIORITY_META: Record<Priority, { label: string; dot: string; chip: string; icon: typeof Siren }> = {
  urgent: {
    label: 'Fracture',
    dot: 'bg-rose-500 shadow-[0_0_10px_rgba(244,63,94,0.6)]',
    chip: 'border-rose-500/30 bg-rose-500/10 text-rose-300',
    icon: Siren,
  },
  pending: {
    label: 'Awaiting AI',
    dot: 'bg-amber-400 shadow-[0_0_10px_rgba(251,191,36,0.5)]',
    chip: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
    icon: Activity,
  },
  review: {
    label: 'Intake',
    dot: 'bg-slate-500',
    chip: 'border-slate-600 bg-slate-800 text-slate-300',
    icon: ClipboardList,
  },
  clear: {
    label: 'Clear',
    dot: 'bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.5)]',
    chip: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
    icon: CheckCircle2,
  },
};

const PRIORITY_ORDER: Record<Priority, number> = { urgent: 0, pending: 1, review: 2, clear: 3 };

function avatarSeed(seed: string): string {
  let h = 0;
  for (const c of seed) h = ((h << 5) - h + c.charCodeAt(0)) | 0;
  const hue = Math.abs(h) % 60 + 210; // blues → indigos
  return `hsl(${hue} 40% 35%)`;
}

export default function QueuePage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<'all' | Priority>('all');

  const { data: patientsPage, isLoading: loadingPatients } = useQuery({
    queryKey: ['patients-queue'],
    queryFn: () => getPatients(0, 100),
  });

  const patients = patientsPage?.content ?? [];

  const visitQueries = useQueries({
    queries: patients.map((p) => ({
      queryKey: ['visits', p.ehrId, undefined],
      queryFn: () => getVisits(p.ehrId),
      enabled: !!p.ehrId,
    })),
  });

  const loadingVisits = visitQueries.some((q) => q.isLoading);

  const rows: QueueRow[] = useMemo(() => {
    const out: QueueRow[] = [];
    patients.forEach((p, idx) => {
      const visits = visitQueries[idx]?.data ?? [];
      for (const v of visits) {
        const c = classifyVisit(v);
        out.push({ visit: v, patient: p, ...c });
      }
    });
    return out.sort((a, b) => {
      const byPriority = PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority];
      if (byPriority !== 0) return byPriority;
      return new Date(b.visit.createdAt).getTime() - new Date(a.visit.createdAt).getTime();
    });
  }, [patients, visitQueries.map((q) => q.dataUpdatedAt).join(',')]);

  const filtered = rows.filter((r) => {
    if (filter !== 'all' && r.priority !== filter) return false;
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      `${r.patient.firstName} ${r.patient.lastName}`.toLowerCase().includes(q) ||
      r.patient.ehrId.toLowerCase().includes(q)
    );
  });

  const counts = useMemo(() => {
    const c = { urgent: 0, pending: 0, review: 0, clear: 0 };
    rows.forEach((r) => (c[r.priority] += 1));
    return c;
  }, [rows]);

  const openVisit = (row: QueueRow) => {
    const { patient, visit } = row;
    if (visit.xrayFiles.length === 1) {
      navigate(`/patients/${patient.ehrId}/visits/${visit.id}/xray/${encodeURIComponent(visit.xrayFiles[0])}?auto=1`);
      return;
    }
    navigate(`/patients/${patient.ehrId}/visits/${visit.id}`);
  };

  const isLoading = loadingPatients || (patients.length > 0 && loadingVisits);

  return (
    <div className="min-h-[calc(100vh-3rem)] bg-[#0A0F1E] text-slate-100">
      {/* Hero strip */}
      <div className="relative overflow-hidden border-b border-slate-800 bg-slate-900">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(59,130,246,0.15),_transparent_70%)]" />
        <div className="relative mx-auto flex w-full max-w-7xl flex-wrap items-end justify-between gap-6 px-6 py-6">
          <div>
            <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.25em] text-blue-400">
              <span className="inline-flex h-1.5 w-1.5 animate-pulse rounded-full bg-blue-400" />
              Live Triage Queue
            </div>
            <h1 className="mt-1 text-3xl font-bold tracking-tight text-white">
              Emergency Radiology
            </h1>
            <p className="mt-1 text-sm text-slate-400">
              {format(new Date(), 'EEEE, d MMMM yyyy · HH:mm')} — Wilhelm AI assisting on {rows.length} {rows.length === 1 ? 'case' : 'cases'}.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <Metric label="Fractures" value={counts.urgent} tone="rose" />
            <Metric label="Awaiting AI" value={counts.pending} tone="amber" />
            <Metric label="Intake" value={counts.review} tone="slate" />
            <Metric label="Cleared" value={counts.clear} tone="emerald" />
          </div>
        </div>
      </div>

      <div className="mx-auto w-full max-w-7xl px-6 py-6">
        {/* Controls */}
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="relative w-full sm:w-80">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search patient or EHR ID…"
              className="h-10 w-full rounded-lg border border-slate-800 bg-slate-900/60 pl-10 pr-3 text-sm text-slate-100 placeholder:text-slate-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div className="flex items-center gap-1 rounded-lg border border-slate-800 bg-slate-900/60 p-1 text-xs">
            {(['all', 'urgent', 'pending', 'clear'] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={[
                  'rounded-md px-3 py-1.5 font-medium capitalize transition',
                  filter === f ? 'bg-slate-800 text-white' : 'text-slate-400 hover:text-slate-200',
                ].join(' ')}
              >
                {f === 'all' ? 'All' : PRIORITY_META[f].label}
              </button>
            ))}
            <button
              onClick={() => navigate('/patients')}
              className="ml-2 inline-flex items-center gap-1.5 rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 font-medium text-slate-300 hover:border-slate-600 hover:text-white"
            >
              <Users className="h-3.5 w-3.5" />
              Patients
            </button>
          </div>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-24"><Spinner /></div>
        ) : filtered.length === 0 ? (
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 py-20 text-center">
            <ClipboardList className="mx-auto h-8 w-8 text-slate-600" />
            <p className="mt-3 text-sm text-slate-400">
              {search || filter !== 'all'
                ? 'No matching cases. Adjust filters or search.'
                : 'Queue is empty. Create a patient and visit to begin.'}
            </p>
          </div>
        ) : (
          <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/40">
            {/* Column headers */}
            <div className="hidden grid-cols-[40px_60px_1fr_180px_200px_40px] items-center gap-4 border-b border-slate-800 bg-slate-900/60 px-5 py-2 text-[10px] font-semibold uppercase tracking-widest text-slate-500 md:grid">
              <span />
              <span>#</span>
              <span>Patient</span>
              <span>Files</span>
              <span>Status</span>
              <span />
            </div>

            <div className="divide-y divide-slate-800">
              {filtered.map((row, i) => (
                <QueueRowView key={`${row.patient.ehrId}-${row.visit.id}`} row={row} index={i + 1} onOpen={() => openVisit(row)} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: number; tone: 'rose' | 'amber' | 'slate' | 'emerald' }) {
  const toneClasses = {
    rose: 'border-rose-500/30 text-rose-300',
    amber: 'border-amber-500/30 text-amber-300',
    slate: 'border-slate-700 text-slate-300',
    emerald: 'border-emerald-500/30 text-emerald-300',
  }[tone];
  return (
    <div className={`flex min-w-[96px] flex-col rounded-lg border bg-slate-900/40 px-3 py-2 ${toneClasses}`}>
      <span className="text-2xl font-bold leading-none tracking-tight">{value}</span>
      <span className="mt-1 text-[10px] font-semibold uppercase tracking-widest text-slate-400">{label}</span>
    </div>
  );
}

function QueueRowView({ row, index, onOpen }: { row: QueueRow; index: number; onOpen: () => void }) {
  const meta = PRIORITY_META[row.priority];
  const waited = formatDistanceToNowStrict(new Date(row.visit.createdAt), { addSuffix: false });

  return (
    <button
      onClick={onOpen}
      className="group grid w-full grid-cols-[40px_60px_1fr_180px_200px_40px] items-center gap-4 px-5 py-4 text-left transition hover:bg-slate-800/40 focus:outline-none focus:bg-slate-800/60"
    >
      {/* Priority dot */}
      <div className="flex justify-center">
        <span className={`h-2.5 w-2.5 rounded-full ${meta.dot}`} />
      </div>

      {/* Queue position */}
      <div className="font-mono text-xs text-slate-500">
        <span className="text-base font-bold text-slate-300">{index.toString().padStart(2, '0')}</span>
      </div>

      {/* Patient + visit */}
      <div className="flex min-w-0 items-center gap-3">
        <div
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-semibold text-white ring-2 ring-slate-800"
          style={{ background: avatarSeed(row.patient.ehrId) }}
        >
          {row.patient.firstName[0]}
          {row.patient.lastName[0]}
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-white">
            {row.patient.lastName}, {row.patient.firstName}
          </p>
          <p className="mt-0.5 flex items-center gap-2 truncate font-mono text-[11px] text-slate-500">
            <span>{row.patient.ehrId}</span>
            <span className="text-slate-700">·</span>
            <span>{row.patient.age}y {row.patient.gender[0]}</span>
            <span className="text-slate-700">·</span>
            <span>{format(new Date(row.visit.visitDate), 'dd MMM')}</span>
          </p>
        </div>
      </div>

      {/* Files summary */}
      <div className="hidden items-center gap-1.5 md:flex">
        {row.visit.xrayFiles.length > 0 && (
          <FilePill icon={Scan} count={row.visit.xrayFiles.length} tone="blue" />
        )}
        {row.visit.reportFiles.length > 0 && (
          <FilePill icon={FileText} count={row.visit.reportFiles.length} tone="emerald" />
        )}
        {row.visit.triageFiles.length > 0 && (
          <FilePill icon={ClipboardList} count={row.visit.triageFiles.length} tone="slate" />
        )}
        {row.visit.xrayFiles.length === 0 && row.visit.reportFiles.length === 0 && row.visit.triageFiles.length === 0 && (
          <span className="text-[11px] text-slate-600">—</span>
        )}
      </div>

      {/* Status */}
      <div className="flex items-center gap-2">
        <span className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] font-semibold ${meta.chip}`}>
          <meta.icon className="h-3 w-3" />
          {meta.label}
          {row.priority === 'urgent' && row.fractureCount > 0 && (
            <span className="ml-1 font-mono">×{row.fractureCount}</span>
          )}
        </span>
        <span className="hidden font-mono text-[10px] text-slate-500 lg:inline" title="Time since intake">
          {waited}
        </span>
      </div>

      <ChevronRight className="h-4 w-4 text-slate-600 transition group-hover:translate-x-0.5 group-hover:text-slate-300" />
    </button>
  );
}

function FilePill({
  icon: Icon,
  count,
  tone,
}: {
  icon: typeof Scan;
  count: number;
  tone: 'blue' | 'emerald' | 'slate';
}) {
  const toneClasses = {
    blue: 'border-blue-500/30 bg-blue-500/10 text-blue-300',
    emerald: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
    slate: 'border-slate-700 bg-slate-800/50 text-slate-300',
  }[tone];
  return (
    <span className={`inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-medium ${toneClasses}`}>
      <Icon className="h-3 w-3" />
      {count}
    </span>
  );
}

