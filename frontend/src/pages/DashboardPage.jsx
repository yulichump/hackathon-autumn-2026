import { useCallback, useEffect, useState } from 'react';
import {
  Alert, Button, Card, CardContent, Chip, Dialog, DialogActions, DialogContent, DialogTitle, FormControl,
  InputLabel, MenuItem, Paper, Select, Snackbar, Stack, Table, TableBody, TableCell, TableContainer, TableHead,
  TableRow, TextField, Typography,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import { getErrorMessage } from '../api/axios';
import { getOccurrences, getSummary, markPaid, markUnpaid, updateOccurrence } from '../api/payments';
import { CURRENCIES, formatDate, formatMoney, formatNumber, todayIso } from '../utils/format';

function SummaryCards({ summary }) {
  return (
    <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ mb: 3 }}>
      {CURRENCIES.map((currency) => {
        const totals = summary?.[currency];
        return (
          <Card key={currency} variant="outlined" sx={{ flex: 1 }}>
            <CardContent>
              <Typography variant="h6">{currency}</Typography>
              <Typography variant="body2">План: {totals ? formatMoney(totals.total_planned, currency) : '—'}</Typography>
              <Typography variant="body2" color="success.main">
                Оплачено: {totals ? formatMoney(totals.total_paid, currency) : '—'}
              </Typography>
              <Typography variant="body2" color="error.main">
                Просрочено: {totals ? formatMoney(totals.total_overdue, currency) : '—'}
              </Typography>
            </CardContent>
          </Card>
        );
      })}
    </Stack>
  );
}

function PayDialog({ occurrence, onClose, onSubmit }) {
  const [date, setDate] = useState(occurrence?.actual_payment_date || todayIso());
  const isEdit = occurrence?.status === 'paid';

  return (
    <Dialog open onClose={onClose}>
      <DialogTitle>{isEdit ? 'Исправить дату оплаты' : 'Отметить оплату'}</DialogTitle>
      <DialogContent>
        <Typography variant="body2" sx={{ mb: 2 }}>
          {occurrence.name} — {formatMoney(occurrence.amount, occurrence.currency)}, срок {formatDate(occurrence.due_date)}
        </Typography>
        <TextField
          type="date"
          label="Фактическая дата оплаты"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          fullWidth
          slotProps={{ inputLabel: { shrink: true }, htmlInput: { max: todayIso() } }}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Отмена</Button>
        <Button variant="contained" disabled={!date} onClick={() => onSubmit(date)}>Сохранить</Button>
      </DialogActions>
    </Dialog>
  );
}

export default function DashboardPage() {
  const [filters, setFilters] = useState({ status: '', currency: '', is_overdue: '' });
  const [occurrences, setOccurrences] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [dialogFor, setDialogFor] = useState(null);

  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getOccurrences(filters), getSummary()])
      .then(([items, totals]) => {
        if (cancelled) return;
        setOccurrences(items);
        setSummary(totals);
      })
      .catch((err) => {
        if (!cancelled) setError(getErrorMessage(err, 'Не удалось загрузить платежи'));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filters, reloadKey]);

  const runAction = useCallback(async (action) => {
    try {
      await action();
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }, []);

  const handlePaySubmit = (date) => {
    const occ = dialogFor;
    setDialogFor(null);
    runAction(() =>
      occ.status === 'paid' ? updateOccurrence(occ.id, { actual_payment_date: date }) : markPaid(occ.id, date),
    );
  };

  const setFilter = (name) => (e) => setFilters((prev) => ({ ...prev, [name]: e.target.value }));

  return (
    <>
      <Typography variant="h4" sx={{ mb: 3, fontSize: { xs: '1.75rem', sm: '2.125rem' } }}>Платежи</Typography>

      <SummaryCards summary={summary} />

      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ mb: 2 }}>
        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel>Статус</InputLabel>
          <Select label="Статус" value={filters.status} onChange={setFilter('status')}>
            <MenuItem value="">Все</MenuItem>
            <MenuItem value="unpaid">Не оплачено</MenuItem>
            <MenuItem value="paid">Оплачено</MenuItem>
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel>Валюта</InputLabel>
          <Select label="Валюта" value={filters.currency} onChange={setFilter('currency')}>
            <MenuItem value="">Все</MenuItem>
            {CURRENCIES.map((c) => <MenuItem key={c} value={c}>{c}</MenuItem>)}
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel>Просрочка</InputLabel>
          <Select label="Просрочка" value={filters.is_overdue} onChange={setFilter('is_overdue')}>
            <MenuItem value="">Все</MenuItem>
            <MenuItem value="true">Просроченные</MenuItem>
            <MenuItem value="false">Без просрочки</MenuItem>
          </Select>
        </FormControl>
      </Stack>

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Название</TableCell>
              <TableCell align="right">Сумма</TableCell>
              <TableCell>Валюта</TableCell>
              <TableCell>Срок</TableCell>
              <TableCell>Статус</TableCell>
              <TableCell>Дата оплаты</TableCell>
              <TableCell>Отметил</TableCell>
              <TableCell>Просрочка</TableCell>
              <TableCell align="right">Действия</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {!loading && occurrences.length === 0 && (
              <TableRow>
                <TableCell colSpan={9} align="center">Платежей нет</TableCell>
              </TableRow>
            )}
            {occurrences.map((p) => (
              <TableRow
                key={p.id}
                sx={p.is_overdue && p.status === 'unpaid' ? { bgcolor: (t) => alpha(t.palette.error.main, 0.08) } : undefined}
              >
                <TableCell>
                  {p.name}
                  {p.recurring_payment_is_deleted && (
                    <Chip size="small" label="платёж прекращён" sx={{ ml: 1 }} />
                  )}
                </TableCell>
                <TableCell align="right">{formatNumber(p.amount)}</TableCell>
                <TableCell>{p.currency}</TableCell>
                <TableCell>{formatDate(p.due_date)}</TableCell>
                <TableCell>
                  <Chip
                    size="small"
                    label={p.status === 'paid' ? 'Оплачено' : 'Не оплачено'}
                    color={p.status === 'paid' ? 'success' : 'default'}
                  />
                </TableCell>
                <TableCell>{formatDate(p.actual_payment_date)}</TableCell>
                <TableCell>
                  {p.paid_by ? (
                    <Typography variant="body2" color={p.paid_by.startsWith('@') ? 'info.main' : 'text.primary'}>
                      {p.paid_by.startsWith('@') ? `${p.paid_by} (Telegram)` : p.paid_by}
                    </Typography>
                  ) : '—'}
                </TableCell>
                <TableCell>
                  {p.is_overdue ? (
                    <Chip size="small" color="error" label={`${p.days_overdue} дн.`} />
                  ) : '—'}
                </TableCell>
                <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                  {p.status === 'paid' ? (
                    <>
                      <Button size="small" onClick={() => setDialogFor(p)}>Изменить дату</Button>
                      <Button size="small" color="inherit" onClick={() => runAction(() => markUnpaid(p.id))}>
                        Отменить
                      </Button>
                    </>
                  ) : (
                    <Button size="small" variant="contained" onClick={() => setDialogFor(p)}>Оплачено</Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {dialogFor && (
        <PayDialog occurrence={dialogFor} onClose={() => setDialogFor(null)} onSubmit={handlePaySubmit} />
      )}

      <Snackbar open={Boolean(error)} autoHideDuration={5000} onClose={() => setError('')}>
        <Alert severity="error" onClose={() => setError('')}>{error}</Alert>
      </Snackbar>
    </>
  );
}
