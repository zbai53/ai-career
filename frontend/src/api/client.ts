import axios from 'axios'
import { showToast } from '../stores/toastStore'

const client = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  (response) => response,
  (error) => {
    const status: number | undefined = error.response?.status

    if (status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    } else if (status !== undefined && status >= 500) {
      showToast('Something went wrong, please try again')
    } else if (status === undefined) {
      // No response received — network / CORS / server down
      showToast('Cannot connect to server', 'warning')
    }

    return Promise.reject(error)
  }
)

export default client
