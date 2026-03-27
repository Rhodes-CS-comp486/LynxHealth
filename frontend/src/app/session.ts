export type SessionRole = 'admin' | 'user';

interface StoredSessionShape {
  email?: unknown;
  mail?: unknown;
  role?: unknown;
  firstName?: unknown;
  first_name?: unknown;
  lastName?: unknown;
  last_name?: unknown;
}

export interface LynxSession {
  email: string;
  requestEmail: string;
  role: SessionRole;
  firstName: string;
  lastName: string;
}

const SESSION_STORAGE_KEY = 'lynxSession';
const ADMIN_EMAIL_SUFFIX = '@admin.edu';
const DEFAULT_ADMIN_EMAIL = 'admin@admin.edu';
const DEFAULT_USER_EMAIL = 'student@lynxhealth.local';

function normalizeEmail(value: unknown): string {
  return typeof value === 'string' ? value.trim().toLowerCase() : '';
}

function normalizeName(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function inferRole(role: unknown, email: string): SessionRole {
  if (typeof role === 'string' && role.trim().toLowerCase() === 'admin') {
    return 'admin';
  }

  return email.endsWith(ADMIN_EMAIL_SUFFIX) ? 'admin' : 'user';
}

function getRequestEmail(email: string, role: SessionRole): string {
  if (role === 'admin') {
    return email.endsWith(ADMIN_EMAIL_SUFFIX) ? email : DEFAULT_ADMIN_EMAIL;
  }

  return email && !email.endsWith(ADMIN_EMAIL_SUFFIX) ? email : DEFAULT_USER_EMAIL;
}

function normalizeSessionValue(value: StoredSessionShape | null | undefined): LynxSession {
  const email = normalizeEmail(value?.email ?? value?.mail);
  const role = inferRole(value?.role, email);
  const fallbackEmail = role === 'admin' ? DEFAULT_ADMIN_EMAIL : DEFAULT_USER_EMAIL;
  const normalizedEmail = email || fallbackEmail;

  return {
    email: normalizedEmail,
    requestEmail: getRequestEmail(normalizedEmail, role),
    role,
    firstName: normalizeName(value?.firstName ?? value?.first_name),
    lastName: normalizeName(value?.lastName ?? value?.last_name),
  };
}

function getStoredSessionValue(): string | null {
  if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
    return null;
  }

  return localStorage.getItem(SESSION_STORAGE_KEY);
}

export function getClientSession(): LynxSession {
  const storedValue = getStoredSessionValue();
  if (!storedValue) {
    return normalizeSessionValue(null);
  }

  try {
    return normalizeSessionValue(JSON.parse(storedValue) as StoredSessionShape);
  } catch {
    return normalizeSessionValue(null);
  }
}

export function saveClientSession(rawSession: string): LynxSession | null {
  if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
    return null;
  }

  try {
    const normalized = normalizeSessionValue(JSON.parse(rawSession) as StoredSessionShape);
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(normalized));
    return normalized;
  } catch {
    return null;
  }
}
