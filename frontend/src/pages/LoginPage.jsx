import { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router';
import { Alert, TextField, Button, Box, Typography } from '@mui/material';
import { useAuth } from '../context/useAuth';
import { getErrorMessage } from '../api/axios';

export default function LoginPage() {
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
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
    <Box sx={{ maxWidth: 400, margin: '100px auto', p: 3 }}>
      <Typography variant="h4" gutterBottom>Вход</Typography>
      {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}
      <form onSubmit={handleSubmit}>
        <TextField fullWidth required autoFocus label="Логин" margin="normal" value={login} onChange={(e) => setLogin(e.target.value)} />
        <TextField fullWidth required label="Пароль" type="password" margin="normal" value={password} onChange={(e) => setPassword(e.target.value)} />
        <Button type="submit" variant="contained" fullWidth sx={{ mt: 2 }} disabled={submitting}>
          {submitting ? 'Входим…' : 'Войти'}
        </Button>
      </form>
    </Box>
  );
}
