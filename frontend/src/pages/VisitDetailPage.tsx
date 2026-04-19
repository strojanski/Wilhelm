import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  FileText,
  ClipboardList,
  Scan,
  Download,
  ExternalLink,
  Upload,
  Loader2,
  AlertTriangle,
  Sparkles,
  CheckCircle,
  RotateCcw,
  Eye,
} from 'lucide-react';
import { getPatient } from '../api/patients';
import {
  getVisit,
  uploadTriage,
  uploadReport,
  uploadXray,
  analyzeXray,
  getFileUrl,
} from '../api/visits';
import type { XrayAnalysis } from '../api/types';
import Spinner from '../components/Spinner';
import { format } from 'date-fns';

type DocType = 'triage' | 'report';

export default function VisitDetailPage() {
  const { ehrId, visitId } = useParams<{ ehrId: string; visitId: string }>();
  const qc = useQueryClient();
  const [uploading, setUploading] = useState<DocType | 'xray' | null>(null);
  const [uploadError, setUploadError] = useState('');

  const visitQueryKey = ['visit', ehrId, visitId];

  const { data: patient } = useQuery({
    queryKey: ['patient', ehrId],
    queryFn: () => getPatient(ehrId!),
    enabled: !!ehrId,
  });

  const { data: visit, isLoading } = useQuery({
    queryKey: visitQueryKey,
    queryFn: () => getVisit(ehrId!, Number(visitId)),
    enabled: !!ehrId && !!visitId,
  });

  const uploadMut = useMutation({
    mutationFn: ({ type, file }: { type: DocType | 'xray'; file: File }) => {
      const id = Number(visitId);
      if (type === 'triage') return uploadTriage(ehrId!, id, file);
      if (type === 'report') return uploadReport(ehrId!, id, file);
      return uploadXray(ehrId!, id, file);
    },
    onSuccess: (updated) => {
      qc.setQueryData(visitQueryKey, updated);
      setUploading(null);
      setUploadError('');
    },
    onError: (err: any) => {
      setUploading(null);
      setUploadError(err.response?.data?.message ?? 'Upload failed.');
    },
  });

  const handleUpload = (type: DocType | 'xray', file: File) => {
    setUploading(type);
    setUploadError('');
    uploadMut.mutate({ type, file });
  };

  // Auto-navigate to the single X-ray when this visit has exactly one
  const autoNavRef = useRef(false);
  const navigate = useNavigate();
  useEffect(() => {
    if (autoNavRef.current) return;
    if (!visit) return;
    if (visit.xrayFiles.length !== 1) return;
    autoNavRef.current = true;
    navigate(
      `/patients/${ehrId}/visits/${visitId}/xray/${encodeURIComponent(visit.xrayFiles[0])}?auto=1`,
      { replace: true },
    );
  }, [visit, ehrId, visitId, navigate]);

  if (isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner />
      </div>
    );
  }

  if (!visit) {
    return <p className="py-20 text-center text-slate-500">Visit not found.</p>;
  }

  return (
    <div className="mx-auto w-full max-w-7xl px-6 py-6">
      {/* Visit summary bar */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-5 py-4">
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 flex-col items-center justify-center rounded-md border border-slate-200 bg-slate-50 leading-none">
            <span className="text-[9px] font-semibold uppercase tracking-widest text-slate-500">
              {format(new Date(visit.visitDate), 'MMM')}
            </span>
            <span className="mt-0.5 font-mono text-base font-bold text-slate-900">
              {format(new Date(visit.visitDate), 'dd')}
            </span>
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900">
              {format(new Date(visit.visitDate), 'EEEE, MMMM d, yyyy')}
            </h1>
            <p className="mt-0.5 font-mono text-[11px] text-slate-500">
              Visit #{visit.id} · created {format(new Date(visit.createdAt), 'dd MMM HH:mm')}
              {patient && ` · ${patient.lastName}, ${patient.firstName}`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <Metric label="triage" value={visit.triageFiles.length} tone="blue" />
          <Metric label="reports" value={visit.reportFiles.length} tone="emerald" />
          <Metric label="x-rays" value={visit.xrayFiles.length} tone="amber" />
        </div>
      </div>

      {uploadError && (
        <div className="mb-4 flex items-center gap-2 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {uploadError}
        </div>
      )}

      {/* 3-column grid */}
      <div className="grid grid-cols-12 gap-4">
        {/* Col A: Triage */}
        <FileColumn
          colClass="col-span-12 md:col-span-3"
          icon={<ClipboardList className="h-3.5 w-3.5" />}
          title="Triage"
          accent="text-blue-600"
          files={visit.triageFiles}
          fileHref={(f) => getFileUrl(ehrId!, visit.id, 'triage', f)}
          uploading={uploading === 'triage'}
          onUpload={(f) => handleUpload('triage', f)}
          accept=".pdf"
          uploadLabel="Upload triage PDF"
        />

        {/* Col B: Reports */}
        <FileColumn
          colClass="col-span-12 md:col-span-3"
          icon={<FileText className="h-3.5 w-3.5" />}
          title="Medical Reports"
          accent="text-emerald-600"
          files={visit.reportFiles}
          fileHref={(f) => getFileUrl(ehrId!, visit.id, 'report', f)}
          uploading={uploading === 'report'}
          onUpload={(f) => handleUpload('report', f)}
          accept=".pdf"
          uploadLabel="Upload report PDF"
        />

        {/* Col C: X-rays */}
        <div className="col-span-12 md:col-span-6">
          <div className="mb-2 flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-widest text-amber-600">
              <Scan className="h-3.5 w-3.5" />
              X-Ray Imaging
              <span className="font-mono text-[10px] text-slate-400">
                · {visit.xrayFiles.length} file{visit.xrayFiles.length !== 1 ? 's' : ''}
              </span>
            </div>
            <span className="inline-flex items-center gap-1 rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-widest text-blue-700">
              <Sparkles className="h-3 w-3" />
              AI detection
            </span>
          </div>

          {visit.xrayFiles.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center">
              <Scan className="mx-auto h-6 w-6 text-slate-300" />
              <p className="mt-2 text-sm font-medium text-slate-600">No X-rays yet</p>
              <p className="mt-0.5 text-xs text-slate-400">
                Upload an image to start AI fracture detection
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {visit.xrayFiles.map((filename) => (
                <XrayCard
                  key={filename}
                  ehrId={ehrId!}
                  visitId={visit.id}
                  filename={filename}
                  analysis={visit.xrayAnnotations?.[filename]}
                  queryKey={visitQueryKey}
                />
              ))}
            </div>
          )}

          <UploadDropzone
            className="mt-3"
            uploading={uploading === 'xray'}
            accept="image/*,.png,.jpg,.jpeg"
            label="Upload X-ray image"
            onUpload={(f) => handleUpload('xray', f)}
          />
        </div>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: 'blue' | 'emerald' | 'amber';
}) {
  const dot =
    tone === 'blue' ? 'bg-blue-500' : tone === 'emerald' ? 'bg-emerald-500' : 'bg-amber-500';
  return (
    <div className="flex items-center gap-2">
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      <span className="font-mono text-xs text-slate-500">{label}</span>
      <span className="font-mono text-xs font-bold text-slate-900">{value}</span>
    </div>
  );
}

function FileColumn({
  colClass,
  icon,
  title,
  accent,
  files,
  fileHref,
  uploading,
  onUpload,
  accept,
  uploadLabel,
}: {
  colClass: string;
  icon: React.ReactNode;
  title: string;
  accent: string;
  files: string[];
  fileHref: (filename: string) => string;
  uploading: boolean;
  onUpload: (file: File) => void;
  accept: string;
  uploadLabel: string;
}) {
  return (
    <div className={colClass}>
      <div className="mb-2 flex items-center justify-between">
        <div
          className={`flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-widest ${accent}`}
        >
          {icon}
          {title}
          <span className="font-mono text-[10px] text-slate-400">
            · {files.length} file{files.length !== 1 ? 's' : ''}
          </span>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-2">
        {files.length === 0 ? (
          <p className="px-2 py-3 text-center text-xs text-slate-400">No files yet.</p>
        ) : (
          <ul className="space-y-0.5">
            {files.map((filename) => (
              <li key={filename}>
                <div className="group flex items-center gap-2 rounded-md px-2.5 py-2 transition hover:bg-slate-50">
                  <FileText className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                  <span
                    className="min-w-0 flex-1 truncate font-mono text-[11px] text-slate-700"
                    title={filename}
                  >
                    {filename}
                  </span>
                  <div className="flex shrink-0 items-center gap-0.5 opacity-0 transition group-hover:opacity-100">
                    <a
                      href={fileHref(filename)}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-blue-600"
                      title="Open"
                    >
                      <ExternalLink className="h-3 w-3" />
                    </a>
                    <a
                      href={fileHref(filename)}
                      download={filename}
                      className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-blue-600"
                      title="Download"
                    >
                      <Download className="h-3 w-3" />
                    </a>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}

        <UploadDropzone
          className="mt-1"
          uploading={uploading}
          accept={accept}
          label={uploadLabel}
          onUpload={onUpload}
          compact
        />
      </div>
    </div>
  );
}

function UploadDropzone({
  uploading,
  accept,
  label,
  onUpload,
  className = '',
  compact = false,
}: {
  uploading: boolean;
  accept: string;
  label: string;
  onUpload: (file: File) => void;
  className?: string;
  compact?: boolean;
}) {
  const id = `upload-${label.replace(/\s+/g, '-').toLowerCase()}-${Math.random().toString(36).slice(2, 7)}`;
  return (
    <label
      htmlFor={id}
      className={`flex cursor-pointer items-center justify-center gap-1.5 rounded-md border border-dashed border-slate-300 text-slate-500 transition hover:border-blue-500 hover:bg-blue-50/50 hover:text-blue-600 ${
        compact ? 'py-2 text-[11px]' : 'py-3 text-xs'
      } ${className} ${uploading ? 'pointer-events-none opacity-60' : ''}`}
    >
      {uploading ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      ) : (
        <Upload className="h-3.5 w-3.5" />
      )}
      <span className="font-medium">{uploading ? 'Uploading…' : label}</span>
      <input
        id={id}
        type="file"
        accept={accept}
        disabled={uploading}
        className="sr-only"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) {
            onUpload(f);
            e.currentTarget.value = '';
          }
        }}
      />
    </label>
  );
}

function XrayCard({
  ehrId,
  visitId,
  filename,
  analysis,
  queryKey,
}: {
  ehrId: string;
  visitId: number;
  filename: string;
  analysis: XrayAnalysis | undefined;
  queryKey: unknown[];
}) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const imgUrl = getFileUrl(ehrId, visitId, 'xray', filename);

  const analyzeMut = useMutation({
    mutationFn: () => analyzeXray(ehrId, visitId, filename),
    onSuccess: (updated) => {
      qc.setQueryData(queryKey, updated);
    },
  });

  const segments = analysis?.segments ?? [];
  const hasSegments = segments.length > 0;
  const notAnalyzed = !analysis;

  const [launching, setLaunching] = useState(false);
  const openDetail = () => {
    if (launching) return;
    setLaunching(true);
    window.setTimeout(() => {
      navigate(`/patients/${ehrId}/visits/${visitId}/xray/${encodeURIComponent(filename)}?auto=1`);
    }, 450);
  };

  let statusBadge: React.ReactNode = null;
  if (notAnalyzed) {
    statusBadge = (
      <span className="inline-flex items-center gap-1 rounded-full border border-slate-600/60 bg-slate-900/80 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-widest text-slate-300 backdrop-blur">
        Not analyzed
      </span>
    );
  } else if (hasSegments) {
    statusBadge = (
      <span
        className="inline-flex items-center gap-1 rounded-full border border-rose-400/60 bg-rose-500/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-widest text-rose-200 backdrop-blur"
        style={{ boxShadow: '0 0 12px rgba(244,63,94,0.35)' }}
      >
        <span className="h-1.5 w-1.5 rounded-full bg-rose-400" />
        {segments.length} fracture{segments.length !== 1 ? 's' : ''}
      </span>
    );
  } else {
    statusBadge = (
      <span className="inline-flex items-center gap-1 rounded-full border border-emerald-400/60 bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-widest text-emerald-200 backdrop-blur">
        <CheckCircle className="h-3 w-3" />
        Clear
      </span>
    );
  }

  return (
    <div
      onClick={openDetail}
      className="group relative aspect-square cursor-pointer overflow-hidden rounded-xl border border-slate-200 bg-black transition-all duration-200 hover:-translate-y-0.5 hover:border-blue-500 hover:shadow-lg hover:shadow-blue-500/20"
    >
      <img src={imgUrl} alt={filename} className="h-full w-full object-contain" />

      {/* Top-right status */}
      <div className="absolute right-2 top-2 z-10">{statusBadge}</div>

      {/* Bottom filename strip */}
      <div className="absolute inset-x-0 bottom-0 z-10 bg-gradient-to-t from-black/80 via-black/40 to-transparent px-3 py-2">
        <p className="truncate font-mono text-[11px] text-slate-200" title={filename}>
          {filename}
        </p>
      </div>

      {/* Hover overlay with actions */}
      <div className="absolute inset-0 z-20 flex items-center justify-center gap-2 bg-black/60 opacity-0 backdrop-blur-sm transition-opacity duration-200 group-hover:opacity-100">
        <button
          onClick={(e) => {
            e.stopPropagation();
            openDetail();
          }}
          className="inline-flex items-center gap-1.5 rounded-md bg-white/95 px-3 py-1.5 text-xs font-semibold text-slate-900 hover:bg-white"
        >
          <Eye className="h-3.5 w-3.5" />
          View
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            analyzeMut.mutate();
          }}
          disabled={analyzeMut.isPending}
          className="inline-flex items-center gap-1.5 rounded-md bg-gradient-to-r from-blue-600 to-blue-500 px-3 py-1.5 text-xs font-semibold text-white shadow-lg shadow-blue-500/40 hover:from-blue-500 hover:to-blue-400 disabled:opacity-60"
        >
          {analyzeMut.isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : notAnalyzed ? (
            <Sparkles className="h-3.5 w-3.5" />
          ) : (
            <RotateCcw className="h-3.5 w-3.5" />
          )}
          {analyzeMut.isPending ? 'Analyzing…' : notAnalyzed ? 'Analyze' : 'Re-analyze'}
        </button>
      </div>

      {/* Analyze-in-progress overlay */}
      {analyzeMut.isPending && (
        <div className="pointer-events-none absolute inset-0 z-30 overflow-hidden">
          <div
            className="animate-scan absolute inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-blue-400 to-transparent"
            style={{ boxShadow: '0 0 20px 3px rgba(59,130,246,0.7)' }}
          />
        </div>
      )}

      {/* Click-launch overlay: signals AI is starting */}
      {launching && (
        <div className="pointer-events-none absolute inset-0 z-40 flex items-center justify-center bg-[#0A0F1E]/75 backdrop-blur-[2px]">
          <div className="absolute inset-0 overflow-hidden">
            <div
              className="animate-scan absolute inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-blue-400 to-transparent"
              style={{ boxShadow: '0 0 24px 4px rgba(59,130,246,0.85)' }}
            />
          </div>
          <div className="relative flex flex-col items-center gap-2 text-center">
            <div className="flex h-10 w-10 items-center justify-center rounded-full border border-blue-400/40 bg-blue-500/20 shadow-[0_0_24px_rgba(59,130,246,0.5)]">
              <Sparkles className="h-5 w-5 text-blue-300" />
            </div>
            <p className="text-[11px] font-semibold uppercase tracking-widest text-blue-200">
              Wilhelm AI · starting
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
