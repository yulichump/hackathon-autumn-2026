
import { useMemo, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    Collapse,
    Dialog,
    DialogContent,
    DialogTitle,
    IconButton,
    Stack,
    Typography,
    ToggleButton,
    ToggleButtonGroup,
} from '@mui/material';
import { formatDate, formatMoney } from '../utils/format';
import './PaymentsCalendar.css';

const pad = (value) => String(value).padStart(2, '0');

const dateKey = (date) =>
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;

const parseDate = (value) => {
    if (!value) return null;

    const [year, month, day] = value.slice(0, 10).split('-').map(Number);

    if (!year || !month || !day) return null;

    return new Date(year, month - 1, day);
};

const monthTitle = (date) =>
    new Intl.DateTimeFormat('ru-RU', {
        month: 'long',
        year: 'numeric',
    }).format(date);

const weekdayNames = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

function PaymentCard({ payment, onPay, onUnpaid }) {
    const paid = payment.status === 'paid';
    const overdue = payment.is_overdue && !paid;

    return (
        <Card
            variant="outlined"
            className={`calendar-payment-card${overdue ? ' is-overdue' : ''}`}
        >
            <CardContent>
                <Stack
                    direction="row"
                    justifyContent="space-between"
                    alignItems="flex-start"
                    gap={1}
                >
                    <Typography
                        variant="subtitle1"
                        fontWeight={700}
                        sx={{ minWidth: 0, overflowWrap: 'anywhere' }}
                    >
                        {payment.name}
                    </Typography>

                    <Chip
                        size="small"
                        label={paid ? 'Оплачено' : 'Ожидает'}
                        color={paid ? 'success' : 'default'}
                    />
                </Stack>

                <Typography
                    variant="h6"
                    sx={{
                        mt: 1.5,
                        mb: 2,
                        fontWeight: 700,
                        overflowWrap: 'anywhere',
                    }}
                >
                    {formatMoney(payment.amount, payment.currency)}
                </Typography>

                <Stack spacing={1}>
                    <Box>
                        <Typography variant="caption" color="text.secondary">
                            Срок оплаты
                        </Typography>
                        <Typography variant="body2">
                            {formatDate(payment.due_date)}
                        </Typography>
                    </Box>

                    <Box>
                        <Typography variant="caption" color="text.secondary">
                            Дата фактической оплаты
                        </Typography>
                        <Typography variant="body2">
                            {formatDate(payment.actual_payment_date)}
                        </Typography>
                    </Box>

                    {payment.paid_by && (
                        <Box>
                            <Typography variant="caption" color="text.secondary">
                                Отметил оплату
                            </Typography>
                            <Typography variant="body2" sx={{ overflowWrap: 'anywhere' }}>
                                {payment.paid_by}
                            </Typography>
                        </Box>
                    )}

                    {overdue && (
                        <Box>
                            <Chip
                                size="small"
                                color="error"
                                label={`Просрочено на ${payment.days_overdue} дн.`}
                            />
                        </Box>
                    )}
                </Stack>

                <Stack
                    direction={{ xs: 'column', sm: 'row' }}
                    spacing={1}
                    sx={{ mt: 2.5, pt: 2, borderTop: 1, borderColor: 'divider' }}
                >
                    {paid ? (
                        <>
                            <Button fullWidth variant="outlined" onClick={() => onPay(payment)}>
                                Изменить дату
                            </Button>
                            <Button
                                fullWidth
                                color="inherit"
                                onClick={() => onUnpaid(payment)}
                            >
                                Отменить оплату
                            </Button>
                        </>
                    ) : (
                        <Button
                            fullWidth
                            variant="contained"
                            onClick={() => onPay(payment)}
                        >
                            Отметить оплату
                        </Button>
                    )}
                </Stack>
            </CardContent>
        </Card>
    );
}

export default function PaymentsCalendar({
    occurrences,
    loading,
    onPay,
    onUnpaid,
}) {
    const [viewMode, setViewMode] = useState('list');
    const [visibleMonth, setVisibleMonth] = useState(
        () => new Date(new Date().getFullYear(), new Date().getMonth(), 1),
    );
    const [selectedDate, setSelectedDate] = useState(null);

    const days = useMemo(() => {
        const year = visibleMonth.getFullYear();
        const month = visibleMonth.getMonth();

        const firstWeekday = (new Date(year, month, 1).getDay() + 6) % 7;
        const daysInMonth = new Date(year, month + 1, 0).getDate();
        const cellCount = Math.ceil((firstWeekday + daysInMonth) / 7) * 7;

        return Array.from({ length: cellCount }, (_, index) => {
            const dayNumber = index - firstWeekday + 1;
            const date = new Date(year, month, dayNumber);

            return {
                date,
                key: dateKey(date),
                inMonth: date.getMonth() === month,
            };
        });
    }, [visibleMonth]);

    const paymentsByDate = useMemo(() => {
        const grouped = {};

        for (const payment of occurrences) {
            if (!payment.due_date) continue;

            const key = payment.due_date.slice(0, 10);

            if (!grouped[key]) grouped[key] = [];
            grouped[key].push(payment);
        }

        return grouped;
    }, [occurrences]);

    const selectedPayments = selectedDate
        ? paymentsByDate[selectedDate] || []
        : [];

    const today = dateKey(new Date());

    const changeMonth = (amount) => {
        setVisibleMonth((current) =>
            new Date(current.getFullYear(), current.getMonth() + amount, 1),
        );
    };

    const openDay = (key) => setSelectedDate(key);

    return (
        <section className="payments-calendar">
            <div className="calendar-toolbar">
                <div>
                    <Typography variant="h5" fontWeight={700}>
                        {monthTitle(visibleMonth)}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                        Выбери день, чтобы посмотреть платежи
                    </Typography>
                </div>

                <div className="calendar-month-controls">
                    <Button
                        variant="outlined"
                        size="small"
                        onClick={() => changeMonth(-1)}
                        aria-label="Предыдущий месяц"
                    >
                        ←
                    </Button>
                    <Button
                        variant="outlined"
                        size="small"
                        onClick={() =>
                            setVisibleMonth(new Date(new Date().getFullYear(), new Date().getMonth(), 1))
                        }
                    >
                        Сегодня
                    </Button>
                    <Button
                        variant="outlined"
                        size="small"
                        onClick={() => changeMonth(1)}
                        aria-label="Следующий месяц"
                    >
                        →
                    </Button>
                </div>
            </div>

            {loading && (
                <Alert severity="info" sx={{ mb: 2 }}>
                    Обновляем платежи…
                </Alert>
            )}

            <div className="calendar-grid">
                {weekdayNames.map((name) => (
                    <div className="calendar-weekday" key={name}>
                        {name}
                    </div>
                ))}

                {days.map(({ date, key, inMonth }) => {
                    const payments = paymentsByDate[key] || [];
                    const overdueCount = payments.filter(
                        (payment) => payment.is_overdue && payment.status !== 'paid',
                    ).length;
                    const paidCount = payments.filter(
                        (payment) => payment.status === 'paid',
                    ).length;

                    return (
                        <button
                            type="button"
                            key={key}
                            className={[
                                'calendar-day',
                                !inMonth ? 'is-outside' : '',
                                key === today ? 'is-today' : '',
                                payments.length ? 'has-payments' : '',
                            ].filter(Boolean).join(' ')}
                            onClick={() => openDay(key)}
                            aria-label={`${formatDate(key)}, платежей: ${payments.length}`}
                        >
                            <span className="calendar-day-number">{date.getDate()}</span>

                            {payments.length > 0 && (
                                <div className="calendar-day-details">
                                    <span className="calendar-payment-count">
                                        {payments.length} {payments.length === 1 ? 'платёж' : 'платежа'}
                                    </span>

                                    <div className="calendar-day-dots">
                                        {paidCount > 0 && (
                                            <span className="calendar-dot is-paid" />
                                        )}
                                        {payments.length - paidCount - overdueCount > 0 && (
                                            <span className="calendar-dot is-pending" />
                                        )}
                                        {overdueCount > 0 && (
                                            <span className="calendar-dot is-overdue" />
                                        )}
                                    </div>
                                </div>
                            )}
                        </button>
                    );
                })}
            </div>

            <div className="calendar-legend">
                <span><i className="calendar-dot is-pending" /> Ожидают оплаты</span>
                <span><i className="calendar-dot is-paid" /> Оплачено</span>
                <span><i className="calendar-dot is-overdue" /> Просрочено</span>
            </div>

            <Dialog
                open={Boolean(selectedDate)}
                onClose={() => setSelectedDate(null)}
                fullWidth
                maxWidth="md"
            >
                <DialogTitle className="calendar-dialog-title">
                    <Box>

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
                        </Stack>

                        <Typography variant="body2" color="text.secondary">
                            {selectedPayments.length
                                ? `Найдено платежей: ${selectedPayments.length}`
                                : 'На этот день платежей нет'}
                        </Typography>
                    </Box>

                    <IconButton
                        aria-label="Закрыть"
                        onClick={() => setSelectedDate(null)}
                    >
                        ×
                    </IconButton>
                </DialogTitle>

                <DialogContent dividers>
                    {selectedPayments.length === 0 ? (
                        <Box className="calendar-empty-day">
                            <Typography variant="body1">
                                Платежей на выбранную дату нет
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                                Выбери другой день или перейди к соседнему месяцу.
                            </Typography>
                        </Box>
                    ) : (
                        <div className="calendar-payment-list">
                            {selectedPayments.map((payment) => (
                                <PaymentCard
                                    key={payment.id}
                                    payment={payment}
                                    onPay={onPay}
                                    onUnpaid={onUnpaid}
                                />
                            ))}
                        </div>
                    )}
                </DialogContent>
            </Dialog>
        </section>
    );
}
