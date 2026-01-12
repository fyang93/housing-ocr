import { ref, onMounted } from 'vue';
import type { Location } from '@/types';
import { fetchLocations } from '@/api';

export function useLocations() {
  const locations = ref<Location[]>([]);
  const loading = ref(true);
  const error = ref<string | null>(null);

  const loadLocations = async () => {
    try {
      loading.value = true;
      const data = await fetchLocations();
      locations.value = data.locations;
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载失败';
    } finally {
      loading.value = false;
    }
  };

  return {
    locations,
    loading,
    error,
    loadLocations,
  };
}
