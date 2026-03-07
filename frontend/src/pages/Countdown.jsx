import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { getCountdown } from '../api/countdown'

function pad(n) {
  return String(Math.max(0, n)).padStart(2, '0')
}

function formatTime(isoString) {
  if (!isoString) return ''
  const d = new Date(isoString)
  return d.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', hour12: false })
}

function getRemainingSeconds(safeUntilIso) {
  if (!safeUntilIso) return null
  return Math.floor((new Date(safeUntilIso) - Date.now()) / 1000)
}

export default function Countdown() {
  const { trayId } = useParams()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [secondsLeft, setSecondsLeft] = useState(null)

  const load = useCallback(() => {
    getCountdown(trayId)
      .then((res) => {
        setData(res.data)
        setSecondsLeft(getRemainingSeconds(res.data.safe_until))
      })
      .catch((err) => {
        setError(err.response?.status === 404 ? 'Tray tidak ditemukan.' : 'Gagal memuat data.')
      })
  }, [trayId])

  useEffect(() => { load() }, [load])

  // Tick down every second
  useEffect(() => {
    if (secondsLeft === null) return
    if (secondsLeft <= 0) return
    const t = setTimeout(() => setSecondsLeft((s) => s - 1), 1000)
    return () => clearTimeout(t)
  }, [secondsLeft])

  const expired = secondsLeft !== null && secondsLeft <= 0
  const waiting = data && !data.delivered_at

  const hours = secondsLeft !== null ? Math.floor(secondsLeft / 3600) : 0
  const mins = secondsLeft !== null ? Math.floor((secondsLeft % 3600) / 60) : 0
  const secs = secondsLeft !== null ? secondsLeft % 60 : 0

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <div className="bg-brand px-5 py-4">
        <div className="text-xs font-semibold text-gold uppercase tracking-widest">Dapur Pintar</div>
        <div className="text-xl font-bold text-white">MBG</div>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center px-5 py-8 gap-6">

        {error && (
          <div className="w-full max-w-sm bg-red-50 border border-red-200 rounded-lg p-4 text-center text-red-700 text-sm">
            {error}
          </div>
        )}

        {data && (
          <>
            {/* Tray ID */}
            <div className="text-center">
              <div className="text-xs text-gray-400 uppercase tracking-widest mb-1">ID Nampan</div>
              <div className="font-mono text-base font-semibold text-brand">{data.tray_id}</div>
            </div>

            {/* School allocations */}
            {data.allocations.length > 0 && (
              <div className="w-full max-w-sm bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
                {data.allocations.map((alloc, i) => (
                  <div key={i} className="flex items-center justify-between px-4 py-3">
                    <span className="text-sm font-medium text-gray-800">{alloc.school}</span>
                    <span className="text-sm font-bold text-brand">{alloc.n_trays} porsi</span>
                  </div>
                ))}
              </div>
            )}

            {/* Delivery time */}
            {data.delivered_at && (
              <div className="text-center text-xs text-gray-400">
                Dikirim pukul <span className="font-semibold text-gray-600">{formatTime(data.delivered_at)}</span>
              </div>
            )}

            {/* Waiting state */}
            {waiting && (
              <div className="text-center text-gray-400 text-sm">Menunggu pengiriman...</div>
            )}

            {/* Countdown */}
            {!waiting && data.safe_until && (
              <div className="w-full max-w-sm">
                <div className="text-center text-xs text-gray-500 uppercase tracking-widest mb-3">
                  Aman dikonsumsi sebelum pukul{' '}
                  <span className="font-semibold text-gray-700">{formatTime(data.safe_until)}</span>
                </div>

                {expired ? (
                  <div className="bg-red-600 rounded-2xl px-6 py-6 text-center">
                    <div className="text-white font-bold text-lg leading-tight">
                      SUDAH MELEWATI<br />BATAS KONSUMSI
                    </div>
                    <div className="text-red-200 text-xs mt-2">Jangan dikonsumsi</div>
                  </div>
                ) : (
                  <div className="bg-brand rounded-2xl px-6 py-6 text-center">
                    <div className="text-accent text-xs uppercase tracking-widest mb-2">Sisa waktu</div>
                    <div className="text-white font-mono text-5xl font-bold tracking-tight">
                      {pad(hours)}:{pad(mins)}:{pad(secs)}
                    </div>
                    <div className="text-blue-200 text-xs mt-2">jam : menit : detik</div>
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {!data && !error && (
          <div className="text-gray-400 text-sm">Memuat...</div>
        )}
      </div>
    </div>
  )
}
