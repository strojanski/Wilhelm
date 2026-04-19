import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Activity, ChevronRight, ScanLine, Users } from 'lucide-react';
import { format } from 'date-fns';
import { getPatient } from '../api/patients';
import { getVisit } from '../api/visits';

type RouteInfo = {
  ehrId?: string;
  visitId?: string;
  filename?: string;
};

function parseRoute(pathname: string): RouteInfo {
  const match = pathname.match(
    /^\/patients(?:\/([^/]+)(?:\/visits\/([^/]+)(?:\/xray\/([^/]+))?)?)?/,
  );
  if (!match) return {};
  return {
    ehrId: match[1] ? decodeURIComponent(match[1]) : undefined,
    visitId: match[2],
    filename: match[3] ? decodeURIComponent(match[3]) : undefined,
  };
}

export default function Layout() {
  const { pathname } = useLocation();
  const { ehrId, visitId, filename } = parseRoute(pathname);

  const { data: patient } = useQuery({
    queryKey: ['patient', ehrId],
    queryFn: () => getPatient(ehrId!),
    enabled: !!ehrId,
  });

  const { data: visit } = useQuery({
    queryKey: ['visit', ehrId, visitId],
    queryFn: () => getVisit(ehrId!, Number(visitId)),
    enabled: !!ehrId && !!visitId,
  });

  const onPatients = pathname.startsWith('/patients');
  const crumbs: { label: string; to?: string; mono?: boolean }[] = [];
  if (onPatients) crumbs.push({ label: 'Patients', to: '/patients' });
  if (ehrId) {
    const name = patient ? `${patient.lastName}, ${patient.firstName}` : ehrId;
    crumbs.push({ label: name, to: `/patients/${ehrId}` });
  }
  if (ehrId && visitId) {
    const label = visit ? format(new Date(visit.visitDate), 'yyyy-MM-dd') : `#${visitId}`;
    crumbs.push({
      label,
      to: `/patients/${ehrId}/visits/${visitId}`,
      mono: true,
    });
  }
  if (filename) {
    crumbs.push({ label: filename, mono: true });
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <header className="sticky top-0 z-40 flex h-12 items-center justify-between border-b border-slate-800 bg-slate-900 px-4 text-white">
        <div className="flex items-center gap-5">
          <Link
            to="/"
            className="flex items-center gap-2 transition-colors hover:text-blue-400"
          >
            <span className="flex h-6 w-6 items-center justify-center rounded-md bg-blue-500/15 text-blue-400 ring-1 ring-blue-500/30">
              <ScanLine className="h-3.5 w-3.5" />
            </span>
            <span className="text-sm font-semibold tracking-tight">Wilhelm</span>
          </Link>

          <nav className="hidden items-center gap-1 text-xs sm:flex">
            <NavLink
              to="/queue"
              className={({ isActive }) =>
                [
                  'flex items-center gap-1.5 rounded-md px-2.5 py-1 font-medium transition',
                  isActive
                    ? 'bg-slate-800 text-white'
                    : 'text-slate-400 hover:bg-slate-800/60 hover:text-white',
                ].join(' ')
              }
            >
              <Activity className="h-3.5 w-3.5" />
              Queue
            </NavLink>
            <NavLink
              to="/patients"
              className={({ isActive }) =>
                [
                  'flex items-center gap-1.5 rounded-md px-2.5 py-1 font-medium transition',
                  isActive
                    ? 'bg-slate-800 text-white'
                    : 'text-slate-400 hover:bg-slate-800/60 hover:text-white',
                ].join(' ')
              }
            >
              <Users className="h-3.5 w-3.5" />
              Patients
            </NavLink>
          </nav>
        </div>

        {crumbs.length > 0 && (
          <nav className="flex items-center gap-1 overflow-hidden text-xs">
            {crumbs.map((c, i) => {
              const isLast = i === crumbs.length - 1;
              const text = (
                <span
                  className={[
                    'truncate transition-colors',
                    c.mono ? 'font-mono' : '',
                    isLast ? 'text-white' : 'text-slate-400 hover:text-white',
                  ].join(' ')}
                  title={c.label}
                >
                  {c.label}
                </span>
              );
              return (
                <div key={i} className="flex items-center gap-1">
                  {i > 0 && <ChevronRight className="h-3 w-3 shrink-0 text-slate-600" />}
                  {c.to && !isLast ? <Link to={c.to}>{text}</Link> : text}
                </div>
              );
            })}
          </nav>
        )}
      </header>

      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
