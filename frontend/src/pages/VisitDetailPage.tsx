import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ChevronRight,
  Users,
  FileText,
  ClipboardList,
  Scan,
  Download,
  ExternalLink,
} from 'lucide-react';
import { getPatient } from '../api/patients';
import { getVisit, uploadTriage, uploadReport, uploadXray, getFileUrl } from '../api/visits';
import Spinner from '../components/Spinner';
import FileUploadButton from '../components/FileUploadButton';
import XrayViewer from '../components/XrayViewer';
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

  if (isLoading) {
    return <div className="flex justify-center py-20"><Spinner /></div>;
  }

  if (!visit) {
    return <p className="py-20 text-center text-gray-500">Visit not found.</p>;
  }

  return (
    <div>
      {/* Breadcrumb */}
      <nav className="mb-6 flex flex-wrap items-center gap-1 text-sm text-gray-500">
        <Link to="/patients" className="flex items-center gap-1 hover:text-brand-600">
          <Users className="h-3.5 w-3.5" /> Patients
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <Link to={`/patients/${ehrId}`} className="hover:text-brand-600">
          {patient ? `${patient.firstName} ${patient.lastName}` : ehrId}
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <span className="font-medium text-gray-900">
          Visit {format(new Date(visit.visitDate), 'MMM d, yyyy')}
        </span>
      </nav>

      {/* Visit header */}
      <div className="mb-6 rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              {format(new Date(visit.visitDate), 'MMMM d, yyyy')}
            </h1>
            <p className="mt-0.5 text-sm text-gray-400">
              Created {format(new Date(visit.createdAt), "MMM d, yyyy 'at' HH:mm")} · Visit #{visit.id}
            </p>
          </div>
          <div className="flex gap-4 text-sm text-gray-500">
            <span>{visit.triageFiles.length} triage</span>
            <span>{visit.reportFiles.length} reports</span>
            <span>{visit.xrayFiles.length} x-rays</span>
          </div>
        </div>
      </div>

      {uploadError && (
        <div className="mb-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
          {uploadError}
        </div>
      )}

      {/* Triage + Reports side by side */}
      <div className="mb-6 grid gap-6 lg:grid-cols-2">
        {/* Triage */}
        <div className="rounded-2xl border border-blue-200 bg-white shadow-sm overflow-hidden">
          <div className="flex items-center justify-between border-b border-blue-200 bg-blue-50 px-5 py-4 text-blue-700">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100 text-blue-600">
                <ClipboardList className="h-4 w-4" />
              </div>
              <span className="font-semibold">Triage</span>
            </div>
            <span className="text-xs font-medium opacity-70">
              {visit.triageFiles.length} file{visit.triageFiles.length !== 1 ? 's' : ''}
            </span>
          </div>
          <div className="p-5">
            {visit.triageFiles.length === 0 ? (
              <p className="mb-4 text-sm text-gray-400">No files uploaded yet.</p>
            ) : (
              <ul className="mb-4 space-y-2">
                {visit.triageFiles.map((filename) => (
                  <FileRow
                    key={filename}
                    filename={filename}
                    href={getFileUrl(ehrId!, visit.id, 'triage', filename)}
                  />
                ))}
              </ul>
            )}
            <FileUploadButton
              label="Upload Triage"
              accept=".pdf"
              loading={uploading === 'triage'}
              onFile={(f) => handleUpload('triage', f)}
            />
          </div>
        </div>

        {/* Medical Reports */}
        <div className="rounded-2xl border border-green-200 bg-white shadow-sm overflow-hidden">
          <div className="flex items-center justify-between border-b border-green-200 bg-green-50 px-5 py-4 text-green-700">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-green-100 text-green-600">
                <FileText className="h-4 w-4" />
              </div>
              <span className="font-semibold">Medical Reports</span>
            </div>
            <span className="text-xs font-medium opacity-70">
              {visit.reportFiles.length} file{visit.reportFiles.length !== 1 ? 's' : ''}
            </span>
          </div>
          <div className="p-5">
            {visit.reportFiles.length === 0 ? (
              <p className="mb-4 text-sm text-gray-400">No files uploaded yet.</p>
            ) : (
              <ul className="mb-4 space-y-2">
                {visit.reportFiles.map((filename) => (
                  <FileRow
                    key={filename}
                    filename={filename}
                    href={getFileUrl(ehrId!, visit.id, 'report', filename)}
                  />
                ))}
              </ul>
            )}
            <FileUploadButton
              label="Upload Report"
              accept=".pdf"
              loading={uploading === 'report'}
              onFile={(f) => handleUpload('report', f)}
            />
          </div>
        </div>
      </div>

      {/* X-Rays — full width with AI viewer per image */}
      <div className="rounded-2xl border border-amber-200 bg-white shadow-sm overflow-hidden">
        <div className="flex items-center justify-between border-b border-amber-200 bg-amber-50 px-5 py-4 text-amber-700">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-100 text-amber-600">
              <Scan className="h-4 w-4" />
            </div>
            <span className="font-semibold">X-Rays</span>
            <span className="text-xs opacity-60">— AI fracture detection</span>
          </div>
          <span className="text-xs font-medium opacity-70">
            {visit.xrayFiles.length} file{visit.xrayFiles.length !== 1 ? 's' : ''}
          </span>
        </div>
        <div className="space-y-6 p-5">
          {visit.xrayFiles.length === 0 && (
            <p className="text-sm text-gray-400">No X-rays uploaded yet.</p>
          )}
          {visit.xrayFiles.map((filename) => (
            <XrayViewer
              key={filename}
              ehrId={ehrId!}
              visitId={visit.id}
              filename={filename}
              analysis={visit.xrayAnnotations?.[filename]}
              queryKey={visitQueryKey}
            />
          ))}
          <FileUploadButton
            label="Upload X-Ray"
            accept="image/*,.png,.jpg,.jpeg"
            loading={uploading === 'xray'}
            onFile={(f) => handleUpload('xray', f)}
          />
        </div>
      </div>
    </div>
  );
}

function FileRow({ filename, href }: { filename: string; href: string }) {
  return (
    <li className="flex items-center justify-between rounded-lg border border-gray-100 bg-gray-50 px-3 py-2 text-sm">
      <span className="truncate font-mono text-xs text-gray-700 max-w-[200px]" title={filename}>
        {filename}
      </span>
      <div className="flex shrink-0 gap-1 ml-2">
        <a href={href} target="_blank" rel="noreferrer"
          className="rounded p-1 text-gray-400 hover:text-brand-600" title="Open">
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
        <a href={href} download={filename}
          className="rounded p-1 text-gray-400 hover:text-brand-600" title="Download">
          <Download className="h-3.5 w-3.5" />
        </a>
      </div>
    </li>
  );
}
