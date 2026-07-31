import { useParams } from 'react-router-dom';
import { useNewsContext } from '../context/NewsContext';
import DepartmentOverviewGrid from '../components/departments/DepartmentOverviewGrid';
import DepartmentDetailPanel from '../components/departments/DepartmentDetailPanel';

export default function DepartmentsPage() {
  const { slug } = useParams();
  const { departments, openArticle } = useNewsContext();

  if (slug) {
    const department = (departments || []).find((d) => d.slug === slug) || null;
    return <DepartmentDetailPanel department={department} onViewDetails={openArticle} />;
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-bold text-primary">Departments</h2>
        <p className="text-sm text-muted">Workload by responsible department</p>
      </div>
      <DepartmentOverviewGrid departments={departments} />
    </div>
  );
}
