import api from './axios';

export const login = (login, password) =>
  api.post('/auth/login', { login, password }).then((r) => r.data);

export const getMe = () => api.get('/auth/me').then((r) => r.data);

export const logout = () => api.post('/auth/logout').then((r) => r.data);
