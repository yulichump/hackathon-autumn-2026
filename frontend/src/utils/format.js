export const CURRENCIES = ['RUB', 'USD', 'EUR'];

export const PERIODS = [
  { value: 'monthly', label: 'Ежемесячно' },
  { value: 'weekly', label: 'Еженедельно' },
  { value: 'quarterly', label: 'Ежеквартально' },
  { value: 'yearly', label: 'Ежегодно' },
  { value: 'daily', label: 'Ежедневно' },
];

export const periodLabel = (value) => PERIODS.find((p) => p.value === value)?.label || value;

export const todayIso = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

export const formatDate = (iso) => (iso ? iso.split('-').reverse().join('.') : '—');

export const formatNumber = (amount) =>
  new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(amount);

export const formatMoney = (amount, currency) =>
  new Intl.NumberFormat('ru-RU', { style: 'currency', currency, minimumFractionDigits: 2 }).format(amount);
