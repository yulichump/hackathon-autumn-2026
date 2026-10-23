import { useContext } from 'react';
import { AuthContext } from './authContextObject';

export const useAuth = () => useContext(AuthContext);
