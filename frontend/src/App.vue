<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue';
import type { Document } from '@/types';
import { useDocuments } from '@/composables/useDocuments';
import { useLocations } from '@/composables/useLocations';
import { useAuthToken } from '@/composables/useAuthToken';

// Initialize token handling (extracts from URL, stores to localStorage)
useAuthToken();
import { fetchPreview, toggleFavorite, deleteDocument, retryOCR, retryLLM, fetchDocument } from '@/api';
import DocumentCard from '@/components/DocumentCard.vue';
import DocumentCardSkeleton from '@/components/DocumentCardSkeleton.vue';
import UploadModal from '@/components/UploadModal.vue';
import LocationModal from '@/components/LocationModal.vue';
import StationModal from '@/components/StationModal.vue';
import ModelModal from '@/components/ModelModal.vue';
import DetailModal from '@/components/DetailModal.vue';
import {
  Upload,
  Map,
  Train,
  Settings,
  Trash2,
  Search,
  ChevronLeft,
  ChevronRight,
  Filter,
  Check,
  XCircle,
  DollarSign,
  Maximize,
  Footprints,
  Layout,
  Heart,
  Menu,
  X,
  Home,
} from 'lucide-vue-next';

const {
  documents,
  sortedDocuments,
  pageDocuments,
  currentPage,
  totalPages,
  filters,
  loading,
  loadDocuments,
  applyFilters,
  goToPage,
  handleCleanup,
  getDocStatus,
  updateDocumentProperties,
  addDocument,
  preloadImages,
  updateDocumentById,
  activeIntervals,
} = useDocuments();

const {
  locations,
  loadLocations,
} = useLocations();

const showDetailModal = ref(false);
const currentDoc = ref<Document | null>(null);
const previewUrl = ref<string | null>(null);
const showUploadModal = ref(false);
const showLocationModal = ref(false);
const showStationModal = ref(false);
const showModelModal = ref(false);
const showFilterPanel = ref(false);
const showMobileMenu = ref(false);
const jumpPageInput = ref<number | null>(null);
const retryLoading = ref(false);

const pageNumbers = computed(() => {
  if (totalPages.value <= 7) {
    return Array.from({ length: totalPages.value }, (_, i) => i + 1);
  }

  const pages: (number | string)[] = [1];

  const leftBound = Math.max(2, currentPage.value - 2);
  const rightBound = Math.min(totalPages.value - 1, currentPage.value + 2);

  if (leftBound > 2) pages.push('...');

  for (let i = leftBound; i <= rightBound; i++) {
    pages.push(i);
  }

  if (rightBound < totalPages.value - 1) pages.push('...');

  pages.push(totalPages.value);
  return pages;
});

const activeFilterCount = computed(() => {
  let count = 0;
  if (filters.value.search) count++;
  if (filters.value.priceMin || filters.value.priceMax) count++;
  if (filters.value.areaMin || filters.value.areaMax) count++;
  if (filters.value.walking) count++;
  if (filters.value.propertyTypes.length > 0) count++;
  if (filters.value.room) count++;
  if (filters.value.pet) count++;
  if (filters.value.favorite) count++;
  return count;
});

const resetFilters = () => {
  filters.value.search = '';
  filters.value.priceMin = null;
  filters.value.priceMax = null;
  filters.value.areaMin = null;
  filters.value.areaMax = null;
  filters.value.walking = null;
  filters.value.propertyTypes = [];
  filters.value.room = null;
  filters.value.pet = false;
  filters.value.favorite = false;
  applyFilters();
};

const removeFilter = (filterName: string) => {
  switch (filterName) {
    case 'search':
      filters.value.search = '';
      break;
    case 'price':
      filters.value.priceMin = null;
      filters.value.priceMax = null;
      break;
    case 'area':
      filters.value.areaMin = null;
      filters.value.areaMax = null;
      break;
    case 'walking':
      filters.value.walking = null;
      break;
    case 'propertyTypes':
      filters.value.propertyTypes = [];
      break;
    case 'room':
      filters.value.room = null;
      break;
    case 'pet':
      filters.value.pet = false;
      break;
    case 'favorite':
      filters.value.favorite = false;
      break;
  }
  applyFilters();
};

const openDetailModal = async (doc: Document) => {
  try {
    currentDoc.value = doc;
    showDetailModal.value = true;

    const blob = await fetchPreview(doc.id);
    previewUrl.value = URL.createObjectURL(blob);
  } catch (error) {
    console.error('打开详情页失败:', error);
    alert('加载预览失败: ' + (error as Error).message);
    closeDetailModal();
  }
};

const closeDetailModal = () => {
  showDetailModal.value = false;
  currentDoc.value = null;
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value);
    previewUrl.value = null;
  }
};

const onFavoriteToggle = async (doc: Document) => {
  const originalFavorite = doc.favorite;
  const isFavoriting = originalFavorite === 0;

  // 乐观更新：立即切换前端状态
  doc.favorite = isFavoriting ? 1 : 0;
  if (isFavoriting) {
    // 喜欢时：设置 sort_order 为喜欢时间
    doc.sort_order = Date.now();
  }
  // 取消喜欢时：不修改 sort_order，位置保持不变

  try {
    const newFavorite = await toggleFavorite(doc.id);
    // 使用后端返回的真实状态更新
    doc.favorite = newFavorite;
    // 强制触发Vue响应式更新
    const docIndex = documents.value.findIndex(d => d.id === doc.id);
    if (docIndex !== -1) {
      documents.value.splice(docIndex, 1, { ...doc });
    }
  } catch (error) {
    // 请求失败：恢复原来的状态
    doc.favorite = originalFavorite;
    const docIndex = documents.value.findIndex(d => d.id === doc.id);
    if (docIndex !== -1) {
      documents.value.splice(docIndex, 1, { ...doc });
    }
    console.error('切换收藏状态失败:', error);
    alert('切换收藏状态失败，请重试');
  }
};

const onDelete = async (doc: Document) => {
  if (!confirm('确定要删除这个文档吗?')) return;

  // 乐观更新：立即从列表中移除
  const docIndex = documents.value.findIndex(d => d.id === doc.id);
  if (docIndex !== -1) {
    documents.value.splice(docIndex, 1);
    applyFilters(); // 更新过滤后的文档列表
  }

  try {
    await deleteDocument(doc.id);
  } catch (error) {
    // 请求失败：恢复文档到列表中
    if (docIndex !== -1) {
      documents.value.splice(docIndex, 0, doc);
      applyFilters(); // 重新应用过滤器
    }
    console.error('删除文档失败:', error);
    alert('删除文档失败，请重试');
  }
};

const onUploaded = (uploadedDocs: Array<{ id: number; filename: string }>) => {
  uploadedDocs.forEach(doc => {
    addDocument(doc);
    pollDocumentStatus(doc.id);
  });
  setTimeout(() => preloadImages(), 100);
};

const pollDocumentStatus = (docId: number) => {
  let attempts = 0;
  const maxAttempts = 60;
  const checkInterval = setInterval(async () => {
    await updateDocumentById(docId);
    const doc = documents.value.find(d => d.id === docId);
    if (doc && doc.ocr_status === 'done' && doc.llm_status === 'done') {
      clearInterval(checkInterval);
      activeIntervals.delete(checkInterval);
    } else if (attempts > maxAttempts) {
      clearInterval(checkInterval);
      activeIntervals.delete(checkInterval);
    }
    attempts++;
  }, 2000);
  activeIntervals.add(checkInterval);
};

const onDetailSaved = (updatedProperties: PropertyDetails, docId: number) => {
  updateDocumentProperties(docId, updatedProperties);
};

const onDetailDelete = async (docId: number) => {
  // 乐观更新：立即从列表中移除
  const docIndex = documents.value.findIndex(d => d.id === docId);
  const doc = docIndex !== -1 ? documents.value[docIndex] : null;
  if (docIndex !== -1) {
    documents.value.splice(docIndex, 1);
    applyFilters(); // 更新过滤后的文档列表
  }

  try {
    await deleteDocument(docId);
    closeDetailModal();
  } catch (error) {
    // 请求失败：恢复文档到列表中
    if (doc && docIndex !== -1) {
      documents.value.splice(docIndex, 0, doc);
      applyFilters(); // 重新应用过滤器
    }
    console.error('删除文档失败:', error);
    alert('删除文档失败，请重试');
  }
};

const onDetailRetryOCR = async (docId: number) => {
  if (retryLoading.value) return;
  retryLoading.value = true;
  try {
    await retryOCR(docId);
    let attempts = 0;
    const checkInterval = setInterval(async () => {
      await updateDocumentById(docId);
      const doc = documents.value.find(d => d.id === docId);
      if (currentDoc.value && currentDoc.value.id === docId) {
        currentDoc.value = doc || null;
      }
      if (doc && doc.ocr_status === 'done' && doc.llm_status === 'done') {
        clearInterval(checkInterval);
        activeIntervals.delete(checkInterval);
        retryLoading.value = false;
      } else if (attempts > 30) {
        clearInterval(checkInterval);
        activeIntervals.delete(checkInterval);
        retryLoading.value = false;
      }
      attempts++;
    }, 2000);
    activeIntervals.add(checkInterval);
  } catch (error) {
    console.error('重试OCR失败:', error);
    alert('重试OCR失败: ' + (error as Error).message);
    retryLoading.value = false;
  }
};

const onDetailRetryLLM = async (docId: number) => {
  if (retryLoading.value) return;
  retryLoading.value = true;
  try {
    await retryLLM(docId);
    let attempts = 0;
    const checkInterval = setInterval(async () => {
      await updateDocumentById(docId);
      const doc = documents.value.find(d => d.id === docId);
      if (currentDoc.value && currentDoc.value.id === docId) {
        currentDoc.value = doc || null;
      }
      if (doc && doc.llm_status === 'done') {
        clearInterval(checkInterval);
        activeIntervals.delete(checkInterval);
        retryLoading.value = false;
      } else if (attempts > 30) {
        clearInterval(checkInterval);
        activeIntervals.delete(checkInterval);
        retryLoading.value = false;
      }
      attempts++;
    }, 2000);
    activeIntervals.add(checkInterval);
  } catch (error) {
    console.error('重试LLM失败:', error);
    alert('重试LLM失败: ' + (error as Error).message);
    retryLoading.value = false;
  }
};

const onLocationModalClose = () => {
  showLocationModal.value = false;
};

const onModelModalClose = () => {
  showModelModal.value = false;
};

onMounted(() => {
  loadLocations();
});

watch(currentPage, () => {
  if (!loading.value) {
    setTimeout(() => preloadImages(), 100);
  }
});

watch(filters, () => applyFilters(), { deep: true });</script>

<template>
  <div class="container mx-auto px-4 py-8 max-w-7xl">
    <header class="mb-8">
      <nav class="flex justify-between items-center gap-4 relative">
        <div class="flex items-center gap-3">
          <span class="text-3xl">🏠</span>
          <div>
            <h1 class="text-2xl font-bold text-gray-900">房了个房</h1>
            <p class="text-sm text-gray-500 hidden sm:block">日本房产文档智能解析</p>
          </div>
        </div>

        <div class="flex items-center gap-3">
          <button
            @click="showUploadModal = true"
            class="hidden md:flex px-5 py-2.5 rounded-xl bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white transition-all font-medium shadow-lg shadow-blue-300 items-center gap-2"
          >
            <Upload class="w-5 h-5" />
            上传文档
          </button>
          <button
            @click="showUploadModal = true"
            class="md:hidden w-12 h-12 rounded-xl bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white transition-all font-medium shadow-lg shadow-blue-300 flex items-center justify-center"
          >
            <Upload class="w-6 h-6" />
          </button>

          <button
            @click="showLocationModal = true"
            class="hidden lg:flex px-4 py-2.5 rounded-xl bg-white border border-gray-200 text-gray-700 hover:bg-gray-50 hover:border-gray-300 hover:text-gray-900 transition-all font-medium shadow-sm items-center gap-2"
          >
            <Map class="w-5 h-5 text-gray-500" />
            位置管理
          </button>

           <button
             @click="showStationModal = true"
             class="hidden lg:flex px-4 py-2.5 rounded-xl bg-white border border-gray-200 text-gray-700 hover:bg-gray-50 hover:border-gray-300 hover:text-gray-900 transition-all font-medium shadow-sm items-center gap-2"
           >
             <Train class="w-5 h-5 text-gray-500" />
             车站时长
           </button>

           <button
             @click="showModelModal = true"
             class="hidden lg:flex px-4 py-2.5 rounded-xl bg-white border border-gray-200 text-gray-700 hover:bg-gray-50 hover:border-gray-300 hover:text-gray-900 transition-all font-medium shadow-sm items-center gap-2"
           >
             <Settings class="w-5 h-5 text-gray-500" />
             模型管理
           </button>

           <button
             @click="handleCleanup"
             class="hidden lg:flex px-4 py-2.5 rounded-xl bg-white border border-red-200 text-red-600 hover:bg-red-50 hover:border-red-300 transition-all font-medium shadow-sm items-center gap-2"
           >
            <Trash2 class="w-5 h-5" />
            清理
          </button>

          <button
            @click="showMobileMenu = !showMobileMenu"
            class="lg:hidden w-12 h-12 rounded-xl bg-white border border-gray-200 hover:bg-gray-50 transition-all shadow-sm flex items-center justify-center relative"
          >
            <Menu class="w-6 h-6 text-gray-600" />
          </button>
        </div>

        <div v-if="showMobileMenu" class="lg:hidden absolute left-auto right-0 top-full mt-2 z-50">
          <div class="bg-white rounded-2xl border border-gray-200 shadow-xl overflow-hidden px-4">
            <div class="flex flex-col">
              <button
                @click="showLocationModal = true; showMobileMenu = false"
                class="w-full px-4 py-3.5 border-b border-gray-100 text-gray-700 hover:bg-gray-50 transition-all font-medium flex items-center gap-3"
              >
                <Map class="w-5 h-5 text-gray-500" />
                位置管理
              </button>
               <button
                 @click="showStationModal = true; showMobileMenu = false"
                 class="w-full px-4 py-3.5 border-b border-gray-100 text-gray-700 hover:bg-gray-50 transition-all font-medium flex items-center gap-3"
               >
                 <Train class="w-5 h-5 text-gray-500" />
                 车站时长
               </button>
               <button
                 @click="showModelModal = true; showMobileMenu = false"
                 class="w-full px-4 py-3.5 border-b border-gray-100 text-gray-700 hover:bg-gray-50 transition-all font-medium flex items-center gap-3"
               >
                 <Settings class="w-5 h-5 text-gray-500" />
                 模型管理
               </button>
               <button
                 @click="handleCleanup; showMobileMenu = false"
                 class="w-full px-4 py-3.5 text-red-600 hover:bg-red-50 transition-all font-medium flex items-center gap-3"
               >
                <Trash2 class="w-5 h-5" />
                清理
              </button>
            </div>
          </div>
        </div>
      </nav>
    </header>

    <div class="mb-6">
      <div class="flex gap-3 mb-3">
        <div class="relative flex-1">
          <input
            v-model="filters.search"
            type="text"
            placeholder="搜索房产名称、地址..."
            class="w-full pl-10 pr-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all bg-white shadow-sm"
          />
          <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
        </div>
        <button
          @click="showFilterPanel = !showFilterPanel"
          class="px-4 py-3 rounded-xl bg-white border border-gray-200 hover:border-blue-300 transition-all shadow-sm flex items-center gap-2 relative"
        >
          <Filter class="w-5 h-5 text-gray-500" />
          <span class="text-gray-700 font-medium">筛选</span>
          <span
            v-if="activeFilterCount > 0"
            class="absolute -top-1 -right-1 px-1.5 py-0.5 bg-blue-500 text-white text-xs rounded-full"
          >
            {{ activeFilterCount }}
          </span>
        </button>
      </div>

      <div
        v-if="showFilterPanel"
        class="bg-white rounded-2xl border border-gray-200 shadow-lg p-5"
      >
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">价格范围 (万円)</label>
            <div class="flex items-center gap-2">
              <input
                v-model.number="filters.priceMin"
                type="number"
                placeholder="最低"
                min="0"
                class="flex-1 min-w-0 px-2 py-2 rounded-lg border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all text-sm"
              />
              <span class="text-gray-400 flex-shrink-0">-</span>
              <input
                v-model.number="filters.priceMax"
                type="number"
                placeholder="最高"
                min="0"
                class="flex-1 min-w-0 px-2 py-2 rounded-lg border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all text-sm"
              />
            </div>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">专有面积 (m²)</label>
            <div class="flex items-center gap-2">
              <input
                v-model.number="filters.areaMin"
                type="number"
                placeholder="最低"
                min="0"
                step="1"
                class="flex-1 min-w-0 px-2 py-2 rounded-lg border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all text-sm"
              />
              <span class="text-gray-400 flex-shrink-0">-</span>
              <input
                v-model.number="filters.areaMax"
                type="number"
                placeholder="最高"
                min="0"
                step="1"
                class="flex-1 min-w-0 px-2 py-2 rounded-lg border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all text-sm"
              />
            </div>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">房产类型</label>
            <div class="flex flex-wrap gap-2">
              <label
                class="inline-flex items-center px-3 py-1.5 rounded-lg border border-gray-200 cursor-pointer hover:bg-gray-50 transition-all"
                :class="{
                  'bg-blue-50 border-blue-300 text-blue-700': filters.propertyTypes.includes('マンション')
                }"
              >
                <input
                  v-model="filters.propertyTypes"
                  type="checkbox"
                  value="マンション"
                  class="hidden"
                />
                <span class="text-sm">マンション</span>
              </label>
              <label
                class="inline-flex items-center px-3 py-1.5 rounded-lg border border-gray-200 cursor-pointer hover:bg-gray-50 transition-all"
                :class="{
                  'bg-blue-50 border-blue-300 text-blue-700': filters.propertyTypes.includes('一戸建て')
                }"
              >
                <input
                  v-model="filters.propertyTypes"
                  type="checkbox"
                  value="一戸建て"
                  class="hidden"
                />
                <span class="text-sm">一戸建て</span>
              </label>
              <label
                class="inline-flex items-center px-3 py-1.5 rounded-lg border border-gray-200 cursor-pointer hover:bg-gray-50 transition-all"
                :class="{
                  'bg-blue-50 border-blue-300 text-blue-700': filters.propertyTypes.includes('土地')
                }"
              >
                <input
                  v-model="filters.propertyTypes"
                  type="checkbox"
                  value="土地"
                  class="hidden"
                />
                <span class="text-sm">土地</span>
              </label>
            </div>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">步行时长 (分钟)</label>
            <select
              v-model="filters.walking"
              class="w-full px-3 py-2 rounded-lg border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all text-sm cursor-pointer"
            >
              <option :value="null">不限</option>
              <option :value="3">3分钟以内</option>
              <option :value="5">5分钟以内</option>
              <option :value="10">10分钟以内</option>
              <option :value="15">15分钟以内</option>
            </select>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">房间布局</label>
            <select
              v-model="filters.room"
              class="w-full px-3 py-2 rounded-lg border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all text-sm cursor-pointer"
            >
              <option :value="null">不限</option>
              <option value="1R">1R</option>
              <option value="1K">1K</option>
              <option value="1DK">1DK</option>
              <option value="1LDK">1LDK</option>
              <option value="2K">2K</option>
              <option value="2DK">2DK</option>
              <option value="2LDK">2LDK</option>
              <option value="3K">3K</option>
              <option value="3DK">3DK</option>
              <option value="3LDK">3LDK</option>
              <option value="4K">4K+</option>
              <option value="4DK">4DK+</option>
              <option value="4LDK">4LDK+</option>
            </select>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">其他条件</label>
            <div class="flex flex-wrap gap-2">
              <label
                class="inline-flex items-center px-3 py-1.5 rounded-lg border border-gray-200 cursor-pointer hover:bg-gray-50 transition-all"
                :class="{
                  'bg-pink-50 border-pink-300 text-pink-700': filters.pet
                }"
              >
                <input v-model="filters.pet" type="checkbox" class="hidden" />
                <span class="text-sm">可养宠物</span>
              </label>
              <label
                class="inline-flex items-center px-3 py-1.5 rounded-lg border border-gray-200 cursor-pointer hover:bg-gray-50 transition-all"
                :class="{
                  'bg-green-50 border-green-300 text-green-700': filters.favorite
                }"
              >
                <input v-model="filters.favorite" type="checkbox" class="hidden" />
                <span class="text-sm">仅收藏</span>
              </label>
            </div>
          </div>
        </div>

        <div class="flex justify-between items-center mt-5 pt-4 border-t border-gray-100">
          <button
            @click="resetFilters"
            class="text-sm text-gray-500 hover:text-gray-700 transition flex items-center gap-1"
          >
            <XCircle class="w-4 h-4" />
            重置筛选
          </button>
          <button
            @click="showFilterPanel = false"
            class="px-6 py-2 rounded-xl bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white font-medium shadow-lg shadow-blue-300 transition-all flex items-center gap-2"
          >
            <Check class="w-4 h-4" />
            应用筛选
          </button>
        </div>
      </div>

      <div
        v-if="activeFilterCount > 0"
        class="flex flex-wrap gap-2 mb-3"
      >
        <span
          v-if="filters.search"
          class="inline-flex items-center px-2 py-1 bg-gray-100 rounded-full text-xs text-gray-700 gap-1"
        >
          <Search class="w-3 h-3" />
          {{ filters.search }}
          <button
            @click="removeFilter('search')"
            class="hover:text-red-500"
          >
            <X class="w-3 h-3" />
          </button>
        </span>
        <span
          v-if="filters.priceMin || filters.priceMax"
          class="inline-flex items-center px-2 py-1 bg-amber-50 rounded-full text-xs text-amber-700 gap-1"
        >
          <DollarSign class="w-3 h-3" />
          {{ filters.priceMin || '0' }} - {{ filters.priceMax || '∞' }}万円
          <button
            @click="removeFilter('price')"
            class="hover:text-red-500"
          >
            <X class="w-3 h-3" />
          </button>
        </span>
        <span
          v-if="filters.areaMin || filters.areaMax"
          class="inline-flex items-center px-2 py-1 bg-blue-50 rounded-full text-xs text-blue-700 gap-1"
        >
          <Maximize class="w-3 h-3" />
          {{ filters.areaMin || '0' }} - {{ filters.areaMax || '∞' }}m²
          <button
            @click="removeFilter('area')"
            class="hover:text-red-500"
          >
            <X class="w-3 h-3" />
          </button>
        </span>
        <span
          v-if="filters.propertyTypes.length > 0"
          class="inline-flex items-center px-2 py-1 bg-purple-50 rounded-full text-xs text-purple-700 gap-1"
        >
          <Home class="w-3 h-3" />
          {{ filters.propertyTypes.join(', ') }}
          <button
            @click="removeFilter('propertyTypes')"
            class="hover:text-red-500"
          >
            <X class="w-3 h-3" />
          </button>
        </span>
        <span
          v-if="filters.walking"
          class="inline-flex items-center px-2 py-1 bg-teal-50 rounded-full text-xs text-teal-700 gap-1"
        >
          <Footprints class="w-3 h-3" />
          {{ filters.walking }}分以内
          <button
            @click="removeFilter('walking')"
            class="hover:text-red-500"
          >
            <X class="w-3 h-3" />
          </button>
        </span>
        <span
          v-if="filters.room"
          class="inline-flex items-center px-2 py-1 bg-gray-100 rounded-full text-xs text-gray-700 gap-1"
        >
          <Layout class="w-3 h-3" />
          {{ filters.room }}
          <button
            @click="removeFilter('room')"
            class="hover:text-red-500"
          >
            <X class="w-3 h-3" />
          </button>
        </span>
        <span
          v-if="filters.pet"
          class="inline-flex items-center px-2 py-1 bg-pink-50 rounded-full text-xs text-pink-700 gap-1"
        >
          <Heart class="w-3 h-3" />
          可养宠
          <button
            @click="removeFilter('pet')"
            class="hover:text-red-500"
          >
            <X class="w-3 h-3" />
          </button>
        </span>
        <span
          v-if="filters.favorite"
          class="inline-flex items-center px-2 py-1 bg-rose-50 rounded-full text-xs text-rose-700 gap-1"
        >
          <Heart class="w-3 h-3" />
          仅收藏
          <button
            @click="removeFilter('favorite')"
            class="hover:text-red-500"
          >
            <X class="w-3 h-3" />
          </button>
        </span>
      </div>
    </div>

    <div class="mb-4 flex justify-between items-center text-sm text-gray-600">
      <template v-if="loading">
        <div class="skeleton-shimmer h-5 w-20 rounded skeleton-pulse"></div>
      </template>
      <template v-else>
        <span>共 {{ documents.length }} 个房产</span>
        <span v-if="sortedDocuments.length < documents.length" class="text-gray-500">显示 {{ sortedDocuments.length }} 个结果</span>
      </template>
    </div>

    <div v-if="loading" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
      <DocumentCardSkeleton :count="6" />
    </div>

    <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          <DocumentCard
            v-for="doc in pageDocuments"
            :key="doc.id"
            :doc="doc"
            :locations="locations"
            :get-status="getDocStatus"
            @open="openDetailModal"
            @toggle-favorite="onFavoriteToggle"
            @delete="onDelete"
          />
    </div>

    <div v-if="totalPages > 1" class="mt-6 flex items-center justify-center gap-2">
      <button
        @click="goToPage(currentPage - 1)"
        :disabled="currentPage === 1"
        class="w-9 h-9 rounded-lg flex items-center justify-center text-gray-600 hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition"
      >
        <ChevronLeft class="w-4 h-4" />
      </button>
      <span class="px-3 py-1.5 text-sm text-gray-500">
        {{ (currentPage - 1) * 12 + 1 }}-{{ Math.min(currentPage * 12, sortedDocuments.length) }} / {{ sortedDocuments.length }}
      </span>
      <button
        v-for="page in pageNumbers"
        :key="page"
        @click="goToPage(page as number)"
        :disabled="page === '...'"
        :class="[
          'w-9 h-9 rounded-lg flex items-center justify-center text-sm font-medium transition',
          page === currentPage ? 'bg-blue-500 text-white' : 'text-gray-600 hover:bg-gray-100',
          page === '...' ? 'cursor-default' : ''
        ]"
      >
        {{ page }}
      </button>
      <button
        @click="goToPage(currentPage + 1)"
        :disabled="currentPage === totalPages"
        class="w-9 h-9 rounded-lg flex items-center justify-center text-gray-600 hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition"
      >
        <ChevronRight class="w-4 h-4" />
      </button>
      <input
        v-model.number="jumpPageInput"
        type="number"
        min="1"
        :max="totalPages"
        @keydown.enter="() => { if (jumpPageInput) goToPage(jumpPageInput); jumpPageInput = null; }"
        placeholder="页"
        class="w-14 px-2 py-1.5 text-sm border border-gray-200 rounded-lg text-center focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
    </div>
  </div>

  <Teleport to="body">
    <DetailModal
      v-if="showDetailModal"
      :doc="currentDoc"
      :preview-url="previewUrl"
      @close="closeDetailModal"
      @saved="onDetailSaved"
      @delete="onDetailDelete"
      @retryOCR="onDetailRetryOCR"
      @retryLLM="onDetailRetryLLM"
    />
  </Teleport>

  <UploadModal :is-open="showUploadModal" @close="showUploadModal = false" @uploaded="onUploaded" />
  <LocationModal :is-open="showLocationModal" @close="onLocationModalClose" @locations-updated="loadLocations" />
   <StationModal
     :is-open="showStationModal"
     :documents="documents"
     :locations="locations"
     @close="showStationModal = false"
   />
   <ModelModal :is-open="showModelModal" @close="onModelModalClose" />
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

