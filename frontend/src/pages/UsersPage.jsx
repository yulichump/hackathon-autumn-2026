import { useCallback, useEffect, useState } from 'react';
import {
  Alert, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, Paper, Snackbar, Stack,
  Switch, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import { getErrorMessage } from '../api/axios';
import { createUser, deleteUser, getUsers, updateUser } from '../api/users';
import ConfirmDialog from '../components/ConfirmDialog';

function UserDialog({ user, onClose, onSaved }) {
  const isEdit = Boolean(user);
  const [login, setLogin] = useState(user?.login || '');
  const [password, setPassword] = useState('');
  const [isActive, setIsActive] = useState(user?.is_active ?? true);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSaving(true);
    try {
      let saved;
      if (isEdit) {
        const changes = { is_active: isActive };
        if (login !== user.login) changes.login = login;
        if (password) changes.password = password;
        saved = await updateUser(user.id, changes);
      } else {
        saved = await createUser({ login, password, role: 'user' });
      }
      onSaved(saved, isEdit);
    } catch (err) {
      setError(getErrorMessage(err, 'Не удалось сохранить пользователя'));
      setSaving(false);
    }
  };

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="xs">
      <form onSubmit={handleSubmit}>
        <DialogTitle>{isEdit ? `Пользователь ${user.login}` : 'Новый пользователь'}</DialogTitle>
        <DialogContent>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Логин"
              required
              autoFocus={!isEdit}
              value={login}
              onChange={(e) => setLogin(e.target.value)}
              helperText="3–50 символов: латиница, цифры, _ . -"
            />
            <TextField
              label={isEdit ? 'Новый пароль' : 'Пароль'}
              type="password"
              required={!isEdit}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              helperText={isEdit ? 'Оставьте пустым, чтобы не менять' : 'Минимум 6 символов'}
            />
            {isEdit && (
              <FormControlLabel
                control={<Switch checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />}
                label={isActive ? 'Активен' : 'Отключён — не сможет войти'}
              />
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Отмена</Button>
          <Button type="submit" variant="contained" disabled={saving}>{isEdit ? 'Сохранить' : 'Создать'}</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

export default function UsersPage() {
  const [users, setUsers] = useState([]);
  const [editing, setEditing] = useState(null);
  const [toDelete, setToDelete] = useState(null);
  const [message, setMessage] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getUsers()
      .then((items) => {
        if (!cancelled) setUsers(items);
      })
      .catch((err) => {
        if (!cancelled) setMessage({ severity: 'error', text: getErrorMessage(err, 'Не удалось загрузить пользователей') });
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  const handleSaved = (saved, isEdit) => {
    setEditing(null);
    setMessage({ severity: 'success', text: isEdit ? `Пользователь ${saved.login} обновлён` : `Пользователь ${saved.login} создан` });
    reload();
  };

  const handleDelete = async () => {
    const user = toDelete;
    setToDelete(null);
    try {
      await deleteUser(user.id);
      setMessage({ severity: 'success', text: `Пользователь ${user.login} удалён` });
      reload();
    } catch (err) {
      setMessage({ severity: 'error', text: getErrorMessage(err, 'Не удалось удалить пользователя') });
    }
  };

  return (
    <>
      <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between', mb: 1, flexWrap: 'wrap', gap: 2 }}>
        <Typography variant="h4" sx={{ fontSize: { xs: '1.75rem', sm: '2.125rem' } }}>Пользователи</Typography>
        <Button variant="contained" onClick={() => setEditing('new')}>Добавить пользователя</Button>
      </Stack>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Учётная запись администратора задаётся в .env и здесь не отображается.
      </Typography>

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Логин</TableCell>
              <TableCell>Статус</TableCell>
              <TableCell align="right">Действия</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {users.length === 0 && (
              <TableRow>
                <TableCell colSpan={3} align="center">Пользователей нет</TableCell>
              </TableRow>
            )}
            {users.map((u) => (
              <TableRow key={u.id}>
                <TableCell>{u.login}</TableCell>
                <TableCell>
                  <Chip size="small" label={u.is_active ? 'Активен' : 'Отключён'} color={u.is_active ? 'success' : 'default'} />
                </TableCell>
                <TableCell align="right">
                  <Button size="small" onClick={() => setEditing(u)}>Изменить</Button>
                  <Button size="small" color="error" onClick={() => setToDelete(u)}>Удалить</Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {editing && (
        <UserDialog user={editing === 'new' ? null : editing} onClose={() => setEditing(null)} onSaved={handleSaved} />
      )}

      <ConfirmDialog
        open={Boolean(toDelete)}
        title="Удалить пользователя?"
        text={toDelete ? `Пользователь ${toDelete.login} будет удалён без возможности восстановления. История оплат сохранится.` : ''}
        onConfirm={handleDelete}
        onClose={() => setToDelete(null)}
      />

      <Snackbar open={Boolean(message)} autoHideDuration={5000} onClose={() => setMessage(null)}>
        {message ? <Alert severity={message.severity} onClose={() => setMessage(null)}>{message.text}</Alert> : <span />}
      </Snackbar>
    </>
  );
}
