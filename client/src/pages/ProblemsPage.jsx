import { useMemo, useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useNewsContext } from '../context/NewsContext';
import PrioritySummary from '../components/problems/PrioritySummary';
import ProblemFilters from '../components/problems/ProblemFilters';
import ActionRequired from '../components/problems/ActionRequired';
import { uniqueSorted } from '../utils/format';
import { sortByPriority } from '../utils/derive';

export default function ProblemsPage() {
  const { articles, stats, openArticle } = useNewsContext();
  const [searchParams, setSearchParams] = useSearchParams();

  const [priority, setPriority] = useState(searchParams.get('priority') || '');
  const [department, setDepartment] = useState(searchParams.get('department') || '');
  const [category, setCategory] = useState(searchParams.get('category') || '');

  useEffect(() => {
    const next = {};
    if (priority) next.priority = priority;
    if (department) next.department = department;
    if (category) next.category = category;
    setSearchParams(next, { replace: true });
  }, [priority, department, category, setSearchParams]);

  const allProblems = useMemo(
    () => sortByPriority((articles || []).filter((a) => a.isActionRequired)),
    [articles]
  );

  const departments = useMemo(
    () => uniqueSorted(allProblems.map((a) => a.department).filter(Boolean)),
    [allProblems]
  );
  const categories = useMemo(
    () => uniqueSorted(allProblems.map((a) => a.category).filter(Boolean)),
    [allProblems]
  );

  const filtered = useMemo(() => {
    return allProblems.filter((a) => {
      if (priority && a.priority !== priority) return false;
      if (department && a.department !== department) return false;
      if (category && a.category !== category) return false;
      return true;
    });
  }, [allProblems, priority, department, category]);

  const reset = () => {
    setPriority('');
    setDepartment('');
    setCategory('');
  };

  return (
    <div className="page-enter space-y-4">
      <div>
        <h2 className="section-title text-xl">Problems</h2>
        <p className="text-sm text-muted">Action queue for issues requiring attention</p>
      </div>

      <PrioritySummary
        counts={stats.problemPriorityCounts}
        total={stats.problems}
        priorityFilter={priority}
        onPriorityChange={setPriority}
      />

      <ProblemFilters
        priority={priority}
        department={department}
        category={category}
        onPriorityChange={setPriority}
        onDepartmentChange={setDepartment}
        onCategoryChange={setCategory}
        departments={departments}
        categories={categories}
        onReset={reset}
      />

      <ActionRequired articles={filtered} onViewDetails={openArticle} />
    </div>
  );
}
