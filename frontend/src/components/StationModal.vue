<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import type { Location, Document } from '@/types';
import { fetchTravelTimes, saveTravelTimes } from '@/api';
import {
  Search,
  Train,
  RefreshCw,
  Save,
  X,
  Loader2,
} from 'lucide-vue-next';

interface Props {
  isOpen: boolean;
  documents: Document[];
  locations: Location[];
}

const props = defineProps<Props>();

const emit = defineEmits<{
  close: [];
}>();

const searchQuery = ref('');
const durations = ref<Record<string, Record<string, number>>>({});
const saving = ref(false);
const loading = ref(false);
const cachedStationNames = ref<string[]>([]);
let abortController: AbortController | null = null;

const extractStationNames = (): string[] => {
  const names = new Set<string>();
  props.documents.forEach((doc) => {
    const stations = doc.properties?.stations;
    if (stations && Array.isArray(stations)) {
      stations.forEach((s) => {
        if (s.name && s.name.trim()) {
          names.add(s.name.trim());
        }
      });
    }
  });
  return Array.from(names).sort();
};

const stationNames = computed(() => {
  return cachedStationNames.value;
});

const filteredStations = computed(() => {
  if (!searchQuery.value) return stationNames.value;
  return stationNames.value.filter((name) => name.toLowerCase().includes(searchQuery.value.toLowerCase()));
});

const getDuration = (station: string, locName: string): string => {
  const stationData = durations.value[station];
  if (!stationData) return '';
  return stationData[locName] !== undefined ? String(stationData[locName]) : '';
};

const setDuration = (station: string, locName: string, value: string) => {
  if (!durations.value[station]) {
    durations.value[station] = {};
  }
  durations.value[station][locName] = value ? parseInt(value) : null;
};

const hasData = computed(() => stationNames.value.length > 0 && props.locations.length > 0);

const loadData = async () => {
  if (loading.value) {
    console.log('Already loading, skipping');
    return;
  }

  if (abortController) {
    abortController.abort();
    console.log('Aborted previous request');
  }

  abortController = new AbortController();
  loading.value = true;

  try {
    console.log('Loading data...');
    cachedStationNames.value = extractStationNames();
    console.log('Station names from docs:', stationNames.value);

    const travelTimesData = await fetchTravelTimes(abortController.signal);
    console.log('Travel times loaded:', travelTimesData.travel_times.length);
    durations.value = {};
    travelTimesData.travel_times.forEach((item) => {
      if (!durations.value[item.station_name]) {
        durations.value[item.station_name] = {};
      }
      durations.value[item.station_name][item.location_name] = item.duration;
    });
    console.log('Durations map:', durations.value);
  } catch (error) {
    console.error('Load error:', error);
    if (error instanceof Error && error.name === 'AbortError') {
      console.log('Request was aborted');
    } else {
      alert('加载数据失败，请重试');
    }
  } finally {
    loading.value = false;
    abortController = null;
  }
};

const save = async () => {
  saving.value = true;
  try {
    await saveTravelTimes(durations.value, props.locations);
    emit('close');
  } catch (error) {
    console.error('保存失败:', error);
    alert('保存失败');
  } finally {
    saving.value = false;
  }
};

watch(
  () => props.isOpen,
  (val) => {
    if (val) {
      loadData();
    }
  }
);
</script>

<template>
  <Teleport to="body">
    <div v-if="isOpen" class="fixed inset-0 modal-overlay z-50 overflow-y-auto" @click.self="$emit('close')">
      <div class="min-h-screen px-4 py-8 flex items-center justify-center">
        <div class="bg-white rounded-2xl shadow-2xl max-w-6xl w-full border border-gray-100">
          <div class="flex justify-between items-center px-6 py-4 border-b border-gray-100">
            <h2 class="text-xl font-bold text-gray-900">车站时长管理</h2>
            <button @click="$emit('close')" class="w-8 h-8 rounded-lg hover:bg-gray-100 transition flex items-center justify-center text-gray-400 hover:text-gray-600">
              <X class="w-5 h-5" />
            </button>
          </div>
          <div class="p-6">
            <div class="mb-4">
              <div class="relative">
                <input
                  v-model="searchQuery"
                  type="text"
                  placeholder="搜索车站名称..."
                  class="w-full px-4 py-2.5 pl-10 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all bg-white shadow-sm"
                />
                <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
              </div>
            </div>

            <div v-if="loading" class="flex justify-center py-12">
              <Loader2 class="w-8 h-8 animate-spin text-gray-400" />
            </div>
            <div v-else-if="!hasData" class="text-center py-12 text-gray-500">
              <Train class="w-12 h-12 mx-auto mb-3 text-gray-300" />
              <p>暂无车站数据</p>
              <p class="text-sm mt-1">请先上传房产文档进行智能解析</p>
            </div>

            <div v-else class="overflow-hidden rounded-xl border border-gray-200">
              <div class="overflow-x-auto">
                <div class="overflow-y-auto max-h-[400px]">
                  <table class="w-full border-collapse table-fixed">
                    <thead class="sticky top-0 bg-gray-50 z-30">
                      <tr>
                        <th class="sticky left-0 bg-gray-50 z-40 px-4 py-3 text-left text-sm font-medium text-gray-700 border-b border-gray-200 min-w-[150px] break-words">
                           车站
                         </th>
                        <th
                          v-for="loc in props.locations"
                          :key="loc.id"
                          class="px-4 py-3 text-center text-sm font-medium text-gray-700 border-b border-gray-200 min-w-[120px]"
                        >
                          {{ loc.name }}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="station in filteredStations" :key="station">
                        <td class="sticky left-0 bg-white z-10 px-4 py-3 text-sm text-gray-700 border-b border-gray-200 font-medium break-words min-w-[150px]">
                           {{ station }}
                         </td>
                        <td v-for="loc in props.locations" :key="loc.id" class="px-2 py-3 border-b border-gray-200 text-center min-w-[100px] sm:min-w-[120px]">
                          <input
                            type="number"
                            min="0"
                            class="w-full max-w-[80px] sm:w-20 px-1.5 py-1.5 text-sm border border-gray-200 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 text-center"
                            :value="getDuration(station, loc.name)"
                            @input="(e) => setDuration(station, loc.name, (e.target as HTMLInputElement).value)"
                          />
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <div v-if="hasData" class="mt-6 flex justify-end gap-3">
              <button
                @click="loadData"
                class="px-5 py-2.5 rounded-xl bg-gray-100 hover:bg-gray-200 text-gray-700 font-medium transition-all flex items-center gap-2"
              >
                <RefreshCw class="w-4 h-4" />
                刷新
              </button>
              <button
                @click="save"
                :disabled="saving"
                class="px-6 py-2.5 rounded-xl bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white font-medium shadow-lg shadow-blue-300 transition-all flex items-center gap-2 disabled:opacity-50"
              >
                <Loader2 v-if="saving" class="animate-spin w-4 h-4" />
                <Save v-else class="w-4 h-4" />
                {{ saving ? '保存中...' : '保存所有时长' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
