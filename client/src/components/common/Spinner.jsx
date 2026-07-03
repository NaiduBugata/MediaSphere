import { FiLoader } from 'react-icons/fi';

export default function Spinner({ size = 'md', label = 'Loading...' }) {
  const sizeClass = size === 'lg' ? 'h-10 w-10' : size === 'sm' ? 'h-5 w-5' : 'h-8 w-8';
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12">
      <FiLoader className={`${sizeClass} animate-spin text-primary`} aria-hidden="true" />
      <p className="text-sm text-gray-500">{label}</p>
    </div>
  );
}
