import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { getCountdown } from '../api/countdown'
import { confirmReceipt, listConfirmationsPublic } from '../api/distributions'

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
  const [confirmations, setConfirmations] = useState([])
  const [confirmingFor, setConfirmingFor] = useState(null)
  const [confirmCount, setConfirmCount] = useState('')
  const [confirmNotes, setConfirmNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [confirmMsg, setConfirmMsg] = useState('')

  const load = useCallback(() => {
    getCountdown(trayId)
      .then((res) => {
        setData(res.data)
        setSecondsLeft(getRemainingSeconds(res.data.safe_until))
      })
      .catch((err) => {
        setError(err.response?.status === 404 ? 'Tray tidak ditemukan.' : 'Gagal memuat data.')
      })
    listConfirmationsPublic(trayId)
      .then(r => setConfirmations(r.data.confirmations || []))
      .catch(() => {})
  }, [trayId])

  useEffect(() => { load() }, [load])

  const startConfirm = (alloc) => {
    setConfirmingFor(alloc)
    setConfirmCount(String(alloc.n_trays))
    setConfirmNotes('')
    setConfirmMsg('')
  }

  const submitConfirm = async () => {
    if (!confirmingFor) return
    const cnt = parseInt(confirmCount, 10)
    if (!cnt || cnt < 0) { setConfirmMsg('Jumlah ompreng invalid.'); return }
    setSubmitting(true); setConfirmMsg('')
    try {
      await confirmReceipt(trayId, {
        school_name: confirmingFor.school,
        confirmed_count: cnt,
        notes: confirmNotes || null,
      })
      setConfirmMsg(`✅ Konfirmasi tercatat: ${cnt} ompreng untuk ${confirmingFor.school}`)
      setConfirmingFor(null); setConfirmCount(''); setConfirmNotes('')
      // refresh list
      const r = await listConfirmationsPublic(trayId)
      setConfirmations(r.data.confirmations || [])
    } catch (e) {
      setConfirmMsg('Gagal: ' + (e.response?.data?.detail || e.message))
    } finally {
      setSubmitting(false)
    }
  }

  const confirmedCountFor = (schoolName) =>
    confirmations.filter(c => c.school_name === schoolName).reduce((s, c) => s + (c.confirmed_count || 0), 0)

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

            {/* School allocations + confirm buttons */}
            {data.allocations.length > 0 && (
              <div className="w-full max-w-sm bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
                {data.allocations.map((alloc, i) => {
                  const confirmed = confirmedCountFor(alloc.school)
                  return (
                    <div key={i} className="px-4 py-3">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-gray-800">{alloc.school}</span>
                        <span className="text-sm font-bold text-brand">{alloc.n_trays} porsi</span>
                      </div>
                      {confirmed > 0 ? (
                        <div className="mt-1 text-xs text-green-700">✅ {confirmed} ompreng sudah dikonfirmasi</div>
                      ) : (
                        <button
                          onClick={() => startConfirm(alloc)}
                          className="mt-2 w-full px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded">
                          ☑ Konfirmasi Terima
                        </button>
                      )}
                    </div>
                  )
                })}
              </div>
            )}

            {/* Confirm receipt modal */}
            {confirmingFor && (
              <div className="w-full max-w-sm bg-white rounded-xl border-2 border-blue-400 p-4">
                <div className="text-sm font-semibold text-gray-800 mb-2">
                  Konfirmasi: {confirmingFor.school}
                </div>
                <label className="block mb-2">
                  <span className="text-xs text-gray-600 block mb-1">Jumlah ompreng diterima</span>
                  <input
                    type="number" min="0" max={confirmingFor.n_trays}
                    value={confirmCount}
                    onChange={(e) => setConfirmCount(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded"
                    inputMode="numeric"
                  />
                  <span className="text-xs text-gray-400">Target: {confirmingFor.n_trays}</span>
                </label>
                <label className="block mb-3">
                  <span className="text-xs text-gray-600 block mb-1">Catatan (opsional)</span>
                  <input
                    value={confirmNotes}
                    onChange={(e) => setConfirmNotes(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded"
                    placeholder="Bu Sari, dst."
                  />
                </label>
                <div className="flex gap-2">
                  <button
                    onClick={submitConfirm}
                    disabled={submitting}
                    className="flex-1 px-3 py-2 bg-green-600 hover:bg-green-700 text-white text-sm rounded disabled:opacity-50">
                    {submitting ? '...' : 'Submit'}
                  </button>
                  <button
                    onClick={() => setConfirmingFor(null)}
                    className="px-3 py-2 bg-gray-200 hover:bg-gray-300 text-sm rounded">
                    Batal
                  </button>
                </div>
              </div>
            )}

            {confirmMsg && (
              <div className="w-full max-w-sm text-xs text-center text-green-700 bg-green-50 border border-green-200 rounded p-2">
                {confirmMsg}
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
