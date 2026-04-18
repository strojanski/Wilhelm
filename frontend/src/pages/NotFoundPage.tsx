import { Link } from 'react-router-dom';

export default function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center py-32 text-center">
      <p className="text-6xl font-bold text-gray-200">404</p>
      <h1 className="mt-4 text-xl font-semibold text-gray-900">Page not found</h1>
      <Link to="/patients" className="mt-6 text-sm font-medium text-brand-600 hover:underline">
        Go to Patients
      </Link>
    </div>
  );
}
