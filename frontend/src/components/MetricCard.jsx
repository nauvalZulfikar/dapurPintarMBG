export default function MetricCard({ label, value, loading }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 border-l-4 border-l-accent p-4">
      <div className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">{label}</div>
      <div className="text-3xl font-bold text-brand dark:text-accent mt-1">
        {loading ? '...' : value}
      </div>
    </div>
  )
}
