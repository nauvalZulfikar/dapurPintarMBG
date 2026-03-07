export default function DataTable({ columns, data, loading }) {
  if (loading) {
    return <div className="text-gray-400 dark:text-gray-500 text-sm py-4">Loading...</div>
  }

  if (!data || data.length === 0) {
    return <div className="text-gray-400 dark:text-gray-500 text-sm py-4">No data.</div>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 dark:border-gray-700">
            {columns.map((col) => (
              <th
                key={col.key}
                className="text-left py-2 px-3 text-gray-500 dark:text-gray-400 font-medium"
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i} className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50">
              {columns.map((col) => (
                <td key={col.key} className="py-2 px-3 text-gray-700 dark:text-gray-300">
                  {col.render ? col.render(row[col.key], row) : (row[col.key] ?? '-')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
