import { FileSpreadsheet, FileText, FileType } from 'lucide-react';
import { VISIT_KIND_LABEL } from '../../services/visitsApi';

const KIND_STYLE = {
  pdf: { Icon: FileText, className: 'bg-red-50 text-red-700 border-red-200' },
  word: { Icon: FileType, className: 'bg-blue-50 text-blue-700 border-blue-200' },
  excel: { Icon: FileSpreadsheet, className: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
};

export default function VisitKindBadge({ kind }) {
  const style = KIND_STYLE[kind] || KIND_STYLE.pdf;
  const { Icon } = style;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-semibold ${style.className}`}
    >
      <Icon className="h-3.5 w-3.5" aria-hidden />
      {VISIT_KIND_LABEL[kind] || 'File'}
    </span>
  );
}
