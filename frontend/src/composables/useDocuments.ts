import { ref, computed, onMounted } from 'vue';
import type { Document, FilterState, PropertyDetails } from '@/types';
import { fetchDocuments, cleanupDocuments } from '@/api';

const ITEMS_PER_PAGE = 12;

export function useDocuments() {
  const documents = ref<Document[]>([]);
  const filteredDocuments = ref<Document[]>([]);
  const currentPage = ref(1);
  const loading = ref(true);
  const error = ref<string | null>(null);

  const filters = ref<FilterState>({
    search: '',
    priceMin: null,
    priceMax: null,
    areaMin: null,
    areaMax: null,
    walking: null,
    propertyTypes: [],
    room: null,
    pet: false,
    favorite: false,
  });

  const loadDocuments = async () => {
    try {
      loading.value = true;
      const data = await fetchDocuments();
      documents.value = data.documents;
      applyFilters();
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载失败';
    } finally {
      loading.value = false;
    }
  };

  const applyFilters = () => {
    filteredDocuments.value = documents.value.filter((doc) => {
      const props = doc.properties || {};

      const matchSearch =
        !filters.value.search ||
        (props.property_name || '').toLowerCase().includes(filters.value.search.toLowerCase()) ||
        (props.address || '').toLowerCase().includes(filters.value.search.toLowerCase());

      const matchPrice =
        (!filters.value.priceMin || !props.price || props.price >= filters.value.priceMin) &&
        (!filters.value.priceMax || !props.price || props.price <= filters.value.priceMax);

      const matchArea =
        (!filters.value.areaMin || !props.exclusive_area || props.exclusive_area >= filters.value.areaMin) &&
        (!filters.value.areaMax || !props.exclusive_area || props.exclusive_area <= filters.value.areaMax);

      const matchWalking =
        !filters.value.walking || !props.walking_minutes || props.walking_minutes <= filters.value.walking;

      const matchType =
        filters.value.propertyTypes.length === 0 ||
        (props.property_type && filters.value.propertyTypes.includes(props.property_type));

      const matchRoom = !filters.value.room || !props.room_layout || props.room_layout === filters.value.room;

      const matchPet = !filters.value.pet || (props.pet_policy && props.pet_policy.includes('可'));

      const matchFavorite = !filters.value.favorite || doc.favorite === 1;

      return matchSearch && matchPrice && matchArea && matchWalking && matchType && matchRoom && matchPet && matchFavorite;
    });

    currentPage.value = 1;
  };

  const sortedDocuments = computed(() => {
    return [...filteredDocuments.value].sort((a, b) => {
      if (b.favorite !== a.favorite) return b.favorite - a.favorite;
      const statusA = getDocStatus(a);
      const statusB = getDocStatus(b);
      return statusA.priority - statusB.priority;
    });
  });

  const totalPages = computed(() => Math.ceil(sortedDocuments.value.length / ITEMS_PER_PAGE));

  const pageDocuments = computed(() => {
    const start = (currentPage.value - 1) * ITEMS_PER_PAGE;
    return sortedDocuments.value.slice(start, start + ITEMS_PER_PAGE);
  });

  const getDocStatus = (doc: Document) => {
    const props = doc.properties || {};
    const hasValidProperties = props.address && props.address.trim() !== '' && props.price && props.price !== null;
    const hasOcrText = doc.ocr_text && doc.ocr_text.trim().length > 0;

    if (doc.llm_status === 'done' && doc.ocr_status === 'done' && hasValidProperties) {
      return { priority: 2, status: '完成', statusClass: 'bg-emerald-500' };
    } else if (doc.ocr_status === 'done' && hasOcrText && (doc.llm_status === 'pending' || doc.llm_status === 'processing')) {
      return { priority: 3, status: '处理中', statusClass: 'bg-blue-500' };
    } else if (doc.ocr_status === 'processing' || doc.llm_status === 'processing') {
      return { priority: 3, status: '处理中', statusClass: 'bg-amber-500' };
    } else if (doc.ocr_status === 'done' && !hasOcrText) {
      return { priority: 3, status: '处理中', statusClass: 'bg-amber-500' };
    } else if (doc.ocr_status === 'pending') {
      return { priority: 3, status: '处理中', statusClass: 'bg-amber-500' };
    } else if (doc.ocr_status === 'failed' || doc.llm_status === 'failed') {
      return { priority: 4, status: '提取失败', statusClass: 'bg-red-500' };
    }
    return { priority: 3, status: '处理中', statusClass: 'bg-amber-500' };
  };

  const goToPage = (page: number) => {
    if (page >= 1 && page <= totalPages.value) {
      currentPage.value = page;
    }
  };

  const handleCleanup = async () => {
    const count = documents.value.filter((d) => d.favorite !== 1).length;
    if (count === 0) {
      alert('没有需要清理的文档');
      return;
    }
    if (!confirm(`确定要删除所有 ${count} 个非收藏文档吗？此操作不可恢复！`)) return;

    const result = await cleanupDocuments();
    if (result.success) {
      alert(`已删除 ${result.deleted_count} 个文档`);
      await loadDocuments();
    } else {
      alert('清理失败');
    }
  };

  const updateDocumentProperties = (docId: number, newProperties: PropertyDetails) => {
    const doc = documents.value.find(d => d.id === docId);
    if (doc) {
      doc.properties = newProperties;
    }
  };

  const addDocument = (docData: { id: number; filename: string }) => {
    const newDoc: Document = {
      id: docData.id,
      filename: docData.filename,
      upload_time: new Date().toISOString(),
      ocr_status: 'pending',
      llm_status: 'pending',
      favorite: 0,
    };
    documents.value.unshift(newDoc);
  };

  const preloadImages = () => {
    const docsToPreload = filteredDocuments.value.slice(
      currentPage.value * ITEMS_PER_PAGE,
      (currentPage.value + 2) * ITEMS_PER_PAGE
    );

    docsToPreload.forEach(doc => {
      const img = new Image();
      img.src = `/api/preview/${doc.id}`;
    });
  };

  onMounted(() => {
    loadDocuments();
  });

  return {
    documents,
    filteredDocuments,
    sortedDocuments,
    pageDocuments,
    currentPage,
    totalPages,
    filters,
    loading,
    error,
    loadDocuments,
    applyFilters,
    goToPage,
    handleCleanup,
    getDocStatus,
    updateDocumentProperties,
    addDocument,
    preloadImages,
  };
}
