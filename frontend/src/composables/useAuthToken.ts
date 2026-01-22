import { ref, onMounted } from 'vue';

const LOCALSTORAGE_KEY = 'housing_ocr_token';

export const accessToken = ref<string | null>(null);

export function getStoredToken(): string | null {
  try {
    return localStorage.getItem(LOCALSTORAGE_KEY);
  } catch {
    return null;
  }
}

export function storeToken(token: string): void {
  try {
    localStorage.setItem(LOCALSTORAGE_KEY, token);
  } catch (e) {
    console.error('Failed to store token:', e);
  }
}

export function clearStoredToken(): void {
  try {
    localStorage.removeItem(LOCALSTORAGE_KEY);
  } catch (e) {
    console.error('Failed to clear token:', e);
  }
}

export function getAuthToken(): string | null {
  // Priority: URL token > localStorage token
  const urlToken = accessToken.value;
  if (urlToken) {
    return urlToken;
  }
  return getStoredToken();
}

export function useAuthToken() {
  function extractTokenFromURL(): string | null {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('token');
  }

  function updateUrlWithToken(token: string) {
    const url = new URL(window.location.href);
    url.searchParams.set('token', token);
    window.history.replaceState({}, '', url.toString());
  }

  onMounted(() => {
    const urlToken = extractTokenFromURL();
    
    if (urlToken) {
      // URL has token: use it and store in localStorage
      accessToken.value = urlToken;
      storeToken(urlToken);
      updateUrlWithToken(urlToken);
      console.log('[AUTH] Token from URL stored:', urlToken.slice(0, 8) + '...');
    } else {
      // No URL token: try localStorage
      const stored = getStoredToken();
      if (stored) {
        accessToken.value = stored;
        console.log('[AUTH] Token from localStorage:', stored.slice(0, 8) + '...');
      } else {
        console.warn('[AUTH] No token found. Add ?token=YOUR_TOKEN to URL.');
      }
    }
  });

  return {
    accessToken,
    getAuthToken,
  };
}
