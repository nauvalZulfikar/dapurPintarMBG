import { useEffect, useRef } from 'react'

export function useSSE(onScanOk, onScanError) {
  const esRef = useRef(null)

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) return

    const kid = localStorage.getItem('active_kitchen_id')
    const url = kid
      ? `/api/stream?token=${token}&kitchen_id=${kid}`
      : `/api/stream?token=${token}`

    const es = new EventSource(url)
    esRef.current = es

    es.addEventListener('scan_ok', (e) => {
      try { onScanOk?.(JSON.parse(e.data)) } catch {}
    })
    es.addEventListener('scan_error', (e) => {
      try { onScanError?.(JSON.parse(e.data)) } catch {}
    })
    es.onerror = () => {}

    return () => {
      es.close()
      esRef.current = null
    }
  }, [])
}
