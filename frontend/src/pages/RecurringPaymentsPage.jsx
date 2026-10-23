import { useCallback, useEffect, useState } from 'react';
import {
  Alert, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, MenuItem, Paper,
  Snackbar, Stack, Switch, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import { useAuth } from '../context/useAuth';
import { getErrorMessage } from '../api/axios';
import { createRecurringPayment, deleteRecurringPayment, getRecurringPayments } from '../api/payments';
import ConfirmDialog from '../components/ConfirmDialog';
import { CURRENCIES, PERIODS, formatDate, formatNumber, periodLabel, todayIso } from '../utils/format';

const EMPTY_FORM = { name: '', amount: '', currency: 'RUB', next_payment_date: todayIso(), period: 'monthly' };

function CreatePaymentDialog({ onClose, onCreated }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const setField = (name) => (e) => setForm((prev) => ({ ...prev, [name]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSaving(true);
    try {
      const created = await createRecurringPayment({ ...form, amount: Number(form.amount) });
      onCreated(created);
    } catch (err) {
      setError(getErrorMessage(err, 'Не удалось создать платёж'));
      setSaving(false);
    }
  };

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <form onSubmit={handleSubmit}>
        <DialogTitle>Новый регулярный платёж</DialogTitle>
        <DialogContent>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="Название" required autoFocus value={form.name} onChange={setField('name')} />
            <Stack direction="row" spacing={2}>
              <TextField
                label="Сумма"
                required
                type="number"
                value={form.amount}
                onChange={setField('amount')}
                sx={{ flex: 1 }}
                slotProps={{ htmlInput: { min: 0.01, step: 0.01 } }}
              />
              <TextField select label="Валюта" value={form.currency} onChange={setField('currency')} sx={{ width: 120 }}>
                {CURRENCIES.map((c) => <MenuItem key={c} value={c}>{c}</MenuItem>)}
              </TextField>
            </Stack>
            <Stack direction="row" spacing={2}>
              <TextField
                label="Дата ближайшей оплаты"
                required
                type="date"
                value={form.next_payment_date}
                onChange={setField('next_payment_date')}
                sx={{ flex: 1 }}
                slotProps={{ inputLabel: { shrink: true } }}
              />
              <TextField select label="Периодичность" value={form.period} onChange={setField('period')} sx={{ flex: 1 }}>
                {PERIODS.map((p) => <MenuItem key={p.value} value={p.value}>{p.label}</MenuItem>)}
              </TextField>
            </Stack>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Отмена</Button>
          <Button type="submit" variant="contained" disabled={saving}>Создать</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

export default function RecurringPaymentsPage() {
  const { isAdmin } = useAuth();
  const [payments, setPayments] = useState([]);
  const [showDeleted, setShowDeleted] = useState(false);
  const [creating, setCreating] = useState(false);
  const [toDelete, setToDelete] = useState(null);
  const [message, setMessage] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getRecurringPayments({ include_deleted: showDeleted })
      .then((items) => {
        if (!cancelled) setPayments(items);
      })
      .catch((err) => {
        if (!cancelled) setMessage({ severity: 'error', text: getErrorMessage(err, 'Не удалось загрузить платежи') });
      });
    return () => {
      cancelled = true;
    };
  }, [showDeleted, reloadKey]);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  const handleCreated = (created) => {
    setCreating(false);
    setMessage({ severity: 'success', text: `Платёж «${created.name}» добавлен` });
    reload();
  };

  const handleDelete = async () => {
    const payment = toDelete;
    setToDelete(null);
    try {
      await deleteRecurringPayment(payment.id);
      setMessage({ severity: 'success', text: `Платёж «${payment.name}» прекращён, история сохранена` });
      reload();
    } catch (err) {
      setMessage({ severity: 'error', text: getErrorMessage(err, 'Не удалось удалить платёж') });
    }
  };

  return (
    <>
      <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between', mb: 2, flexWrap: 'wrap', gap: 2 }}>
        <Typography variant="h4" sx={{ fontSize: { xs: '1.75rem', sm: '2.125rem' } }}>Регулярные платежи</Typography>
        <Stack direction="row" sx={{ alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
          <FormControlLabel
            control={<Switch checked={showDeleted} onChange={(e) => setShowDeleted(e.target.checked)} />}
            label="Показать прекращённые"
          />
          {isAdmin && <Button variant="contained" onClick={() => setCreating(true)}>Добавить платёж</Button>}
        </Stack>
      </Stack>

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Название</TableCell>
              <TableCell align="right">Сумма</TableCell>
              <TableCell>Валюта</TableCell>
              <TableCell>Периодичность</TableCell>
              <TableCell>Ближайшая оплата</TableCell>
              <TableCell>Начало</TableCell>
              {isAdmin && <TableCell align="right">Действия</TableCell>}
            </TableRow>
          </TableHead>
          <TableBody>
            {payments.length === 0 && (
              <TableRow>
                <TableCell colSpan={isAdmin ? 7 : 6} align="center">Регулярных платежей нет</TableCell>
              </TableRow>
            )}
            {payments.map((p) => (
              <TableRow key={p.id} sx={p.is_deleted ? { opacity: 0.6 } : undefined}>
                <TableCell>
                  {p.name}
                  {p.is_deleted && <Chip size="small" label="прекращён" sx={{ ml: 1 }} />}
                </TableCell>
                <TableCell align="right">{formatNumber(p.amount)}</TableCell>
                <TableCell>{p.currency}</TableCell>
                <TableCell>{periodLabel(p.period)}</TableCell>
                <TableCell>{formatDate(p.next_payment_date)}</TableCell>
                <TableCell>{formatDate(p.start_date)}</TableCell>
                {isAdmin && (
                  <TableCell align="right">
                    {!p.is_deleted && (
                      <Button size="small" color="error" onClick={() => setToDelete(p)}>Удалить</Button>
                    )}
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {creating && <CreatePaymentDialog onClose={() => setCreating(false)} onCreated={handleCreated} />}

      <ConfirmDialog
        open={Boolean(toDelete)}
        title="Прекратить регулярный платёж?"
        text={toDelete ? `«${toDelete.name}» больше не будет создавать периоды и напоминания. Прошлые оплаты останутся в истории.` : ''}
        onConfirm={handleDelete}
        onClose={() => setToDelete(null)}
      />

      <Snackbar open={Boolean(message)} autoHideDuration={5000} onClose={() => setMessage(null)}>
        {message ? <Alert severity={message.severity} onClose={() => setMessage(null)}>{message.text}</Alert> : <span />}
      </Snackbar>
    </>
  );
}
