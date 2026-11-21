<script setup>
import { computed } from 'vue'

const props = defineProps({ nodes: { type: Array, required: true }, selectedId: String })
defineEmits(['select'])
const width = computed(() => Math.max(320, props.nodes.length * 115))
const points = computed(() => props.nodes.map((_, i) => [60 + i * 115, i % 2 ? 76 : 28]))
const path = computed(() => points.value.map(([x, y], i) => {
  if (!i) return 'M ' + x + ' ' + y
  const [px, py] = points.value[i - 1]
  const middle = (px + x) / 2
  return ['C', middle, py, middle, y, x, y].join(' ')
}).join(' '))
</script>

<template>
  <div v-if="nodes.length" class="route-scroll journey-scroll" aria-label="当日路线">
    <div class="route-curve" :style="{ width: width + 'px' }">
      <svg :width="width" height="108" aria-hidden="true">
        <path class="journey-ink-line" :d="path" pathLength="1" fill="none" stroke="#758a7a" stroke-width="2" stroke-dasharray="1" />
      </svg>
      <button v-for="(node, i) in nodes" :key="node.id" type="button"
        :aria-label="node.attractionName" :aria-pressed="selectedId === node.id"
        :style="{ left: points[i][0] + 'px', top: points[i][1] + 'px', '--station-delay': `${Math.min(i, 6) * 90}ms` }"
        @click="$emit('select', node.id)">{{ i + 1 }}</button>
    </div>
  </div>
</template>
