<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import PhotoSwipeLightbox from 'photoswipe/lightbox';
import 'photoswipe/style.css';

interface Props {
  images: Array<{
    src: string;
    width?: number;
    height?: number;
    alt?: string;
    thumb?: string;
  }>;
  options?: Record<string, unknown>;
}

const props = withDefaults(defineProps<Props>(), {
  options: () => ({}),
});

const containerRef = ref<HTMLElement | null>(null);
let lightbox: PhotoSwipeLightbox | null = null;

const defaultOptions = {
  wheelToZoom: true,
  bgOpacity: 0.9,
  clickToZoomNonFullscreen: false,
  doubleTapSpeed: 300,
  imageClickAction: 'zoom',
  tapAction: 'zoom',
};

onMounted(() => {
  if (containerRef.value) {
    lightbox = new PhotoSwipeLightbox({
      container: containerRef.value,
      children: 'a',
      ...defaultOptions,
      ...props.options,
    });

    lightbox.init();
  }
});

onUnmounted(() => {
  lightbox?.destroy();
});

defineExpose({
  open: (index: number) => lightbox?.open(index),
});
</script>

<template>
  <div ref="containerRef" class="pswp-gallery" style="display: none;">
    <a
      v-for="(image, index) in images"
      :key="index"
      :href="image.src"
      :data-pswp-width="image.width || 1200"
      :data-pswp-height="image.height || 1600"
      :target="_blank"
    >
      <img :src="image.thumb || image.src" :alt="image.alt || ''" />
    </a>
  </div>
</template>
