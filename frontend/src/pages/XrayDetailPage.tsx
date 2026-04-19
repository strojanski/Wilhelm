import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ChevronRight, Users, Scan, RotateCcw, ZoomIn, ZoomOut,
  Eye, EyeOff, Pencil, Trash2, X, Save, CheckCircle,
  Loader2, AlertTriangle, FileText, Edit3, Download,
} from 'lucide-react';
import { getPatient } from '../api/patients';
import { getVisit, analyzeXray, saveAnnotations, getFileUrl, uploadReport } from '../api/visits';
import { analyzeWithLLM } from '../api/llm';
import type { FractureSegment } from '../api/types';
import Spinner from '../components/Spinner';
import { format } from 'date-fns';
import ReactMarkdown from 'react-markdown';

type DrawMode = 'view' | 'draw' | 'delete';
interface DrawBox { x1: number; y1: number; x2: number; y2: number; }

const FRACTURE_COLOR = 'rgba(255,60,60,0.55)';
const FRACTURE_BORDER = 'rgba(255,60,60,0.95)';
const USER_COLOR = 'rgba(255,200,0,0.55)';
const USER_BORDER = 'rgba(255,200,0,0.95)';

export default function XrayDetailPage() {
  const { ehrId, visitId, filename } = useParams<{ ehrId: string; visitId: string; filename: string }>();
  const decodedFilename = decodeURIComponent(filename ?? '');
  const qc = useQueryClient();

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

  const analysis = visit?.xrayAnnotations?.[decodedFilename];
  const imgUrl = getFileUrl(ehrId!, Number(visitId), 'xray', decodedFilename);

  // ── fracture overlay state ─────────────────────────────────────────────────
  const [segments, setSegments] = useState<FractureSegment[]>(analysis?.segments ?? []);
  const [showOverlay, setShowOverlay] = useState(true);
  const [mode, setMode] = useState<DrawMode>('view');
  const [drawing, setDrawing] = useState<DrawBox | null>(null);
  const [zoom, setZoom] = useState(1);
  const [dirty, setDirty] = useState(false);
  const [selectedSeg, setSelectedSeg] = useState<number | null>(null);

  useEffect(() => {
    maskImagesRef.current.clear();
    setSegments(analysis?.segments ?? []);
    setDirty(false);
  }, [analysis]);

  // ── report state ───────────────────────────────────────────────────────────
  const [reportMd, setReportMd] = useState('');
  const [doctorNotes, setDoctorNotes] = useState('');
  const [reportTab, setReportTab] = useState<'preview' | 'edit'>('preview');
  const [showPdf, setShowPdf] = useState(false);
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null);
  const reportPdfName = `${decodedFilename}_report.pdf`;
  const existingReport = visit?.reportFiles?.includes(reportPdfName) ? reportPdfName : null;
  const reportPdfUrl = existingReport ? getFileUrl(ehrId!, Number(visitId), 'report', existingReport) : null;
  const mdPreviewRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!showPdf || !reportPdfUrl) return;
    if (pdfBlobUrl) return; // already loaded
    fetch(reportPdfUrl)
      .then(r => r.blob())
      .then(blob => setPdfBlobUrl(URL.createObjectURL(blob)));
  }, [showPdf, reportPdfUrl]);

  useEffect(() => {
    return () => { if (pdfBlobUrl) URL.revokeObjectURL(pdfBlobUrl); };
  }, [pdfBlobUrl]);

  // ── canvas refs ────────────────────────────────────────────────────────────
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const [imgNaturalSize, setImgNaturalSize] = useState<{ w: number; h: number } | null>(null);
  // Pre-loaded HTMLImageElements for SAM masks, keyed by annId
  const maskImagesRef = useRef<Map<number, HTMLImageElement>>(new Map());

  // Pre-load mask images whenever segments change
  useEffect(() => {
    let cancelled = false;
    const map = maskImagesRef.current;
    const pending: Promise<void>[] = [];
    segments.forEach((seg) => {
      if (!seg.maskB64 || map.has(seg.annId)) return;
      const p = new Promise<void>((resolve) => {
        const img = new window.Image();
        img.onload = () => { if (!cancelled) { map.set(seg.annId, img); } resolve(); };
        img.onerror = resolve;
        img.src = `data:image/png;base64,${seg.maskB64}`;
      });
      pending.push(p);
    });
    if (pending.length > 0) {
      Promise.all(pending).then(() => { if (!cancelled) renderCanvas(); });
    }
    return () => { cancelled = true; };
  }, [segments]);

  // ── mutations ──────────────────────────────────────────────────────────────
  const analyzeMut = useMutation({
    mutationFn: () => analyzeXray(ehrId!, Number(visitId), decodedFilename),
    onSuccess: (updated) => qc.setQueryData(visitQueryKey, updated),
  });

  const saveMut = useMutation({
    mutationFn: () => saveAnnotations(ehrId!, Number(visitId), decodedFilename, segments),
    onSuccess: (updated) => { qc.setQueryData(visitQueryKey, updated); setDirty(false); },
  });

  const triagePdfUrl = visit?.triageFiles?.length && patient
    ? getFileUrl(ehrId!, Number(visitId), 'triage', visit.triageFiles[0])
    : null;

  const category = analysis
    ? `fracture_probability_${Math.round((analysis.segments[0]?.iouScore ?? 0) * 100)}pct_confidence`
    : 'radiology';

  const reportMut = useMutation({
    mutationFn: () => {
      return analyzeWithLLM(doctorNotes || 'Produce a structured medical radiology report in Markdown.', patient!, category, triagePdfUrl);
    },
    enabled: !!patient,
    onSuccess: (md) => { setReportMd(md); setReportTab('preview'); },
  });

  const saveReportMut = useMutation({
    mutationFn: async () => {
      const { default: jsPDF } = await import('jspdf');
      const { default: html2canvas } = await import('html2canvas');
      const el = mdPreviewRef.current;
      if (!el) throw new Error('No report content');
      const canvas = await html2canvas(el, { scale: 2, useCORS: true, backgroundColor: '#ffffff' });
      const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
      const pageW = pdf.internal.pageSize.getWidth();
      const pageH = pdf.internal.pageSize.getHeight();
      const imgW = pageW - 20;
      const imgH = (canvas.height * imgW) / canvas.width;
      let y = 10;
      let remaining = imgH;
      const dataUrl = canvas.toDataURL('image/png');
      while (remaining > 0) {
        const sliceH = Math.min(remaining, pageH - 20);
        const sliceCanvas = document.createElement('canvas');
        sliceCanvas.width = canvas.width;
        sliceCanvas.height = (sliceH * canvas.width) / imgW;
        const sliceCtx = sliceCanvas.getContext('2d')!;
        sliceCtx.drawImage(canvas, 0, (imgH - remaining) * canvas.width / imgW, canvas.width, sliceCanvas.height, 0, 0, canvas.width, sliceCanvas.height);
        pdf.addImage(sliceCanvas.toDataURL('image/png'), 'PNG', 10, y, imgW, sliceH);
        remaining -= sliceH;
        if (remaining > 0) { pdf.addPage(); y = 10; }
      }
      const blob = pdf.output('blob');
      const file = new File([blob], reportPdfName, { type: 'application/pdf' });
      return uploadReport(ehrId!, Number(visitId), file);
    },
    onSuccess: (updated) => { qc.setQueryData(visitQueryKey, updated); setPdfBlobUrl(null); setShowPdf(true); },
  });

  // ── canvas render ──────────────────────────────────────────────────────────
  const renderCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !imgNaturalSize) return;
    const { w: nw, h: nh } = imgNaturalSize;
    const displayW = canvas.offsetWidth;
    const displayH = canvas.offsetHeight;
    canvas.width = displayW;
    canvas.height = displayH;
    const ctx = canvas.getContext('2d')!;
    ctx.clearRect(0, 0, displayW, displayH);

    // Compute the actual rendered image rect inside the object-contain container
    const scale = Math.min(displayW / nw, displayH / nh);
    const rendW = nw * scale;
    const rendH = nh * scale;
    const offX = (displayW - rendW) / 2;
    const offY = (displayH - rendH) / 2;
    const sx = rendW / nw, sy = rendH / nh;

    if (showOverlay) {
      segments.forEach((seg, idx) => {
        const [x1, y1, x2, y2] = seg.bbox;
        const rx = offX + x1 * sx, ry = offY + y1 * sy, rw = (x2 - x1) * sx, rh = (y2 - y1) * sy;
        const isSelected = selectedSeg === idx;
        const border = seg.userCorrected ? USER_BORDER : FRACTURE_BORDER;
        const fillColor = seg.userCorrected ? USER_COLOR : FRACTURE_COLOR;
        const maskImg = maskImagesRef.current.get(seg.annId);

        if (maskImg) {
          // The SAM mask is a grayscale opaque PNG — convert brightness to alpha.
          // Draw only within the rendered image area (respects object-contain offsets).
          const offscreen = document.createElement('canvas');
          offscreen.width = rendW;
          offscreen.height = rendH;
          const offCtx = offscreen.getContext('2d')!;
          offCtx.drawImage(maskImg, 0, 0, rendW, rendH);
          const pixels = offCtx.getImageData(0, 0, rendW, rendH);
          const [r, g, b] = seg.userCorrected ? [255, 200, 0] : [255, 60, 60];
          const alpha = isSelected ? 180 : 120;
          for (let i = 0; i < pixels.data.length; i += 4) {
            const brightness = pixels.data[i];
            pixels.data[i]     = r;
            pixels.data[i + 1] = g;
            pixels.data[i + 2] = b;
            pixels.data[i + 3] = brightness > 128 ? alpha : 0;
          }
          offCtx.putImageData(pixels, 0, 0);
          ctx.drawImage(offscreen, offX, offY);
        } else {
          // Fallback bbox fill (user-drawn regions without a mask)
          ctx.fillStyle = fillColor;
          ctx.fillRect(rx, ry, rw, rh);
        }

        // Outline bbox for selected or user-drawn segments
        if (!maskImg || isSelected) {
          ctx.strokeStyle = border;
          ctx.lineWidth = isSelected ? 3 : 1.5;
          ctx.strokeRect(rx, ry, rw, rh);
        }

        // Label
        ctx.font = `bold ${Math.max(10, 12 * sx)}px system-ui`;
        ctx.fillStyle = border;
        ctx.fillText(seg.userCorrected ? 'corrected' : `${Math.round(seg.iouScore * 100)}%`, rx + 3, ry - 3);

        if (mode === 'delete') {
          ctx.fillStyle = 'rgba(220,38,38,0.9)';
          ctx.beginPath(); ctx.arc(rx + rw - 6, ry + 6, 8, 0, Math.PI * 2); ctx.fill();
          ctx.fillStyle = '#fff'; ctx.font = 'bold 10px system-ui';
          ctx.fillText('×', rx + rw - 10, ry + 11);
        }
      });
    }
    if (drawing) {
      ctx.strokeStyle = '#facc15'; ctx.lineWidth = 2;
      ctx.setLineDash([6, 3]);
      ctx.strokeRect(offX + drawing.x1 * sx, offY + drawing.y1 * sy, (drawing.x2 - drawing.x1) * sx, (drawing.y2 - drawing.y1) * sy);
      ctx.setLineDash([]);
    }
  }, [segments, showOverlay, drawing, mode, selectedSeg, imgNaturalSize]);

  useEffect(() => { renderCanvas(); }, [renderCanvas]);

  const toImgCoords = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const r = canvasRef.current!.getBoundingClientRect();
    const { w: nw, h: nh } = imgNaturalSize!;
    const displayW = r.width, displayH = r.height;
    const scale = Math.min(displayW / nw, displayH / nh);
    const offX = (displayW - nw * scale) / 2;
    const offY = (displayH - nh * scale) / 2;
    return {
      x: ((e.clientX - r.left) - offX) / scale,
      y: ((e.clientY - r.top)  - offY) / scale,
    };
  };

  const onPointerDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!imgNaturalSize || mode !== 'draw') return;
    const { x, y } = toImgCoords(e);
    setDrawing({ x1: x, y1: y, x2: x, y2: y });
    (e.target as HTMLCanvasElement).setPointerCapture(e.pointerId);
  };
  const onPointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawing || mode !== 'draw' || !imgNaturalSize) return;
    const { x, y } = toImgCoords(e);
    setDrawing((d) => d ? { ...d, x2: x, y2: y } : null);
  };
  const onPointerUp = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (mode === 'draw' && drawing && imgNaturalSize) {
      const b = { x1: Math.min(drawing.x1, drawing.x2), y1: Math.min(drawing.y1, drawing.y2), x2: Math.max(drawing.x1, drawing.x2), y2: Math.max(drawing.y1, drawing.y2) };
      if (b.x2 - b.x1 > 10 && b.y2 - b.y1 > 10) {
        setSegments((p) => [...p, { annId: Date.now(), bbox: [Math.round(b.x1), Math.round(b.y1), Math.round(b.x2), Math.round(b.y2)], iouScore: 1, userCorrected: true }]);
        setDirty(true);
      }
      setDrawing(null);
    }
    if (mode === 'delete' && imgNaturalSize) {
      const { x, y } = toImgCoords(e);
      const hit = segments.findIndex(({ bbox: [x1, y1, x2, y2] }) => x >= x1 && x <= x2 && y >= y1 && y <= y2);
      if (hit >= 0) { setSegments((p) => p.filter((_, i) => i !== hit)); setDirty(true); setSelectedSeg(null); }
    }
    if (mode === 'view' && imgNaturalSize) {
      const { x, y } = toImgCoords(e);
      const hit = segments.findIndex(({ bbox: [x1, y1, x2, y2] }) => x >= x1 && x <= x2 && y >= y1 && y <= y2);
      setSelectedSeg(hit >= 0 ? hit : null);
    }
  };

  const cursor = mode === 'draw' ? 'crosshair' : mode === 'delete' ? 'pointer' : 'default';

  if (isLoading) return <div className="flex justify-center py-20"><Spinner /></div>;

  return (
    <div className="flex flex-col gap-4">
      {/* Hidden div used to render markdown for PDF export */}
      <div style={{ position: 'fixed', left: '-9999px', top: 0, width: '794px', background: '#fff', padding: '40px' }}>
        <div ref={mdPreviewRef} className="prose prose-sm max-w-none text-gray-800">
          <ReactMarkdown>{reportMd}</ReactMarkdown>
        </div>
      </div>
      {/* Breadcrumb */}
      <nav className="flex flex-wrap items-center gap-1 text-sm text-gray-500">
        <Link to="/patients" className="flex items-center gap-1 hover:text-brand-600">
          <Users className="h-3.5 w-3.5" /> Patients
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <Link to={`/patients/${ehrId}`} className="hover:text-brand-600">
          {patient ? `${patient.firstName} ${patient.lastName}` : ehrId}
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <Link to={`/patients/${ehrId}/visits/${visitId}`} className="hover:text-brand-600">
          {visit ? format(new Date(visit.visitDate), 'MMM d, yyyy') : `Visit ${visitId}`}
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <span className="font-medium text-gray-900 font-mono">{decodedFilename}</span>
      </nav>

      {/* Split layout */}
      <div className="flex gap-4 items-start" style={{ minHeight: 0 }}>

        {/* ── LEFT: image + fracture controls ── */}
        <div className="flex flex-col gap-3 min-w-0" style={{ width: '45%' }}>
          <div className="rounded-2xl border border-gray-200 bg-white shadow-sm overflow-hidden">
            {/* toolbar */}
            <div className="flex flex-wrap items-center gap-1.5 border-b border-gray-100 px-4 py-3">
              <span className="text-sm font-semibold text-gray-700 mr-1">Fracture detection</span>

              <button onClick={() => setZoom((z) => Math.min(z + 0.25, 4))}
                className="rounded-lg border border-gray-200 p-1.5 text-gray-500 hover:bg-gray-50" title="Zoom in">
                <ZoomIn className="h-4 w-4" />
              </button>
              <button onClick={() => setZoom((z) => Math.max(z - 0.25, 0.5))}
                className="rounded-lg border border-gray-200 p-1.5 text-gray-500 hover:bg-gray-50" title="Zoom out">
                <ZoomOut className="h-4 w-4" />
              </button>
              <button onClick={() => setShowOverlay((v) => !v)}
                className={`rounded-lg border p-1.5 transition-colors ${showOverlay ? 'border-amber-300 bg-amber-50 text-amber-600' : 'border-gray-200 text-gray-400 hover:bg-gray-50'}`}>
                {showOverlay ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
              </button>

              <div className="mx-1 h-5 w-px bg-gray-200" />

              {!analysis ? (
                <button onClick={() => analyzeMut.mutate()} disabled={analyzeMut.isPending}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-amber-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-600 disabled:opacity-60">
                  {analyzeMut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Scan className="h-3.5 w-3.5" />}
                  {analyzeMut.isPending ? 'Analyzing…' : 'Analyze'}
                </button>
              ) : (
                <button onClick={() => analyzeMut.mutate()} disabled={analyzeMut.isPending}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-60" title="Re-run">
                  {analyzeMut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}
                  Re-analyze
                </button>
              )}

              <button onClick={() => setMode((m) => m === 'draw' ? 'view' : 'draw')}
                className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${mode === 'draw' ? 'bg-yellow-500 text-white' : 'border border-gray-200 bg-white text-gray-600 hover:bg-yellow-50'}`}>
                <Pencil className="h-3.5 w-3.5" />
                {mode === 'draw' ? 'Drawing…' : 'Draw region'}
              </button>
              <button onClick={() => setMode((m) => m === 'delete' ? 'view' : 'delete')}
                className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${mode === 'delete' ? 'bg-red-500 text-white' : 'border border-gray-200 bg-white text-gray-600 hover:bg-red-50'}`}>
                <Trash2 className="h-3.5 w-3.5" />
                {mode === 'delete' ? 'Click to remove' : 'Remove region'}
              </button>
              {mode !== 'view' && (
                <button onClick={() => setMode('view')}
                  className="inline-flex items-center gap-1 rounded-lg border border-gray-200 px-2.5 py-1.5 text-xs text-gray-500 hover:bg-gray-100">
                  <X className="h-3.5 w-3.5" /> Cancel
                </button>
              )}

              <div className="flex-1" />
              {dirty && (
                <button onClick={() => saveMut.mutate()} disabled={saveMut.isPending}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-700 disabled:opacity-60">
                  {saveMut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                  Save corrections
                </button>
              )}
              {saveMut.isSuccess && !dirty && (
                <span className="flex items-center gap-1 text-xs text-green-600">
                  <CheckCircle className="h-3.5 w-3.5" /> Saved
                </span>
              )}
            </div>

            {analyzeMut.isError && (
              <div className="flex items-center gap-2 bg-red-50 px-4 py-2 text-sm text-red-700">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                {(analyzeMut.error as any)?.message ?? 'Analysis failed'}
              </div>
            )}

            {/* image */}
            <div className="bg-black overflow-auto" style={{ height: '420px' }}>
              <div className="relative select-none"
                style={{ width: `${zoom * 100}%`, minHeight: `${zoom * 420}px` }}>
                  <img
                    ref={imgRef}
                    src={imgUrl}
                    alt={decodedFilename}
                    className="block w-full object-contain"
                    style={{ height: `${zoom * 420}px` }}
                    onLoad={(e) => {
                      const el = e.currentTarget;
                      setImgNaturalSize({ w: el.naturalWidth, h: el.naturalHeight });
                    }}
                    draggable={false}
                  />
                  {imgNaturalSize && (
                    <canvas ref={canvasRef} className="absolute inset-0 w-full h-full"
                      style={{ cursor }}
                      onPointerDown={onPointerDown}
                      onPointerMove={onPointerMove}
                      onPointerUp={onPointerUp}
                    />
                  )}
                  {analyzeMut.isPending && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/50">
                      <Spinner size="lg" />
                      <p className="mt-3 text-sm font-medium text-white">Running AI fracture detection…</p>
                    </div>
                  )}
                  {!analysis && !analyzeMut.isPending && (
                    <div className="absolute inset-0 flex items-center justify-center bg-black/30">
                      <div className="rounded-xl bg-white/90 px-5 py-3 text-center shadow-lg">
                        <Scan className="mx-auto mb-1.5 h-6 w-6 text-amber-500" />
                        <p className="text-sm font-semibold text-gray-900">Not analyzed yet</p>
                        <p className="text-xs text-gray-500">Click "Analyze" to detect fractures</p>
                      </div>
                    </div>
                  )}
                </div>
            </div>

            {/* segment chips */}
            {segments.length > 0 && showOverlay && (
              <div className="flex flex-wrap gap-1.5 px-4 py-3 border-t border-gray-100">
                {segments.map((seg, idx) => (
                  <button key={idx}
                    onClick={() => setSelectedSeg(selectedSeg === idx ? null : idx)}
                    className={`inline-flex items-center gap-1 rounded-lg px-2 py-0.5 text-xs font-medium transition-colors ${selectedSeg === idx ? 'bg-red-600 text-white' : seg.userCorrected ? 'bg-yellow-100 text-yellow-800 border border-yellow-200' : 'bg-red-50 text-red-700 border border-red-200'}`}>
                    {seg.userCorrected ? '✏️' : '⚠️'} Region {idx + 1}
                    {!seg.userCorrected && ` · ${Math.round(seg.iouScore * 100)}%`}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── RIGHT: report panel ── */}
        <div className="flex-1 min-w-0 flex flex-col gap-3">
          <div className="rounded-2xl border border-gray-200 bg-white shadow-sm overflow-hidden">
            {/* header */}
            <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
                <FileText className="h-4 w-4 text-brand-500" />
                Medical Report
                {existingReport && (
                  <>
                    <button
                      onClick={() => setShowPdf(v => !v)}
                      className={`ml-2 inline-flex items-center gap-1 rounded-lg px-2 py-0.5 text-xs font-medium transition-colors ${showPdf ? 'bg-brand-100 text-brand-700 border border-brand-200' : 'bg-gray-100 text-gray-600 border border-gray-200 hover:bg-brand-50'}`}>
                      <FileText className="h-3 w-3" />
                      {showPdf ? 'Hide PDF' : 'View PDF'}
                    </button>
                    <a
                      href={reportPdfUrl!}
                      download={reportPdfName}
                      className="ml-1 inline-flex items-center gap-1 rounded-lg px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-600 border border-gray-200 hover:bg-gray-200 transition-colors">
                      <Download className="h-3 w-3" />
                      Download
                    </a>
                  </>
                )}
              </div>
              <div className="flex items-center gap-1.5">
                {reportMd && (
                  <button
                    onClick={() => setReportTab((t) => t === 'edit' ? 'preview' : 'edit')}
                    className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors ${reportTab === 'edit' ? 'bg-brand-50 text-brand-700 border border-brand-200' : 'border border-gray-200 text-gray-600 hover:bg-gray-50'}`}>
                    <Edit3 className="h-3.5 w-3.5" />
                    {reportTab === 'edit' ? 'Preview' : 'Edit'}
                  </button>
                )}
                {reportMd && (
                  <button
                    onClick={() => saveReportMut.mutate()}
                    disabled={saveReportMut.isPending}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-60">
                    {saveReportMut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : saveReportMut.isSuccess ? <CheckCircle className="h-3.5 w-3.5 text-green-500" /> : <Save className="h-3.5 w-3.5" />}
                    {saveReportMut.isPending ? 'Saving…' : saveReportMut.isSuccess ? 'Saved' : 'Save'}
                  </button>
                )}
                <button
                  onClick={() => reportMut.mutate()}
                  disabled={reportMut.isPending}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-700 disabled:opacity-60">
                  {reportMut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileText className="h-3.5 w-3.5" />}
                  {reportMut.isPending ? 'Generating…' : reportMd ? 'Regenerate' : 'Generate Report'}
                </button>
              </div>
            </div>

            {/* Doctor notes input */}
            {!showPdf && (
              <div className="px-4 pt-3 border-b border-gray-100">
                <label className="block text-xs font-medium text-gray-600 mb-1">Doctor notes</label>
                <textarea
                  value={doctorNotes}
                  onChange={(e) => setDoctorNotes(e.target.value)}
                  placeholder="Add clinical observations, symptoms, or notes to include in the report…"
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-xs text-gray-800 placeholder-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 resize-none"
                  rows={3}
                />
              </div>
            )}

            {/* PDF viewer */}
            {showPdf && (
              <div className="w-full border-b border-gray-100" style={{ height: '600px' }}>
                {pdfBlobUrl
                  ? <iframe src={pdfBlobUrl} className="w-full h-full" title="Medical Report PDF" />
                  : <div className="flex items-center justify-center h-full text-gray-400"><Loader2 className="h-6 w-6 animate-spin" /></div>
                }
              </div>
            )}

            {/* report content */}
            {!showPdf && <div className="p-4 overflow-y-auto" style={{ maxHeight: '600px' }}>
              {reportMut.isError && (
                <div className="flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 mb-3">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  {(reportMut.error as any)?.message ?? 'Report generation failed'}
                </div>
              )}

              {reportMut.isPending && (
                <div className="flex flex-col items-center justify-center py-12 text-gray-400">
                  <Loader2 className="h-8 w-8 animate-spin mb-3" />
                  <p className="text-sm">Generating report…</p>
                </div>
              )}

              {!reportMd && !reportMut.isPending && (
                <div className="flex flex-col items-center justify-center py-12 text-center text-gray-400">
                  <FileText className="h-8 w-8 mb-3 opacity-40" />
                  <p className="text-sm font-medium text-gray-500">No report yet</p>
                  <p className="text-xs mt-1">Click "Generate Report" to create an AI medical report for this X-ray</p>
                </div>
              )}

              {reportMd && !reportMut.isPending && (
                <>
                  {reportTab === 'preview' ? (
                    <div className="prose prose-sm max-w-none
                      text-gray-700 leading-relaxed
                      prose-headings:font-semibold prose-headings:text-gray-900 prose-headings:mt-4 prose-headings:mb-1
                      prose-h1:text-sm prose-h1:uppercase prose-h1:tracking-wide prose-h1:text-brand-700 prose-h1:border-b prose-h1:border-brand-100 prose-h1:pb-1
                      prose-h2:text-sm prose-h2:text-gray-800
                      prose-h3:text-xs prose-h3:text-gray-600 prose-h3:uppercase prose-h3:tracking-wide
                      prose-p:my-1 prose-p:text-xs
                      prose-li:text-xs prose-li:my-0
                      prose-ul:my-1 prose-ol:my-1
                      prose-strong:text-gray-900 prose-strong:font-semibold
                      prose-hr:my-3 prose-hr:border-gray-200">
                      <ReactMarkdown>{reportMd}</ReactMarkdown>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-2">
                      <textarea
                        value={reportMd}
                        onChange={(e) => setReportMd(e.target.value)}
                        className="w-full rounded-lg border border-gray-300 p-3 font-mono text-xs text-gray-800 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 resize-none"
                        rows={20}
                      />
                      <button
                        onClick={() => setReportTab('preview')}
                        className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-brand-600 px-3 py-2 text-xs font-semibold text-white hover:bg-brand-700">
                        <CheckCircle className="h-3.5 w-3.5" /> Done editing
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>}
          </div>
        </div>
      </div>
    </div>
  );
}
