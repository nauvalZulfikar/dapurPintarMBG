export default function Pagination({ page, totalPages, onPageChange }) {
  if (totalPages <= 1) return null

  return (
    <div className="flex items-center gap-3 mt-3">
      <button
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 1}
        className="px-3 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800"
      >
        Prev
      </button>
      <span className="text-sm text-gray-500 dark:text-gray-400">
        {page} / {totalPages}
      </span>
      <button
        onClick={() => onPageChange(page + 1)}
        disabled={page >= totalPages}
        className="px-3 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800"
      >
        Next
      </button>
    </div>
  )
}
