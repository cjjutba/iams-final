import api from './api'

export const settingsService = {
  getAll: () =>
    api.get('/settings').then(r => r.data),
  update: (settings: Record<string, string>) =>
    api.patch('/settings', { settings }).then(r => r.data),
}
