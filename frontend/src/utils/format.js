export function formatDate(dateStr) {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  return d.toLocaleDateString('id-ID', {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}

export function formatDateTime(dateStr) {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  return d.toLocaleString('id-ID', {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export function formatWeight(grams, unit) {
  if (unit === 'kg') return `${(grams / 1000).toFixed(1)} kg`
  if (unit === 'pcs') return `${grams} pcs`
  return `${grams} g`
}

export function todayISO() {
  return new Date().toISOString().split('T')[0]
}
