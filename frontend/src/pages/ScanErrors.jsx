import { useState, useEffect, useCallback } from 'react'
import DataTable from '../components/DataTable'
import Pagination from '../components/Pagination'
import { getScanErrors } from '../api/errors'

const COLUMNS = [
  { key: 'id', label: 'ID' },
  { key: 'code', label: 'Code' },
  { key: 'step', label: 'Step' },
  { key: 'reason', label: 'Reason' },
  { key: 'created_at', label: 'Time' },
]

export default function ScanErrors() {
  const [errors, setErrors] = useState([])
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [loading, setLoading] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    getScanErrors({ page })
      .then((res) => {
        setErrors(res.data.errors)
        setTotalPages(res.data.total_pages)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [page])

  useEffect(() => { load() }, [load])

  return (
    <div>
      <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100 mb-4">Scan Errors</h2>
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
        <DataTable columns={COLUMNS} data={errors} loading={loading} />
        <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
      </div>
    </div>
  )
}
