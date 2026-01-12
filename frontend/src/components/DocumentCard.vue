<script setup lang="ts">
import type { Document } from '@/types';
import {
  MapPin,
  Train,
  Footprints,
  Heart,
  Trash2,
} from 'lucide-vue-next';

interface Props {
  doc: Document;
  getStatus: (doc: Document) => { priority: number; status: string; statusClass: string };
}

const props = defineProps<Props>();

const emit = defineEmits<{
  open: [doc: Document];
  toggleFavorite: [doc: Document];
  delete: [doc: Document];
}>();

const stationDurations = props.doc.station_durations || [];
const locationMap = new Map();

stationDurations.forEach((sd) => {
  if (sd.show_in_tag === 1) {
    if (!locationMap.has(sd.location_name) || sd.duration < locationMap.get(sd.location_name).duration) {
      locationMap.set(sd.location_name, sd);
    }
  }
});

const locationTags = Array.from(locationMap.values());
</script>

<template>
  <div
    class="group bg-white rounded-2xl shadow-sm hover:shadow-xl transition-all duration-300 cursor-pointer relative overflow-hidden border border-gray-100 hover:border-blue-300 h-full flex flex-col"
    :class="{ 'ring-2 ring-rose-400': doc.favorite === 1 }"
    @click="$emit('open', doc)"
  >
    <div class="p-5 pb-3 flex flex-col h-full relative">
      <div class="flex items-start justify-between gap-2 mb-3">
        <h3 class="font-semibold text-gray-900 leading-snug flex-1 pr-8">
          {{ doc.properties?.property_name || doc.filename }}
        </h3>
        <div class="flex gap-1.5 flex-shrink-0">
          <button
            class="action-btn w-8 h-8 rounded-full flex items-center justify-center transition-all"
            :class="
              doc.favorite === 1
                ? 'bg-rose-500 text-white shadow-md shadow-rose-300'
                : 'bg-gray-100 text-gray-400 hover:bg-rose-500 hover:text-white'
            "
            @click.stop="$emit('toggleFavorite', doc)"
          >
            <Heart class="w-4 h-4" :class="{ fill: doc.favorite === 1 }" />
          </button>
          <button
            class="action-btn w-8 h-8 rounded-full flex items-center justify-center bg-gray-100 text-gray-400 hover:bg-red-500 hover:text-white transition-all"
            @click.stop="$emit('delete', doc)"
          >
            <Trash2 class="w-4 h-4" />
          </button>
        </div>
      </div>

      <div class="flex items-end justify-between mb-3">
        <div>
          <span v-if="doc.properties?.price" class="text-3xl font-bold text-gray-900">{{ doc.properties.price }}</span>
          <span v-else class="animate-pulse bg-gray-200 rounded h-9 w-24 inline-block"></span>
          <span class="text-gray-500 ml-1">万円</span>
        </div>
        <div class="flex items-center gap-1.5">
          <span v-if="doc.properties?.exclusive_area" class="px-2.5 py-1 bg-blue-50 text-blue-700 rounded-lg text-sm font-medium">{{ doc.properties.exclusive_area }}m²</span>
          <span v-if="doc.properties?.balcony_area" class="px-2.5 py-1 bg-teal-50 text-teal-700 rounded-lg text-sm font-medium">阳台{{ doc.properties.balcony_area }}m²</span>
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-2 mb-3">
        <span v-if="doc.properties?.property_type" class="px-2 py-0.5 bg-indigo-50 text-indigo-600 rounded text-xs font-medium">{{ doc.properties.property_type }}</span>
        <span v-if="doc.properties?.room_layout" class="px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs font-medium">{{ doc.properties.room_layout }}</span>
        <span v-if="doc.properties?.land_rights" class="px-2 py-0.5 bg-orange-50 text-orange-600 rounded text-xs font-medium">{{ doc.properties.land_rights }}</span>
        <span v-if="doc.properties?.build_year" class="px-2 py-0.5 bg-amber-50 text-amber-600 rounded text-xs font-medium">{{ new Date().getFullYear() - doc.properties.build_year }}年</span>
        <span v-if="doc.properties?.pet_policy?.includes('可')" class="px-2 py-0.5 bg-pink-50 text-pink-600 rounded text-xs font-medium">可养宠</span>
        <span v-if="doc.properties?.corner_room" class="px-2 py-0.5 bg-violet-50 text-violet-600 rounded text-xs font-medium">角部屋</span>
      </div>

      <div class="space-y-2 mb-3">
        <div class="flex items-start gap-2 text-sm">
          <MapPin class="w-4 h-4 text-gray-400 flex-shrink-0 mt-0.5" />
          <span class="text-gray-600 leading-relaxed">{{ doc.properties?.address || '地址加载中...' }}</span>
        </div>
        <div v-if="doc.properties?.stations?.length || locationTags.length" class="flex items-start gap-2 text-sm">
          <Train class="w-4 h-4 text-emerald-500 flex-shrink-0 mt-0.5" />
          <div class="flex flex-wrap gap-1.5">
            <span
              v-for="s in doc.properties.stations"
              :key="s.name"
              class="inline-flex items-center px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded text-xs font-medium"
            >
              {{ s.name }}
              <Footprints class="w-3 h-3 mx-0.5 text-emerald-500" />
              {{ s.walking_minutes }}分
            </span>
            <span
              v-for="lt in locationTags"
              :key="lt.location_name"
              class="inline-flex items-center px-2 py-0.5 bg-purple-50 rounded text-xs text-purple-600 font-medium"
            >
              {{ lt.location_name }} {{ lt.duration }}分
            </span>
          </div>
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-2 mt-auto pt-3 border-t border-gray-100 -mx-5 px-5">
        <div class="flex items-center gap-2">
          <span class="px-2 py-0.5 rounded-full text-xs font-medium text-white" :class="getStatus(doc).statusClass">
            {{ getStatus(doc).status }}
          </span>
          <span v-if="doc.extracted_model" class="px-2 py-0.5 bg-gray-100 text-gray-500 rounded text-xs" :title="doc.extracted_model">
            {{ doc.extracted_model.split('/').pop()?.split(':')[0] }}
          </span>
        </div>
        <span class="text-xs text-gray-400 ml-auto">{{ new Date(doc.upload_time).toLocaleDateString('zh-CN') }}</span>
      </div>
    </div>
  </div>
</template>
