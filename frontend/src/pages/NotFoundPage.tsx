import { Link } from 'react-router-dom';
import { ScanLine, ArrowRight } from 'lucide-react';

export default function NotFoundPage() {
  return (
    <div className="flex min-h-[calc(100vh-3rem)] flex-col items-center justify-center px-6 text-center">
      <div className="relative">
        <p className="text-[120px] font-bold leading-none tracking-tight text-slate-200">404</p>
        <ScanLine className="absolute left-1/2 top-1/2 h-10 w-10 -translate-x-1/2 -translate-y-1/2 text-blue-500" />
      </div>
      <h1 className="mt-2 text-lg font-bold tracking-tight text-slate-900">Page not found</h1>
      <p className="mt-1 max-w-sm text-sm text-slate-500">
        This scan slipped off the viewer. Let's get you back to the patient list.
      </p>
      <Link
        to="/patients"
        className="mt-6 inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm shadow-blue-500/30 transition hover:bg-blue-500"
      >
        Go to Patients
        <ArrowRight className="h-3.5 w-3.5" />
      </Link>
    </div>
  );
}
