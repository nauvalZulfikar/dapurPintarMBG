import axios from 'axios'

export const getCountdown = (trayId) => axios.get(`/api/countdown/${trayId}`)
