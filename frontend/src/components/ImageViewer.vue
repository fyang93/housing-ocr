<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import {
  X,
  ZoomIn,
  ZoomOut,
  RotateCw,
  RotateCcw,
} from 'lucide-vue-next';

interface Props {
  docId: number;
  docName: string;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  close: [];
}>();

const show = ref(true);
const scale = ref(1);
const rotation = ref(0);
const fitMode = ref<'long' | 'short'>('long');
const translateX = ref(0);
const translateY = ref(0);
const isDragging = ref(false);
const isMultitouch = ref(false);
const lastTouchX = ref(0);
const lastTouchY = ref(0);
const initialPinchDistance = ref(0);
const initialScale = ref(1);
const imageLoaded = ref(false);

const imageUrl = ref(`/api/preview/${props.docId}`);
const naturalWidth = ref(1200);
const naturalHeight = ref(1600);
const imageLoadAttempted = ref(false);

const containerRef = ref<HTMLElement | null>(null);
const imageRef = ref<HTMLImageElement | null>(null);

const loadImageInfo = async () => {
  if (imageLoadAttempted.value) return;
  imageLoadAttempted.value = true;
  
  try {
    const res = await fetch(`/api/preview-info/${props.docId}`);
    const data = await res.json();
    if (data.width && data.height) {
      naturalWidth.value = data.width;
      naturalHeight.value = data.height;
    }
  } catch (e) {
    console.error('Failed to load image info:', e);
  }
};

const fitToScreen = () => {
  if (!containerRef.value || !imageRef.value) return;

  const containerWidth = containerRef.value.clientWidth;
  const containerHeight = containerRef.value.clientHeight;
  const containerRatio = containerWidth / containerHeight;
  const imgRatio = naturalWidth.value / naturalHeight.value;

  if (fitMode.value === 'long') {
    if (imgRatio > containerRatio) {
      scale.value = Math.min(containerWidth, naturalWidth.value) / naturalWidth.value;
    } else {
      scale.value = Math.min(containerHeight, naturalHeight.value) / naturalHeight.value;
    }
  } else {
    if (imgRatio > containerRatio) {
      scale.value = containerHeight / naturalHeight.value;
    } else {
      scale.value = containerWidth / naturalWidth.value;
    }
  }
  translateX.value = 0;
  translateY.value = 0;
};

const actualSize = () => {
  scale.value = 1;
  translateX.value = 0;
  translateY.value = 0;
};

const zoomIn = () => {
  scale.value = Math.min(scale.value * 1.2, 5);
};

const zoomOut = () => {
  scale.value = Math.max(scale.value / 1.2, 0.1);
};

const rotateRight = () => {
  rotation.value = (rotation.value + 90) % 360;
};

const rotateLeft = () => {
  rotation.value = (rotation.value - 90 + 360) % 360;
};

const toggleFitMode = () => {
  fitMode.value = fitMode.value === 'long' ? 'short' : 'long';
  fitToScreen();
};

let lastDoubleClickTime = 0;
const DOUBLE_CLICK_THRESHOLD = 300;

const handleDoubleClick = (e: MouseEvent) => {
  e.preventDefault();
  const now = Date.now();
  if (now - lastDoubleClickTime < DOUBLE_CLICK_THRESHOLD) return;
  lastDoubleClickTime = now;
  toggleFitMode();
};

const handleMouseDown = (e: MouseEvent) => {
  if (scale.value <= 0) return;
  e.preventDefault();
  isDragging.value = true;
  lastTouchX.value = e.clientX;
  lastTouchY.value = e.clientY;
};

const handleMouseMove = (e: MouseEvent) => {
  if (!isDragging.value || isMultitouch.value) return;
  e.preventDefault();
  translateX.value += e.clientX - lastTouchX.value;
  translateY.value += e.clientY - lastTouchY.value;
  lastTouchX.value = e.clientX;
  lastTouchY.value = e.clientY;
};

const handleMouseUp = () => {
  isDragging.value = false;
  isMultitouch.value = false;
};

const getPinchDistance = (touches: TouchList) => {
  const dx = touches[0].clientX - touches[1].clientX;
  const dy = touches[0].clientY - touches[1].clientY;
  return Math.sqrt(dx * dx + dy * dy);
};

const handleTouchStart = (e: TouchEvent) => {
  if (e.touches.length === 1) {
    isDragging.value = true;
    isMultitouch.value = false;
    lastTouchX.value = e.touches[0].clientX;
    lastTouchY.value = e.touches[0].clientY;
  } else if (e.touches.length === 2) {
    e.preventDefault();
    isMultitouch.value = true;
    initialPinchDistance.value = getPinchDistance(e.touches);
    initialScale.value = scale.value;
  }
};

const handleTouchMove = (e: TouchEvent) => {
  if (e.touches.length === 1 && isDragging.value && !isMultitouch.value) {
    e.preventDefault();
    const dx = e.touches[0].clientX - lastTouchX.value;
    const dy = e.touches[0].clientY - lastTouchY.value;
    translateX.value += dx;
    translateY.value += dy;
    lastTouchX.value = e.touches[0].clientX;
    lastTouchY.value = e.touches[0].clientY;
  } else if (e.touches.length === 2) {
    e.preventDefault();
    const currentDistance = getPinchDistance(e.touches);
    const pinchRatio = currentDistance / initialPinchDistance.value;
    scale.value = Math.max(0.1, Math.min(initialScale.value * pinchRatio, 5));
  }
};

const handleTouchEnd = () => {
  isMultitouch.value = false;
};

const handleWheel = (e: WheelEvent) => {
  if (Math.abs(e.deltaY) < 10) return;
  e.preventDefault();
  const delta = e.deltaY > 0 ? 0.9 : 1.1;
  scale.value = Math.max(0.1, Math.min(scale.value * delta, 5));
};

const handleKeyDown = (e: KeyboardEvent) => {
  if (e.key === 'Escape') {
    emit('close');
  } else if (e.key === '+' || e.key === '=') {
    zoomIn();
  } else if (e.key === '-') {
    zoomOut();
  } else if (e.key === 'f') {
    toggleFitMode();
  } else if (e.key === '0') {
    actualSize();
  }
};

const handleImageLoad = () => {
  imageLoaded.value = true;
  if (imageRef.value) {
    naturalWidth.value = imageRef.value.naturalWidth;
    naturalHeight.value = imageRef.value.naturalHeight;
  }
  requestAnimationFrame(() => {
    fitToScreen();
  });
};

onMounted(() => {
  loadImageInfo();
  window.addEventListener('keydown', handleKeyDown);
  window.addEventListener('mouseup', handleMouseUp);
  window.addEventListener('mousemove', handleMouseMove);
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown);
  window.removeEventListener('mouseup', handleMouseUp);
  window.removeEventListener('mousemove', handleMouseMove);
});
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 bg-black/90 backdrop-blur-md z-[60]">
      <div class="absolute top-0 left-0 right-0 p-3 flex justify-between items-start z-10">
        <h3 class="text-white font-medium truncate px-3 py-1.5 rounded-lg bg-black/40 backdrop-blur-md">{{ docName }}</h3>
        <button
          @click="emit('close')"
          class="w-8 h-8 rounded-full hover:bg-white/20 flex items-center justify-center text-white transition"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <div
        ref="containerRef"
        class="absolute inset-0 flex items-center justify-center"
        style="touch-action: none; user-select: none; -webkit-user-select: none; -webkit-user-drag: none;"
        @dblclick="handleDoubleClick"
        @mousedown="handleMouseDown"
        @touchstart="handleTouchStart"
        @touchmove="handleTouchMove"
        @touchend="handleTouchEnd"
        @wheel="handleWheel"
      >
        <div
          v-if="!imageLoaded"
          class="absolute inset-0 flex items-center justify-center"
        >
          <div class="text-white text-center">
            <div class="w-12 h-12 border-4 border-white/20 border-t-white rounded-full animate-spin mx-auto mb-3"></div>
            <p class="text-sm">加载中...</p>
          </div>
        </div>
        <div
          v-show="imageLoaded"
          class="absolute inset-0 flex items-center justify-center"
        >
          <img
            ref="imageRef"
            :src="imageUrl"
            class="max-w-none max-h-none object-contain will-change-transform transition-transform duration-200 ease-out"
            :class="{ 'cursor-grab': !isDragging && !isMultitouch, 'cursor-grabbing': isDragging && !isMultitouch }"
            draggable="false"
            :style="{
              width: `${naturalWidth}px`,
              height: `${naturalHeight}px`,
              transform: `translate(${translateX}px, ${translateY}px) rotate(${rotation}deg) scale(${scale})`,
            }"
            @load="handleImageLoad"
            @dragstart.prevent
            alt="文档预览"
          />
        </div>
      </div>

      <div class="absolute bottom-0 left-0 right-0 p-3 flex justify-center items-center gap-2 z-10">
        <button
          @click="zoomOut"
          class="w-10 h-10 rounded-lg bg-black/40 backdrop-blur-md hover:bg-white/20 flex items-center justify-center text-white transition"
          title="缩小"
        >
          <ZoomOut class="w-5 h-5" />
        </button>
        <button
          @click="actualSize"
          class="px-4 h-10 rounded-lg bg-black/40 backdrop-blur-md hover:bg-white/20 flex items-center justify-center text-white transition font-medium"
          title="实际大小"
        >
          {{ Math.round(scale * 100) }}%
        </button>
        <button
          @click="zoomIn"
          class="w-10 h-10 rounded-lg bg-black/40 backdrop-blur-md hover:bg-white/20 flex items-center justify-center text-white transition"
          title="放大"
        >
          <ZoomIn class="w-5 h-5" />
        </button>

        <div class="w-px h-6 bg-white/30 mx-2"></div>

        <button
          @click="rotateLeft"
          class="w-10 h-10 rounded-lg bg-black/40 backdrop-blur-md hover:bg-white/20 flex items-center justify-center text-white transition"
          title="向左旋转"
        >
          <RotateCcw class="w-5 h-5" />
        </button>
        <button
          @click="rotateRight"
          class="w-10 h-10 rounded-lg bg-black/40 backdrop-blur-md hover:bg-white/20 flex items-center justify-center text-white transition"
          title="向右旋转"
        >
          <RotateCw class="w-5 h-5" />
        </button>
      </div>
    </div>
  </Teleport>
</template>
