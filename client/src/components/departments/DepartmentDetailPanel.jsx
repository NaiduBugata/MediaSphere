import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import ActionRequired from '../problems/ActionRequired';
import EmptyState from '../common/EmptyState';

export default function DepartmentDetailPanel({ department, onViewDetails }) {
  if (!department) {
    return (
      <div className="card">
        <EmptyState title="Department not found" message="Choose a department from the overview." />
        <div className="px-5 pb-5">
          <Link to="/departments" className="text-sm font-semibold text-primary hover:underline">
            ← Back to departments
          </Link>
        </div>
      </div>
    );
  }

  return (
    <section aria-label={`${department.name} detail`} className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link
            to="/departments"
            className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline mb-1"
          >
            <ArrowLeft className="h-3 w-3" /> All departments
          </Link>
          <h2 className="section-title text-lg">{department.name}</h2>
          <p className="text-sm text-muted mt-1">
            {department.problems} open problems · {department.high} high priority · {department.total}{' '}
            articles
          </p>
        </div>
        <Link
          to={`/problems?department=${encodeURIComponent(department.name)}`}
          className="text-sm font-semibold text-primary hover:underline"
        >
          Open in Problems →
        </Link>
      </div>

      <ActionRequired articles={department.problemsList || []} onViewDetails={onViewDetails} />
    </section>
  );
}
