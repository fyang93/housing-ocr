<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue';
import Sortable from 'sortablejs';
import { fetchModels, addModel, deleteModel, reorderModels } from '@/api';
import {
  Settings,
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
  modelsUpdated: [];
}>();

const models = ref<string[]>([]);
const newModelName = ref('');
let sortableInstance: Sortable | null = null;
const listContainer = ref<HTMLElement | null>(null);
const loading = ref(false);
let skipNextInit = false;

const loadModels = async () => {
  loading.value = true;
  try {
    const data = await fetchModels();
    models.value = data.models;
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
      ghostClass: 'bg-blue-50',
      handle: '[data-handle]',
      onEnd: async (evt) => {
        if (evt.oldIndex === evt.newIndex) return;

        const newModels = [...models.value];
        const [moved] = newModels.splice(evt.oldIndex!, 1);
        newModels.splice(evt.newIndex!, 0, moved);
        skipNextInit = true;
        models.value = newModels;

        try {
          await reorderModels(newModels);
          emit('modelsUpdated');
        } catch (error) {
          console.error('Failed to reorder models:', error);
          skipNextInit = true;
          await loadModels();
        }
      },
    });
  }
};

const handleAddModel = async () => {
  const name = newModelName.value.trim();
  if (!name) return;

  try {
    await addModel(name);
    newModelName.value = '';
    skipNextInit = true;
    await loadModels();
    emit('modelsUpdated');
  } catch (error) {
    console.error('Failed to add model:', error);
    alert('添加模型失败: ' + (error as Error).message);
  }
};

const handleDeleteModel = async (modelName: string) => {
  if (!confirm(`确定要删除模型 "${modelName}" 吗？`)) return;

  try {
    await deleteModel(modelName);
    skipNextInit = true;
    await loadModels();
    emit('modelsUpdated');
  } catch (error) {
    console.error('Failed to delete model:', error);
    alert('删除模型失败: ' + (error as Error).message);
  }
};

const handleClose = () => {
  emit('close');
};

watch(
  () => props.isOpen,
  (isOpen) => {
    if (isOpen) {
      loadModels();
      nextTick(() => {
        initSortable();
      });
    } else if (sortableInstance) {
      sortableInstance.destroy();
      sortableInstance = null;
    }
  }
);

watch(
  () => models.value,
  async () => {
    if (skipNextInit) {
      skipNextInit = false;
      return;
    }
    await nextTick();
    setTimeout(() => initSortable(), 50);
  }
);

onMounted(() => {
  if (props.isOpen) {
    loadModels();
    nextTick(() => {
      initSortable();
    });
  }
});
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-300"
      leave-active-class="transition-opacity duration-200"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="isOpen"
        class="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50"
        @click.self="handleClose"
      >
        <Transition
          enter-active-class="transition-all duration-300"
          leave-active-class="transition-all duration-200"
          enter-from-class="opacity-0 scale-95 translate-y-4"
          enter-to-class="opacity-100 scale-100 translate-y-0"
          leave-from-class="opacity-100 scale-100 translate-y-0"
          leave-to-class="opacity-0 scale-95 translate-y-4"
        >
          <div
            v-if="isOpen"
            class="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-hidden"
          >
            <div class="flex justify-between items-center px-6 py-4 border-b border-gray-100">
              <h2 class="text-xl font-bold text-gray-900">模型管理</h2>
              <button
                @click="handleClose"
                class="w-8 h-8 rounded-lg hover:bg-gray-100 transition flex items-center justify-center text-gray-400 hover:text-gray-600"
              >
                <X class="w-5 h-5" />
              </button>
            </div>

            <div class="p-6 overflow-y-auto max-h-[calc(90vh-120px)]">
              <div class="mb-5">
                <label class="block text-sm font-medium text-gray-700 mb-2">添加新模型</label>
                <div class="flex gap-2">
                  <input
                    v-model="newModelName"
                    type="text"
                    placeholder="例如: google/gemini-2.0-flash-exp:free"
                    class="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all bg-white shadow-sm"
                    @keyup.enter="handleAddModel"
                  />
                  <button
                    @click="handleAddModel"
                    class="px-5 py-2.5 rounded-xl bg-blue-500 hover:bg-blue-600 text-white font-medium shadow-md shadow-blue-300 transition-all"
                  >
                    添加
                  </button>
                </div>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">可用模型 <span class="text-xs text-gray-400">(可拖拽排序)</span></label>
                <div v-if="loading" class="flex justify-center py-8">
                  <Loader2 class="w-6 h-6 animate-spin text-blue-500" />
                </div>
                <div
                  v-else-if="models.length === 0"
                  class="text-center py-8 text-gray-500"
                >
                  <Settings class="w-12 h-12 mx-auto mb-3 text-gray-300" />
                  <p>暂无模型</p>
                </div>
                <div
                  v-else
                  ref="listContainer"
                  class="space-y-2 max-h-64 overflow-y-auto pr-1"
                >
                  <div
                    v-for="(model, index) in models"
                    :key="model"
                    class="flex items-center gap-3 p-3 rounded-xl border border-gray-200 bg-white hover:bg-gray-50 transition-all group"
                  >
                    <div
                      data-handle
                      class="cursor-move text-gray-400 hover:text-gray-600 transition-colors"
                    >
                      <GripVertical class="w-4 h-4" />
                    </div>
                    <div class="flex-1 min-w-0">
                      <p class="text-sm font-medium text-gray-900 truncate">{{ model }}</p>
                    </div>
                    <button
                      @click="handleDeleteModel(model)"
                      class="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 p-2 rounded-lg hover:bg-red-50 transition-all"
                    >
                      <Trash2 class="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>