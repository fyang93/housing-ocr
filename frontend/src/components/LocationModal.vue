<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue';
import Sortable from 'sortablejs';
import type { Location } from '@/types';
import { fetchLocations, addLocation, deleteLocation, updateLocationDisplay, reorderLocations } from '@/api';
import {
  MapPin,
  GripVertical,
  Trash2,
  X,
  Loader2,
} from 'lucide-vue-next';

interface Props {
  isOpen: boolean;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  close: [];
  locationsUpdated: [];
}>();

const locations = ref<Location[]>([]);
const newLocationName = ref('');
let sortableInstance: Sortable | null = null;
const listContainer = ref<HTMLElement | null>(null);
const loading = ref(false);

const loadLocations = async () => {
  loading.value = true;
  try {
    const data = await fetchLocations();
    locations.value = data.locations;
  } finally {
    loading.value = false;
  }
};

const initSortable = () => {
  if (listContainer.value && sortableInstance) {
    sortableInstance.destroy();
  }
  if (listContainer.value) {
    sortableInstance = new Sortable(listContainer.value, {
      animation: 150,
      ghostClass: 'opacity-50',
      handle: '[data-handle]',
      delay: 100,
      delayOnTouchOnly: true,
      onEnd: async (evt) => {
        const newOrder: number[] = [];
        listContainer.value?.querySelectorAll('[data-location-id]').forEach((item) => {
          const id = parseInt(item.getAttribute('data-location-id') || '0');
          newOrder.push(id);
        });
        skipNextInit = true;
        const reorderedLocations = newOrder.map(id => locations.value.find(l => l.id === id)!).filter(Boolean);
        locations.value = reorderedLocations;
        try {
          await reorderLocations(newOrder);
          emit('updated');
        } catch (error) {
          console.error('保存位置顺序失败:', error);
          skipNextInit = true;
          await loadLocations();
        }
      },
    });
  }
};

const addNewLocation = async () => {
  if (!newLocationName.value.trim()) return;

  const tempId = Date.now();
  const newLoc: Location = {
    id: tempId,
    name: newLocationName.value.trim(),
    display_order: locations.value.length + 1,
    show_in_tag: 0,
  };

  locations.value.push(newLoc);
  const nameToAdd = newLocationName.value.trim();
  newLocationName.value = '';

  try {
    const result = await addLocation(nameToAdd);
    const index = locations.value.findIndex(l => l.id === tempId);
    if (index !== -1) {
      locations.value[index] = result.location;
    }
    emit('updated');
  } catch (error) {
    locations.value = locations.value.filter(l => l.id !== tempId);
    console.error('添加位置失败:', error);
  }
};

const removeLocation = async (id: number) => {
  if (!confirm('确定要删除这个位置吗？这将同时删除相关的车站时长数据。')) return;

  const loc = locations.value.find(l => l.id === id);
  locations.value = locations.value.filter(l => l.id !== id);

  try {
    await deleteLocation(id);
    emit('updated');
  } catch (error) {
    if (loc) locations.value.push(loc);
    console.error('删除位置失败:', error);
  }
};

const toggleDisplay = async (id: number, current: number) => {
  const loc = locations.value.find(l => l.id === id);
  if (!loc) return;
  const oldValue = loc.show_in_tag;
  loc.show_in_tag = current === 0 ? 1 : 0;
  try {
    await updateLocationDisplay(id, current === 0);
    emit('locationsUpdated');
  } catch (error) {
    loc.show_in_tag = oldValue;
    console.error('更新显示状态失败:', error);
  }
};

watch(
  () => props.isOpen,
  async (val) => {
    if (val) {
      await loadLocations();
    }
  }
);

let skipNextInit = false;

watch(
  () => locations.value,
  async () => {
    if (skipNextInit) {
      skipNextInit = false;
      return;
    }
    await nextTick();
    setTimeout(() => initSortable(), 50);
  }
);
</script>

<template>
  <Teleport to="body">
    <div v-if="isOpen" class="fixed inset-0 modal-overlay z-50 overflow-y-auto" @click.self="$emit('close')">
      <div class="min-h-screen px-4 py-8 flex items-center justify-center">
        <div class="bg-white rounded-2xl shadow-2xl max-w-2xl w-full border border-gray-100">
          <div class="flex justify-between items-center px-6 py-4 border-b border-gray-100">
            <h2 class="text-xl font-bold text-gray-900">位置管理</h2>
            <button @click="$emit('close')" class="w-8 h-8 rounded-lg hover:bg-gray-100 transition flex items-center justify-center text-gray-400 hover:text-gray-600">
              <X class="w-5 h-5" />
            </button>
          </div>
          <div class="p-6">
            <div class="mb-5">
              <label class="block text-sm font-medium text-gray-700 mb-2">添加新位置</label>
              <div class="flex gap-2">
                <input
                  v-model="newLocationName"
                  type="text"
                  placeholder="例如: 渋谷"
                  class="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all bg-white shadow-sm"
                  @keydown.enter="addNewLocation"
                />
                <button @click="addNewLocation" class="px-5 py-2.5 rounded-xl bg-blue-500 hover:bg-blue-600 text-white font-medium shadow-md shadow-blue-300 transition-all">
                  添加
                </button>
              </div>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">
                位置列表
                <span class="text-xs text-gray-400 font-normal">(可拖拽排序，勾选显示在卡片tag)</span>
              </label>
              <div v-if="loading" class="flex justify-center py-12">
                <Loader2 class="w-8 h-8 animate-spin text-gray-400" />
              </div>
              <div v-else-if="locations.length === 0" class="text-center py-12 text-gray-500">
                <MapPin class="w-12 h-12 mx-auto mb-3 text-gray-300" />
                <p>暂无位置</p>
              </div>
              <div ref="listContainer" v-else class="space-y-2 max-h-64 overflow-y-auto pr-1">
                <div
                  v-for="loc in locations"
                  :key="loc.id"
                  :data-location-id="loc.id"
                  class="flex justify-between items-center p-3 bg-gradient-to-r from-gray-50 to-gray-100 rounded-xl border border-gray-200 hover:border-blue-300 transition-all group cursor-move"
                  style="user-select: none;"
                >
                  <div class="flex items-center gap-2">
                    <span data-handle class="cursor-move text-gray-400" style="user-select: none;">
                      <GripVertical class="w-4 h-4" />
                    </span>
                    <div class="w-8 h-8 rounded-lg bg-indigo-100 flex items-center justify-center">
                      <MapPin class="w-4 h-4 text-indigo-600" />
                    </div>
                    <span class="text-gray-700 font-medium text-sm">{{ loc.name }}</span>
                  </div>
                  <div class="flex items-center gap-2">
                    <label class="inline-flex items-center px-3 py-1 rounded-lg border border-gray-200 cursor-pointer hover:bg-gray-50 transition-all" :class="{ 'bg-indigo-50 border-indigo-300': loc.show_in_tag === 1 }">
                      <input
                        type="checkbox"
                        class="hidden"
                        :checked="loc.show_in_tag === 1"
                        @change="toggleDisplay(loc.id, loc.show_in_tag)"
                      />
                      <span class="text-xs text-gray-600" :class="{ 'text-indigo-700': loc.show_in_tag === 1 }">显示tag</span>
                    </label>
                    <button @click="removeLocation(loc.id)" class="text-red-500 hover:text-red-700 hover:bg-red-50 p-2 rounded-lg transition-all group-hover:scale-105">
                      <Trash2 class="w-5 h-5" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

