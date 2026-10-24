import { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  IconButton,
  InputAdornment,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { Eye, EyeOff } from 'lucide-react';

import { useAuth } from '../context/useAuth';
import { getErrorMessage } from '../api/axios';
import './LoginPage.css';
import OrbitLogo from './../components/OrbitLogo';

export default function LoginPage() {
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const { user, login: signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const redirectTo = location.state?.from || '/dashboard';

  if (user) {
    return <Navigate to={redirectTo} replace />;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);

    try {
      await signIn(login, password);
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setError(getErrorMessage(err, 'Не удалось войти'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Box className="login-page">
      <div className="login-page__glow login-page__glow--top" />
      <div className="login-page__glow login-page__glow--bottom" />

      <Paper className="login-card" elevation={0}>
        <header className="login-card__header">
          <div className="login-brand__logo">
            <OrbitLogo size={44} />
          </div>

          <Typography component="p" className="login-card__eyebrow">
            ЛИЧНЫЙ КАБИНЕТ
          </Typography>

          <Typography component="h1" className="login-card__title">
            С возвращением
          </Typography>

          <Typography component="p" className="login-card__subtitle">
            Войдите, чтобы управлять платежами
            и следить за своими финансами.
          </Typography>
        </header>

        {error && (
          <Alert
            severity="error"
            className="login-card__error"
            onClose={() => setError('')}
          >
            {error}
          </Alert>
        )}

        <Box
          component="form"
          className="login-form"
          onSubmit={handleSubmit}
        >
          <TextField
            className="login-form__field"
            fullWidth
            required
            autoFocus
            autoComplete="username"
            label="Логин"
            value={login}
            onChange={(e) => setLogin(e.target.value)}
            disabled={submitting}
          />

          <TextField
            className="login-form__field"
            fullWidth
            required
            autoComplete="current-password"
            label="Пароль"
            type={showPassword ? 'text' : 'password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={submitting}
            slotProps={{
              input: {
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      className="login-form__password-toggle"
                      aria-label={
                        showPassword ? 'Скрыть пароль' : 'Показать пароль'
                      }
                      onClick={() => setShowPassword((value) => !value)}
                      edge="end"
                      disabled={submitting}
                    >
                      {showPassword ? (
                        <EyeOff size={19} />
                      ) : (
                        <Eye size={19} />
                      )}
                    </IconButton>
                  </InputAdornment>
                ),
              },
            }}
          />

          <Button
            className="login-form__submit"
            type="submit"
            variant="contained"
            fullWidth
            disabled={submitting || !login.trim() || !password}
          >
            {submitting ? (
              <>
                <CircularProgress
                  size={19}
                  thickness={5}
                  className="login-form__spinner"
                />
                Входим…
              </>
            ) : (
              'Войти в аккаунт'
            )}
          </Button>
        </Box>

        <footer className="login-card__footer">
          <span className="login-card__status-dot" />
          <Typography component="span">
            Ваши платежи — под контролем
          </Typography>
        </footer>
      </Paper>

      <Typography component="p" className="login-page__copyright">
        INVOICE KEEPER · УПРАВЛЕНИЕ ПЛАТЕЖАМИ
      </Typography>
    </Box>
  );
}
