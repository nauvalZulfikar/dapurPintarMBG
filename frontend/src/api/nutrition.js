import api from './client'

export const getNutritionDaily = (date) =>
  api.get('/nutrition/daily', { params: { date } })

export const getWeeklyCompliance = (weekStart) =>
  api.get('/nutrition/weekly-compliance', { params: { week_start: weekStart } })
