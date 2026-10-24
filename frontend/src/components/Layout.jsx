import { useState } from 'react';
import { NavLink, Outlet } from 'react-router';
import {
  AppBar,
  Avatar,
  Box,
  Collapse,
  Divider,
  IconButton,
  Stack,
  Toolbar,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import {
  Wallet,
  LayoutDashboard,
  CalendarClock,
  Users,
  Menu,
  X,
  LogOut,
} from 'lucide-react';
import { useAuth } from '../context/useAuth';
import './Layout.css';
import OrbitLogo from './OrbitLogo';

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Платежи', icon: LayoutDashboard },
  { to: '/recurring', label: 'Регулярные платежи', icon: CalendarClock },
  { to: '/users', label: 'Пользователи', icon: Users, adminOnly: true },
];

export default function Layout() {
  const { user, isAdmin, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const navItems = NAV_ITEMS.filter(
    (item) => !item.adminOnly || isAdmin,
  );

  const closeMenu = () => setMenuOpen(false);

  const renderNavItems = (mobile = false) =>
    navItems.map(({ to, label, icon: Icon }) => (
      <Box
        key={to}
        component={NavLink}
        to={to}
        onClick={mobile ? closeMenu : undefined}
        className="layout-nav-link"
      >
        <Icon size={18} />
        <span>{label}</span>
      </Box>
    ));

  return (
    <>
      <AppBar position="sticky" elevation={0} className="layout-header">
        <Toolbar className="layout-toolbar">
          <Stack direction="row" alignItems="center" spacing={1.5} className="layout-brand">
            <div className="layout-brand">
              <OrbitLogo size={44} />
            </div>
          </Stack>

          {!isMobile && (
            <Box component="nav" className="layout-desktop-nav">
              {renderNavItems()}
            </Box>
          )}

          {!isMobile && (
            <Stack direction="row" alignItems="center" spacing={1.5} className="layout-profile">
              <Avatar className="layout-avatar">
                {(user?.login || '?').slice(0, 1).toUpperCase()}
              </Avatar>
              <Box className="layout-user-info">
                <Typography className="layout-user-login" title={user?.login || ''}>
                  {user?.login}
                </Typography>
                <Typography className="layout-user-role">
                  {isAdmin ? 'Администратор' : 'Пользователь'}
                </Typography>
              </Box>
              <IconButton
                onClick={logout}
                aria-label="Выйти из аккаунта"
                title="Выйти"
                className="layout-logout"
              >
                <LogOut size={19} />
              </IconButton>
            </Stack>
          )}

          {isMobile && (
            <IconButton
              onClick={() => setMenuOpen((open) => !open)}
              aria-label={menuOpen ? 'Закрыть меню' : 'Открыть меню'}
              aria-expanded={menuOpen}
              className="layout-menu-toggle"
            >
              {menuOpen ? <X size={21} /> : <Menu size={21} />}
            </IconButton>
          )}
        </Toolbar>

        {isMobile && (
          <Collapse in={menuOpen} timeout={180} unmountOnExit>
            <Divider />
            <Box className="layout-mobile-menu">
              <Box component="nav" className="layout-mobile-nav">
                {renderNavItems(true)}
              </Box>

              <Divider />

              <Stack direction="row" alignItems="center" spacing={1.5} className="layout-mobile-profile">
                <Avatar className="layout-avatar">
                  {(user?.login || '?').slice(0, 1).toUpperCase()}
                </Avatar>
                <Box className="layout-user-info">
                  <Typography className="layout-user-login">
                    {user?.login}
                  </Typography>
                  <Typography className="layout-user-role">
                    {isAdmin ? 'Администратор' : 'Пользователь'}
                  </Typography>
                </Box>
                <IconButton
                  onClick={logout}
                  aria-label="Выйти из аккаунта"
                  className="layout-logout"
                >
                  <LogOut size={19} />
                </IconButton>
              </Stack>
            </Box>
          </Collapse>
        )}
      </AppBar>

      <Box component="main" className="layout-main">
        <Outlet />
      </Box>
    </>
  );
}
