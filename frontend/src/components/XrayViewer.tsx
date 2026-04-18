import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Scan, Loader2, RotateCcw, ChevronRight } from 'lucide-react';
import { analyzeXray, getFileUrl } from '../api/visits';
import type { FractureSegment, XrayAnalysis } from '../api/types';

interface Props {
  ehrId: string;
  visitId: number;
  filename: string;
  analysis: XrayAnalysis | undefined;
  queryKey: unknown[];
}

export default function XrayViewer({ ehrId, visitId, filename, analysis, queryKey }: Props) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const imgUrl = getFileUrl(ehrId, visitId, 'xray', filename);

  const [segments] = useState<FractureSegment[]>(analysis?.segments ?? []);

  const analyzeMut = useMutation({
    mutationFn: () => analyzeXray(ehrId, visitId, filename),
    onSuccess: (updated) => {
      qc.setQueryData(queryKey, updated);
    },
  });

  const notAnalyzed = !analysis;
  const hasSegments = segments.length > 0;

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors"
        onClick={() => navigate(`/patients/${ehrId}/visits/${visitId}/xray/${encodeURIComponent(filename)}`)}
      >
        {/* Thumbnail */}
        <div className="relative h-12 w-12 shrink-0 overflow-hidden rounded-lg border border-gray-200 bg-gray-100">
          <img src={imgUrl} alt="" className="h-full w-full object-cover" />
          {hasSegments && (
            <div className="absolute inset-0 flex items-center justify-center bg-red-500/20">
              <span className="text-[10px] font-bold text-red-700">{segments.length}</span>
            </div>
          )}
        </div>

        {/* Filename + status badges */}
        <div className="flex min-w-0 flex-1 items-center gap-2 flex-wrap">
          <span className="font-mono text-sm font-medium text-gray-800 truncate max-w-[180px]" title={filename}>
            {filename}
          </span>
          {!analysis && (
            <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500">not analyzed</span>
          )}
          {analysis?.corrected && (
            <span className="rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-700">corrected</span>
          )}
          {hasSegments && (
            <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
              {segments.length} fracture{segments.length !== 1 ? 's' : ''}
            </span>
          )}
          {analysis && !hasSegments && (
            <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">clear</span>
          )}
        </div>

        {/* Right-side actions */}
        <div className="flex shrink-0 items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
          {notAnalyzed ? (
            <button
              onClick={() => analyzeMut.mutate()}
              disabled={analyzeMut.isPending}
              className="inline-flex items-center gap-1.5 rounded-lg bg-amber-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-600 disabled:opacity-60"
            >
              {analyzeMut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Scan className="h-3.5 w-3.5" />}
              {analyzeMut.isPending ? 'Analyzing…' : 'Analyze'}
            </button>
          ) : (
            <button
              onClick={() => analyzeMut.mutate()}
              disabled={analyzeMut.isPending}
              className="rounded-lg border border-gray-200 p-1.5 text-gray-400 hover:bg-gray-100 disabled:opacity-50"
              title="Re-analyze"
            >
              {analyzeMut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}
            </button>
          )}
          <ChevronRight className="h-4 w-4 text-gray-300" />
        </div>
      </div>
    </div>
  );
}
