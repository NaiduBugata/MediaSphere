import { Link } from 'react-router-dom';
import { Briefcase } from 'lucide-react';
import EmptyState from '../common/EmptyState';

export default function DepartmentOverviewGrid({ departments }) {
  if (!departments?.length) {
    return (
      <div className="card">
        <EmptyState
          title="No departments yet"
          message="Department workload appears once articles are categorized."
        />
      </div>
    );
  }

  return (
    <section aria-label="Departments overview">
      <div className="flex items-center gap-2 mb-4">
        <Briefcase className="h-5 w-5 text-primary" />
        <h2 className="section-title">Department Workload</h2>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {departments.map((dept) => (
          <Link
            key={dept.slug}
            to={`/departments/${dept.slug}`}
            className="card p-5 hover:border-primary/40 transition-colors block"
          >
            <h3 className="text-sm font-semibold text-app leading-snug">{dept.name}</h3>
            <div className="mt-3 grid grid-cols-3 gap-2 text-center">
              <div>
                <p className="text-lg font-bold text-primary">{dept.problems}</p>
                <p className="text-[10px] uppercase tracking-wide text-muted">Problems</p>
              </div>
              <div>
                <p className="text-lg font-bold text-primary">{dept.high}</p>
                <p className="text-[10px] uppercase tracking-wide text-muted">High</p>
              </div>
              <div>
                <p className="text-lg font-bold text-app">{dept.total}</p>
                <p className="text-[10px] uppercase tracking-wide text-muted">Articles</p>
              </div>
            </div>
            {dept.latest && (
              <p className="mt-3 text-xs text-muted line-clamp-2">
                Latest: {dept.latest.title}
              </p>
            )}
          </Link>
        ))}
      </div>
    </section>
  );
}
