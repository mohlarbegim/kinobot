import axios from 'axios'

const ACCESS = 'kb_access'
const REFRESH = 'kb_refresh'

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS)
  },
  get refresh() {
    return localStorage.getItem(REFRESH)
  },
  set(access: string, refresh?: string) {
    localStorage.setItem(ACCESS, access)
    if (refresh) localStorage.setItem(REFRESH, refresh)
  },
  clear() {
    localStorage.removeItem(ACCESS)
    localStorage.removeItem(REFRESH)
  },
}

// Prod va dev'da API bir xil origin ostida (/api). Dev'da Vite proxy Django'ga yo'naltiradi.
export const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  const t = tokens.access
  if (t) config.headers.Authorization = `Bearer ${t}`
  return config
})

let refreshing: Promise<string | null> | null = null

async function refreshAccess(): Promise<string | null> {
  const r = tokens.refresh
  if (!r) return null
  try {
    const resp = await axios.post('/api/auth/refresh/', { refresh: r })
    const newAccess = resp.data.access as string
    const newRefresh = resp.data.refresh as string | undefined
    tokens.set(newAccess, newRefresh)
    return newAccess
  } catch {
    tokens.clear()
    return null
  }
}

api.interceptors.response.use(
  (resp) => resp,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && original && !original._retry) {
      original._retry = true
      if (!refreshing) refreshing = refreshAccess()
      const newAccess = await refreshing
      refreshing = null
      if (newAccess) {
        original.headers.Authorization = `Bearer ${newAccess}`
        return api(original)
      }
      // refresh muvaffaqiyatsiz -> loginga
      if (location.pathname !== '/dashboard/login') {
        location.href = '/dashboard/login'
      }
    }
    return Promise.reject(error)
  },
)
