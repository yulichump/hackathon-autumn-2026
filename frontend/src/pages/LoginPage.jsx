import { useState } from 'react';
import { useNavigate } from 'react-router';
import { TextField, Button, Box, Typography } from '@mui/material';

export default function LoginPage() {
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();

  const handleSubmit = (e) => {
    e.preventDefault();
    // Здесь позже будет вызов API
    console.log('Login attempt:', { login, password });
    navigate('/dashboard');
  };

  return (
    <Box sx={{ maxWidth: 400, margin: '100px auto', p: 3 }}>
      <Typography variant="h4" gutterBottom>Вход</Typography>
      <form onSubmit={handleSubmit}>
        <TextField fullWidth label="Логин" margin="normal" value={login} onChange={(e) => setLogin(e.target.value)} />
        <TextField fullWidth label="Пароль" type="password" margin="normal" value={password} onChange={(e) => setPassword(e.target.value)} />
        <Button type="submit" variant="contained" fullWidth sx={{ mt: 2 }}>Войти</Button>
      </form>
    </Box>
  );
}