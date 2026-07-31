import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { toChartData, toSentimentChartData } from '../../utils/stats';

const RED_SHADES = ['#D72638', '#B91C2B', '#F04452', '#F87171', '#FCA5A5', '#FECACA', '#FEE2E2'];
const GRID = '#E5E7EB';
const GRID_DARK = '#334155';

function ChartCard({ title, children, className = '' }) {
  return (
    <div className={`card p-4 sm:p-5 ${className}`}>
      <h3 className="text-sm font-semibold text-app mb-4">{title}</h3>
      {children}
    </div>
  );
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-control border border-app bg-surface px-3 py-2 shadow-lift text-sm">
      <p className="font-medium text-app">{label || payload[0]?.name}</p>
      <p className="text-primary">{payload[0]?.value} articles</p>
    </div>
  );
}

function useIsDark() {
  if (typeof document === 'undefined') return false;
  return document.documentElement.classList.contains('dark');
}

export default function Charts({ stats }) {
  const sentimentData = toSentimentChartData(stats.sentimentCounts);
  const categoryData = toChartData(stats.categoryCounts, 12);
  const mandalData = toChartData(stats.mandalCounts, 10);
  const villageData = toChartData(stats.villageCounts, 10);
  const dark = useIsDark();
  const gridStroke = dark ? GRID_DARK : GRID;
  const tickFill = dark ? '#94A3B8' : '#6B7280';

  return (
    <section aria-label="Analytics charts">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title="Sentiment Distribution">
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={sentimentData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={90}
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
              >
                {sentimentData.map((_, i) => (
                  <Cell key={i} fill={RED_SHADES[i % RED_SHADES.length]} />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Category Distribution">
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={categoryData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={90}
                label={({ name, percent }) =>
                  percent > 0.05 ? `${name} ${(percent * 100).toFixed(0)}%` : ''
                }
              >
                {categoryData.map((_, i) => (
                  <Cell key={i} fill={RED_SHADES[i % RED_SHADES.length]} />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Daily Trend (Last 7 Days)" className="lg:col-span-2">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={stats.dailyTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
              <XAxis dataKey="label" tick={{ fontSize: 12, fill: tickFill }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: tickFill }} />
              <Tooltip content={<CustomTooltip />} />
              <Line
                type="monotone"
                dataKey="count"
                stroke="#D72638"
                strokeWidth={2}
                dot={{ fill: '#D72638', r: 4 }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Articles by Category">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={categoryData} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} horizontal={false} />
              <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: tickFill }} />
              <YAxis
                type="category"
                dataKey="name"
                width={100}
                tick={{ fontSize: 11, fill: tickFill }}
              />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="value" fill="#D72638" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Top 10 Mandals">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={mandalData} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} horizontal={false} />
              <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: tickFill }} />
              <YAxis
                type="category"
                dataKey="name"
                width={100}
                tick={{ fontSize: 11, fill: tickFill }}
              />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="value" fill="#B91C2B" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Top 10 Villages" className="lg:col-span-2">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={villageData} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} horizontal={false} />
              <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: tickFill }} />
              <YAxis
                type="category"
                dataKey="name"
                width={120}
                tick={{ fontSize: 11, fill: tickFill }}
              />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="value" fill="#F04452" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </section>
  );
}
