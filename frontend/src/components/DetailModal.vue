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
const properties = ref<PropertyDetails>({});

const updateContainerHeight = () => {
  const vw = window.innerWidth;
  const vh = window.innerHeight;

  let containerWidth: number;
  if (vw >= 1024) {
    const modalWidth = Math.min(72 * 16, vw - 32);
    const columnWidth = (modalWidth - 16) / 2;
    containerWidth = Math.min(600, columnWidth);
  } else {
    containerWidth = vw - 64;
  }

  const maxDisplayHeight = vh * 0.5;
  const aspectRatio = props.doc?.image_width && props.doc?.image_height
    ? props.doc.image_width / props.doc.image_height
    : 1.333;

  containerWidth = Math.min(containerWidth, maxDisplayHeight * aspectRatio);
};

watch(() => props.doc, (newDoc) => {
  if (newDoc?.properties) {
    properties.value = JSON.parse(JSON.stringify(newDoc.properties));
  } else {
    properties.value = {};
  }
}, { immediate: true });

watch(() => [props.doc?.image_width, props.doc?.image_height], updateContainerHeight);

onMounted(() => {
  updateContainerHeight();
  window.addEventListener('resize', updateContainerHeight);
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateContainerHeight);
});

const toggleOcrText = () => {
  showOcrText.value = !showOcrText.value;
};

const saveProperties = async () => {
  if (!props.doc) return;

  saving.value = true;
  try {
    await updateDocument(props.doc.id, properties.value);
    emit('saved', properties.value, props.doc.id);
    emit('close');
  } catch (error) {
    console.error('保存失败:', error);
    alert('保存失败: ' + (error as Error).message);
  } finally {
    saving.value = false;
  }
};

const onRetryOCR = () => {
  if (props.doc) {
    emit('retryOCR', props.doc.id);
  }
};

const onRetryLLM = () => {
  if (props.doc) {
    emit('retryLLM', props.doc.id);
  }
};

const onDelete = () => {
  if (props.doc && confirm('确定要删除这个文档吗?')) {
    emit('delete', props.doc.id);
  }
};

const openImageViewer = () => {
  showImageViewer.value = true;
};

const ocrText = computed(() => props.doc?.ocr_text || '暂无OCR文本');
</script>

<template>
  <div class="fixed inset-0 modal-overlay z-50 overflow-y-auto" @click.self="emit('close')">
    <div class="min-h-screen px-4 py-4 flex items-center justify-center">
      <div class="bg-white rounded-2xl shadow-2xl max-w-6xl w-full border border-gray-100">
        <div class="flex justify-between items-center px-4 py-3 border-b border-gray-100">
          <h2 class="text-lg font-bold text-gray-900">
            {{ doc?.properties?.property_name || doc?.filename }}
          </h2>
          <button
            @click="emit('close')"
            class="w-8 h-8 rounded-lg hover:bg-gray-100 transition flex items-center justify-center text-gray-400 hover:text-gray-600"
          >
            <X class="w-5 h-5" />
          </button>
        </div>
        <div class="p-4">
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div>
              <h3 class="font-semibold text-gray-900 mb-3">文档预览</h3>
              <div
                class="border border-gray-200 rounded-xl bg-gray-50 overflow-hidden cursor-pointer relative"
                @click="previewUrl && openImageViewer()"
                :title="previewUrl ? '点击查看大图' : '加载中...'"
              >
                <div
                  class="w-full"
                  :style="{ aspectRatio: `${props.doc?.image_width || 4} / ${props.doc?.image_height || 3}` }"
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
            <div>
              <h4 class="font-medium text-gray-700 mb-2 flex items-center gap-2">
                <Home class="w-4 h-4" />
                房产信息
              </h4>
              <form class="space-y-1 max-h-[calc(100vh-280px)] lg:max-h-[calc(50vh+100px)] overflow-y-auto pr-2 pl-1">
                <div class="mb-3">
                  <label class="text-xs text-gray-500 mb-1 block">售价 (万円)</label>
                  <input
                    v-model.number="properties.price"
                    type="text"
                    class="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-gradient-to-r from-emerald-50 to-blue-50 text-xl font-bold text-emerald-600"
                  />
                </div>

                <div class="grid grid-cols-3 gap-3 mb-3">
                  <div>
                    <label class="text-xs text-gray-500 mb-1 block">户型</label>
                    <input
                      v-model="properties.room_layout"
                      type="text"
                      class="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-sm"
                    />
                  </div>
                  <div>
                    <label class="text-xs text-gray-500 mb-1 block">面积 (m²)</label>
                    <input
                      v-model.number="properties.exclusive_area"
                      type="text"
                      class="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-sm"
                    />
                  </div>
                  <div>
                    <label class="text-xs text-gray-500 mb-1 block">建成年份</label>
                    <input
                      v-model.number="properties.build_year"
                      type="text"
                      class="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-sm"
                    />
                  </div>
                </div>

                <div class="mb-3">
                  <label class="text-xs text-gray-500 mb-1 block">地址</label>
                  <input
                    v-model="properties.address"
                    type="text"
                    class="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-sm"
                  />
                </div>

                <div class="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2 mt-4">
                  建筑信息
                </div>

                <div class="grid grid-cols-6 gap-2 mb-3">
                  <div class="col-span-1">
                    <label class="text-xs text-gray-500 mb-1 block">构造</label>
                    <input
                      v-model="properties.structure"
                      type="text"
                      class="w-full px-2 py-1.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-sm"
                    />
                  </div>
                  <div class="col-span-2">
                    <label class="text-xs text-gray-500 mb-1 block">楼层</label>
                    <div class="flex gap-1">
                      <input
                        v-model.number="properties.floor_number"
                        type="text"
                        class="w-1/2 px-2 py-1.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-sm"
                      />
                      <span class="flex items-center text-gray-400 text-sm">/</span>
                      <input
                        v-model.number="properties.total_floors"
                        type="text"
                        class="w-1/2 px-2 py-1.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-sm"
                      />
                    </div>
                  </div>
                  <div class="col-span-1">
                    <label class="text-xs text-gray-500 mb-1 block">朝向</label>
                    <input
                      v-model="properties.orientation"
                      type="text"
                      class="w-full px-2 py-1.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-sm"
                    />
                  </div>
                  <div class="col-span-1">
                    <label class="text-xs text-gray-500 mb-1 block">角部屋</label>
                    <select
                      v-model="properties.corner_room"
                      class="w-full px-2 py-1.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-sm cursor-pointer"
                    >
                      <option :value="undefined">-</option>
                      <option :value="true">是</option>
                      <option :value="false">否</option>
                    </select>
                  </div>
                  <div class="col-span-1">
                    <label class="text-xs text-gray-500 mb-1 block">阳台(m²)</label>
                    <input
                      v-model.number="properties.balcony_area"
                      type="text"
                      class="w-full px-2 py-1.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-sm"
                    />
                  </div>
                </div>

                <div class="grid grid-cols-6 gap-2 mb-3">
                  <div class="col-span-3">
                    <label class="text-xs text-gray-500 mb-1 block">停车场</label>
                    <input
                      v-model="properties.parking"
                      type="text"
                      class="w-full px-2 py-1.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-sm"
                    />
                  </div>
                </div>

                <div class="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2 mt-4">
                  费用信息
                </div>

                <div class="grid grid-cols-2 gap-3 mb-3">
                  <div>
                    <label class="text-xs text-gray-500 mb-1 block">管理费 (円/月)</label>
                    <input
                      v-model.number="properties.management_fee"
                      type="text"
                      class="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-sm"
                    />
                  </div>
                  <div>
                    <label class="text-xs text-gray-500 mb-1 block">修缮费 (円/月)</label>
                    <input
                      v-model.number="properties.repair_fee"
                      type="text"
                      class="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-sm"
                    />
                  </div>
                </div>

                <div class="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2 mt-4">
                  权利状态
                </div>

                <div class="grid grid-cols-2 gap-3 mb-3">
                  <div>
                    <label class="text-xs text-gray-500 mb-1 block">土地权利</label>
                    <input
                      v-model="properties.land_rights"
                      type="text"
                      class="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-sm"
                    />
                  </div>
                  <div>
                    <label class="text-xs text-gray-500 mb-1 block">现状</label>
                    <input
                      v-model="properties.current_status"
                      type="text"
                      class="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-sm"
                    />
                  </div>
                  <div>
                    <label class="text-xs text-gray-500 mb-1 block">交房日期</label>
                    <input
                      v-model="properties.handover_date"
                      type="text"
                      class="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-sm"
                    />
                  </div>
                  <div>
                    <label class="text-xs text-gray-500 mb-1 block">宠物政策</label>
                    <input
                      v-model="properties.pet_policy"
                      type="text"
                      class="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-sm"
                    />
                  </div>
                </div>

                <div class="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2 mt-4">
                  最近车站
                </div>

                <div class="space-y-2">
                  <div
                    v-for="(station, index) in (properties.stations || []).slice(0, 3)"
                    :key="index"
                    class="grid grid-cols-12 gap-2 items-center"
                  >
                    <div class="col-span-4">
                      <input
                        v-model="station.name"
                        type="text"
                        placeholder="车站名"
                        class="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-sm"
                      />
                    </div>
                    <div class="col-span-6">
                      <input
                        v-model="station.line"
                        type="text"
                        placeholder="线路"
                        class="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-sm"
                      />
                    </div>
                    <div class="col-span-2">
                      <input
                        v-model.number="station.walking_minutes"
                        type="text"
                        placeholder="分钟"
                        class="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-sm"
                      />
                    </div>
                  </div>
                </div>
              </form>
            </div>
          </div>

          <div class="mt-4 pt-3 border-t border-gray-100">
            <button
              @click="toggleOcrText"
              class="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 font-medium transition-all text-sm"
            >
              <ChevronDown class="w-4 h-4 transition-transform" :class="{ 'rotate-180': showOcrText }" />
              <span>OCR文本</span>
            </button>
            <div v-if="showOcrText" class="mt-2">
              <div
                class="border border-gray-200 rounded-lg bg-gray-50 p-3 max-h-[200px] overflow-y-auto text-sm text-gray-600 font-mono whitespace-pre-wrap"
              >
                {{ ocrText }}
              </div>
            </div>
          </div>

          <div class="flex flex-col md:flex-row justify-center gap-2 pt-3 border-t border-gray-100 mt-4">
            <button
              @click="onRetryOCR"
              class="flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-600 text-white font-medium shadow-md shadow-amber-300 transition-all active:scale-95 text-sm"
            >
              <RefreshCw class="w-4 h-4" />
              重试OCR
            </button>
            <button
              @click="onRetryLLM"
              class="flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-blue-500 hover:bg-blue-600 text-white font-medium shadow-md shadow-blue-300 transition-all active:scale-95 text-sm"
            >
              <Sparkles class="w-4 h-4" />
              重试LLM
            </button>
            <button
              @click="saveProperties"
              :disabled="saving"
              class="flex items-center justify-center gap-2 px-6 py-2 rounded-lg bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 text-white font-medium shadow-lg shadow-green-300 transition-all active:scale-95 md:shadow-md text-sm disabled:opacity-50"
            >
              <Check class="w-4 h-4" />
              {{ saving ? '保存中...' : '保存修改' }}
            </button>
            <button
              @click="onDelete"
              class="flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-red-50 hover:bg-red-100 text-red-600 font-medium transition-all active:scale-95 md:bg-red-500 md:hover:bg-red-600 md:text-white md:shadow-md md:shadow-red-300 text-sm"
            >
              <Trash2 class="w-4 h-4" />
              删除文档
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <ImageViewer
    v-if="showImageViewer && doc"
    :doc-id="doc.id"
    :doc-name="doc.filename"
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
