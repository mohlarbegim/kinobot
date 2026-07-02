import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export function useList<T = any>(resource: string, params: Record<string, any> = {}) {
  return useQuery({
    queryKey: [resource, params],
    queryFn: async () => {
      const { data } = await api.get<Paginated<T>>(`/${resource}/`, { params })
      return data
    },
  })
}

export function useCreate(resource: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: any) => (await api.post(`/${resource}/`, payload)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: [resource] }),
  })
}

export function useUpdate(resource: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...payload }: any) =>
      (await api.patch(`/${resource}/${id}/`, payload)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: [resource] }),
  })
}

export function useRemove(resource: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number | string) => {
      await api.delete(`/${resource}/${id}/`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: [resource] }),
  })
}

/** Custom action, masalan POST /users/5/ban/ */
export function useAction(resource: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, action, payload }: { id: number | string; action: string; payload?: any }) =>
      (await api.post(`/${resource}/${id}/${action}/`, payload ?? {})).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: [resource] }),
  })
}

export function useStats() {
  return useQuery({
    queryKey: ['stats'],
    queryFn: async () => (await api.get('/stats/')).data,
  })
}
