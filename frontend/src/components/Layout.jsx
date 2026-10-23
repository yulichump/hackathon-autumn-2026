import { NavLink, Outlet } from 'react-router';
import { AppBar, Box, Button, Chip, Stack, Toolbar, Typography } from '@mui/material';
import { useAuth } from '../context/useAuth';

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Платежи' },
  { to: '/recurring', label: 'Регулярные платежи' },
  { to: '/users', label: 'Пользователи', adminOnly: true },
];

export default function Layout() {
  const { user, isAdmin, logout } = useAuth();

  return (
    <>
      <AppBar position="static" color="default" elevation={1}>
        <Toolbar sx={{ columnGap: 2, rowGap: 0.5, flexWrap: 'wrap', py: 1 }}>
          <Typography variant="h6" sx={{ mr: 2 }}>Invoice Keeper</Typography>
          <Stack direction="row" sx={{ flexGrow: 1, flexWrap: 'wrap', columnGap: 1 }}>
            {NAV_ITEMS.filter((item) => !item.adminOnly || isAdmin).map((item) => (
              <Button
                key={item.to}
                component={NavLink}
                to={item.to}
                color="inherit"
                sx={{ '&.active': { color: 'primary.main', fontWeight: 600 } }}
              >
                {item.label}
              </Button>
            ))}
          </Stack>
          <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
            <Typography>{user?.login}</Typography>
            <Chip size="small" label={isAdmin ? 'Администратор' : 'Пользователь'} color={isAdmin ? 'primary' : 'default'} />
            <Button onClick={logout}>Выйти</Button>
          </Stack>
        </Toolbar>
      </AppBar>
      <Box sx={{ p: { xs: 2, sm: 3 }, maxWidth: 1200, mx: 'auto' }}>
        <Outlet />
      </Box>
    </>
  );
}
