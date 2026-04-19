import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/Layout';
import QueuePage from './pages/QueuePage';
import PatientListPage from './pages/PatientListPage';
import PatientDetailPage from './pages/PatientDetailPage';
import VisitDetailPage from './pages/VisitDetailPage';
import XrayDetailPage from './pages/XrayDetailPage';
import NotFoundPage from './pages/NotFoundPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Navigate to="/queue" replace />} />
            <Route path="queue" element={<QueuePage />} />
            <Route path="patients" element={<PatientListPage />} />
            <Route path="patients/:ehrId" element={<PatientDetailPage />} />
            <Route path="patients/:ehrId/visits/:visitId" element={<VisitDetailPage />} />
            <Route path="patients/:ehrId/visits/:visitId/xray/:filename" element={<XrayDetailPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
