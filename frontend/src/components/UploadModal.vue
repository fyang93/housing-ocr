<script setup lang="ts">
import { ref, watch } from 'vue';
import { uploadDocument } from '@/api';
import {
  CloudUpload,
  FileText,
  X,
  Loader2,
} from 'lucide-vue-next';

interface Props {
  isOpen: boolean;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  close: [];
  uploaded: [docs: Array<{ id: number; filename: string }>];
}>();

const selectedFiles = ref<File[]>([]);
const uploading = ref(false);
const uploadMessage = ref('');
const uploadMessageType = ref<'success' | 'info' | 'error'>('info');
const isDragging = ref(false);

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
};

const handleFileSelect = (e: Event) => {
  const input = e.target as HTMLInputElement;
  if (input.files) {
    for (const file of input.files) {
      if (!selectedFiles.value.some((f) => f.name === file.name)) {
        selectedFiles.value.push(file);
      }
    }
  }
  input.value = '';
  uploadMessage.value = '';
};

const handleDragOver = (e: DragEvent) => {
  e.preventDefault();
  isDragging.value = true;
};

const handleDragLeave = (e: DragEvent) => {
  e.preventDefault();
  isDragging.value = false;
};

const handleDrop = (e: DragEvent) => {
  e.preventDefault();
  isDragging.value = false;
  if (e.dataTransfer?.files) {
    for (const file of e.dataTransfer.files) {
      if (!selectedFiles.value.some((f) => f.name === file.name)) {
        selectedFiles.value.push(file);
      }
    }
  }
  uploadMessage.value = '';
};

const removeFile = (index: number) => {
  selectedFiles.value.splice(index, 1);
};

const uploadFiles = async () => {
  if (selectedFiles.value.length === 0) return;

  uploading.value = true;
  uploadMessage.value = '';
  let uploadedCount = 0;
  let duplicateCount = 0;
  const uploadedDocs: Array<{ id: number; filename: string }> = [];

  for (const file of selectedFiles.value) {
    try {
      const result = await uploadDocument(file);
      if (!result.duplicate) {
        uploadedDocs.push({ id: result.id, filename: result.filename });
        uploadedCount++;
      } else {
        duplicateCount++;
      }
    } catch (error) {
      console.error('上传失败:', file.name, error);
    }
  }

  if (uploadedCount > 0 && duplicateCount > 0) {
    uploadMessage.value = `成功上传 ${uploadedCount} 个文件，跳过 ${duplicateCount} 个重复文件`;
    uploadMessageType.value = 'success';
  } else if (uploadedCount > 0) {
    uploadMessage.value = `成功上传 ${uploadedCount} 个文件`;
    uploadMessageType.value = 'success';
  } else if (duplicateCount > 0) {
    uploadMessage.value = `跳过 ${duplicateCount} 个重复文件`;
    uploadMessageType.value = 'info';
  } else {
    uploadMessage.value = '上传完成';
    uploadMessageType.value = 'info';
  }

  selectedFiles.value = [];
  uploading.value = false;

  setTimeout(() => {
    emit('uploaded', uploadedDocs);
    emit('close');
  }, 1500);
};

const close = () => {
  selectedFiles.value = [];
  uploadMessage.value = '';
  isDragging.value = false;
  emit('close');
};

watch(() => props.isOpen, (newVal) => {
  if (newVal) {
    selectedFiles.value = [];
    uploadMessage.value = '';
    isDragging.value = false;
  }
});
</script>

<template>
  <Teleport to="body">
    <div v-if="isOpen" class="fixed inset-0 modal-overlay z-50 overflow-y-auto" @click.self="close">
      <div class="min-h-screen px-4 py-8 flex items-center justify-center">
        <div class="bg-white rounded-2xl shadow-2xl max-w-2xl w-full border border-gray-100">
          <div class="flex justify-between items-center px-6 py-4 border-b border-gray-100">
            <h2 class="text-xl font-bold text-gray-900">上传文档</h2>
            <button @click="close" class="w-8 h-8 rounded-lg hover:bg-gray-100 transition flex items-center justify-center text-gray-400 hover:text-gray-600">
              <X class="w-5 h-5" />
            </button>
          </div>
          <div class="p-6">
            <div
              class="drop-zone border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition"
              :class="[
                isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-gray-50',
                isDragging ? 'hover:border-blue-500 hover:bg-blue-50' : 'hover:bg-gray-100'
              ]"
              @click="($refs.fileInput as HTMLInputElement)?.click()"
              @dragover.prevent="handleDragOver"
              @dragleave.prevent="handleDragLeave"
              @drop.prevent="handleDrop"
            >
              <input ref="fileInput" type="file" multiple accept=".pdf,.png,.jpg,.jpeg" class="hidden" @change="handleFileSelect" />
              <div class="text-gray-500">
                <div class="w-16 h-16 mx-auto mb-4 rounded-2xl bg-blue-100 flex items-center justify-center">
                  <CloudUpload class="w-8 h-8 text-blue-500" />
                </div>
                <p class="text-lg font-medium text-gray-700">拖拽文件到此处</p>
                <p class="text-sm text-gray-500 mt-1">或点击选择文件</p>
                <p class="text-xs text-gray-400 mt-3">支持 PDF、PNG、JPG 格式</p>
              </div>
            </div>

            <div v-if="uploadMessage" :class="[
              'mt-4 p-4 rounded-xl text-sm text-center',
              uploadMessageType === 'success' ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-600'
            ]">
              {{ uploadMessage }}
            </div>

            <div v-if="selectedFiles.length > 0" class="mt-4 space-y-2">
              <div v-for="(file, index) in selectedFiles" :key="file.name" class="flex justify-between items-center p-4 bg-gradient-to-r from-gray-50 to-gray-100 rounded-xl border border-gray-200">
                <div class="flex items-center gap-3 overflow-hidden">
                  <div class="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
                    <FileText class="w-5 h-5 text-blue-600" />
                  </div>
                  <div class="flex-1 min-w-0">
                    <p class="text-sm font-medium text-gray-900 truncate">{{ file.name }}</p>
                    <p class="text-xs text-gray-500">{{ formatFileSize(file.size) }}</p>
                  </div>
                </div>
                <button @click="removeFile(index)" class="text-gray-400 hover:text-red-500 hover:bg-red-50 p-2 rounded-lg transition-all">
                  <X class="w-5 h-5" />
                </button>
              </div>
            </div>

            <div class="mt-6 flex gap-3">
              <button
                @click="uploadFiles"
                :disabled="selectedFiles.length === 0 || uploading"
                class="flex-1 bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white px-6 py-3 rounded-xl font-medium shadow-lg shadow-blue-300 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                <Loader2 v-if="uploading" class="animate-spin w-5 h-5" />
                {{ uploading ? '上传中...' : '开始上传' }}
              </button>
              <button @click="close" class="px-6 py-3 rounded-xl border border-gray-200 hover:bg-gray-50 transition font-medium">
                取消
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
