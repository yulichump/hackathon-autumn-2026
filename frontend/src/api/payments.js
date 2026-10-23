import api from './axios';

const clean = (params = {}) =>
  Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined));

export const getRecurringPayments = (params) =>
  api.get('/recurring-payments', { params: clean(params) }).then((r) => r.data);

export const createRecurringPayment = (data) =>
  api.post('/recurring-payments', data).then((r) => r.data);

export const deleteRecurringPayment = (id) => api.delete(`/recurring-payments/${id}`);

export const getOccurrences = (params) =>
  api.get('/payment-occurrences', { params: clean(params) }).then((r) => r.data);

export const getOccurrence = (id) => api.get(`/payment-occurrences/${id}`).then((r) => r.data);

export const updateOccurrence = (id, data) =>
  api.patch(`/payment-occurrences/${id}`, data).then((r) => r.data);

export const markPaid = (id, actualPaymentDate) =>
  updateOccurrence(id, { status: 'paid', actual_payment_date: actualPaymentDate });

export const markUnpaid = (id) => updateOccurrence(id, { status: 'unpaid', actual_payment_date: null });

export const getSummary = (params) =>
  api.get('/payments/summary', { params: clean(params) }).then((r) => r.data);

export const getBudget = (params) =>
  api.get('/payments/budget', { params: clean(params) }).then((r) => r.data);
