<script setup>
import { computed, onBeforeUnmount, onMounted, onUpdated, reactive, ref, watch, nextTick } from 'vue'
import { ElDialog, ElMessageBox } from 'element-plus'
import { get, post, put } from './api.js'
import RouteCurve from './RouteCurve.vue'
import TripMap from './TripMap.vue'

const pageNames = ['home', 'destinations', 'work', 'settings', 'places']
const page = ref(pageNames.includes(location.hash.slice(1)) ? location.hash.slice(1) : 'home')
const state = ref(null)
const attractions = ref([])
const recs = ref([])
const nearby = ref(null)
const selectedNode = ref('')
const tripMap = ref(null)
const selectedAttractionIds = ref([])
const guide = ref(null)
const guideOpen = ref(false)
const guideLoading = ref(false)
const guideError = ref('')
const guideSettings = reactive({ attractionId: '', depth: 'short', availableMinutes: 30 })
let guideRequestVersion = 0
const feedbackOpen = ref(false)
const feedbackBusy = ref(false)
const feedbackError = ref('')
const feedbackSuccess = ref(false)
const feedbackRequestId = ref('')
const feedbackDraft = reactive({ kind: 'too_tiring', attractionId: '' })
const feedbackAttraction = computed(() => attractions.value.find(item => item.id === feedbackDraft.attractionId))
const guideAttraction = computed(() => attractions.value.find(item => item.id === guideSettings.attractionId))
const guidePhoto = computed(() => ({ history: 'new-lake-temple.jpg', nature: 'new-canopy.jpg', food: 'coffee.jpg' })[guideAttraction.value?.category] || 'new-alley.jpg')
const eventType = ref('delay')
const eventData = reactive({ minutes: 40, attractionId: '', interest: 'nature', lat: 27.811, lng: 99.706 })
const busy = ref(false)
const notice = ref('')
const error = ref('')
const filter = ref('all')
const search = ref('')
const activeDay = ref(0)
const recStatus = ref('idle')
const recMessage = ref('')
const profileDraft = ref(null)
const destinationDetail = ref(null)
const destinationTheme = ref('全部')
const editing = ref(null)
const form = reactive({ name: '', category: 'history', tags: ['history'], lat: 27.811, lng: 99.706, openTime: '09:00', closeTime: '17:00', ticketYuan: 0, stayMinutes: 60, indoor: true, intensity: 'low', enabled: true, knowledgeText: '请填写景点介绍。', sourceTitle: '原型景点资料' })

const interests = [ ['history', '历史文化'], ['nature', '自然风光'], ['food', '地方美食'] ]
function interestPhoto(key) { return ({ history: 'new-alley.jpg', nature: 'new-canopy.jpg', food: 'breakfast.jpg' })[key] || 'meadow.jpg' }
const destinations = [
  { id: 'hainan', name: '海南岛', region: '中国 · 海南', image: 'island.jpg', detailImage: 'tropical.jpg', mood: '海岛放空', themes: ['海岛', '美食'], interests: ['nature', 'food'], title: '沿着海湾，逛逛椰林', description: '以海边散步和椰林观景为主，搭配当地风味小店，适合喜欢海岛风景与轻松行程的你。', highlights: ['海湾散步', '椰林光影', '海边早餐'], days: '3—5 天灵感' },
  { id: 'xishuangbanna', name: '西双版纳', region: '中国 · 云南', image: 'tropical.jpg', detailImage: 'tropical-table.jpg', mood: '热带慢生活', themes: ['森林', '美食', '人文'], interests: ['nature', 'food', 'history'], title: '逛雨林，也逛傣式街巷', description: '从热带植物到傣式街巷，再安排一顿当地风味，适合把自然与人文体验放进同一趟旅行。', highlights: ['热带植物', '傣式街巷', '风味小食'], days: '3—4 天灵感' },
  { id: 'shangrila', name: '香格里拉', region: '中国 · 云南', image: 'meadow.jpg', detailImage: 'monastery.jpg', mood: '高原漫游', themes: ['山野', '人文', '森林'], interests: ['nature', 'history'], title: '从古城出发，去看山湖', description: '在古城、展馆与高原风景之间选择停留点，根据可用时间和体力安排行程。', highlights: ['高原草甸', '古城漫步', '藏式文化'], days: '3—4 天灵感' },
  { id: 'dunhuang', name: '敦煌', region: '中国 · 甘肃', image: 'desert-river.jpg', detailImage: 'desert-town.jpg', mood: '沙漠与丝路', themes: ['沙漠', '人文', '美食'], interests: ['history', 'food'], title: '看沙丘光影，逛丝路古城', description: '以沙漠风景、文化展陈和老街风味为线索，寻找适合你的游览组合。', highlights: ['沙丘光影', '丝路文化', '老街风味'], days: '3—4 天灵感' },
  { id: 'dali', name: '大理', region: '中国 · 云南', image: 'coastal-lane.jpg', detailImage: 'river.jpg', mood: '湖畔与古城', themes: ['山野', '人文', '美食'], interests: ['nature', 'history', 'food'], title: '逛古城，沿湖走一段', description: '把古城街巷、湖畔风景和咖啡小店搭配起来，按你的兴趣和时间决定每一站。', highlights: ['湖畔慢行', '古城街巷', '咖啡时光'], days: '3—5 天灵感' },
]
const destinationThemes = ['全部', '海岛', '森林', '山野', '人文', '沙漠', '美食']
const destinationResults = computed(() => destinations
  .filter(item => destinationTheme.value === '全部' || item.themes.includes(destinationTheme.value))
  .map(item => {
    const ranked = [...item.interests].sort((a, b) => (state.value?.profile.interests[b] || 0) - (state.value?.profile.interests[a] || 0))
    const match = item.interests.length
      ? Math.round(item.interests.reduce((sum, key) => sum + (state.value?.profile.interests[key] || 0), 0) / item.interests.length * 100)
      : 0
    const strongest = interests.find(([key]) => key === ranked[0])?.[1] || '旅行'
    return { ...item, match, reason: `与你的${strongest}偏好相合` }
  }))
const currentTrip = computed(() => state.value?.trip)
const canEditTrip = computed(() => !!currentTrip.value && currentTrip.value.nodes.every(n => n.status === 'pending'))
const nodesByDay = computed(() => {
  const list = currentTrip.value?.nodes || []
  return Array.from({ length: state.value?.conditions.days || 1 }, (_, i) => list.filter(n => n.dayIndex === i + 1))
})
const routeCurveKey = computed(() => `${activeDay.value}:${(nodesByDay.value[activeDay.value] || []).map(node => `${node.id}-${node.arriveAt}`).join('|')}`)
const filteredAttractions = computed(() => attractions.value.filter(a => (filter.value === 'all' || a.category === filter.value) && a.name.toLowerCase().includes(search.value.trim().toLowerCase())))
const currentNode = computed(() => currentTrip.value?.nodes.find(n => n.status === 'current'))
const pendingCount = computed(() => currentTrip.value?.nodes.filter(n => n.status === 'pending').length || 0)

function say(value) { notice.value = value; error.value = '' }
function fail(err) { error.value = err?.message || '操作没有完成'; notice.value = '' }
async function confirmAction(message, title, confirmText) {
  try { await ElMessageBox.confirm(message, title, { confirmButtonText: confirmText, cancelButtonText: '返回', type: 'warning', distinguishCancelAndClose: true, customClass: 'travel-confirm' }); return true }
  catch { return false }
}
async function run(fn, success = '') {
  if (busy.value) return
  busy.value = true; error.value = ''; notice.value = ''
  try { const value = await fn(); if (success) say(success); return value }
  catch (err) { fail(err) }
  finally { busy.value = false }
}
async function loadAll() {
  await run(async () => {
    const [s, a] = await Promise.all([get('/api/state'), get('/api/attractions')])
    state.value = s; attractions.value = a.items
    if (s.trip && !selectedNode.value) selectedNode.value = s.trip.nodes[0]?.id || ''
    await loadNearby()
  })
}
async function refreshState() { state.value = await get('/api/state'); attractions.value = (await get('/api/attractions')).items }
async function loadNearby() { if (!state.value) return; nearby.value = await post('/api/nearby', { action: 'query' }) }

async function saveProfile() {
  if (!profileDraft.value.conditions.dayStart || profileDraft.value.conditions.dayStart >= profileDraft.value.conditions.dayEnd) {
    fail(new Error('结束时间必须晚于开始时间。'))
    return
  }
  const saved = await run(() => put('/api/profile', profileDraft.value))
  if (saved) {
    state.value = saved
    await recommend()
  }
}
async function recommend() {
  if (busy.value) return
  navigate('work')
  recStatus.value = 'loading'
  await nextTick()
  document.querySelector('.rec-section')?.scrollIntoView({ block: 'start' })
  const result = await run(() => post('/api/recommend', {}))
  recs.value = result?.items || []
  recStatus.value = result ? 'ready' : 'error'
  recMessage.value = result?.emptyReason || '当前条件下没有推荐景点。'
}
function navigate(target) {
  page.value = pageNames.includes(target) ? target : 'home'
  if (location.hash !== `#${page.value}`) history.pushState(null, '', `#${page.value}`)
  window.scrollTo({ top: 0, behavior: 'smooth' })
}
function resizeTripMap(event) { if (event.target.open) nextTick(() => tripMap.value?.resize()) }
window.addEventListener('popstate', () => { page.value = pageNames.includes(location.hash.slice(1)) ? location.hash.slice(1) : 'home' })

const revealSelector = '.welcome, .home-gallery article, .destination-card, .settings-page .form-section, .timeline-row, .subheading'
const observedMotionTargets = new WeakSet()
const observedRouteTargets = new WeakSet()
let revealObserver
let routeObserver
let revealFrame = 0
let lastAnimatedPage = ''
function prefersReducedMotion() { return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false }
function syncMotion() {
  if (prefersReducedMotion()) return
  const view = document.querySelector('main .destination-heading, main .page-heading, main .home-hero')
  if (view && lastAnimatedPage !== page.value) {
    lastAnimatedPage = page.value
    requestAnimationFrame(() => view.classList.add('tm-view-enter'))
  }
  if (revealFrame) return
  revealFrame = requestAnimationFrame(() => {
    revealFrame = 0
    if (!revealObserver && 'IntersectionObserver' in window) {
      revealObserver = new IntersectionObserver(entries => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue
          entry.target.classList.add('tm-enter')
          revealObserver.unobserve(entry.target)
        }
      }, { threshold: .08 })
    }
    if (!routeObserver && 'IntersectionObserver' in window) {
      routeObserver = new IntersectionObserver(entries => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue
          entry.target.classList.add('is-route-visible')
          routeObserver.unobserve(entry.target)
        }
      }, { threshold: .2 })
    }
    document.querySelectorAll(revealSelector).forEach(element => {
      if (observedMotionTargets.has(element)) return
      observedMotionTargets.add(element)
      if (revealObserver) revealObserver.observe(element)
      else element.classList.add('tm-enter')
    })
    document.querySelectorAll('.journey-scroll').forEach(element => {
      if (observedRouteTargets.has(element)) return
      observedRouteTargets.add(element)
      routeObserver?.observe(element)
      if (!routeObserver) element.classList.add('is-route-visible')
    })
  })
}
onUpdated(syncMotion)
onBeforeUnmount(() => {
  revealObserver?.disconnect()
  routeObserver?.disconnect()
  if (revealFrame) cancelAnimationFrame(revealFrame)
})
async function makePlan(mode = 'generate') {
  if (mode === 'generate' && state.value.trip && !(await confirmAction('重新生成会替换当前行程，并清除已经记录的到达、完成和跳过状态。', '重新安排当前行程', '继续生成'))) return
  const ids = mode === 'edit' ? selectedAttractionIds.value : selectedAttractionIds.value.length ? selectedAttractionIds.value : []
  if (mode === 'edit' && !ids.length) { fail(new Error('路线至少需要保留一个景点。')); return }
  const result = await run(() => post('/api/plan', { mode, attractionIds: ids }), mode === 'edit' ? '景点增删已重新排程。' : '行程已根据当前偏好与时间安排。')
  if (result) { state.value = result; selectedNode.value = result.trip.nodes[0]?.id || ''; await loadNearby() }
}
function toggleAttraction(id) {
  if (state.value?.trip && !canEditTrip.value) return
  selectedAttractionIds.value = selectedAttractionIds.value.includes(id)
    ? selectedAttractionIds.value.filter(x => x !== id)
    : [...selectedAttractionIds.value, id]
}
async function setStatus(node, action) {
  const current = Date.parse(state.value.runtime.now)
  const planned = Date.parse(action === 'complete' || action === 'leave' ? node.leaveAt : node.arriveAt)
  const localClock = new Date(Math.max(current, planned) + 8 * 60 * 60 * 1000).toISOString().slice(0, -1) + '+08:00'
  const at = localClock
  const result = await run(() => post('/api/trip/status', { nodeId: node.id, action, at }), action === 'complete' ? '已记录完成。' : '行程状态已更新。')
  if (result) { state.value = result; await loadNearby() }
}
function changeEventType() { eventData.attractionId = state.value?.trip?.nodes.find(n => n.status === 'pending')?.attractionId || '' }
async function createReplan() {
  const event = eventType.value === 'delay' ? { type: 'delay', minutes: Number(eventData.minutes) }
    : eventType.value === 'closed' ? { type: 'closed', attractionId: eventData.attractionId }
      : eventType.value === 'interest_change' ? { type: 'interest_change', interest: eventData.interest }
        : { type: eventType.value }
  const result = await run(() => post('/api/replan', { events: [event], now: state.value.runtime.now, point: { lat: Number(eventData.lat), lng: Number(eventData.lng) } }), '新的行程建议已生成；确认后才会替换正式路线。')
  if (result) state.value = result
}
async function proposalAction(action) {
  if (!state.value?.proposal) return
  const proposalId = state.value.proposal.id
  const result = await run(async () => {
    try { return await post(`/api/replan/${action}`, { proposalId }) }
    catch (err) {
      if (err.status === 409 || err.status === 404) await refreshState()
      throw err
    }
  }, action === 'confirm' ? '调整已应用到正式行程。' : '已放弃调整，原行程保留。')
  if (result) { state.value = result; await loadNearby() }
}
async function loadGuide() {
  if (!guideOpen.value || !guideSettings.attractionId) return
  const requestVersion = ++guideRequestVersion
  guideLoading.value = true
  guideError.value = ''
  guide.value = null
  try {
    guide.value = await post('/api/guide', {
      attractionId: guideSettings.attractionId,
      depth: guideSettings.depth,
      availableMinutes: Number(guideSettings.availableMinutes),
    })
  } catch (err) {
    if (requestVersion === guideRequestVersion) guideError.value = err?.message || '解说暂时无法加载。'
  } finally {
    if (requestVersion === guideRequestVersion) guideLoading.value = false
  }
}
function openGuide(attractionId) {
  Object.assign(guideSettings, {
    attractionId,
    depth: state.value?.profile.guideDepth || 'short',
    availableMinutes: 30,
  })
  guideOpen.value = true
  loadGuide()
}
function cancelGuide() {
  guideRequestVersion += 1
  guideLoading.value = false
  guide.value = null
  guideError.value = ''
  guideOpen.value = false
}
function openFeedback(attractionId = '') {
  feedbackDraft.attractionId = attractionId
  feedbackDraft.kind = attractionId ? 'like' : 'too_tiring'
  feedbackRequestId.value = ''
  feedbackError.value = ''
  feedbackSuccess.value = false
  feedbackOpen.value = true
}
function resetFeedbackAttempt() {
  feedbackRequestId.value = ''
  feedbackError.value = ''
}
async function submitFeedback() {
  if (feedbackBusy.value || feedbackSuccess.value) return
  if (['like', 'dislike'].includes(feedbackDraft.kind) && !feedbackDraft.attractionId) {
    feedbackError.value = '请从具体景点打开反馈，再评价喜欢或不喜欢。'
    return
  }
  feedbackRequestId.value ||= `feedback-${crypto.randomUUID()}`
  const payload = {
    requestId: feedbackRequestId.value,
    kind: feedbackDraft.kind,
    ...(['like', 'dislike'].includes(feedbackDraft.kind) ? { attractionId: feedbackDraft.attractionId } : {}),
  }
  feedbackBusy.value = true
  feedbackError.value = ''
  try {
    const result = await post('/api/feedback', payload)
    state.value = result.state
    feedbackSuccess.value = true
    say(result.duplicate ? '这条反馈此前已记录，没有重复调整偏好。' : '反馈已记录，并已更新对应偏好。')
    try {
      const updated = await post('/api/recommend', {})
      recs.value = updated.items || []
      recStatus.value = 'ready'
      recMessage.value = updated.emptyReason || '当前条件下没有推荐景点。'
    } catch (err) {
      recStatus.value = 'error'
      recMessage.value = err?.message || '推荐刷新失败，可稍后重试。'
    }
  } catch (err) {
    feedbackError.value = err?.message || '反馈暂时没有提交成功。可以重试；本次重试会沿用同一请求编号。'
  } finally {
    feedbackBusy.value = false
  }
}
async function viewUpdatedRecommendations() {
  feedbackOpen.value = false
  navigate('work')
  await nextTick()
  document.querySelector('.rec-section')?.scrollIntoView({ block: 'start' })
}
async function nearbyAction(action, extra = {}) {
  const result = await run(() => post('/api/nearby', { action, ...extra }), action === 'ignore' ? '已在本次旅行中隐藏这条推荐。' : '')
  if (result) nearby.value = result
}
function blankForm() {
  editing.value = null
  Object.assign(form, { name: '', category: 'history', tags: ['history'], lat: 27.811, lng: 99.706, openTime: '09:00', closeTime: '17:00', ticketYuan: 0, stayMinutes: 60, indoor: true, intensity: 'low', enabled: true, knowledgeText: '请填写景点介绍。', sourceTitle: '原型景点资料' })
}
function editAttraction(a) {
  editing.value = a.id
  Object.assign(form, { ...a, lat: a.point.lat, lng: a.point.lng, sourceTitle: a.sources?.[0]?.title || '原型景点资料' })
  window.scrollTo({ top: 0, behavior: 'smooth' })
}
async function saveAttraction() {
  const payload = { name: form.name.trim(), category: form.category, tags: form.tags, point: { lat: Number(form.lat), lng: Number(form.lng) }, openTime: form.openTime, closeTime: form.closeTime, ticketYuan: Number(form.ticketYuan), stayMinutes: Number(form.stayMinutes), indoor: form.indoor, intensity: form.intensity, enabled: form.enabled, knowledgeText: form.knowledgeText.trim(), sources: [{ title: form.sourceTitle, url: null, note: '人工录入资料，请在出行前核对。' }], presetGuides: Object.fromEntries(['history','nature','food'].map(tag => [tag, { short: `${form.name} · ${{history:'历史文化',nature:'自然',food:'地方体验'}[tag]}：${form.knowledgeText.trim()}`, detailed: `${form.name}：${form.knowledgeText.trim()} 出行前请核对开放安排与费用。` }])) }
  const result = await run(() => editing.value ? put('/api/attractions', { id: editing.value, ...payload }) : post('/api/attractions', payload), editing.value ? '景点资料已更新。' : '新景点已添加。')
  if (result) { await loadAll(); blankForm() }
}
async function resetDemo() {
  if (!(await confirmAction('这会清除当前偏好、行程、反馈及景点修改，并恢复原型内置的初始资料。', '恢复初始资料', '确认重置'))) return
  const result = await run(() => post('/api/reset', { confirm: 'RESET_DEMO' }), '已恢复原型景点初始资料。')
  if (result) {
    guideRequestVersion++
    guideOpen.value = false; guideLoading.value = false; guideError.value = ''; guide.value = null
    guideSettings.attractionId = ''; guideSettings.depth = 'short'; guideSettings.availableMinutes = 30
    feedbackOpen.value = false; feedbackBusy.value = false; feedbackError.value = ''; feedbackSuccess.value = false; feedbackRequestId.value = ''
    feedbackDraft.kind = 'too_tiring'; feedbackDraft.attractionId = ''
    destinationDetail.value = null; destinationTheme.value = '全部'; profileDraft.value = null
    editing.value = null; blankForm(); search.value = ''; filter.value = 'all'
    eventType.value = 'delay'; Object.assign(eventData, { minutes: 40, attractionId: '', interest: 'nature', lat: result.conditions.startPoint.lat, lng: result.conditions.startPoint.lng })
    state.value = result; await loadAll(); navigate('work')
    recs.value = []; recStatus.value = 'idle'; recMessage.value = ''; activeDay.value = 0; selectedAttractionIds.value = []; selectedNode.value = ''
  }
}
function categoryLabel(x) { return ({ history: '历史文化', nature: '自然风光', food: '地方美食', photography: '摄影' })[x] || x }
function originalSlot(node) {
  const original = currentTrip.value?.nodes.find(item => item.attractionId === node.attractionId)
  return original ? timeLabel(original.startAt) + '—' + timeLabel(original.leaveAt) : '新增'
}
function timeLabel(value) { return value?.slice(11, 16) || '' }
function nodeActionLabel(node) { return node.status === 'completed' ? '已完成' : node.status === 'skipped' ? '已跳过' : node.status === 'current' ? '游览中' : '待出发' }
function selectTag(tag) { form.tags = form.tags.includes(tag) ? form.tags.filter(x => x !== tag) : [...form.tags, tag] }

watch([page, state], ([current, saved], [previous, old]) => {
  if (current === 'settings' && saved && (current !== previous || !old)) {
    profileDraft.value = JSON.parse(JSON.stringify({ profile: saved.profile, conditions: saved.conditions }))
  }
  if (current !== previous) { destinationDetail.value = null; guide.value = null }
})
watch(nodesByDay, days => {
  if (!days[activeDay.value]?.some(n => n.id === selectedNode.value)) {
    selectedNode.value = days[activeDay.value]?.[0]?.id || ''
  }
})
function selectDay(index) {
  activeDay.value = index
  selectedNode.value = nodesByDay.value[index]?.[0]?.id || ''
}
watch(() => state.value?.runtime.point, point => { if (point) { eventData.lat = point.lat; eventData.lng = point.lng } }, { deep: true })
watch(() => state.value?.trip?.nodes, nodes => { if (nodes) selectedAttractionIds.value = nodes.map(n => n.attractionId) }, { deep: true })
onMounted(loadAll)
</script>

<template>
  <div class="app-frame">
    <header class="topbar" :class="{onHero:page==='home'}">
      <a class="brand" href="#home" @click.prevent="navigate('home')"><strong>旅伴 AI</strong><small>旅行规划助手</small></a>
      <nav class="main-nav" aria-label="主导航">
        <button v-for="item in [{id:'home',label:'发现'},{id:'destinations',label:'目的地灵感'},{id:'work',label:'我的旅程'},{id:'settings',label:'旅行偏好'},{id:'places',label:'景点管理'}]" :key="item.id" :class="{active:page===item.id}" @click="navigate(item.id)">{{ item.label }}</button>
      </nav>
      <button class="reset-link" @click="resetDemo">恢复初始资料</button>
    </header>

    <main v-if="state" class="page-wrap">
      <div v-if="notice || error" class="toast" :class="error ? 'toast-error' : 'toast-ok'" role="status">{{ error || notice }}<button aria-label="关闭提示" @click="notice='';error=''">×</button></div>

      <section v-if="page==='home' || page==='work'" class="work-page">
        <template v-if="page==='home'">
          <section class="home-hero">
            <img src="/images/hero.jpg" alt="雪山、湖泊与高原草甸">
            <div class="home-hero-copy"><span class="eyebrow">旅行灵感</span><h1>出发，<br>去喜欢的地方</h1><p>选喜欢的景点，排合适的行程，途中有变化也能调整。</p><button :disabled="busy" @click="recommend">看看适合我的景点 ↗</button></div>
            <div class="home-hero-foot"><span>中国 · 云南 · 香格里拉</span><span>高原旅行灵感</span></div>
          </section>
          <section class="welcome">
            <div><span class="eyebrow">从目的地开始</span><h2>这次，想去哪里？</h2><p>已有目的地，就开始安排行程；还没决定，也可以先找找灵感。</p></div>
            <div class="welcome-actions"><button @click="navigate('settings')">设置我的行程 →</button><button class="secondary" @click="navigate('destinations')">浏览目的地 ↗</button><button class="text" @click="navigate('work')">看看适合我的景点 ↗</button></div>
          </section>
          <section class="home-gallery" aria-label="旅行灵感照片">
            <article v-for="(pic,index) in [{image:'new-alpine-lake.jpg',alt:'山湖风景意境',title:'去山湖之间走一走',label:'山湖风景'},{image:'new-alley.jpg',alt:'古城街巷意境',title:'逛逛古城与老街',label:'古城街巷'},{image:'breakfast.jpg',alt:'当地早餐意境',title:'尝尝当地的味道',label:'当地风味'}]" :key="pic.image" role="link" tabindex="0" @click="navigate('settings')" @keydown.enter.prevent="navigate('settings')" @keydown.space.prevent="navigate('settings')"><img :src="`/images/${pic.image}`" :alt="pic.alt" loading="lazy"><div><span>0{{ index + 1 }} / {{ pic.label }}</span><h3>{{ pic.title }}</h3></div></article>
          </section>
        </template>
        <template v-else>
          <section class="page-heading"><span class="eyebrow">我的旅程</span><div><h1>香格里拉 · 我的行程</h1><button v-if="state.trip" class="button button-outline" :disabled="busy" @click="makePlan('generate')">重新安排行程 ↗</button></div></section>
          <section class="scene"><img src="/images/meadow.jpg" alt="高原草甸与山湖旅行意境"><div><span class="eyebrow">香格里拉 · 旅行计划</span><p>查看沿途安排，按需要调整行程</p></div></section>
        </template>
        <template v-if="page==='work'">
        <section class="section-block rec-section">
          <div class="section-heading"><div><p class="eyebrow">按你的兴趣排列</p><h2>这次，可以去看看这些地方。</h2><p v-if="recs.length" class="selection-note">已选 {{ selectedAttractionIds.length }} 处 · 可先增删，再重新计算时间与预算</p></div><div v-if="recs.length" class="recommend-actions"><button v-if="selectedAttractionIds.length && (!currentTrip || canEditTrip)" class="button button-dark route-generate-primary" :disabled="busy" :aria-label="canEditTrip ? '应用所选景点调整' : '生成所选景点路线'" @click="makePlan(canEditTrip ? 'edit' : 'generate')"><span>{{ canEditTrip ? '应用所选景点调整' : '生成所选景点路线' }}</span><span class="route-action-count">{{ selectedAttractionIds.length }} 处</span><span aria-hidden="true">→</span></button><button v-else-if="canEditTrip" class="button button-outline" disabled>应用景点调整</button><button v-else class="text-button" @click="makePlan('generate')">{{ currentTrip ? '按推荐重新安排' : '按推荐生成路线' }} <span>→</span></button></div></div>
          <div v-if="!recs.length" class="quiet-empty" aria-live="polite">
            <p>{{ recStatus === 'loading' ? '正在获取推荐…' : recStatus === 'error' ? '暂时无法获取推荐。' : recStatus === 'ready' ? recMessage : '按你的兴趣、预算与开放时间寻找景点。' }}</p>
            <button v-if="recStatus !== 'loading'" class="text-button" @click="recommend">{{ recStatus === 'error' ? '重试' : '获取推荐' }}</button>
          </div>
          <div v-else class="recommend-grid">
            <article v-for="(item,index) in recs.slice(0,4)" :key="item.attractionId" class="recommend-card">
              <div class="recommend-photo" :class="`scene-${index % 4}`"><span>{{ String(index+1).padStart(2,'0') }}</span></div>
              <div class="recommend-body"><div class="small-meta">{{ categoryLabel(attractions.find(a=>a.id===item.attractionId)?.category) }} <span>·</span> {{ item.stayMinutes }} 分钟</div><h3>{{ item.name }}</h3><p>{{ item.reasons.join('；') }}</p><div class="card-bottom"><span>匹配度 {{ Math.round(item.score*100) }}%</span><span>门票 ¥{{ item.ticketYuan }}</span></div><div class="card-actions"><button class="text-button" @click="openGuide(item.attractionId)">地点解说 ↗</button><button class="text-button" @click="openFeedback(item.attractionId)">偏好反馈</button></div><button class="pick-button" :disabled="!!state.trip && !canEditTrip" @click="toggleAttraction(item.attractionId)">{{ selectedAttractionIds.includes(item.attractionId) ? '从路线移除' : '加入路线' }} <span>{{ selectedAttractionIds.includes(item.attractionId) ? '−' : '+' }}</span></button></div>
            </article>
          </div>
        </section>

        <section v-if="!state.trip" class="section-block pretrip-nearby">
          <div class="section-heading"><div><p class="eyebrow">从出发位置附近开始</p><h2>也可以先看看顺路的地方。</h2></div><button class="text-button" @click="nearbyAction('set_enabled',{enabled:!nearby?.enabled})">{{ nearby?.enabled ? '关闭附近推荐' : '开启附近推荐' }} <span>↗</span></button></div>
          <div v-if="nearby?.enabled && nearby.items.length" class="nearby-pick-grid"><article v-for="item in nearby.items" :key="item.attractionId"><div><h3>{{ item.name }}</h3><p>{{ item.distanceMeters }} 米 · 约 {{ item.estimatedMinutes }} 分钟</p><small>{{ item.reasons.join('；') }}</small></div><button class="pick-button" @click="toggleAttraction(item.attractionId)">{{ selectedAttractionIds.includes(item.attractionId) ? '已加入待安排' : '加入待安排' }} <span>{{ selectedAttractionIds.includes(item.attractionId) ? '−' : '+' }}</span></button></article></div>
          <p v-else class="nearby-empty">{{ nearby?.enabled ? '出发位置附近暂时没有合适地点。' : '附近推荐已关闭。' }}</p>
          <p class="form-help">加入后仍须通过路线时间、开放时段与预算检查；未生成路线前可以继续调整。</p>
        </section>

        <section class="section-block trip-section">
          <div class="section-heading"><div><p class="eyebrow">路线与时间安排</p><h2>{{ state.trip ? '给今天留出一点余地。' : '把喜欢的地方，排成一段路。' }}</h2></div><button v-if="state.trip" class="button button-outline" :disabled="busy" @click="makePlan('generate')">重新安排</button></div>
          <div v-if="!state.trip" class="route-empty"><div class="route-empty-art"><span>{{ state.conditions.dayStart.slice(0, 2) }}</span><i></i><span>{{ state.conditions.dayEnd.slice(0, 2) }}</span></div><p>推荐景点后，生成一日或两日路线。时间轴与地图会保持一致。</p><button class="button button-dark" @click="recommend">先看景点推荐 <span>→</span></button></div>
          <div v-else class="trip-layout">
            <div class="trip-list">
              <div class="trip-summary"><span>{{ state.trip.nodes.length }} 个景点</span><span>门票约 ¥{{ state.trip.estimatedTicketYuan }}</span><span>交通时间为原型路线估算</span></div>
              <nav v-if="nodesByDay.length > 1" class="segmented" aria-label="行程日期">
                <button v-for="(_, index) in nodesByDay" :key="index" :aria-pressed="activeDay === index" :class="{chosen:activeDay === index}" @click="selectDay(index)">第 {{ index + 1 }} 天</button>
              </nav>
              <RouteCurve :key="routeCurveKey" :nodes="nodesByDay[activeDay] || []" :selected-id="selectedNode" @select="selectedNode = $event" />
              <div v-for="(dayNodes,di) in nodesByDay" v-show="di === activeDay" :key="di" class="day-group">
                <div class="day-label"><span>第 {{ di+1 }} 天</span><span>{{ dayNodes[0] ? dayNodes[0].arriveAt.slice(0,10) : state.conditions.startDate }}</span></div>
                <div v-for="(node,index) in dayNodes" :key="node.id" class="timeline-row" :class="{'is-selected':selectedNode===node.id}">
                  <button class="timeline-marker" :class="`status-${node.status}`" :aria-label="`选择${node.attractionName}`" @click="selectedNode=node.id">{{ String(index+1).padStart(2,'0') }}</button>
                  <div class="timeline-content" @click="selectedNode=node.id">
                    <div class="timeline-time">{{ timeLabel(node.startAt) }} <span>—</span> {{ timeLabel(node.leaveAt) }} <i v-if="node.travelMinutes">· 路程 {{ node.travelMinutes }} 分钟</i></div>
                    <h3>{{ node.attractionName }} <small :class="`state-${node.status}`">{{ nodeActionLabel(node) }}</small></h3>
                    <p>停留约 {{ node.stayMinutes }} 分钟 <span>·</span> 门票 ¥{{ node.ticketYuan }}</p>
                  </div>
                  <div class="node-actions">
                    <button v-if="canEditTrip" class="icon-button" title="从路线移除此景点" @click="toggleAttraction(node.attractionId)">移除</button>
                    <button v-if="node.status==='pending'" class="mini-button" :disabled="busy || currentNode" @click="setStatus(node,'arrive')">到达</button>
                    <button v-if="node.status==='current'" class="mini-button mini-dark" :disabled="busy" @click="setStatus(node,'complete')">完成</button>
                    <button v-if="node.status==='current'" class="icon-button" title="提前离开" :disabled="busy" @click="setStatus(node,'leave')">离开</button>
                    <button v-if="node.status==='pending'" class="icon-button" title="跳过此处" :disabled="busy" @click="setStatus(node,'skip')">跳过</button>
                    <button class="icon-button" title="查看景点解说" @click="openGuide(node.attractionId)">解说</button>
                    <button class="icon-button" title="反馈这个景点" @click="openFeedback(node.attractionId)">反馈</button>
                  </div>
                </div>
              </div>
              <p v-if="state.trip.warnings.length" class="warning-line">{{ state.trip.warnings.join('；') }}</p>
              <p class="route-footnote">路线按预置交通时间安排；地图只展示景点顺序示意，不代表真实导航。</p>
            </div>
            <div class="trip-aside"><details class="geographic-map" @toggle="resizeTripMap"><summary>查看景点位置与路线顺序 <span>展开地图 ↗</span></summary><TripMap ref="tripMap" :nodes="nodesByDay[activeDay] || []" :selected-id="selectedNode" @select="selectedNode = $event" /></details>
              <div class="nearby-panel">
                <div class="nearby-head"><div><p class="eyebrow">走到附近时</p><h3>顺路看看</h3></div><label class="switch"><input type="checkbox" :checked="nearby?.enabled ?? state.nearbyEnabled" @change="nearbyAction('set_enabled',{enabled:$event.target.checked})"><span></span></label></div>
                <div v-if="nearby?.enabled && nearby.items.length" class="nearby-list"><article v-for="item in nearby.items" :key="item.attractionId"><div><b>{{ item.name }}</b><p>{{ item.distanceMeters }} 米 · 约 {{ item.estimatedMinutes }} 分钟</p><small>{{ item.reasons.join('；') }}</small></div><button class="icon-button" @click="nearbyAction('ignore',{attractionId:item.attractionId})">忽略</button></article></div>
                <p v-else class="nearby-empty">{{ nearby?.enabled ? '当前附近没有合适的新地点。' : '附近推荐已关闭。' }}</p>
              </div>
            </div>
          </div>
        </section>

        <section v-if="state.trip" class="section-block adapt-section">
          <div class="section-heading"><div><p class="eyebrow">途中计划有变</p><h2>留一条灵活的后路。</h2></div><p class="section-note">先生成候选方案，确认后才会更新正式路线。</p></div>
          <div class="adapt-controls"><label>遇到的情况<select v-model="eventType" @change="changeEventType"><option value="delay">行程延误</option><option value="fatigue">有些疲惫</option><option value="rain">开始下雨</option><option value="closed">景点临时关闭</option><option value="interest_change">临时改变兴趣</option></select></label>
            <label v-if="eventType==='delay'">延误时间<select v-model.number="eventData.minutes"><option :value="20">20 分钟</option><option :value="40">40 分钟</option><option :value="60">60 分钟</option></select></label>
            <label v-if="eventType==='closed'">关闭景点<select v-model="eventData.attractionId"><option v-for="n in state.trip.nodes.filter(n=>n.status==='pending')" :key="n.id" :value="n.attractionId">{{ n.attractionName }}</option></select></label>
            <label v-if="eventType==='interest_change'">更想看看<select v-model="eventData.interest"><option v-for="[key,label] in interests" :key="key" :value="key">{{ label }}</option></select></label>
            <div class="location-fields"><label>现在所在位置 · 纬度<input v-model.number="eventData.lat" type="number" min="-90" max="90" step="0.001"></label><label>经度<input v-model.number="eventData.lng" type="number" min="-180" max="180" step="0.001"></label></div><button class="button button-dark" :disabled="busy || !pendingCount || (eventType==='closed' && !eventData.attractionId)" @click="createReplan">重新安排后续 <span>→</span></button>
          </div>
          <div v-if="state.proposal" class="proposal-box"><div class="proposal-copy"><p class="eyebrow">待确认的调整建议</p><h3>{{ state.proposal.reasons.join(' · ') }}</h3><p>新增 {{ state.proposal.addedAttractionIds.length }} 处，移除 {{ state.proposal.removedAttractionIds.length }} 处；已完成与已跳过记录会保留。</p><ol class="proposal-route" aria-label="调整后路线"><li v-for="(node,index) in state.proposal.trip.nodes" :key="node.id"><span>{{ String(index+1).padStart(2,'0') }}</span><b>{{ node.attractionName }}</b><small>{{ originalSlot(node) }} → {{ timeLabel(node.startAt) }}—{{ timeLabel(node.leaveAt) }}</small><i>{{ node.status==='completed' ? '已完成' : node.status==='skipped' ? '已跳过' : '调整后安排' }}</i></li></ol></div><div class="proposal-actions"><button class="button button-outline" :disabled="busy" @click="proposalAction('discard')">保留原行程</button><button class="button button-dark" :disabled="busy" @click="proposalAction('confirm')">确认调整</button></div></div>
        </section>

      </template>
      </section>

      <section v-else-if="page==='destinations'" class="destinations-page">
        <section class="destination-heading"><div><span class="eyebrow">目的地灵感</span><h1>还没想好去哪？<br>看看这些目的地</h1><p>看海、逛古城、走进山野，或尝尝当地风味。<br>从你喜欢的体验开始，选一个目的地。</p></div><div class="destination-heading-photo"><img src="/images/new-canopy.jpg" alt="林间旅行意境图"><span>换个地方，看看风景</span></div></section>
        <section class="destination-content"><div class="destination-toolbar"><div class="destination-filters"><button v-for="theme in destinationThemes" :key="theme" :class="{chosen:destinationTheme===theme}" @click="destinationTheme=theme">{{ theme }}</button></div><span>为你找到 {{ destinationResults.length }} 个目的地</span></div><p class="destination-explainer">按你的兴趣排列。查看目的地介绍，选好后即可规划当地行程。</p>
          <div class="destination-results"><article v-for="(place,index) in destinationResults" :key="place.id" class="destination-card"><button class="destination-cover" @click="destinationDetail=place" :aria-label="`了解${place.name}`"><img :src="`/images/${place.image}`" :alt="`${place.name}主题旅行意境图`" loading="lazy"><span class="destination-cover-top"><span>0{{ index + 1 }} / {{ place.region }}</span><span>{{ place.mood }}</span></span><span class="destination-cover-name">{{ place.name }}<small>{{ place.region }}</small></span><span class="destination-arrow">↗</span></button><div class="destination-card-body"><div class="destination-card-meta"><span>{{ place.days }}</span><span>{{ place.match }}% 兴趣匹配</span></div><h3>{{ place.title }}</h3><p>{{ place.description }}</p><div class="destination-tags"><span v-for="tag in place.highlights" :key="tag">{{ tag }}</span></div><div class="destination-card-action"><span>{{ place.reason }}</span><button class="text-button" @click="destinationDetail=place">查看介绍 →</button></div></div></article></div>
          <p class="destination-footnote">灵感天数用于展示；目的地卡展示旅行灵感；当前行程使用原型内置的香格里拉景点资料，图片为旅行意境图，不代表当地实拍。</p>
        </section>
        <el-dialog v-if="destinationDetail" :model-value="true" :title="destinationDetail.name + ' · 灵感展示'" @close="destinationDetail=null" width="min(600px, 92vw)">
          <img class="detail-photo" :src="`/images/${destinationDetail.detailImage}`" :alt="`${destinationDetail.name}旅行意境图`">
          <p>{{ destinationDetail.description }}</p>
          <button class="button button-dark" @click="navigate('settings')">规划香格里拉路线</button>
        </el-dialog>
      </section>
      <section v-else-if="page==='settings'" v-show="profileDraft" class="settings-page">
        <section class="page-heading"><span class="eyebrow">旅行设置</span><div><h1>安排一趟适合你的旅行</h1><p>选好兴趣与时间，再安排每一站。</p></div></section>
        <section class="scene"><img src="/images/meadow.jpg" alt="高原草甸与山湖旅行意境"><div><span class="eyebrow">香格里拉 · 旅行计划</span><p>选好兴趣与时间，再安排每一站</p></div></section>
        <div class="chosen-destination"><span>本次目的地</span><strong>香格里拉</strong><small>路线使用原型内置的香格里拉景点与交通估算。</small><button class="text-button" @click="navigate('destinations')">浏览目的地灵感 ↗</button></div>
        <div class="settings-layout">
          <div class="settings-form">
        <div v-if="profileDraft" class="form-section"><div class="form-title"><span>01</span><h2>旅行中，你更喜欢什么</h2></div><div class="interest-grid"><label v-for="[key,label] in interests" :key="key" class="interest-card" :class="`interest-${key}`" :style="{'--interest-photo':`url('/images/${interestPhoto(key)}')`}"><span class="interest-label">{{ label }}</span><strong>{{ Math.round(profileDraft.profile.interests[key]*100) }}<small>%</small></strong><input v-model.number="profileDraft.profile.interests[key]" type="range" min="0" max="1" step="0.05" :aria-label="`${label}兴趣权重`"><span class="range-hints"><i>不太感兴趣</i><i>非常喜欢</i></span></label></div></div>
        <div v-if="profileDraft" class="form-section"><div class="form-title"><span>02</span><h2>什么时候出发，准备玩多久？</h2></div><div class="field-grid"><label>出发日期<input v-model="profileDraft.conditions.startDate" type="date" :disabled="!!state.trip"></label><label>旅行天数<select v-model.number="profileDraft.conditions.days" :disabled="!!state.trip"><option :value="1">1 天 · 短途游览</option><option :value="2">2 天 · 慢慢逛逛</option></select></label><label>每天几点开始<input v-model="profileDraft.conditions.dayStart" type="time" :disabled="!!state.trip"></label><label>每天几点结束<input v-model="profileDraft.conditions.dayEnd" type="time" :disabled="!!state.trip"></label><label>出发位置 · 纬度<input v-model.number="profileDraft.conditions.startPoint.lat" type="number" min="-90" max="90" step="0.001" :disabled="!!state.trip"></label><label>出发位置 · 经度<input v-model.number="profileDraft.conditions.startPoint.lng" type="number" min="-180" max="180" step="0.001" :disabled="!!state.trip"></label></div><p v-if="state.trip" class="form-help">当前已有行程，出发日期、游玩天数、时间和起点暂时锁定；恢复初始资料后可重新设置。</p></div>
        <div v-if="profileDraft" class="form-section"><div class="form-title"><span>03</span><h2>选好节奏和预算。</h2></div><div class="field-grid"><fieldset><legend>旅行节奏</legend><div class="segmented"><button :class="{chosen:profileDraft.profile.pace==='relaxed'}" @click="profileDraft.profile.pace='relaxed'">轻松一点</button><button :class="{chosen:profileDraft.profile.pace==='normal'}" @click="profileDraft.profile.pace='normal'">多逛一些</button></div></fieldset><label>门票预算 · 元<input v-model.number="profileDraft.conditions.budgetYuan" type="number" min="0" step="10" :disabled="!!state.trip"></label><fieldset><legend>解说长度</legend><div class="segmented"><button :class="{chosen:profileDraft.profile.guideDepth==='short'}" @click="profileDraft.profile.guideDepth='short'">简短</button><button :class="{chosen:profileDraft.profile.guideDepth==='detailed'}" @click="profileDraft.profile.guideDepth='detailed'">详细</button></div></fieldset></div><p class="form-help">预算只累计景点门票；不含交通、餐饮与住宿。景点坐标、开放时间与门票来自原型内置资料，尚未外部核验。</p></div>
        <div class="form-submit"><button class="button button-dark" :disabled="busy" @click="saveProfile">保存偏好与安排 <span>→</span></button><button class="text-button" @click="navigate('work')">返回我的旅程</button></div>
          </div>
          <aside class="settings-collage"><img class="collage-tall" src="/images/monastery.jpg" alt="高原寺院与山湖意境"><div><img src="/images/new-lake-temple.jpg" alt="湖畔建筑意境"><img src="/images/detail-coffee.jpg" alt="旅途中休息的咖啡意境"></div><h2>喜欢的地方，<br>按自己的节奏逛</h2></aside>
        </div>
      </section>

      <section v-else-if="page==='places'" class="places-page">
        <section class="page-heading"><span class="eyebrow">景点资料库 · 本机管理</span><div><h1>管理景点与资料</h1><button class="button button-outline" @click="blankForm">新增景点 ＋</button></div></section>
        <section class="scene"><img src="/images/new-alley.jpg" alt="古城街巷旅行意境"><div><span class="eyebrow">原型景点资料</span><p>记录景点信息，完善推荐依据</p></div></section>
        <p class="places-intro-note">景点名称和路线资料沿用用户指定的原型内容；新增或修改时请填写可核实的信息。</p>
        <div class="places-layout"><form class="place-form" @submit.prevent="saveAttraction"><div class="form-title"><span>{{ editing ? '编辑' : '新增' }}</span><h2>{{ editing ? '更新景点资料' : '添加一个景点' }}</h2></div>
            <label>景点名称<input v-model="form.name" required maxlength="80" placeholder="例如：河畔展览馆"></label><label>景点分类<select v-model="form.category"><option value="history">历史文化</option><option value="nature">自然风光</option><option value="food">地方美食</option><option value="photography">摄影</option></select></label>
            <fieldset><legend>兴趣标签</legend><div class="tag-picks"><button v-for="[key,label] in interests" :key="key" type="button" :class="{chosen:form.tags.includes(key)}" @click="selectTag(key)">{{ label }}</button></div></fieldset>
            <div class="field-grid compact"><label>纬度<input v-model.number="form.lat" type="number" min="-90" max="90" step="0.001" required></label><label>经度<input v-model.number="form.lng" type="number" min="-180" max="180" step="0.001" required></label><label>开放时间<input v-model="form.openTime" type="time" required></label><label>闭园时间<input v-model="form.closeTime" type="time" required></label><label>门票 · 元<input v-model.number="form.ticketYuan" type="number" min="0" step="0.5" required></label><label>游览 · 分钟<input v-model.number="form.stayMinutes" type="number" min="10" max="240" step="5" required></label></div>
            <div class="field-grid compact"><label>游览强度<select v-model="form.intensity"><option value="low">低</option><option value="medium">中</option><option value="high">高</option></select></label><label class="check-label"><input v-model="form.indoor" type="checkbox"> 室内景点</label><label class="check-label"><input v-model="form.enabled" type="checkbox"> 参与推荐</label></div>
            <label>景点资料<textarea v-model="form.knowledgeText" rows="3" required></textarea></label><label>资料来源名称<input v-model="form.sourceTitle" required></label>
            <div class="form-actions"><button class="button button-dark" :disabled="busy || !form.tags.length">{{ editing ? '保存修改' : '添加景点' }} <span>→</span></button><button v-if="editing" class="text-button" type="button" @click="blankForm">取消编辑</button></div>
          </form>
          <div class="places-table-wrap"><div class="table-tools"><div><p class="eyebrow">景点资料</p><h2>{{ filteredAttractions.length }} 个地点</h2></div><input v-model="search" type="search" aria-label="搜索景点" placeholder="搜索景点"><select v-model="filter" aria-label="景点分类"><option value="all">全部分类</option><option value="history">历史文化</option><option value="nature">自然风光</option><option value="food">地方美食</option><option value="photography">摄影</option></select></div><div class="place-list"><article v-for="a in filteredAttractions" :key="a.id" class="place-row"><div class="place-dot" :class="`dot-${a.category}`"></div><div class="place-info"><h3>{{ a.name }} <small>{{ categoryLabel(a.category) }}</small></h3><p>{{ a.openTime }}—{{ a.closeTime }} <span>·</span> {{ a.stayMinutes }} 分钟 <span>·</span> ¥{{ a.ticketYuan }}</p></div><span class="enabled-state" :class="{disabled:!a.enabled}">{{ a.enabled ? '启用中' : '已停用' }}</span><button class="text-button" @click="editAttraction(a)">编辑</button></article></div><p class="form-help">停用景点不参与推荐与新行程；既有路线保留原有景点快照。</p></div>
        </div>
      </section>
      <el-dialog v-model="guideOpen" :title="`${guideAttraction?.name || '景点'} · 地点解说`" width="min(680px, 94vw)" @close="cancelGuide">
        <img v-if="guideAttraction" class="guide-modal-photo" :src="`/images/${guidePhoto}`" :alt="`${guideAttraction.name}主题意境图`">
        <div class="guide-modal-controls"><label>解说深度<select v-model="guideSettings.depth" @change="loadGuide"><option value="short">简短</option><option value="detailed">详细</option></select></label><label>可用时间 · 分钟<input v-model.number="guideSettings.availableMinutes" type="number" min="1" max="120" @change="loadGuide"></label></div>
        <p v-if="guideLoading" class="form-help" role="status">正在读取景点资料… <button class="text-button" @click="cancelGuide">取消等待</button></p>
        <p v-if="guideError" class="guide-error" role="alert">{{ guideError }} <button class="text-button" @click="loadGuide">重试</button></p>
        <template v-if="guide"><p class="guide-modal-text">{{ guide.text }}</p><p class="source-note">{{ guide.notice }} <span v-for="source in guide.sources" :key="source.title">· {{ source.title }}</span></p><button class="text-button" @click="openFeedback(guideSettings.attractionId); cancelGuide()">反馈这次体验 ↗</button></template>
      </el-dialog>
      <el-dialog v-model="feedbackOpen" title="让下一段旅程，更像你" width="min(560px, 94vw)" :close-on-click-modal="!feedbackBusy" :close-on-press-escape="!feedbackBusy">
        <p v-if="feedbackAttraction" class="feedback-place-name">{{ feedbackAttraction.name }}</p>
        <label class="feedback-modal-field">选择要更新的偏好<select v-model="feedbackDraft.kind" @change="resetFeedbackAttempt"><option value="like" :disabled="!feedbackDraft.attractionId">喜欢：增加相关兴趣</option><option value="dislike" :disabled="!feedbackDraft.attractionId">不喜欢：减少相关兴趣</option><option value="too_tiring">走得有点累：以后安排轻松一些</option><option value="too_long">解说太长：以后默认简短</option></select></label>
        <p class="form-help">提交即确认更新。兴趣调整限制在 0—1；请求不确定时重试会沿用同一编号，不会重复加权。</p>
        <p v-if="feedbackError" class="guide-error" role="alert">{{ feedbackError }}</p>
        <p v-if="feedbackSuccess" class="feedback-success" role="status">偏好已更新。{{ recStatus === 'ready' ? '推荐也已刷新。' : '推荐刷新暂未成功，可关闭后再重试推荐。' }}</p>
        <div class="feedback-modal-actions"><button class="button button-dark" :disabled="feedbackBusy || feedbackSuccess" @click="submitFeedback">{{ feedbackBusy ? '正在提交…' : feedbackError ? '使用同一编号重试' : '确认提交反馈' }}</button><button v-if="feedbackSuccess && recStatus === 'ready'" class="button button-outline" @click="viewUpdatedRecommendations">查看更新后推荐</button><button class="text-button" :disabled="feedbackBusy" @click="feedbackOpen=false">{{ feedbackSuccess ? '关闭' : '返回' }}</button></div>
      </el-dialog>
      <footer class="app-footer"><span>旅伴 AI · 本机旅行规划</span><span>香格里拉景点与交通数据来自原型内置资料，出行前请核实 · 地图底图 © OpenStreetMap</span></footer>
    </main>
    <div v-else class="loading-screen"><div class="loading-mark">旅</div><p>正在打开你的旅行计划…</p><p v-if="error" class="error-text">{{ error }}<br><button class="text-button" @click="loadAll">重新连接</button></p></div>
  </div>
</template>
