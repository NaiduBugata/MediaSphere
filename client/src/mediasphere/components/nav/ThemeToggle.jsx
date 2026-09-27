import { Monitor, Moon, Sun } from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';

const LABELS = { light: 'Light', dark: 'Dark', system: 'System' };

export default function ThemeToggle() {
  const { theme, cycleTheme, resolved } = useTheme();

  const Icon = theme === 'system' ? Monitor : resolved === 'dark' ? Moon : Sun;

  return (
    <button
      type="button"
      onClick={cycleTheme}
      title={`Theme: ${LABELS[theme]} (click to change)`}
      aria-label={`Theme ${LABELS[theme]}. Click to cycle.`}
      className="inline-flex h-9 w-9 items-center justify-center rounded-control border border-msline bg-surface text-app hover:bg-msbg transition-colors duration-200"
    >
      <Icon className="h-4 w-4" strokeWidth={2} />
    </button>
  );
}
