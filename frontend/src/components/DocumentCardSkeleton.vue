<script setup lang="ts">
import { computed } from 'vue';

const props = withDefaults(defineProps<{ count?: number }>(), { count: 6 });

const skeletonArray = computed(() => Array.from({ length: props.count }));
</script>

<template>
  <div
    v-for="_, index in skeletonArray"
    :key="index"
    class="bg-white rounded-2xl shadow-sm border border-gray-100 h-full flex flex-col p-5 pb-3"
  >
    <div class="flex items-start justify-between gap-2 mb-3">
      <div class="flex-1 space-y-2">
        <div class="skeleton-shimmer h-6 w-3/4 rounded skeleton-pulse"></div>
      </div>
      <div class="flex gap-1.5 flex-shrink-0">
        <div class="skeleton-shimmer w-8 h-8 rounded-full skeleton-pulse"></div>
        <div class="skeleton-shimmer w-8 h-8 rounded-full skeleton-pulse"></div>
      </div>
    </div>

    <div class="flex items-end justify-between mb-3">
      <div class="space-y-2">
        <div class="skeleton-shimmer h-9 w-24 rounded skeleton-pulse"></div>
        <div class="skeleton-shimmer h-5 w-12 rounded skeleton-pulse"></div>
      </div>
      <div class="flex gap-1.5">
        <div class="skeleton-shimmer h-8 w-16 rounded-lg skeleton-pulse"></div>
        <div class="skeleton-shimmer h-8 w-16 rounded-lg skeleton-pulse"></div>
      </div>
    </div>

    <div class="flex flex-wrap items-center gap-2 mb-3">
      <div class="skeleton-shimmer h-5 w-12 rounded skeleton-pulse"></div>
      <div class="skeleton-shimmer h-5 w-16 rounded skeleton-pulse"></div>
      <div class="skeleton-shimmer h-5 w-12 rounded skeleton-pulse"></div>
      <div class="skeleton-shimmer h-5 w-14 rounded skeleton-pulse"></div>
    </div>

    <div class="space-y-2 mb-3">
      <div class="flex items-start gap-2">
        <div class="skeleton-shimmer w-4 h-4 rounded flex-shrink-0 mt-0.5 skeleton-pulse"></div>
        <div class="flex-1 space-y-1.5">
          <div class="skeleton-shimmer h-4 w-full rounded skeleton-pulse"></div>
          <div class="skeleton-shimmer h-4 w-5/6 rounded skeleton-pulse"></div>
        </div>
      </div>
      <div class="flex items-start gap-2">
        <div class="skeleton-shimmer w-4 h-4 rounded flex-shrink-0 mt-0.5 skeleton-pulse"></div>
        <div class="flex flex-wrap gap-1.5">
          <div class="skeleton-shimmer h-5 w-20 rounded skeleton-pulse"></div>
          <div class="skeleton-shimmer h-5 w-24 rounded skeleton-pulse"></div>
        </div>
      </div>
    </div>

    <div class="flex items-center gap-2 mt-auto pt-3 border-t border-gray-100 -mx-5 px-5">
      <div class="skeleton-shimmer h-5 w-16 rounded-full skeleton-pulse"></div>
      <div class="skeleton-shimmer h-5 w-20 rounded skeleton-pulse"></div>
      <div class="skeleton-shimmer h-4 w-16 rounded ml-auto skeleton-pulse"></div>
    </div>
  </div>
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
