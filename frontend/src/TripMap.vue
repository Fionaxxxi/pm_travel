<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import L from 'leaflet'

const props = defineProps({ nodes: { type: Array, default: () => [] }, selectedId: { type: String, default: '' } })
const emit = defineEmits(['select'])
const el = ref(null)
let map, layer

function paint() {
  if (!map) return
  if (layer) map.removeLayer(layer)
  const nodes = props.nodes
  layer = L.layerGroup().addTo(map)
  if (!nodes.length) return
  const points = nodes.map(n => [n.point.lat, n.point.lng])
  L.polyline(points, { color: '#24394a', weight: 3, dashArray: '7 8' }).addTo(layer)
  nodes.forEach((node, index) => {
    const marker = L.circleMarker([node.point.lat, node.point.lng], {
      radius: node.id === props.selectedId ? 11 : 8,
      color: '#f8f6f0', weight: 3,
      fillColor: node.status === 'completed' ? '#9aa28e' : '#24394a', fillOpacity: 1,
    }).bindTooltip(`${String(index + 1).padStart(2, '0')} · ${node.attractionName}`, { direction: 'top' })
    marker.on('click', () => emit('select', node.id))
    marker.addTo(layer)
  })
  const bounds = L.latLngBounds(points)
  map.fitBounds(bounds.pad(.35), { maxZoom: 14, animate: true })
}
function resize() { if (!map) return; map.invalidateSize({ animate: false }); paint() }

onMounted(() => {
  map = L.map(el.value, { scrollWheelZoom: false, zoomControl: false, attributionControl: true })
  L.control.zoom({ position: 'bottomright' }).addTo(map)
  const tiles = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap' })
  tiles.on('tileerror', () => el.value?.classList.add('map-offline'))
  tiles.addTo(map)
  map.setView([30.25, 120.15], 13)
  paint()
})
watch(() => [props.nodes, props.selectedId], paint, { deep: true })
onBeforeUnmount(() => map?.remove())
defineExpose({ resize })
</script>

<template>
  <div class="map-shell">
    <div ref="el" class="map-canvas" aria-label="景点位置与行程顺序地图"></div>
    <div class="map-note"><span class="map-dash"></span>路线顺序示意 · 交通时间为演示估计</div>
    <div class="map-offline-note">底图暂不可用，景点位置与路线顺序仍可查看</div>
  </div>
</template>
