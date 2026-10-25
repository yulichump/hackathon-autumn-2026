import { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  MenuItem,
  Snackbar,
  Stack,
  Switch,
  TextField,
  Typography,
} from '@mui/material';
import { useAuth } from '../context/useAuth';
import { getErrorMessage } from '../api/axios';
import {
  createRecurringPayment,
  deleteRecurringPayment,
  getRecurringPayments,
  restoreRecurringPayment,
  updateRecurringPayment,
} from '../api/payments';
import ConfirmDialog from '../components/ConfirmDialog';
import {
  CURRENCIES,
  PERIODS,
  formatDate,
  formatNumber,
  periodLabel,
  todayIso,
} from '../utils/format';

const EMPTY_FORM = {
  name: '',
  amount: '',
  currency: 'RUB',
  next_payment_date: todayIso(),
  period: 'monthly',
};

function InfoItem({ label, value }) {
  return (
    <Box
      sx={{
        minWidth: 0,
        p: 1.5,
        borderRadius: 2,
        bgcolor: 'rgba(255,255,255,0.035)',
      }}
    >
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ display: 'block', mb: 0.5 }}
      >
        {label}
      </Typography>
      <Typography
        variant="body2"
        fontWeight={600}
        sx={{ overflowWrap: 'anywhere' }}
      >
        {value || '—'}
      </Typography>
    </Box>
  );
}

const formFromPayment = (payment) => ({
  name: payment.name,
  amount: String(payment.amount),
  currency: payment.currency,
  next_payment_date: payment.next_payment_date || todayIso(),
  period: payment.period,
});

const changedFields = (initial, form) =>
  Object.fromEntries(
    Object.entries(form)
      .filter(([key, value]) =>
        key === 'amount' ? Number(value) !== Number(initial.amount) : value !== initial[key],
      )
      .map(([key, value]) => [key, key === 'amount' ? Number(value) : value]),
  );

function PaymentFormDialog({ payment, onClose, onSaved }) {
  const isEdit = Boolean(payment);
  const initial = isEdit ? formFromPayment(payment) : EMPTY_FORM;
  const [form, setForm] = useState(initial);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const setField = (name) => (e) =>
    setForm((prev) => ({ ...prev, [name]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (isEdit) {
      const changes = changedFields(initial, form);
      if (Object.keys(changes).length === 0) {
        onClose();
        return;
      }
      setSaving(true);
      try {
        onSaved(await updateRecurringPayment(payment.id, changes), true);
      } catch (err) {
        setError(getErrorMessage(err, 'Не удалось сохранить изменения'));
        setSaving(false);
      }
      return;
    }

    setSaving(true);
    try {
      const created = await createRecurringPayment({
        ...form,
        amount: Number(form.amount),
      });
      onSaved(created, false);
    } catch (err) {
      setError(getErrorMessage(err, 'Не удалось создать платёж'));
      setSaving(false);
    }
  };

  return (
    <Dialog open onClose={saving ? undefined : onClose} fullWidth maxWidth="sm">
      <form onSubmit={handleSubmit}>
        <DialogTitle sx={{ pb: 1 }}>
          {isEdit ? 'Изменить регулярный платёж' : 'Новый регулярный платёж'}
        </DialogTitle>

        <DialogContent>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          {isEdit && (
            <Alert severity="info" sx={{ mb: 1 }}>
              Изменения применятся к будущим неоплаченным периодам. Прошлые, просроченные
              и оплаченные периоды останутся как есть.
            </Alert>
          )}

          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Название"
              required
              autoFocus
              fullWidth
              value={form.name}
              onChange={setField('name')}
            />

            <Stack
              direction={{ xs: 'column', sm: 'row' }}
              spacing={2}
            >
              <TextField
                label="Сумма"
                required
                type="number"
                value={form.amount}
                onChange={setField('amount')}
                fullWidth
                slotProps={{
                  htmlInput: { min: 0.01, step: 0.01 },
                }}
              />

              <TextField
                select
                label="Валюта"
                value={form.currency}
                onChange={setField('currency')}
                fullWidth
                sx={{ minWidth: 0 }}
              >
                {CURRENCIES.map((currency) => (
                  <MenuItem key={currency} value={currency}>
                    {currency}
                  </MenuItem>
                ))}
              </TextField>
            </Stack>

            <TextField
              label="Дата ближайшей оплаты"
              required
              type="date"
              value={form.next_payment_date}
              onChange={setField('next_payment_date')}
              fullWidth
              slotProps={{ inputLabel: { shrink: true } }}
            />

            <TextField
              select
              label="Периодичность"
              value={form.period}
              onChange={setField('period')}
              fullWidth
            >
              {PERIODS.map((period) => (
                <MenuItem key={period.value} value={period.value}>
                  {period.label}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
        </DialogContent>

        <DialogActions
          sx={{
            px: 3,
            pb: 2.5,
            flexDirection: { xs: 'column-reverse', sm: 'row' },
            '& > :not(style) ~ :not(style)': { ml: { xs: 0, sm: 1 } },
            gap: 1,
          }}
        >
          <Button
            onClick={onClose}
            disabled={saving}
            fullWidth
            sx={{ width: { xs: '100%', sm: 'auto' } }}
          >
            Отмена
          </Button>
          <Button
            type="submit"
            variant="contained"
            disabled={saving}
            fullWidth
            sx={{ width: { xs: '100%', sm: 'auto' } }}
          >
            {isEdit
              ? saving ? 'Сохранение…' : 'Сохранить'
              : saving ? 'Создание…' : 'Создать платёж'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

function RecurringPaymentCard({ payment, isAdmin, onEdit, onDelete, onRestore }) {
  const isDeleted = payment.is_deleted;

  return (
    <Card
      sx={{
        height: '100%',
        opacity: isDeleted ? 0.72 : 1,
        transition: 'border-color 0.2s ease, transform 0.2s ease',
        '&:hover': {
          borderColor: isDeleted ? 'divider' : 'primary.main',
          transform: { sm: 'translateY(-2px)' },
        },
      }}
    >
      <CardContent
        sx={{
          p: { xs: 2, sm: 2.5 },
          '&:last-child': { pb: { xs: 2, sm: 2.5 } },
        }}
      >
        <Stack spacing={2}>
          <Stack
            direction="row"
            spacing={1.5}
            sx={{ alignItems: 'flex-start', justifyContent: 'space-between' }}
          >
            <Box sx={{ minWidth: 0, flex: 1 }}>
              <Typography
                variant="h6"
                sx={{
                  fontSize: '1.05rem',
                  lineHeight: 1.4,
                  overflowWrap: 'anywhere',
                }}
              >
                {payment.name}
              </Typography>

              <Chip
                size="small"
                label={isDeleted ? 'Прекращён' : 'Активен'}
                color={isDeleted ? 'default' : 'success'}
                variant={isDeleted ? 'outlined' : 'filled'}
                sx={{ mt: 1 }}
              />
            </Box>

            <Box sx={{ textAlign: 'right', flexShrink: 0 }}>
              <Typography
                variant="h5"
                color={isDeleted ? 'text.secondary' : 'primary.main'}
                sx={{
                  fontWeight: 700,
                  fontSize: { xs: '1.25rem', sm: '1.4rem' },
                  overflowWrap: 'anywhere',
                }}
              >
                {formatNumber(payment.amount)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {payment.currency}
              </Typography>
            </Box>
          </Stack>

          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: {
                xs: '1fr',
                sm: 'repeat(2, minmax(0, 1fr))',
              },
              gap: 1,
            }}
          >
            <InfoItem
              label="Периодичность"
              value={periodLabel(payment.period)}
            />
            <InfoItem
              label="Ближайшая оплата"
              value={formatDate(payment.next_payment_date)}
            />
            <InfoItem
              label="Дата начала"
              value={formatDate(payment.start_date)}
            />
          </Box>

          {isAdmin && (
            <Box
              sx={{
                display: 'flex',
                flexDirection: { xs: 'column', sm: 'row' },
                justifyContent: 'flex-end',
                gap: 1,
                pt: 1.5,
                borderTop: 1,
                borderColor: 'divider',
              }}
            >
              {isDeleted ? (
                <Button
                  variant="contained"
                  onClick={() => onRestore(payment)}
                  sx={{ width: { xs: '100%', sm: 'auto' } }}
                >
                  Восстановить
                </Button>
              ) : (
                <>
                  <Button
                    variant="outlined"
                    onClick={() => onEdit(payment)}
                    sx={{ width: { xs: '100%', sm: 'auto' } }}
                  >
                    Изменить
                  </Button>
                  <Button
                    color="error"
                    variant="outlined"
                    onClick={() => onDelete(payment)}
                    sx={{ width: { xs: '100%', sm: 'auto' } }}
                  >
                    Прекратить платёж
                  </Button>
                </>
              )}
            </Box>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}

export default function RecurringPaymentsPage() {
  const { isAdmin } = useAuth();
  const [payments, setPayments] = useState([]);
  const [showDeleted, setShowDeleted] = useState(false);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState(null);
  const [toDelete, setToDelete] = useState(null);
  const [toRestore, setToRestore] = useState(null);
  const [message, setMessage] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    getRecurringPayments({ include_deleted: showDeleted })
      .then((items) => {
        if (!cancelled) setPayments(items);
      })
      .catch((err) => {
        if (!cancelled) {
          setMessage({
            severity: 'error',
            text: getErrorMessage(err, 'Не удалось загрузить платежи'),
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [showDeleted, reloadKey]);

  const reload = useCallback(() => {
    setReloadKey((key) => key + 1);
  }, []);

  const handleSaved = (saved, isEdit) => {
    setCreating(false);
    setEditing(null);
    setMessage({
      severity: 'success',
      text: isEdit ? `Платёж «${saved.name}» обновлён` : `Платёж «${saved.name}» добавлен`,
    });
    reload();
  };

  const handleRestore = async () => {
    const payment = toRestore;
    if (!payment) return;

    setToRestore(null);

    try {
      const restored = await restoreRecurringPayment(payment.id);
      setMessage({
        severity: 'success',
        text: `Платёж «${restored.name}» восстановлен, ближайшая оплата ${formatDate(restored.next_payment_date)}`,
      });
      reload();
    } catch (err) {
      setMessage({
        severity: 'error',
        text: getErrorMessage(err, 'Не удалось восстановить платёж'),
      });
    }
  };

  const handleDelete = async () => {
    const payment = toDelete;
    if (!payment) return;

    setToDelete(null);

    try {
      await deleteRecurringPayment(payment.id);
      setMessage({
        severity: 'success',
        text: `Платёж «${payment.name}» прекращён, история сохранена`,
      });
      reload();
    } catch (err) {
      setMessage({
        severity: 'error',
        text: getErrorMessage(err, 'Не удалось удалить платёж'),
      });
    }
  };

  return (
    <>
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        sx={{
          alignItems: { xs: 'stretch', sm: 'center' },
          justifyContent: 'space-between',
          mb: 3,
          gap: 2,
        }}
      >
        <Box>
          <Typography
            variant="h4"
            sx={{
              fontSize: { xs: '1.65rem', sm: '2.125rem' },
              mb: 0.5,
            }}
          >
            Регулярные платежи
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Управление повторяющимися расходами
          </Typography>
        </Box>

        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          sx={{
            alignItems: { xs: 'stretch', sm: 'center' },
            gap: 1.5,
          }}
        >
          <FormControlLabel
            sx={{ mr: 0 }}
            control={
              <Switch
                checked={showDeleted}
                onChange={(e) => setShowDeleted(e.target.checked)}
              />
            }
            label="Показать прекращённые"
          />

          {isAdmin && (
            <Button
              variant="contained"
              onClick={() => setCreating(true)}
              sx={{ minHeight: 42 }}
            >
              Добавить платёж
            </Button>
          )}
        </Stack>
      </Stack>

      {payments.length === 0 ? (
        <Card>
          <CardContent sx={{ py: 5, textAlign: 'center' }}>
            <Typography variant="h6" sx={{ mb: 1 }}>
              {showDeleted
                ? 'Платежей не найдено'
                : 'Регулярных платежей пока нет'}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {showDeleted
                ? 'Попробуйте изменить настройки отображения.'
                : isAdmin
                  ? 'Добавьте регулярный платёж, чтобы он появился здесь.'
                  : 'Когда регулярные платежи будут добавлены, они появятся здесь.'}
            </Typography>

            {isAdmin && !showDeleted && (
              <Button
                variant="contained"
                onClick={() => setCreating(true)}
                sx={{ mt: 2 }}
              >
                Добавить первый платёж
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: {
              xs: 'minmax(0, 1fr)',
              md: 'repeat(2, minmax(0, 1fr))',
              xl: 'repeat(3, minmax(0, 1fr))',
            },
            gap: { xs: 1.5, sm: 2 },
            alignItems: 'stretch',
          }}
        >
          {payments.map((payment) => (
            <RecurringPaymentCard
              key={payment.id}
              payment={payment}
              isAdmin={isAdmin}
              onEdit={setEditing}
              onDelete={setToDelete}
              onRestore={setToRestore}
            />
          ))}
        </Box>
      )}

      {(creating || editing) && (
        <PaymentFormDialog
          key={editing ? editing.id : 'new'}
          payment={editing}
          onClose={() => {
            setCreating(false);
            setEditing(null);
          }}
          onSaved={handleSaved}
        />
      )}

      <ConfirmDialog
        open={Boolean(toRestore)}
        title="Восстановить регулярный платёж?"
        text={
          toRestore
            ? `«${toRestore.name}» снова начнёт создавать периоды и напоминания. Сроки, прошедшие, пока платёж был прекращён, не создаются — расписание продолжится с ближайшей даты.`
            : ''
        }
        confirmLabel="Восстановить"
        confirmColor="primary"
        onConfirm={handleRestore}
        onClose={() => setToRestore(null)}
      />

      <ConfirmDialog
        open={Boolean(toDelete)}
        title="Прекратить регулярный платёж?"
        text={
          toDelete
            ? `«${toDelete.name}» больше не будет создавать периоды и напоминания. Прошлые оплаты останутся в истории.`
            : ''
        }
        onConfirm={handleDelete}
        onClose={() => setToDelete(null)}
      />

      <Snackbar
        open={Boolean(message)}
        autoHideDuration={5000}
        onClose={() => setMessage(null)}
      >
        {message ? (
          <Alert
            severity={message.severity}
            onClose={() => setMessage(null)}
          >
            {message.text}
          </Alert>
        ) : (
          <span />
        )}
      </Snackbar>
    </>
  );
}