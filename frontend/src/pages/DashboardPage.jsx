import { useCallback, useEffect, useState } from 'react';
import {
  Alert, Box, Button, Card, CardContent, Chip, Collapse,
  Dialog, DialogActions, DialogContent, DialogTitle,
  FormControl, IconButton, InputLabel, MenuItem, Paper,
  Select, Snackbar, Stack, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, TextField, Typography, ToggleButton, ToggleButtonGroup
} from '@mui/material';

import { ChevronDown, ChartNoAxesCombined } from 'lucide-react';

import { alpha } from '@mui/material/styles';
import { getErrorMessage } from '../api/axios';
import { getOccurrences, getSummary, markPaid, markUnpaid, updateOccurrence } from '../api/payments';
import { CURRENCIES, formatDate, formatMoney, formatNumber, todayIso } from '../utils/format';

import PaymentsCalendar from '../components/PaymentsCalendar';

function SummaryCards({ summary }) {
  const [expanded, setExpanded] = useState(true);

  return (
    <Card
      variant="outlined"
      sx={{
        mb: 3,
        borderRadius: 3,
        overflow: 'hidden',
        borderColor: expanded ? 'rgba(22, 185, 207, 0.3)' : 'divider',
        background: (theme) =>
          `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.045)}, transparent 65%), ${theme.palette.background.paper}`,
        transition: 'border-color 0.25s ease',
      }}
    >
      <Box
        component="button"
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        aria-expanded={expanded}
        sx={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 2,
          p: { xs: 2, sm: 2.5 },
          border: 0,
          color: 'inherit',
          background: 'transparent',
          textAlign: 'left',
          cursor: 'pointer',
          font: 'inherit',
          '&:hover': {
            backgroundColor: (theme) =>
              alpha(theme.palette.primary.main, 0.045),
          },
          '&:focus-visible': {
            outline: '2px solid',
            outlineColor: 'primary.main',
            outlineOffset: '-3px',
          },
        }}
      >
        <Stack direction="row" spacing={1.5} alignItems="center">
          <Box
            sx={{
              width: 42,
              height: 42,
              display: 'grid',
              placeItems: 'center',
              flexShrink: 0,
              borderRadius: 2.5,
              color: 'primary.main',
              backgroundColor: (theme) =>
                alpha(theme.palette.primary.main, 0.12),
            }}
          >
            <ChartNoAxesCombined size={22} />
          </Box>

          <Box>
            <Typography variant="subtitle1" fontWeight={700}>
              Общая сводка
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {expanded
                ? 'План, оплачено и просрочено по валютам'
                : `${CURRENCIES.length} валют · нажми, чтобы показать итоги`}
            </Typography>
          </Box>
        </Stack>

        <IconButton
          tabIndex={-1}
          aria-hidden="true"
          sx={{
            color: 'primary.main',
            transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 250ms ease',
          }}
        >
          <ChevronDown size={22} />
        </IconButton>
      </Box>

      <Collapse in={expanded} timeout={300}>
        <Box
          sx={{
            px: { xs: 2, sm: 2.5 },
            pb: { xs: 2, sm: 2.5 },
          }}
        >
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: {
                xs: 'minmax(0, 1fr)',
                sm: 'repeat(2, minmax(0, 1fr))',
                lg: 'repeat(3, minmax(0, 1fr))',
              },
              gap: 2,
            }}
          >
            {CURRENCIES.map((currency) => {
              const totals = summary?.[currency];

              return (
                <Card
                  key={currency}
                  variant="outlined"
                  sx={{
                    minWidth: 0,
                    borderRadius: 2.5,
                    backgroundColor: 'background.paper',
                    borderColor: 'divider',
                    transition: 'border-color 200ms ease, transform 200ms ease',
                    '&:hover': {
                      borderColor: 'primary.main',
                      transform: 'translateY(-2px)',
                    },
                  }}
                >
                  <CardContent
                    sx={{
                      p: 2,
                      '&:last-child': { pb: 2 },
                    }}
                  >
                    <Stack
                      direction="row"
                      alignItems="center"
                      justifyContent="space-between"
                      sx={{ mb: 1.5 }}
                    >
                      <Typography variant="subtitle1" fontWeight={700}>
                        {currency}
                      </Typography>

                      <Box
                        sx={{
                          width: 7,
                          height: 7,
                          borderRadius: '50%',
                          backgroundColor: 'primary.main',
                          boxShadow: '0 0 10px rgba(22, 185, 207, 0.45)',
                        }}
                      />
                    </Stack>

                    <Stack spacing={1}>
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Запланировано
                        </Typography>
                        <Typography variant="body1" fontWeight={600}>
                          {totals
                            ? formatMoney(totals.total_planned, currency)
                            : '—'}
                        </Typography>
                      </Box>

                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Оплачено
                        </Typography>
                        <Typography
                          variant="body2"
                          color="success.main"
                          fontWeight={600}
                        >
                          {totals
                            ? formatMoney(totals.total_paid, currency)
                            : '—'}
                        </Typography>
                      </Box>

                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Просрочено
                        </Typography>
                        <Typography
                          variant="body2"
                          color="error.main"
                          fontWeight={600}
                        >
                          {totals
                            ? formatMoney(totals.total_overdue, currency)
                            : '—'}
                        </Typography>
                      </Box>
                    </Stack>
                  </CardContent>
                </Card>
              );
            })}
          </Box>
        </Box>
      </Collapse>
    </Card>
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

  const [viewMode, setViewMode] = useState('list');

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

      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        justifyContent="space-between"
        alignItems={{ xs: 'stretch', sm: 'center' }}
        spacing={2}
        sx={{ mb: 3 }}
      >
        <Typography
          variant="h4"
          sx={{ fontSize: { xs: '1.75rem', sm: '2.125rem' } }}
        >
          Платежи
        </Typography>

        <ToggleButtonGroup
          value={viewMode}
          exclusive
          onChange={(_, value) => {
            if (value) setViewMode(value);
          }}
          size="small"
          aria-label="Представление платежей"
          sx={{
            alignSelf: { xs: 'flex-start', sm: 'auto' },
            backgroundColor: 'background.paper',
            borderRadius: 2,
            '& .MuiToggleButton-root': {
              px: 2,
              py: 1,
              borderColor: 'divider',
              textTransform: 'none',
              fontWeight: 600,
            },
            '& .MuiToggleButton-root.Mui-selected': {
              color: 'primary.main',
              backgroundColor: 'rgba(22, 185, 207, 0.12)',
              borderColor: 'rgba(22, 185, 207, 0.4)',
            },
            '& .MuiToggleButton-root.Mui-selected:hover': {
              backgroundColor: 'rgba(22, 185, 207, 0.2)',
            },
          }}
        >
          <ToggleButton value="list">☷ Список</ToggleButton>
          <ToggleButton value="calendar">▦ Календарь</ToggleButton>
        </ToggleButtonGroup>
      </Stack>

      {viewMode === 'list' && (
        <>
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
        </>
      )}
      {viewMode === 'calendar' ? (
        <PaymentsCalendar
          occurrences={occurrences}
          loading={loading}
          onPay={(payment) => setDialogFor(payment)}
          onUnpaid={(payment) => runAction(() => markUnpaid(payment.id))}
        />
      ) : (
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: {
              xs: 'minmax(0, 1fr)',
              md: 'repeat(2, minmax(0, 1fr))',
              xl: 'repeat(3, minmax(0, 1fr))',
            },
            gap: 2,
            alignItems: 'stretch',
          }}
        >
          {!loading && occurrences.length === 0 && (
            <Paper
              sx={{
                gridColumn: '1 / -1',
                p: 5,
                textAlign: 'center',
                border: '1px dashed',
                borderColor: 'divider',
              }}
            >
              <Typography variant="h6" sx={{ mb: 1 }}>
                Платежей нет
              </Typography>
              <Typography color="text.secondary" variant="body2">
                Попробуй изменить фильтры или проверь позже.
              </Typography>
            </Paper>
          )}

          {loading && occurrences.length === 0 && (
            <Paper
              sx={{
                gridColumn: '1 / -1',
                p: 4,
                textAlign: 'center',
              }}
            >
              <Typography color="text.secondary">
                Загружаем платежи...
              </Typography>
            </Paper>
          )}

          {occurrences.map((p) => {
            const paid = p.status === 'paid';
            const overdue = p.is_overdue && !paid;

            return (
              <Card
                key={p.id}
                variant="outlined"
                sx={{
                  minWidth: 0,
                  display: 'flex',
                  flexDirection: 'column',
                  borderColor: overdue ? 'error.main' : 'divider',
                  borderRadius: 3,
                  backgroundColor: 'background.paper',
                  transition: 'border-color 0.2s, transform 0.2s',
                  '&:hover': {
                    borderColor: overdue ? 'error.light' : 'primary.main',
                    transform: 'translateY(-2px)',
                  },
                }}
              >
                <CardContent
                  sx={{
                    p: 2.5,
                    display: 'flex',
                    flexDirection: 'column',
                    flexGrow: 1,
                    '&:last-child': { pb: 2.5 },
                  }}
                >
                  {/* Название и статус */}
                  <Stack
                    direction="row"
                    justifyContent="space-between"
                    alignItems="flex-start"
                    spacing={1}
                    sx={{ mb: 2 }}
                  >
                    <Box sx={{ minWidth: 0, flex: 1 }}>
                      <Typography
                        variant="h6"
                        sx={{
                          fontSize: '1rem',
                          overflowWrap: 'anywhere',
                          lineHeight: 1.5,
                        }}
                      >
                        {p.name}
                      </Typography>

                      {p.recurring_payment_is_deleted && (
                        <Chip
                          size="small"
                          label="Платёж прекращён"
                          sx={{ mt: 1, maxWidth: '100%' }}
                        />
                      )}
                    </Box>

                    <Chip
                      size="small"
                      label={paid ? 'Оплачено' : 'Ожидает оплаты'}
                      color={paid ? 'success' : 'default'}
                      sx={{ flexShrink: 0, maxWidth: '55%' }}
                    />
                  </Stack>

                  {/* Сумма */}
                  <Typography
                    variant="h5"
                    sx={{
                      color: paid ? 'success.main' : 'text.primary',
                      fontWeight: 700,
                      mb: 2.5,
                      overflowWrap: 'anywhere',
                    }}
                  >
                    {formatMoney(p.amount, p.currency)}
                  </Typography>

                  {/* Основная информация */}
                  <Stack spacing={1.5} sx={{ mb: 2.5 }}>
                    <Stack direction="row" spacing={1.5} alignItems="flex-start">
                      <Box sx={{ color: 'text.secondary', pt: 0.2 }}>
                        <span>◷</span>
                      </Box>
                      <Box sx={{ minWidth: 0, flex: 1 }}>
                        <Typography variant="body2" color="text.secondary">
                          Срок оплаты
                        </Typography>
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>
                          {formatDate(p.due_date)}
                        </Typography>
                      </Box>
                    </Stack>

                    <Stack direction="row" spacing={1.5} alignItems="flex-start">
                      <Box sx={{ color: 'text.secondary', pt: 0.2 }}>
                        <span>✓</span>
                      </Box>
                      <Box sx={{ minWidth: 0, flex: 1 }}>
                        <Typography variant="body2" color="text.secondary">
                          Дата оплаты
                        </Typography>
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>
                          {formatDate(p.actual_payment_date)}
                        </Typography>
                      </Box>
                    </Stack>

                    <Stack direction="row" spacing={1.5} alignItems="flex-start">
                      <Box sx={{ color: 'text.secondary', pt: 0.2 }}>
                        <span>◎</span>
                      </Box>
                      <Box sx={{ minWidth: 0, flex: 1 }}>
                        <Typography variant="body2" color="text.secondary">
                          Отметил оплату
                        </Typography>
                        <Typography
                          variant="body2"
                          sx={{ overflowWrap: 'anywhere' }}
                        >
                          {p.paid_by
                            ? p.paid_by.startsWith('@')
                              ? `${p.paid_by} (Telegram)`
                              : p.paid_by
                            : 'Не указано'}
                        </Typography>
                      </Box>
                    </Stack>
                  </Stack>

                  {/* Просрочка */}
                  {overdue && (
                    <Box sx={{ mb: 2 }}>
                      <Chip
                        size="small"
                        color="error"
                        label={`Просрочено на ${p.days_overdue} дн.`}
                      />
                    </Box>
                  )}

                  {/* Действия */}
                  <Box sx={{ mt: 'auto', pt: 2, borderTop: 1, borderColor: 'divider' }}>
                    {paid ? (
                      <Stack
                        direction={{ xs: 'column', sm: 'row' }}
                        spacing={1}
                      >
                        <Button
                          fullWidth
                          size="medium"
                          variant="outlined"
                          onClick={() => setDialogFor(p)}
                        >
                          Изменить дату
                        </Button>

                        <Button
                          fullWidth
                          size="medium"
                          color="inherit"
                          onClick={() => runAction(() => markUnpaid(p.id))}
                        >
                          Отменить оплату
                        </Button>
                      </Stack>
                    ) : (
                      <Button
                        fullWidth
                        size="large"
                        variant="contained"
                        onClick={() => setDialogFor(p)}
                      >
                        <span style={{ marginRight: 8 }}>✓</span>
                        Отметить оплату
                      </Button>
                    )}
                  </Box>
                </CardContent>
              </Card>
            );
          })}
        </Box>
      )}

      {dialogFor && (
        <PayDialog occurrence={dialogFor} onClose={() => setDialogFor(null)} onSubmit={handlePaySubmit} />
      )}

      <Snackbar open={Boolean(error)} autoHideDuration={5000} onClose={() => setError('')}>
        <Alert severity="error" onClose={() => setError('')}>{error}</Alert>
      </Snackbar>
    </>
  );
}
