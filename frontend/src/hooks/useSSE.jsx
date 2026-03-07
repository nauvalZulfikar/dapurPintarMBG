import { useEffect, useRef } from 'react'

export function useSSE(onScanOk, onScanError) {
  const esRef = useRef(null)

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) return

    const es = new EventSource(`/api/stream?token=${token}`)
    esRef.current = es

    es.addEventListener('scan_ok', (e) => {
      try {
        onScanOk?.(JSON.parse(e.data))
      } catch {}
    })

    es.addEventListener('scan_error', (e) => {
      try {
        onScanError?.(JSON.parse(e.data))
      } catch {}
    })

    es.onerror = () => {
      // EventSource auto-reconnects
    }

    return () => {
      es.close()
      esRef.current = null
    }
  }, []) // Connect once on mount
}
