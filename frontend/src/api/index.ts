import type { Document, Location } from '@/types';

const API_BASE = '/api';

async function fetchWithRetry(
  url: string,
  options: RequestInit = {},
  timeout = 10000,
  externalSignal?: AbortSignal,
  maxRetries = 3
): Promise<Response> {
  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    if (externalSignal?.aborted) {
      throw new DOMException('Aborted', 'AbortError');
    }

    try {
      return await fetchWithTimeout(url, options, timeout, externalSignal);
    } catch (error) {
      lastError = error as Error;
      console.warn(`Request failed (attempt ${attempt + 1}/${maxRetries + 1}):`, error);

      if (attempt === maxRetries) {
        break;
      }

      if (externalSignal?.aborted) {
        throw lastError;
      }

      await new Promise(resolve => setTimeout(resolve, 1000 * (attempt + 1)));
    }
  }

  throw lastError;
}

async function fetchWithTimeout(url: string, options: RequestInit = {}, timeout = 10000, externalSignal?: AbortSignal): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  let signal = controller.signal;
  if (externalSignal) {
    const combinedController = new AbortController();
    const onAbort = () => {
      controller.abort();
      combinedController.abort();
    };
    externalSignal.addEventListener('abort', onAbort);
    try {
      const response = await fetch(url, {
        ...options,
        signal: combinedController.signal,
      });
      clearTimeout(timeoutId);
      externalSignal.removeEventListener('abort', onAbort);
      return response;
    } catch (error) {
      clearTimeout(timeoutId);
      externalSignal.removeEventListener('abort', onAbort);
      throw error;
    }
  }

  try {
    const response = await fetch(url, {
      ...options,
      signal,
    });
    clearTimeout(timeoutId);
    return response;
  } catch (error) {
    clearTimeout(timeoutId);
    throw error;
  }
}

export async function fetchDocuments(signal?: AbortSignal): Promise<{ documents: Document[] }> {
  const res = await fetchWithRetry(`${API_BASE}/documents`, {}, 10000, signal);
  return res.json();
}

export async function fetchDocument(docId: number, signal?: AbortSignal): Promise<Document> {
  const res = await fetchWithRetry(`${API_BASE}/documents/${docId}`, {}, 10000, signal);
  return res.json();
}

export async function fetchPreview(docId: number): Promise<Blob> {
  const res = await fetchWithRetry(`${API_BASE}/preview/${docId}`, {}, 60000);
  return res.blob();
}

export async function fetchThumbnail(docId: number): Promise<string> {
  const res = await fetchWithRetry(`${API_BASE}/preview/${docId}?thumbnail=true`);
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export async function uploadDocument(file: File): Promise<{ id: number; filename: string; duplicate?: boolean; duplicate_type?: string }> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetchWithRetry(`${API_BASE}/upload`, {
    method: 'POST',
    body: formData,
  }, 60000);
  return res.json();
}

export async function updateDocument(docId: number, data: Record<string, unknown>): Promise<void> {
  await fetchWithRetry(`${API_BASE}/documents/${docId}/update`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

export async function deleteDocument(docId: number): Promise<void> {
  await fetchWithRetry(`${API_BASE}/documents/${docId}`, { method: 'DELETE' });
}

export async function toggleFavorite(docId: number): Promise<void> {
  await fetchWithRetry(`${API_BASE}/documents/${docId}/favorite`, { method: 'POST' });
}

export async function retryOCR(docId: number): Promise<void> {
  await fetchWithRetry(`${API_BASE}/documents/${docId}/retry_ocr`, { method: 'POST' });
}

export async function retryLLM(docId: number): Promise<void> {
  await fetchWithRetry(`${API_BASE}/documents/${docId}/retry_llm`, { method: 'POST' });
}

export async function cleanupDocuments(): Promise<{ success: boolean; deleted_count: number }> {
  const res = await fetchWithRetry(`${API_BASE}/documents/cleanup`, { method: 'POST' });
  return res.json();
}

export async function fetchLocations(signal?: AbortSignal): Promise<{ locations: Location[] }> {
  const res = await fetchWithRetry(`${API_BASE}/locations`, {}, 10000, signal);
  return res.json();
}

export async function addLocation(name: string): Promise<{ success: boolean; location: Location }> {
  const res = await fetchWithRetry(`${API_BASE}/locations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  return res.json();
}

export async function deleteLocation(id: number): Promise<void> {
  await fetchWithRetry(`${API_BASE}/locations/${id}`, { method: 'DELETE' });
}

export async function updateLocationDisplay(id: number, showInTag: boolean): Promise<void> {
  await fetchWithRetry(`${API_BASE}/locations/${id}/display`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ show_in_tag: showInTag ? 1 : 0 }),
  });
}

export async function reorderLocations(ids: number[]): Promise<void> {
  await fetchWithRetry(`${API_BASE}/locations/reorder`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ location_ids: ids }),
  });
}

export async function fetchModels(): Promise<{ models: string[] }> {
  const res = await fetchWithRetry(`${API_BASE}/models?t=${Date.now()}`);
  return res.json();
}

export async function addModel(name: string): Promise<{ success: boolean; error?: string }> {
  const res = await fetchWithRetry(`${API_BASE}/models`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  return res.json();
}

export async function deleteModel(name: string): Promise<void> {
  await fetchWithRetry(`${API_BASE}/models/delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
}

export async function reorderModels(models: string[]): Promise<void> {
  await fetchWithRetry(`${API_BASE}/models/reorder`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ models }),
  });
}

export interface StationDurationData {
  station_name: string;
  location_name: string;
  duration: number;
}

export async function fetchTravelTimes(signal?: AbortSignal): Promise<{ travel_times: StationDurationData[] }> {
  const res = await fetchWithRetry(`${API_BASE}/travel-times?t=${Date.now()}`, {}, 30000, signal);
  return res.json();
}

export async function saveTravelTimes(data: Record<string, Record<string, number>>, locations: { id: number; name: string }[]): Promise<void> {
  const locationMap = new Map(locations.map((loc) => [loc.name, loc.id]));
  const travelTimes = Object.entries(data).flatMap(([station_name, locs]) =>
    Object.entries(locs).map(([location_name, duration]) => ({
      station_name,
      location_id: locationMap.get(location_name),
      duration,
    })).filter((item) => item.location_id !== undefined)
  );
  await fetchWithRetry(`${API_BASE}/travel-times/batch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ travel_times: travelTimes }),
  });
}
