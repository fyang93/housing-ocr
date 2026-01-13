<script setup lang="ts">
import { ref, reactive, watch } from 'vue';
import { uploadDocument } from '@/api';
import {
  CloudUpload,
  FileText,
  X,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Copy,
} from 'lucide-vue-next';

interface FileItem {
  file: File;
  id: number;
  status: 'pending' | 'uploading' | 'done' | 'skipped' | 'error';
  progress: number;
  error?: string;
}

interface Props {
  isOpen: boolean;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  close: [];
  uploaded: [docs: Array<{ id: number; filename: string }>];
}>();

const fileItems = ref<FileItem[]>([]);
const uploading = ref(false);
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
      if (!fileItems.value.some((f) => f.file.name === file.name)) {
        fileItems.value.push({
          file,
          id: Date.now() + Math.random(),
          status: 'pending',
          progress: 0,
        });
      }
    }
  }
  input.value = '';
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
      if (!fileItems.value.some((f) => f.file.name === file.name)) {
        fileItems.value.push({
          file,
          id: Date.now() + Math.random(),
          status: 'pending',
          progress: 0,
        });
      }
    }
  }
};

const removeFile = (index: number) => {
  fileItems.value.splice(index, 1);
};

const uploadFiles = async () => {
  if (fileItems.value.length === 0) return;

  uploading.value = true;
  const pendingFiles = fileItems.value.filter(f => f.status === 'pending' || f.status === 'error');
  const uploadedDocs: Array<{ id: number; filename: string }> = [];

  const uploadWithProgress = async (item: FileItem) => {
    item.status = 'uploading';
    item.progress = 0;

    const totalChunks = 10;
    for (let i = 0; i <= totalChunks; i++) {
      await new Promise(resolve => setTimeout(resolve, 100));
      item.progress = (i / totalChunks) * 100;
    }

    try {
      const result = await uploadDocument(item.file);
      if (result.duplicate) {
        item.status = 'skipped';
        item.progress = 100;
      } else {
        item.status = 'done';
        item.progress = 100;
        uploadedDocs.push({ id: result.id, filename: result.filename });
      }
    } catch (error) {
      item.status = 'error';
      item.error = error instanceof Error ? error.message : '上传失败';
    }
  };

  await Promise.all(pendingFiles.map(item => uploadWithProgress(item)));

  uploading.value = false;

  setTimeout(() => {
    emit('uploaded', uploadedDocs);
  }, 200);
};

const close = () => {
  fileItems.value = [];
  uploading.value = false;
  isDragging.value = false;
  emit('close');
};

watch(() => props.isOpen, (newVal) => {
  if (newVal) {
    fileItems.value = [];
    isDragging.value = false;
  }
});
</script>

<template>
  <Teleport to="body">
    <div v-if="isOpen" class="fixed inset-0 modal-overlay z-50 overflow-y-auto" @click.self="close">
      <div class="min-h-screen px-4 py-8 flex items-center justify-center">
        <div class="bg-white rounded-2xl shadow-2xl max-w-2xl w-full border border-gray-100">
          <div class="flex justify-between items-center px-6 py-4 border-b border-gray-100 flex-shrink-0">
            <h2 class="text-xl font-bold text-gray-900">上传文档</h2>
            <button @click="close" class="w-8 h-8 rounded-lg hover:bg-gray-100 transition flex items-center justify-center text-gray-400 hover:text-gray-600">
              <X class="w-5 h-5" />
            </button>
          </div>
          <div class="flex flex-col max-h-[60vh]">
            <div class="p-6 flex-shrink-0">
              <div
                class="drop-zone border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition"
                :class="[
                  uploading ? 'pointer-events-none opacity-50' : '',
                  isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-gray-50 hover:bg-gray-100'
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
            </div>

            <div v-if="fileItems.length > 0" class="flex-1 overflow-y-auto px-6">
              <TransitionGroup name="file-list" tag="div" class="space-y-2 pb-2">
                <div
                  v-for="(item, index) in fileItems"
                  :key="item.id"
                  class="file-item"
                >
                  <div class="file-bg" :style="{ width: item.progress + '%' }" :class="item.status"></div>
                  <div class="file-content">
                    <div class="file-icon" :class="item.status">
                      <FileText v-if="item.status === 'pending'" class="w-5 h-5" />
                      <Loader2 v-else-if="item.status === 'uploading'" class="w-5 h-5 spin" />
                      <CheckCircle2 v-else-if="item.status === 'done'" class="w-5 h-5" />
                      <Copy v-else-if="item.status === 'skipped'" class="w-5 h-5" />
                      <AlertCircle v-else-if="item.status === 'error'" class="w-5 h-5" />
                    </div>
                    <div class="file-info">
                      <p class="file-name">{{ item.file.name }}</p>
                      <p class="file-meta">{{ formatFileSize(item.file.size) }}</p>
                    </div>
                    <div class="file-status">
                      <span v-if="item.status === 'done'" class="status-text done">完成</span>
                      <span v-if="item.status === 'skipped'" class="status-text skipped">已存在</span>
                      <span v-if="item.status === 'error'" class="status-text error">{{ item.error }}</span>
                    </div>
                    <button
                      v-if="item.status === 'pending' || item.status === 'error'"
                      class="remove-btn"
                      @click="removeFile(index)"
                    >
                      <X class="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </TransitionGroup>
            </div>

            <div class="flex-shrink-0 px-6 py-4 border-t border-gray-100 bg-white">
              <div class="flex gap-3">
                <button
                  @click="uploadFiles"
                  :disabled="fileItems.filter(f => f.status === 'pending' || f.status === 'error').length === 0 || uploading"
                  class="flex-1 bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white px-6 py-3 rounded-xl font-medium shadow-lg shadow-blue-300 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  <Loader2 v-if="uploading" class="animate-spin w-5 h-5" />
                  {{ uploading ? '上传中...' : '开始上传' }}
                </button>
                <button
                  @click="close"
                  :disabled="uploading"
                  class="px-6 py-3 rounded-xl border border-gray-200 hover:bg-gray-50 transition font-medium disabled:opacity-50"
                >
                  取消
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.file-list-move,
.file-list-enter-active,
.file-list-leave-active {
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.file-list-enter-from {
  opacity: 0;
  transform: translateX(-30px);
}

.file-list-leave-to {
  opacity: 0;
  transform: translateX(30px);
}

.file-list-leave-active {
  position: absolute;
  width: 100%;
}

.file-item {
  position: relative;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  overflow: hidden;
}

.file-bg {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  transition: width 0.3s ease;
}

.file-bg.uploading {
  background: #eff6ff;
}

.file-bg.done {
  background: #ecfdf5;
}

.file-bg.skipped {
  background: #fffbeb;
}

.file-bg.error {
  background: #fef2f2;
}

.file-content {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
}

.file-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  flex-shrink: 0;
  background: #fff;
}

.file-icon.pending {
  color: #6b7280;
}

.file-icon.uploading {
  color: #2563eb;
}

.file-icon.done {
  color: #16a34a;
}

.file-icon.skipped {
  color: #d97706;
}

.file-icon.error {
  color: #dc2626;
}

.file-info {
  flex: 1;
  min-width: 0;
}

.file-name {
  font-size: 13px;
  font-weight: 500;
  color: #111827;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-meta {
  font-size: 11px;
  color: #9ca3af;
  margin-top: 2px;
}

.file-status {
  flex-shrink: 0;
}

.status-text {
  font-size: 11px;
  font-weight: 500;
}

.status-text.done {
  color: #16a34a;
}

.status-text.skipped {
  color: #d97706;
}

.status-text.error {
  color: #dc2626;
}

.remove-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  color: #d1d5db;
  transition: all 0.15s;
}

.remove-btn:hover {
  background: #fee2e2;
  color: #dc2626;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
