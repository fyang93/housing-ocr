<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue';
import type { Document, PropertyDetails } from '@/types';
import { updateDocument, retryOCR as apiRetryOCR, retryLLM as apiRetryLLM } from '@/api';
import ImageViewer from '@/components/ImageViewer.vue';
import {
  X,
  Home,
  ChevronDown,
  RefreshCw,
  Sparkles,
  Check,
  Trash2,
  FileText,
} from 'lucide-vue-next';

interface Props {
  doc: Document | null;
  previewUrl: string | null;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  close: [];
  saved: [properties: PropertyDetails, docId: number];
  delete: [id: number];
  retryOCR: [id: number];
  retryLLM: [id: number];
}>();

const showOcrText = ref(false);
const saving = ref(false);
const showImageViewer = ref(false);
const retryLoading = ref(false);
const properties = ref<PropertyDetails>({});

let originalOverflow = '';

const lockScroll = () => {
  // 只在移动端禁用背景滚动，桌面端允许滚动
  if (window.innerWidth < 768) {
    originalOverflow = document.body.style.overflow || '';
    document.body.style.overflow = 'hidden';
  }
};

const unlockScroll = () => {
  // 只在移动端恢复背景滚动
  if (window.innerWidth < 768) {
    document.body.style.overflow = originalOverflow;
  }
};

watch(() => props.doc, (newDoc) => {
  if (newDoc) {
    lockScroll();
    if (newDoc.properties) {
      properties.value = JSON.parse(JSON.stringify(newDoc.properties));
      // 确保stations数组存在
      if (!properties.value.stations) {
        properties.value.stations = [];
      }
    } else {
      properties.value = { stations: [] };
    }
  } else {
    unlockScroll();
  }
}, { immediate: true });

onBeforeUnmount(() => {
  unlockScroll();
});



const toggleOcrText = () => {
  showOcrText.value = !showOcrText.value;
};

const saveProperties = async () => {
  if (!props.doc) return;

  saving.value = true;
  try {
    // 清理空的占位符车站
    const cleanedProperties = { ...properties.value };
    if (cleanedProperties.stations) {
      cleanedProperties.stations = cleanedProperties.stations.filter(
        station => station.name.trim() || station.line.trim() || station.walking_minutes
      );
    }

    await updateDocument(props.doc.id, cleanedProperties);
    emit('saved', cleanedProperties, props.doc.id);
    emit('close');
  } catch (error) {
    console.error('保存失败:', error);
    alert('保存失败: ' + (error as Error).message);
  } finally {
    saving.value = false;
  }
};

const onRetryOCR = () => {
  if (props.doc && !retryLoading.value) {
    retryLoading.value = true;
    emit('retryOCR', props.doc.id);
    emit('close');
  }
};

const onRetryLLM = () => {
  if (props.doc && !retryLoading.value) {
    retryLoading.value = true;
    emit('retryLLM', props.doc.id);
    emit('close');
  }
};

const onDelete = () => {
  if (props.doc && confirm('确定要删除这个文档吗?')) {
    emit('delete', props.doc.id);
    emit('close');
  }
};

const openImageViewer = () => {
  showImageViewer.value = true;
};

const ocrText = computed(() => props.doc?.ocr_text || '暂无OCR文本');

// 确保至少有3个车站编辑框
const editableStations = computed(() => {
  const stations = properties.value.stations || [];
  const minStations = 3;

  // 如果现有的车站少于3个，添加空的占位符
  while (stations.length < minStations) {
    stations.push({ name: '', line: '', walking_minutes: '' });
  }

  return stations.slice(0, minStations);
});
</script>

<template>
  <div class="fixed inset-0 modal-overlay z-50 overflow-y-auto">
    <div class="min-h-screen px-3 py-4 sm:px-4 sm:py-6 flex items-start sm:items-center justify-center" @click.self="emit('close')">
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-6xl border border-gray-100 modal-content">
        <div class="flex justify-between items-center px-4 py-3 border-b border-gray-100 sticky top-0 bg-white rounded-t-2xl z-10">
          <h2 class="text-lg font-bold text-gray-900 truncate max-w-[calc(100%-48px)]">
            {{ doc?.properties?.property_name || doc?.display_filename || doc?.original_filename || doc?.filename }}
          </h2>
          <button
            @click="emit('close')"
            class="w-9 h-9 rounded-full flex items-center justify-center bg-gray-100 text-gray-400 hover:bg-gray-200 hover:text-gray-600 transition-all duration-300 hover:scale-110 shrink-0"
          >
            <X class="w-5 h-5" />
          </button>
        </div>
        <div class="p-4 sm:p-6">
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div>
              <h3 class="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <Home class="w-4 h-4" />
                文档预览
              </h3>
              <div
                class="border border-gray-200 rounded-xl bg-gray-50 overflow-hidden cursor-pointer relative"
                @click="previewUrl && openImageViewer()"
                :title="previewUrl ? '点击查看大图' : '加载中...'"
              >
                <div
                  class="w-full"
                  :style="{ aspectRatio: `${doc?.image_width || 4} / ${doc?.image_height || 3}` }"
                >
                  <div
                    v-if="!previewUrl"
                    class="w-full h-full skeleton-pulse bg-gray-200"
                  ></div>
                  <img
                    v-else
                    :src="previewUrl"
                    class="w-full h-full object-contain"
                    alt="文档预览"
                  />
                </div>
              </div>
            </div>
            <div class="lg:static lg:overflow-visible">
              <h4 class="font-medium text-gray-700 mb-4 flex items-center gap-2">
                <Home class="w-4 h-4" />
                房产信息
              </h4>
              <form class="space-y-5 lg:max-h-[calc(50vh+100px)] lg:overflow-y-auto pr-2 pl-1">
                  <div class="bg-gray-50 rounded-xl p-4">
                    <div class="text-xs font-medium text-gray-400 uppercase tracking-wide mb-3">
                      基本信息
                    </div>
                    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-4 gap-y-3">
                      <div class="sm:col-span-2 lg:col-span-3 flex items-center gap-2 min-w-0">
                        <span class="text-xs text-gray-500 shrink-0">售价</span>
                        <div class="relative min-w-0 flex-1 max-w-[140px]">
                          <input
                            v-model.number="properties.price"
                            type="text"
                            class="w-full px-2 py-1.5 pr-8 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all duration-300 bg-white text-lg font-bold text-emerald-600 truncate"
                          />
                          <span class="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-emerald-500">万円</span>
                        </div>
                      </div>
                     <div class="flex items-center gap-2">
                       <span class="text-xs text-gray-500 shrink-0">户型</span>
                       <input
                         v-model="properties.room_layout"
                         type="text"
                         class="flex-1 px-2 py-1.5 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-300 bg-white text-sm min-w-0"
                         placeholder="-"
                       />
                     </div>
                     <div class="flex items-center gap-2">
                       <span class="text-xs text-gray-500 shrink-0">面积</span>
                       <div class="relative flex-1 min-w-0">
                          <input
                            v-model.number="properties.exclusive_area"
                            type="text"
                            class="w-full px-2 py-1.5 pr-6 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-300 bg-white text-sm"
                            placeholder="-"
                          />
                         <span class="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-gray-400">m²</span>
                       </div>
                     </div>
                      <div class="flex items-center gap-2">
                        <span class="text-xs text-gray-500 shrink-0">建成年份</span>
                         <input
                           v-model.number="properties.build_year"
                           type="text"
                           class="flex-1 px-2 py-1.5 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-300 bg-white text-sm min-w-0"
                           placeholder="-"
                         />
                      </div>
                      <div class="flex items-center gap-2 sm:col-span-2 lg:col-span-3 min-w-0">
                        <span class="text-xs text-gray-500 shrink-0">地址</span>
                         <input
                           v-model="properties.address"
                           type="text"
                           class="flex-1 px-3 py-2 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-300 bg-white text-sm min-w-0"
                         />
                      </div>
                    </div>
                 </div>

                 <div class="bg-gray-50 rounded-xl p-4">
                  <div class="text-xs font-medium text-gray-400 uppercase tracking-wide mb-3">
                    建筑信息
                  </div>
                  <div class="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-3">
                    <div class="flex items-center gap-2">
                      <span class="text-xs text-gray-500 shrink-0">构造</span>
                       <input
                         v-model="properties.structure"
                         type="text"
                         class="flex-1 px-2 py-1.5 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-300 bg-white text-sm min-w-0"
                         placeholder="-"
                       />
                    </div>
                    <div class="flex items-center gap-2">
                      <span class="text-xs text-gray-500 shrink-0">楼层</span>
                      <div class="flex items-center gap-1 flex-1 min-w-0">
                         <input
                           v-model.number="properties.floor_number"
                           type="text"
                           class="w-10 px-1.5 py-1.5 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-300 bg-white text-sm text-center"
                           placeholder="-"
                         />
                         <span class="text-gray-400 text-xs">/</span>
                         <input
                           v-model.number="properties.total_floors"
                           type="text"
                           class="w-10 px-1.5 py-1.5 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-300 bg-white text-sm text-center"
                           placeholder="-"
                         />
                      </div>
                    </div>
                    <div class="flex items-center gap-2">
                      <span class="text-xs text-gray-500 shrink-0">朝向</span>
                       <input
                         v-model="properties.orientation"
                         type="text"
                         class="flex-1 px-2 py-1.5 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-300 bg-white text-sm min-w-0"
                         placeholder="-"
                       />
                    </div>
                    <div class="flex items-center gap-2">
                      <span class="text-xs text-gray-500 shrink-0">角部屋</span>
                       <select
                         v-model="properties.corner_room"
                         class="flex-1 px-2 py-1.5 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-300 bg-white text-sm cursor-pointer min-w-0"
                       >
                        <option :value="undefined">-</option>
                        <option :value="true">是</option>
                        <option :value="false">否</option>
                      </select>
                    </div>
                    <div class="flex items-center gap-2">
                      <span class="text-xs text-gray-500 shrink-0">阳台</span>
                      <div class="relative flex-1 min-w-0">
                         <input
                           v-model.number="properties.balcony_area"
                           type="text"
                           class="w-full px-2 py-1.5 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-300 bg-white text-sm pr-6"
                           placeholder="-"
                         />
                        <span class="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-gray-400">m²</span>
                      </div>
                    </div>
                    <div class="flex items-center gap-2">
                      <span class="text-xs text-gray-500 shrink-0">停车</span>
                       <input
                         v-model="properties.parking"
                         type="text"
                         class="flex-1 px-2 py-1.5 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-300 bg-white text-sm min-w-0"
                         placeholder="-"
                       />
                    </div>
                  </div>
                </div>

                <div class="bg-gray-50 rounded-xl p-4">
                  <div class="text-xs font-medium text-gray-400 uppercase tracking-wide mb-3">
                    费用信息
                  </div>
                  <div class="grid grid-cols-2 gap-3">
                     <div>
                       <label class="text-xs text-gray-500 mb-1 block">管理费</label>
                       <div class="relative">
                         <input
                           v-model.number="properties.management_fee"
                           type="text"
                           class="w-full px-3 py-2 pr-12 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-300 bg-white text-sm"
                         />
                         <span class="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-gray-400">円/月</span>
                       </div>
                     </div>
                     <div>
                       <label class="text-xs text-gray-500 mb-1 block">修缮费</label>
                       <div class="relative">
                         <input
                           v-model.number="properties.repair_fee"
                           type="text"
                           class="w-full px-3 py-2 pr-12 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-300 bg-white text-sm"
                         />
                         <span class="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-gray-400">円/月</span>
                       </div>
                     </div>
                  </div>
                </div>

                <div class="bg-gray-50 rounded-xl p-4">
                  <div class="text-xs font-medium text-gray-400 uppercase tracking-wide mb-3">
                    权利状态
                  </div>
                  <div class="grid grid-cols-2 gap-3">
                    <div>
                      <label class="text-xs text-gray-500 mb-1 block">土地权利</label>
                       <input
                         v-model="properties.land_rights"
                         type="text"
                         class="w-full px-3 py-2 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-300 bg-white text-sm"
                       />
                    </div>
                    <div>
                      <label class="text-xs text-gray-500 mb-1 block">现状</label>
                       <input
                         v-model="properties.current_status"
                         type="text"
                         class="w-full px-3 py-2 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-300 bg-white text-sm"
                       />
                    </div>
                    <div>
                      <label class="text-xs text-gray-500 mb-1 block">交房日期</label>
                       <input
                         v-model="properties.handover_date"
                         type="text"
                         class="w-full px-3 py-2 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-300 bg-white text-sm"
                       />
                    </div>
                    <div>
                      <label class="text-xs text-gray-500 mb-1 block">宠物政策</label>
                       <input
                         v-model="properties.pet_policy"
                         type="text"
                         class="w-full px-3 py-2 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-300 bg-white text-sm"
                       />
                    </div>
                  </div>
                </div>

                <div class="bg-gray-50 rounded-xl p-4">
                  <div class="text-xs font-medium text-gray-400 uppercase tracking-wide mb-3">
                    最近车站
                  </div>
                   <div class="space-y-2">
                     <div
                       v-for="(station, index) in editableStations"
                       :key="index"
                       class="grid grid-cols-1 sm:grid-cols-12 gap-2 items-center"
                     >
                       <div class="sm:col-span-4">
                          <input
                            v-model="station.name"
                            type="text"
                            placeholder="车站名"
                            class="w-full px-3 py-2 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-300 bg-white text-sm"
                          />
                       </div>
                       <div class="sm:col-span-6">
                          <input
                            v-model="station.line"
                            type="text"
                            placeholder="线路"
                            class="w-full px-3 py-2 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-300 bg-white text-sm"
                          />
                       </div>
                       <div class="sm:col-span-2">
                         <div class="relative">
                            <input
                              v-model.number="station.walking_minutes"
                              type="text"
                              placeholder="分钟"
                              class="w-full px-3 py-2 pr-8 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-300 bg-white text-sm"
                            />
                           <span class="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-gray-400">分</span>
                         </div>
                       </div>
                     </div>
                   </div>
                </div>
              </form>
            </div>
          </div>

          <div class="mt-6 pt-4 border-t border-gray-100">
             <button
               @click="toggleOcrText"
               class="flex items-center gap-2 px-4 py-2 rounded-xl bg-white border border-gray-200 text-gray-700 hover:bg-gray-50 hover:border-gray-300 hover:text-gray-900 font-medium transition-all duration-300 text-sm mb-4 shadow-sm hover:scale-105"
             >
              <ChevronDown class="w-4 h-4 transition-transform duration-300" :class="{ 'rotate-180': showOcrText }" />
              <span>OCR文本</span>
            </button>
            <div v-if="showOcrText" class="mb-4">
              <div
                class="border border-gray-200 rounded-lg bg-gray-50 p-3 max-h-[200px] overflow-y-auto text-sm text-gray-600 font-mono whitespace-pre-wrap"
              >
                {{ ocrText }}
              </div>
            </div>
          </div>

          <div class="flex flex-col sm:flex-row justify-center gap-3 pt-4 border-t border-gray-100 mt-4">
             <button
               @click="onRetryOCR"
               :disabled="retryLoading"
               class="flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-white border border-orange-200 text-orange-600 hover:bg-orange-50 hover:border-orange-300 font-medium transition-all duration-300 text-sm order-5 sm:order-1 disabled:opacity-50 shadow-sm hover:scale-105"
             >
               <FileText class="w-4 h-4" />
               {{ retryLoading ? '处理中...' : '重试OCR' }}
             </button>
             <button
               @click="onRetryLLM"
               :disabled="retryLoading"
               class="flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-white border border-blue-200 text-blue-700 hover:bg-blue-50 hover:border-blue-300 font-medium transition-all duration-300 text-sm order-4 sm:order-2 disabled:opacity-50 shadow-sm hover:scale-105"
             >
              <Sparkles class="w-4 h-4" :class="{ 'animate-spin': retryLoading }" />
              {{ retryLoading ? '处理中...' : '重试LLM' }}
            </button>
             <button
               @click="onDelete"
               class="flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-white border border-red-200 text-red-600 hover:bg-red-50 hover:border-red-300 font-medium transition-all duration-300 text-sm order-2 sm:order-3 shadow-sm hover:scale-105"
             >
              <Trash2 class="w-4 h-4" />
              删除文档
            </button>
             <button
               @click="saveProperties"
               :disabled="saving"
               class="flex items-center justify-center gap-2 px-6 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white font-medium shadow-lg shadow-emerald-300 transition-all duration-300 text-sm order-1 sm:order-4 disabled:opacity-50 hover:scale-105 hover:-translate-y-0.5"
             >
              <Check class="w-4 h-4" />
              {{ saving ? '保存中...' : '保存修改' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <ImageViewer
    v-if="showImageViewer && doc"
    :doc-id="doc.id"
    :doc-name="doc.display_filename || doc.original_filename || doc.filename"
    @close="showImageViewer = false"
  />
</template>

<style scoped>
.skeleton-shimmer {
  background: linear-gradient(
    90deg,
    #e5e7eb 0%,
    #f3f4f6 25%,
    #e5e7eb 50%,
    #f3f4f6 75%,
    #e5e7eb 100%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s ease-in-out infinite;
}

@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

.skeleton-pulse {
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 0.8;
  }
  50% {
    opacity: 0.4;
  }
}
</style>
