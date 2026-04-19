import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ScanLine, RotateCcw, ZoomIn, ZoomOut,
  Eye, EyeOff, Pencil, Trash2, X, Save, CheckCircle,
  Loader2, AlertTriangle, FileText, Edit3, Download, Sparkles,
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

const ACCENT = '#9f1239';

function seededBarcode(seed: string, width = 150, height = 40, scale = 1) {
  let h = 0;
  for (const c of seed) h = ((h << 5) - h + c.charCodeAt(0)) | 0;
  let rnd = (Math.abs(h) || 42) >>> 0;
  const bars: Array<{ x: number; w: number }> = [];
  let x = 0;
  while (x < width) {
    rnd = (rnd * 1103515245 + 12345) >>> 0;
    const barW = ((rnd % 3) + 1) * scale;
    rnd = (rnd * 1103515245 + 12345) >>> 0;
    const gapW = ((rnd % 3) + 1) * scale;
    if (x + barW > width) break;
    bars.push({ x, w: barW });
    x += barW + gapW;
  }
  const digits = (Math.abs(h) % 1_000_000_000).toString().padStart(9, '0');
  return { bars, height, width, digits };
}

function Barcode({ seed, width = 150, height = 40 }: { seed: string; width?: number; height?: number }) {
  const { bars, digits } = seededBarcode(seed, width, height);
  return (
    <div style={{ display: 'inline-block', textAlign: 'center' }}>
      <div style={{ position: 'relative', width: `${width}px`, height: `${height}px`, background: '#fff' }}>
        {bars.map((b, i) => (
          <div key={i} style={{ position: 'absolute', left: `${b.x}px`, top: 0, width: `${b.w}px`, height: `${height}px`, background: '#000' }} />
        ))}
      </div>
      <div style={{ fontSize: '9px', letterSpacing: '0.25em', marginTop: '2px', fontFamily: 'Arial, Helvetica, sans-serif', color: '#000' }}>
        {digits}
      </div>
    </div>
  );
}

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
        img.onerror = () => resolve();
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

  // ── auto-run fracture analysis on arrival when not yet analyzed ────────────
  const autoAnalyzedRef = useRef(false);
  useEffect(() => {
    if (autoAnalyzedRef.current) return;
    if (!visit) return;
    if (analysis) return;
    if (analyzeMut.isPending) return;
    autoAnalyzedRef.current = true;
    analyzeMut.mutate();
  }, [visit, analysis, analyzeMut]);

  // ── auto-save PDF immediately after report is generated ────────────────────
  const autoSavedRef = useRef(false);
  useEffect(() => {
    if (autoSavedRef.current) return;
    if (!reportMd || !reportMut.isSuccess) return;
    if (existingReport) return;
    if (saveReportMut.isPending) return;
    autoSavedRef.current = true;
    const id = window.setTimeout(() => saveReportMut.mutate(), 300);
    return () => window.clearTimeout(id);
  }, [reportMd, reportMut.isSuccess, existingReport, saveReportMut]);

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

        // Ground-truth bbox — always shown in green (AI) or amber (user-corrected)
        ctx.strokeStyle = seg.userCorrected
          ? 'rgba(251,191,36,0.95)'
          : 'rgba(74,222,128,0.95)';
        ctx.lineWidth = isSelected ? 3 : 1.5;
        ctx.strokeRect(rx, ry, rw, rh);

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

  // ── magnifier state ────────────────────────────────────────────────────────
  const MAGNIFIER_SIZE = 160;
  const MAGNIFIER_ZOOM = 3;
  const [magnifier, setMagnifier] = useState<{ x: number; y: number } | null>(null);

  const onMouseMoveImg = (e: React.MouseEvent<HTMLDivElement>) => {
    if (mode !== 'view') return;
    const rect = e.currentTarget.getBoundingClientRect();
    setMagnifier({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  };

  if (isLoading) {
    return (
      <div className="flex h-[calc(100vh-3rem)] items-center justify-center bg-[#0A0F1E]">
        <Spinner />
      </div>
    );
  }

  const ToolbarBtn = ({
    onClick, active, disabled, title, children,
  }: { onClick: () => void; active?: boolean; disabled?: boolean; title: string; children: React.ReactNode }) => (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`group flex h-10 w-10 items-center justify-center rounded-md border backdrop-blur transition-all duration-150 disabled:opacity-40 ${
        active
          ? 'border-blue-500/70 bg-blue-500/20 text-blue-300 ring-1 ring-blue-500/60'
          : 'border-slate-700/80 bg-slate-900/70 text-slate-300 hover:border-blue-500/50 hover:text-blue-300'
      }`}
    >
      {children}
    </button>
  );

  return (
    <>
      {/* Hidden div used to render markdown for PDF export — izvid layout, English */}
      <div style={{ position: 'fixed', left: '-9999px', top: 0, width: '794px', background: '#fff' }}>
        <div ref={mdPreviewRef} style={{ fontFamily: '"Times New Roman", Georgia, serif', color: '#000', background: '#fff', padding: '56px 64px', fontSize: '11.5px', lineHeight: 1.55 }}>

          {/* Top row: registration/patient grid (left) + hospital branding (right) */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '18px' }}>

            {/* Left: labels + values, two-column grid, sans-serif */}
            <div style={{ flex: 1, fontFamily: 'Arial, Helvetica, sans-serif', fontSize: '11px', color: '#000' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '110px 1fr', columnGap: '24px', rowGap: '6px', alignItems: 'baseline' }}>
                <div>Reg. No.</div>
                <div>Patient ID:</div>

                <div style={{ fontSize: '26px', fontWeight: 300, letterSpacing: '0.01em', lineHeight: 1 }}>
                  {String(visit?.id ?? 0).padStart(5, '0')}/26
                </div>
                <div style={{ fontSize: '11px' }}>{patient?.ehrId ?? '—'}</div>

                <div>Name:</div>
                <div style={{ textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  {patient ? `${patient.lastName}   ${patient.firstName}` : '—'}
                </div>

                <div>Sex / Age:</div>
                <div>{patient ? `${patient.gender}, ${patient.age} years` : '—'}</div>

                <div>Date of birth:</div>
                <div>—</div>
              </div>
            </div>

            {/* Right: hospital name, logo mark, department block */}
            <div style={{ textAlign: 'right', minWidth: '260px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '8px' }}>
                <div style={{ fontFamily: 'Georgia, "Times New Roman", serif', fontSize: '16px', fontWeight: 400, color: '#000', letterSpacing: '0.005em' }}>
                  wilhelm medical center
                </div>
                <svg width="26" height="20" viewBox="0 0 26 20">
                  <path d="M2 18 C 6 2, 12 2, 14 10 C 16 18, 22 18, 24 4" stroke={ACCENT} strokeWidth="3" fill="none" strokeLinecap="round" />
                </svg>
              </div>
              <div style={{ marginTop: '8px', fontFamily: 'Arial, Helvetica, sans-serif', fontSize: '10.5px', color: '#000', lineHeight: 1.55, textAlign: 'right' }}>
                <div style={{ color: ACCENT, fontWeight: 600 }}>Radiology Clinic</div>
                <div style={{ textTransform: 'uppercase', letterSpacing: '0.02em' }}>Emergency Imaging Unit</div>
                <div>AI-Assisted Fracture Detection</div>
                <div>Ljubljana, Zaloška 7</div>
              </div>
            </div>
          </div>

          {/* Second row: barcode + visit/report dates (right side) */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'flex-start', gap: '40px', marginTop: '4px', marginBottom: '22px', fontFamily: 'Arial, Helvetica, sans-serif', fontSize: '11px' }}>
            <div>
              <Barcode seed={`${patient?.ehrId ?? 'X'}-${visit?.id ?? 0}-${decodedFilename}`} width={160} height={42} />
            </div>
            <div style={{ textAlign: 'right', color: '#000', lineHeight: 1.6 }}>
              <div>Date of visit: <span style={{ fontWeight: 600 }}>{visit ? format(new Date(visit.visitDate), 'dd.MM.yyyy') : '—'}</span></div>
              <div>Date of report: <span style={{ fontWeight: 600 }}>{format(new Date(), 'dd.MM.yyyy HH:mm')}</span></div>
            </div>
          </div>

          {/* Separator + template subheader */}
          <hr style={{ border: 'none', borderTop: '0.7px solid #000', margin: 0 }} />
          <p style={{ fontFamily: 'Arial, Helvetica, sans-serif', fontSize: '11px', color: '#000', margin: '10px 0', fontStyle: 'normal' }}>
            The patient was examined in the radiology department for diagnostic imaging and fracture assessment.
          </p>
          <hr style={{ border: 'none', borderTop: '0.7px solid #000', margin: '0 0 22px' }} />

          {/* Department code line */}
          <div style={{ fontFamily: '"Times New Roman", Georgia, serif', fontSize: '11px', color: '#000', marginBottom: '2px' }}>
            rd/xr
          </div>

          {/* Markdown body — serif, izvid-style plain headings */}
          <div style={{ fontSize: '11.5px', lineHeight: 1.6, color: '#000' }}
            dangerouslySetInnerHTML={{ __html: (() => {
              let html = reportMd
                .replace(/^# (.+)$/gm, '<h1 style="font-size:13px;font-weight:400;color:#000;margin:18px 0 4px;font-family:\'Times New Roman\',Georgia,serif">$1</h1>')
                .replace(/^## (.+)$/gm, '<h2 style="font-size:12px;font-weight:400;color:#000;margin:16px 0 3px;font-family:\'Times New Roman\',Georgia,serif">$1</h2>')
                .replace(/^### (.+)$/gm, '<h3 style="font-size:11px;font-weight:400;color:#000;margin:12px 0 2px;font-family:\'Times New Roman\',Georgia,serif;font-style:italic">$1</h3>')
                .replace(/\*\*(.+?)\*\*/g, '<strong style="color:#000;font-weight:700">$1</strong>')
                .replace(/^---+$/gm, '<hr style="border:none;border-top:0.5px solid #000;margin:16px 0" />')
                .replace(/^- (.+)$/gm, '<li style="margin:1px 0">$1</li>')
                .replace(/(<li[^>]*>.*<\/li>\n?)+/g, (m) => `<ul style="margin:4px 0;padding-left:22px;list-style:disc">${m}</ul>`)
                .replace(/^(?!<[hul]|<hr|<strong)(.+)$/gm, '<p style="margin:4px 0">$1</p>');
              return html;
            })() }}
          />

          {/* Small italic ancillary print */}
          <p style={{ fontSize: '9.5px', color: '#000', fontStyle: 'italic', margin: '22px 0 0', lineHeight: 1.55, fontFamily: '"Times New Roman", Georgia, serif' }}>
            Should you require these X-ray images for consultation outside our institution, they may be collected from
            the Radiology Department reception, Monday to Friday between 08:00 and 19:00. Please bring a valid form of
            identification and this report. Authorised representatives must present written authorisation signed by the
            patient in order to collect the images.
          </p>

          {/* Signature */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '48px', marginBottom: '60px' }}>
            <div style={{ textAlign: 'left', fontFamily: '"Times New Roman", Georgia, serif', fontSize: '11.5px', color: '#000', minWidth: '220px' }}>
              <div>Wilhelm AI Radiology System,</div>
              <div>electronic radiology report</div>
            </div>
          </div>

          {/* Footer */}
          <div style={{ borderTop: '0.5px solid #000', paddingTop: '6px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', fontSize: '9px', color: '#000', fontFamily: 'Arial, Helvetica, sans-serif' }}>
            <div style={{ lineHeight: 1.4 }}>
              Signed by: Hospital<br/>
              information system<br/>
              Wilhelm Medical Center
            </div>
            <div>Page: 1 of 1</div>
          </div>
        </div>
      </div>

      {/* Split layout — full viewport minus header */}
      <div className="flex h-[calc(100vh-3rem)] w-full bg-[#0A0F1E] text-slate-200">

        {/* ═══════════════════ LEFT: DICOM-style dark viewer (55%) ═══════════════════ */}
        <section className="relative flex w-[55%] min-w-0 flex-col border-r border-slate-800">

          {/* Canvas area */}
          <div className="relative flex-1 overflow-auto bg-black">
            <div
              className="relative select-none"
              style={{ width: `${zoom * 100}%`, minHeight: '100%' }}
              onMouseMove={onMouseMoveImg}
              onMouseLeave={() => setMagnifier(null)}
            >
              <img
                ref={imgRef}
                src={imgUrl}
                alt={decodedFilename}
                className="block h-full w-full object-contain"
                style={{ minHeight: `calc(100vh - 3rem - 48px)` }}
                onLoad={(e) => {
                  const el = e.currentTarget;
                  setImgNaturalSize({ w: el.naturalWidth, h: el.naturalHeight });
                }}
                draggable={false}
              />
              {imgNaturalSize && (
                <canvas
                  ref={canvasRef}
                  className="absolute inset-0 h-full w-full"
                  style={{
                    cursor,
                    filter: 'drop-shadow(0 0 6px rgba(244,63,94,0.35))',
                  }}
                  onPointerDown={onPointerDown}
                  onPointerMove={onPointerMove}
                  onPointerUp={onPointerUp}
                />
              )}

              {/* Magnifier lens */}
              {magnifier && mode === 'view' && imgNaturalSize && (() => {
                const containerW = (canvasRef.current?.offsetWidth ?? imgNaturalSize.w) ;
                const containerH = (canvasRef.current?.offsetHeight ?? imgNaturalSize.h);
                const bgW = containerW * MAGNIFIER_ZOOM;
                const bgH = containerH * MAGNIFIER_ZOOM;
                const bgX = -(magnifier.x * MAGNIFIER_ZOOM - MAGNIFIER_SIZE / 2);
                const bgY = -(magnifier.y * MAGNIFIER_ZOOM - MAGNIFIER_SIZE / 2);
                return (
                  <div
                    className="pointer-events-none absolute z-30 rounded-full border-2 border-blue-400/70 shadow-xl shadow-black/60 overflow-hidden"
                    style={{
                      width: MAGNIFIER_SIZE,
                      height: MAGNIFIER_SIZE,
                      left: magnifier.x - MAGNIFIER_SIZE / 2,
                      top: magnifier.y - MAGNIFIER_SIZE - 16,
                      backgroundImage: `url(${imgUrl})`,
                      backgroundRepeat: 'no-repeat',
                      backgroundSize: `${bgW}px ${bgH}px`,
                      backgroundPosition: `${bgX}px ${bgY}px`,
                    }}
                  />
                );
              })()}

              {/* Scan line animation during analysis */}
              {analyzeMut.isPending && (
                <div className="pointer-events-none absolute inset-0 overflow-hidden">
                  <div
                    className="animate-scan absolute inset-x-0 h-[3px] bg-gradient-to-r from-transparent via-blue-400 to-transparent"
                    style={{ boxShadow: '0 0 24px 4px rgba(59,130,246,0.7)' }}
                  />
                  <div className="absolute inset-x-0 top-0 bg-gradient-to-b from-blue-500/10 via-transparent to-transparent h-full" />
                </div>
              )}

              {/* Analyzing label */}
              {analyzeMut.isPending && (
                <div className="pointer-events-none absolute left-1/2 top-6 -translate-x-1/2 rounded-full border border-blue-500/40 bg-slate-900/80 px-4 py-1.5 text-xs font-medium text-blue-300 backdrop-blur">
                  <span className="inline-flex items-center gap-2">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    Running AI fracture detection…
                  </span>
                </div>
              )}

              {/* Idle empty state */}
              {!analysis && !analyzeMut.isPending && (
                <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                  <div className="rounded-xl border border-slate-700/60 bg-slate-900/60 px-5 py-4 text-center backdrop-blur-sm">
                    <Sparkles className="mx-auto mb-2 h-6 w-6 text-blue-400" />
                    <p className="text-sm font-semibold text-slate-100">Ready for analysis</p>
                    <p className="mt-0.5 text-xs text-slate-400">Click "Analyze with AI" below</p>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Vertical toolbar — pinned left edge */}
          <div className="absolute left-3 top-3 flex flex-col gap-1.5 z-20">
            <ToolbarBtn onClick={() => setZoom((z) => Math.min(z + 0.25, 4))} title="Zoom in">
              <ZoomIn className="h-4 w-4" />
            </ToolbarBtn>
            <ToolbarBtn onClick={() => setZoom((z) => Math.max(z - 0.25, 0.5))} title="Zoom out">
              <ZoomOut className="h-4 w-4" />
            </ToolbarBtn>
            <ToolbarBtn onClick={() => setZoom(1)} title="Fit to screen">
              <RotateCcw className="h-4 w-4" />
            </ToolbarBtn>
            <div className="my-1 h-px bg-slate-800" />
            <ToolbarBtn onClick={() => setShowOverlay((v) => !v)} active={showOverlay} title={showOverlay ? 'Hide overlay' : 'Show overlay'}>
              {showOverlay ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
            </ToolbarBtn>
            <ToolbarBtn onClick={() => setMode((m) => m === 'draw' ? 'view' : 'draw')} active={mode === 'draw'} title="Draw region">
              <Pencil className="h-4 w-4" />
            </ToolbarBtn>
            <ToolbarBtn onClick={() => setMode((m) => m === 'delete' ? 'view' : 'delete')} active={mode === 'delete'} title="Remove region">
              <Trash2 className="h-4 w-4" />
            </ToolbarBtn>
            {mode !== 'view' && (
              <ToolbarBtn onClick={() => setMode('view')} title="Cancel">
                <X className="h-4 w-4" />
              </ToolbarBtn>
            )}
            {dirty && (
              <>
                <div className="my-1 h-px bg-slate-800" />
                <button
                  onClick={() => saveMut.mutate()}
                  disabled={saveMut.isPending}
                  title="Save corrections"
                  className="flex h-10 w-10 items-center justify-center rounded-md border border-emerald-500/60 bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25 disabled:opacity-50"
                >
                  {saveMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                </button>
              </>
            )}
            {saveMut.isSuccess && !dirty && (
              <div className="flex h-10 w-10 items-center justify-center rounded-md border border-emerald-500/30 bg-emerald-500/10 text-emerald-400" title="Saved">
                <CheckCircle className="h-4 w-4" />
              </div>
            )}
          </div>

          {/* Error banner — top center */}
          {analyzeMut.isError && (
            <div className="absolute left-1/2 top-3 z-20 flex -translate-x-1/2 items-center gap-2 rounded-md border border-rose-500/50 bg-rose-500/15 px-3 py-1.5 text-xs text-rose-200 backdrop-blur">
              <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
              {(analyzeMut.error as any)?.message ?? 'Analysis failed'}
            </div>
          )}

          {/* Filename badge — top right */}
          <div className="absolute right-3 top-3 z-20 rounded-md border border-slate-700/80 bg-slate-900/70 px-2.5 py-1 font-mono text-[10px] text-slate-400 backdrop-blur">
            {decodedFilename}
          </div>

          {/* Segment chips — absolute, above bottom CTA */}
          {segments.length > 0 && showOverlay && (
            <div className="absolute bottom-[60px] left-0 right-0 z-10 px-4">
              <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
                <span className="shrink-0 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                  Regions
                </span>
                {segments.map((seg, idx) => {
                  const isSel = selectedSeg === idx;
                  return (
                    <button
                      key={idx}
                      onClick={() => setSelectedSeg(isSel ? null : idx)}
                      className={`shrink-0 inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs backdrop-blur transition-all duration-150 ${
                        isSel
                          ? 'border-blue-500 bg-blue-500/20 text-blue-200 ring-2 ring-blue-500/60 ring-offset-2 ring-offset-[#0A0F1E]'
                          : 'border-slate-700 bg-slate-900/80 text-slate-200 hover:border-slate-500'
                      }`}
                    >
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${
                          seg.userCorrected ? 'bg-amber-400' : 'bg-rose-500'
                        }`}
                        style={seg.userCorrected ? undefined : { boxShadow: '0 0 6px rgba(244,63,94,0.8)' }}
                      />
                      <span className="font-medium">Region {idx + 1}</span>
                      <span className="font-mono text-[10px] text-slate-400">
                        {seg.userCorrected ? 'user' : `${Math.round(seg.iouScore * 100)}%`}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Bottom CTA strip */}
          <div className="relative z-10 flex h-12 items-center justify-center border-t border-slate-800 bg-slate-950/90 backdrop-blur">
            <button
              onClick={() => analyzeMut.mutate()}
              disabled={analyzeMut.isPending}
              className={`group inline-flex items-center gap-2 rounded-md bg-gradient-to-r from-blue-600 to-blue-500 px-6 py-2 text-sm font-semibold text-white shadow-lg shadow-blue-500/40 transition-all duration-200 hover:from-blue-500 hover:to-blue-400 hover:shadow-blue-500/60 disabled:opacity-60`}
            >
              {analyzeMut.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <ScanLine className="h-4 w-4" />
              )}
              {analyzeMut.isPending
                ? 'Analyzing…'
                : analysis
                  ? 'Re-analyze with AI'
                  : 'Analyze with AI'}
            </button>
          </div>
        </section>

        {/* ═══════════════════ RIGHT: light report panel (45%) ═══════════════════ */}
        <section className="flex w-[45%] min-w-0 flex-col bg-slate-50 text-slate-900">

          {/* Patient context strip */}
          <div className="flex h-12 shrink-0 items-center gap-3 border-b border-slate-200 bg-white px-5 text-xs">
            <FileText className="h-4 w-4 text-blue-500" />
            <span className="font-semibold text-slate-900">
              {patient ? `${patient.lastName}, ${patient.firstName}` : '—'}
            </span>
            <span className="font-mono text-slate-500">{patient?.ehrId ?? '—'}</span>
            <span className="text-slate-300">·</span>
            <span className="font-mono text-slate-500">
              {visit ? format(new Date(visit.visitDate), 'dd MMM yyyy') : '—'}
            </span>
            {existingReport && (
              <span className="ml-auto inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-widest text-emerald-700">
                <CheckCircle className="h-3 w-3" /> Report saved
              </span>
            )}
          </div>

          {/* PDF viewer takes over when active */}
          {showPdf && (
            <div className="flex flex-1 flex-col bg-slate-100">
              <div className="flex items-center justify-between border-b border-slate-200 bg-white px-5 py-2">
                <span className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                  Saved report · PDF
                </span>
                <button
                  onClick={() => setShowPdf(false)}
                  className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2.5 py-1 text-xs text-slate-600 hover:border-slate-300 hover:bg-slate-50"
                >
                  <X className="h-3.5 w-3.5" /> Close
                </button>
              </div>
              <div className="flex-1">
                {pdfBlobUrl ? (
                  <iframe src={pdfBlobUrl} className="h-full w-full" title="Medical Report PDF" />
                ) : (
                  <div className="flex h-full items-center justify-center text-slate-400">
                    <Loader2 className="h-6 w-6 animate-spin" />
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Report authoring (hidden when PDF active) */}
          {!showPdf && (
            <>
              {/* Patient key info card */}
              {patient && (
                <div className="shrink-0 border-b border-slate-200 bg-white px-5 py-3">
                  <div className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-slate-400">
                    Patient
                  </div>
                  <div className="flex flex-wrap items-start gap-x-4 gap-y-2">
                    <div>
                      <p className="text-sm font-bold tracking-tight text-slate-900">
                        {patient.lastName}, {patient.firstName}
                      </p>
                      <p className="mt-0.5 font-mono text-[11px] text-slate-500">{patient.ehrId}</p>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      <span className="inline-flex items-center rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-700">
                        <span className="mr-1 text-slate-400">Age</span>
                        {patient.age}
                      </span>
                      <span
                        className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium ${
                          patient.gender === 'MALE'
                            ? 'border-blue-200 bg-blue-50 text-blue-700'
                            : patient.gender === 'FEMALE'
                            ? 'border-violet-200 bg-violet-50 text-violet-700'
                            : 'border-slate-200 bg-slate-50 text-slate-700'
                        }`}
                      >
                        {patient.gender}
                      </span>
                      {visit && (
                        <span className="inline-flex items-center rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 font-mono text-[11px] text-slate-600">
                          {format(new Date(visit.visitDate), 'dd MMM yyyy')}
                        </span>
                      )}
                      {analysis && (
                        <span
                          className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-semibold ${
                            analysis.segments.length > 0
                              ? 'border-rose-200 bg-rose-50 text-rose-700'
                              : 'border-emerald-200 bg-emerald-50 text-emerald-700'
                          }`}
                        >
                          {analysis.segments.length > 0
                            ? `${analysis.segments.length} fracture${analysis.segments.length !== 1 ? 's' : ''} detected`
                            : 'No fractures'}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Doctor notes */}
              <div className="border-b border-slate-200 bg-white px-5 py-4">
                <div className="mb-1.5 flex items-center justify-between">
                  <label className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                    Doctor Notes
                  </label>
                  {doctorNotes && (
                    <span className="text-[10px] font-mono text-slate-400">
                      {doctorNotes.length} chars
                    </span>
                  )}
                </div>
                <textarea
                  value={doctorNotes}
                  onChange={(e) => setDoctorNotes(e.target.value)}
                  placeholder="Clinical observations, symptoms, referring information…"
                  className="w-full resize-none border-0 bg-transparent p-0 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-0"
                  rows={3}
                />
              </div>

              {/* Report body — scrollable */}
              <div className="flex-1 overflow-y-auto bg-slate-50 px-5 py-4">
                {reportMut.isError && (
                  <div className="mb-3 flex items-center gap-2 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    {(reportMut.error as any)?.message ?? 'Report generation failed'}
                  </div>
                )}

                {reportMut.isPending && (
                  <div className="animate-fade-in-up rounded-lg border border-blue-200 bg-white p-5">
                    <div className="mb-2 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-widest text-blue-600">
                      <Sparkles className="h-3 w-3" />
                      Wilhelm AI
                    </div>
                    <p className="font-serif text-sm text-slate-700">
                      Generating radiology report
                      <span className="animate-caret ml-0.5 inline-block h-4 w-[2px] -mb-0.5 bg-blue-500" />
                    </p>
                    <div className="mt-4 space-y-2">
                      {[90, 70, 85, 55].map((w, i) => (
                        <div
                          key={i}
                          className="h-2 animate-pulse rounded bg-slate-200"
                          style={{ width: `${w}%`, animationDelay: `${i * 120}ms` }}
                        />
                      ))}
                    </div>
                  </div>
                )}

                {!reportMd && !reportMut.isPending && (
                  <div className="flex flex-col items-center justify-center py-16 text-center">
                    <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full border border-slate-200 bg-white">
                      <FileText className="h-5 w-5 text-slate-400" />
                    </div>
                    <p className="text-sm font-semibold text-slate-700">No report yet</p>
                    <p className="mt-1 max-w-xs text-xs text-slate-500">
                      Review the X-ray findings, then click Generate Report to have Wilhelm draft a
                      structured radiology report.
                    </p>
                    <button
                      onClick={() => reportMut.mutate()}
                      disabled={reportMut.isPending || !patient}
                      className="mt-6 inline-flex items-center gap-2 rounded-md bg-gradient-to-r from-blue-600 to-blue-500 px-5 py-2 text-sm font-semibold text-white shadow-lg shadow-blue-500/30 transition hover:from-blue-500 hover:to-blue-400 disabled:opacity-60"
                    >
                      <Sparkles className="h-4 w-4" /> Generate Report
                    </button>
                  </div>
                )}

                {reportMd && !reportMut.isPending && (
                  <div className="animate-fade-in-up">
                    {reportTab === 'preview' ? (
                      <article
                        className="font-serif text-[13.5px] leading-[1.65] text-slate-800
                          [&_h1]:mb-2 [&_h1]:mt-5 [&_h1]:font-sans [&_h1]:text-base [&_h1]:font-bold [&_h1]:tracking-tight [&_h1]:text-slate-900
                          [&_h2]:mb-1.5 [&_h2]:mt-5 [&_h2]:font-sans [&_h2]:text-sm [&_h2]:font-bold [&_h2]:uppercase [&_h2]:tracking-widest [&_h2]:text-blue-700
                          [&_h3]:mb-1 [&_h3]:mt-4 [&_h3]:font-sans [&_h3]:text-sm [&_h3]:font-semibold [&_h3]:text-slate-900
                          [&_p]:my-2
                          [&_strong]:font-semibold [&_strong]:text-slate-900
                          [&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-5
                          [&_ol]:my-2 [&_ol]:list-decimal [&_ol]:pl-5
                          [&_li]:my-1
                          [&_hr]:my-4 [&_hr]:border-t [&_hr]:border-slate-200
                          [&_em]:italic [&_em]:text-slate-600"
                      >
                        <ReactMarkdown>{reportMd}</ReactMarkdown>
                      </article>
                    ) : (
                      <div className="flex flex-col gap-2">
                        <textarea
                          value={reportMd}
                          onChange={(e) => setReportMd(e.target.value)}
                          className="w-full rounded-md border border-slate-200 bg-white p-3 font-mono text-xs text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
                          rows={24}
                        />
                        <button
                          onClick={() => setReportTab('preview')}
                          className="inline-flex items-center justify-center gap-1.5 rounded-md bg-blue-600 px-3 py-2 text-xs font-semibold text-white hover:bg-blue-500"
                        >
                          <CheckCircle className="h-3.5 w-3.5" /> Done editing
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Sticky export footer */}
              <div className="flex shrink-0 items-center justify-between gap-2 border-t border-slate-200 bg-white px-5 py-3">
                <div className="flex items-center gap-1.5 text-[10px] font-mono text-slate-400">
                  {reportMd && (
                    <>
                      <Sparkles className="h-3 w-3 text-blue-500" />
                      <span>Generated by Wilhelm AI · {category.replace(/_/g, ' ')}</span>
                    </>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {reportMd && (
                    <button
                      onClick={() => setReportTab((t) => (t === 'edit' ? 'preview' : 'edit'))}
                      className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:border-slate-300 hover:bg-slate-50"
                    >
                      <Edit3 className="h-3.5 w-3.5" />
                      {reportTab === 'edit' ? 'Preview' : 'Edit'}
                    </button>
                  )}
                  {existingReport && (
                    <>
                      <a
                        href={reportPdfUrl!}
                        download={reportPdfName}
                        className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:border-slate-300 hover:bg-slate-50"
                      >
                        <Download className="h-3.5 w-3.5" />
                        Download
                      </a>
                      <button
                        onClick={() => setShowPdf(true)}
                        className="inline-flex items-center gap-1.5 rounded-md border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100"
                      >
                        <FileText className="h-3.5 w-3.5" />
                        View PDF
                      </button>
                    </>
                  )}
                  {reportMd && (
                    <button
                      onClick={() => saveReportMut.mutate()}
                      disabled={saveReportMut.isPending}
                      className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm shadow-blue-500/30 hover:bg-blue-500 disabled:opacity-60"
                    >
                      {saveReportMut.isPending ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : saveReportMut.isSuccess ? (
                        <CheckCircle className="h-3.5 w-3.5" />
                      ) : (
                        <Save className="h-3.5 w-3.5" />
                      )}
                      {saveReportMut.isPending ? 'Saving…' : saveReportMut.isSuccess ? 'Saved' : 'Save as PDF'}
                    </button>
                  )}
                  {reportMd && !reportMut.isPending && (
                    <button
                      onClick={() => reportMut.mutate()}
                      disabled={reportMut.isPending}
                      className="inline-flex items-center gap-1.5 rounded-md bg-gradient-to-r from-blue-600 to-blue-500 px-3 py-1.5 text-xs font-semibold text-white shadow-sm shadow-blue-500/40 hover:from-blue-500 hover:to-blue-400"
                    >
                      <Sparkles className="h-3.5 w-3.5" />
                      Regenerate
                    </button>
                  )}
                </div>
              </div>
            </>
          )}
        </section>
      </div>
    </>
  );
}
