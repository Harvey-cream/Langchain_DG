let redirectingToLogin = false;

/** Clear an invalid login and leave protected pages immediately. */
export function expireAuthSession(): void {
  if (typeof window === 'undefined') return;

  window.localStorage.removeItem('token');
  if (window.location.pathname === '/login' || redirectingToLogin) return;

  redirectingToLogin = true;
  window.location.replace('/login');
}

export function handleUnauthorizedStatus(status: number | undefined): boolean {
  if (status !== 401) return false;
  expireAuthSession();
  return true;
}
