import { useRef } from 'react';
import { Upload } from 'lucide-react';
import Spinner from './Spinner';

interface Props {
  label: string;
  accept?: string;
  loading?: boolean;
  onFile: (file: File) => void;
}

export default function FileUploadButton({ label, accept = '.pdf', loading, onFile }: Props) {
  const ref = useRef<HTMLInputElement>(null);

  return (
    <>
      <input
        ref={ref}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) {
            onFile(file);
            e.target.value = '';
          }
        }}
      />
      <button
        type="button"
        disabled={loading}
        onClick={() => ref.current?.click()}
        className="inline-flex items-center gap-2 rounded-lg border border-dashed border-brand-500 px-3 py-2 text-sm font-medium text-brand-600 transition-colors hover:bg-brand-50 disabled:opacity-50"
      >
        {loading ? <Spinner size="sm" /> : <Upload className="h-4 w-4" />}
        {label}
      </button>
    </>
  );
}
