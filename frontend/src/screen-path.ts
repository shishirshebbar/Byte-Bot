import { useLocation } from 'react-router-dom';

export function useScreenPath() {
  const { pathname } = useLocation();
  const workspace = pathname === '/workspace' || pathname.startsWith('/workspace/');
  return (path: string) => workspace ? (path === '/' ? '/workspace' : '/workspace' + path) : path;
}
