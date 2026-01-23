<script setup lang="ts">
import { computed } from 'vue';
import type { Document, Location } from '@/types';
import {
  MapPin,
  Train,
  Footprints,
  Heart,
  Trash2,
  HousePlus,
} from 'lucide-vue-next';

interface Props {
  doc: Document;
  locations: Location[];
  getStatus: (doc: Document) => { priority: number; status: string; statusClass: string };
}

const props = defineProps<Props>();

const emit = defineEmits<{
  open: [doc: Document];
  toggleFavorite: [doc: Document];
  delete: [doc: Document];
}>();

const locationTags = computed(() => {
  const travelTimes = props.doc.travel_times || [];
  const locationMap = new Map();
  const locationShowMap = new Map(props.locations.map(l => [l.id, l.show_in_tag === 1]));

  travelTimes.forEach((sd) => {
    if (locationShowMap.get(sd.location_id)) {
      if (!locationMap.has(sd.location_name) || sd.duration < locationMap.get(sd.location_name).duration) {
        locationMap.set(sd.location_name, sd);
      }
    }
  });

  return Array.from(locationMap.values());
});

const isLoading = computed(() => {
  return props.doc.llm_status === 'pending' || props.doc.llm_status === 'processing';
});
</script>

<template>
  <div
    class="group bg-white rounded-2xl shadow-sm relative overflow-hidden border border-gray-100 h-full flex flex-col"
    @mouseenter="$el.style.setProperty('--scale', '1.02')"
    @mouseleave="$el.style.setProperty('--scale', '1')"
    :style="`
      transform: scale(var(--scale, 1));
      transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
    `"
  >
    <div
      class="absolute inset-0 rounded-2xl pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-500"
      style="background: linear-gradient(135deg, rgba(59,130,246,0.05) 0%, transparent 50%);"
    ></div>
    <div
      class="absolute inset-0 rounded-2xl pointer-events-none overflow-hidden opacity-0 group-hover:opacity-100 transition-opacity duration-700"
    >
      <div class="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent -translate-x-full group-hover:animate-shimmer"></div>
      <div class="absolute bottom-0 left-0 right-0 h-1/3 bg-gradient-to-t from-blue-400/5 to-transparent transform translate-y-full group-hover:translate-y-0 transition-transform duration-500"></div>
    </div>
    <div class="p-5 pb-3 flex flex-col h-full relative z-10">
      <div class="flex items-start justify-between gap-2 mb-3">
        <h3 class="font-semibold text-gray-900 leading-snug flex-1 pr-8 transition-colors duration-300 group-hover:text-blue-600 cursor-pointer" @click="$emit('open', doc)">
          {{ doc.properties?.property_name || doc.display_filename || doc.original_filename || doc.filename }}
        </h3>
        <div class="flex gap-1.5 flex-shrink-0">
          <button
            class="action-btn w-8 h-8 rounded-full flex items-center justify-center transition-all duration-300 group-hover:scale-110"
            :class="[
              doc.favorite === 1
                ? 'bg-rose-500 text-white shadow-md shadow-rose-300'
                : 'bg-gray-100 text-gray-400 active:bg-rose-500 active:text-white md:hover:bg-rose-500 md:hover:text-white',
              doc.favorite === 1 ? 'animate-heartbeat' : ''
            ]"
            @click.stop="$emit('toggleFavorite', doc)"
          >
            <Heart class="w-4 h-4" :class="{ fill: doc.favorite === 1 }" />
          </button>
          <button
            class="action-btn w-8 h-8 rounded-full flex items-center justify-center bg-gray-100 text-gray-400 hover:bg-red-500 hover:text-white transition-all duration-300 group-hover:scale-110"
            @click.stop="$emit('delete', doc)"
          >
            <Trash2 class="w-4 h-4" />
          </button>
        </div>
      </div>

      <div class="flex items-end justify-between mb-3">
        <div>
          <span v-if="doc.properties?.price" class="text-3xl font-bold text-gray-900 transition-transform duration-300 group-hover:scale-110 inline-block">{{ doc.properties.price }}</span>
          <span v-else-if="isLoading" class="animate-pulse bg-gray-200 rounded h-9 w-24 inline-block align-middle"></span>
          <span v-else class="text-3xl font-bold text-gray-400">--</span>
          <span class="text-gray-500 ml-1 text-sm">万円</span>
        </div>
        <div class="flex items-center gap-1.5">
          <template v-if="doc.properties?.exclusive_area || doc.properties?.balcony_area">
            <span v-if="doc.properties?.exclusive_area" class="px-2 py-0.5 sm:px-2.5 sm:py-1 bg-blue-50 text-blue-700 rounded-lg text-xs sm:text-sm font-medium transition-all duration-300 group-hover:scale-105 group-hover:bg-blue-100">{{ doc.properties.exclusive_area }}m²</span>
            <span v-if="doc.properties?.balcony_area" class="inline-flex items-center px-2 py-0.5 sm:px-2.5 sm:py-1 bg-teal-50 text-teal-700 rounded-lg text-xs sm:text-sm font-medium gap-1 transition-all duration-300 group-hover:scale-105 group-hover:bg-teal-100">
              <HousePlus class="w-3 h-3 sm:w-3.5 sm:h-3.5" />
              {{ doc.properties.balcony_area }}m²
            </span>
          </template>
          <template v-else-if="isLoading">
            <span class="animate-pulse bg-gray-200 rounded-lg h-6 w-14"></span>
            <span class="animate-pulse bg-gray-200 rounded-lg h-6 w-16"></span>
          </template>
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-2 mb-3">
        <template v-if="doc.properties?.property_type || doc.properties?.room_layout || doc.properties?.land_rights || doc.properties?.build_year">
          <span v-if="doc.properties?.property_type" class="px-2 py-0.5 bg-indigo-50 text-indigo-600 rounded text-xs font-medium transition-all duration-300 group-hover:scale-105 group-hover:bg-indigo-100">{{ doc.properties.property_type }}</span>
          <span v-if="doc.properties?.room_layout" class="px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs font-medium transition-all duration-300 group-hover:scale-105 group-hover:bg-gray-200">{{ doc.properties.room_layout }}</span>
          <span v-if="doc.properties?.land_rights" class="px-2 py-0.5 bg-orange-50 text-orange-600 rounded text-xs font-medium transition-all duration-300 group-hover:scale-105 group-hover:bg-orange-100">{{ doc.properties.land_rights }}</span>
          <span v-if="doc.properties?.build_year" class="px-2 py-0.5 bg-amber-50 text-amber-600 rounded text-xs font-medium transition-all duration-300 group-hover:scale-105 group-hover:bg-amber-100">{{ new Date().getFullYear() - doc.properties.build_year }}年</span>
          <span v-if="doc.properties?.pet_policy?.includes('可')" class="px-2 py-0.5 bg-pink-50 text-pink-600 rounded text-xs font-medium transition-all duration-300 group-hover:scale-105 group-hover:bg-pink-100">可养宠</span>
          <span v-if="doc.properties?.corner_room" class="px-2 py-0.5 bg-violet-50 text-violet-600 rounded text-xs font-medium transition-all duration-300 group-hover:scale-105 group-hover:bg-violet-100">角部屋</span>
        </template>
        <template v-else-if="isLoading">
          <span class="animate-pulse bg-gray-200 rounded h-5 w-12"></span>
          <span class="animate-pulse bg-gray-200 rounded h-5 w-10"></span>
          <span class="animate-pulse bg-gray-200 rounded h-5 w-14"></span>
          <span class="animate-pulse bg-gray-200 rounded h-5 w-8"></span>
        </template>
      </div>

      <div class="space-y-2 mb-3">
        <div class="flex items-start gap-2 text-sm">
          <MapPin class="w-4 h-4 text-gray-400 flex-shrink-0 mt-0.5" />
          <span v-if="doc.properties?.address" class="text-gray-600 leading-relaxed">{{ doc.properties.address }}</span>
          <span v-else-if="isLoading" class="animate-pulse bg-gray-200 rounded h-4 w-48"></span>
          <span v-else class="text-gray-400">--</span>
        </div>
            <div v-if="doc.properties?.stations?.length || locationTags.length" class="flex items-start gap-2 text-sm">
            <Train class="w-4 h-4 text-emerald-500 flex-shrink-0 mt-0.5" />
            <div class="flex flex-wrap gap-1.5">
               <span
                 v-for="s in doc.properties.stations"
                 :key="s.name"
                 class="inline-flex items-center px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded text-xs font-medium transition-all duration-300 group-hover:scale-105 group-hover:bg-emerald-100"
               >
                 {{ s.name }}
                 <Footprints class="w-3 h-3 mx-0.5 text-emerald-500" />
                 {{ s.walking_minutes }}分
               </span>
            <span
              v-for="lt in locationTags"
              :key="lt.location_name"
              class="inline-flex items-center px-2 py-0.5 bg-purple-50 rounded text-xs text-purple-600 font-medium transition-all duration-300 group-hover:scale-105 group-hover:bg-purple-100"
            >
              {{ lt.location_name }} {{ lt.duration }}分
            </span>
          </div>
        </div>
        <div v-else-if="isLoading" class="flex items-start gap-2 text-sm">
          <Train class="w-4 h-4 text-gray-300 flex-shrink-0 mt-0.5" />
          <div class="flex flex-wrap gap-1.5">
            <span class="animate-pulse bg-gray-200 rounded h-5 w-20"></span>
            <span class="animate-pulse bg-gray-200 rounded h-5 w-16"></span>
          </div>
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-2 mt-auto pt-3 border-t border-gray-100 -mx-5 px-5">
        <div class="flex items-center gap-2">
          <span class="px-2 py-0.5 rounded-full text-xs font-medium text-white transition-all duration-300 group-hover:scale-105" :class="getStatus(doc).statusClass">
            {{ getStatus(doc).status }}
          </span>
          <span v-if="doc.extracted_model" class="px-2 py-0.5 bg-gray-100 text-gray-500 rounded text-xs transition-all duration-300 group-hover:scale-105 group-hover:bg-gray-200" :title="doc.extracted_model">
            {{ doc.extracted_model.split('/').pop()?.split(':')[0] }}
          </span>
        </div>
        <span class="text-xs text-gray-400 ml-auto transition-opacity duration-300 group-hover:text-gray-600">{{ new Date(doc.upload_time).toLocaleDateString('zh-CN') }}</span>
      </div>
    </div>
  </div>
</template>
