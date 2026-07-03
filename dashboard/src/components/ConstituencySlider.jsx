import { useCallback, useEffect, useState } from 'react';
import { FiChevronLeft, FiChevronRight, FiBarChart2 } from 'react-icons/fi';
import { formatDateTime } from '../utils/format';

const ROTATE_INTERVAL = 3500;

export default function ConstituencySlider({ stats }) {
  const slides = [
    { label: 'Total Articles Collected', value: stats.total },
    { label: 'Positive Developments', value: stats.positive },
    { label: 'Negative Developments', value: stats.negative },
    { label: 'Total Problems', value: stats.problems },
    { label: 'High Priority Problems', value: stats.highPriorityProblems },
    { label: 'Most Affected Mandal', value: stats.topMandal },
    { label: 'Most Affected Village', value: stats.topVillage },
    { label: 'Most Common Category', value: stats.topCategory },
    { label: 'Latest News Time', value: formatDateTime(stats.latestTime) },
  ];

  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const count = slides.length;

  const goTo = useCallback((i) => setIndex((i + count) % count), [count]);
  const next = useCallback(() => setIndex((i) => (i + 1) % count), [count]);
  const prev = useCallback(() => setIndex((i) => (i - 1 + count) % count), [count]);

  useEffect(() => {
    if (paused) return undefined;
    const timer = setInterval(next, ROTATE_INTERVAL);
    return () => clearInterval(timer);
  }, [paused, next]);

  const current = slides[index];

  return (
    <section aria-label="Constituency overview" className="flex-1 flex flex-col">
      <div
        className="card flex-1 flex flex-col overflow-hidden"
        onMouseEnter={() => setPaused(true)}
        onMouseLeave={() => setPaused(false)}
      >
        <div className="flex items-center justify-between gap-3 border-b border-gray-100 px-5 py-4 shrink-0">
          <div className="flex items-center gap-2">
            <FiBarChart2 className="h-5 w-5 text-primary" />
            <h2 className="section-title">Constituency Overview</h2>
          </div>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={prev}
              aria-label="Previous"
              className="rounded p-1.5 text-gray-400 hover:bg-secondary hover:text-primary transition-colors"
            >
              <FiChevronLeft className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={next}
              aria-label="Next"
              className="rounded p-1.5 text-gray-400 hover:bg-secondary hover:text-primary transition-colors"
            >
              <FiChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="flex flex-1 flex-col items-center justify-center px-6 py-8 text-center">
          <p className="text-5xl font-bold text-primary leading-none">{current.value}</p>
          <p className="mt-3 text-sm font-medium text-gray-500">{current.label}</p>
        </div>

        <div className="flex items-center justify-center gap-1.5 border-t border-gray-100 px-5 py-4 shrink-0">
          {slides.map((slide, i) => (
            <button
              key={slide.label}
              type="button"
              onClick={() => goTo(i)}
              aria-label={`Go to ${slide.label}`}
              className={`h-1.5 rounded-full transition-all ${
                i === index ? 'w-5 bg-primary' : 'w-1.5 bg-gray-300 hover:bg-gray-400'
              }`}
            />
          ))}
        </div>
      </div>
    </section>
  );
}
