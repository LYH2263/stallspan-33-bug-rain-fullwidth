<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'

interface RunData {
  id: number
  created_at?: string
  segment: {
    id: number; name: string
    width_m: number
    effective_width_m?: number
    registered_width_m?: number
    rainy?: boolean
    rain_width_factor?: number | null
  }
  placements: any[]
  rejected: any[]
  free_spans: any[]
  pillars: any[]
  voided_pillars?: any[]
}
interface RunMeta {
  id: number; created_at: string; segment_name?: string
  effective_width_m: number; registered_width_m?: number
  rainy: boolean; rain_width_factor?: number | null
  placed: number; rejected: number
}

const data = ref<RunData | null>(null)
const vendors = ref<any[]>([])
const runs = ref<RunMeta[]>([])
const drawerOpen = ref(false)
const activeRunId = ref<number | null>(null)
const loading = ref(false)
const colors = ['#e8a87c','#85dcb8','#e27d60','#c38d9e','#41b3a3','#f4a261','#e76f51']

// 右端口径：只认本次运行快照里的有效宽；旧快照无该字段时回退其 width_m（仍是当次右端）。
const effWidth = computed(() => {
  const s = data.value?.segment
  if (!s) return 0
  return s.effective_width_m ?? s.width_m
})
const registeredWidth = computed(() => data.value?.segment.registered_width_m ?? null)
const isRainy = computed(() => !!data.value?.segment.rainy)

interface Cell { kind: 'pillar' | 'stall'; start: number; end: number; label: string; color?: string; pillarId?: number }
interface PositionedCell extends Cell { leftPct: number; widthPct: number }

// 与后端 clip_pillars_to_width 同策略的旧快照兜底：米标超右端整根不画。
function pillarGeom(p: any, w: number): { start: number; end: number } | null {
  if (p.start_m != null && p.end_m != null) {
    if (p.position_m != null && (p.position_m > w + 1e-9 || p.position_m < -1e-9)) return null
    return { start: p.start_m, end: p.end_m }
  }
  const half = (p.thickness_m ?? 0.4) / 2
  if (p.position_m > w + 1e-9 || p.position_m < -1e-9) return null
  return { start: Math.max(0, p.position_m - half), end: Math.min(w, p.position_m + half) }
}

const cells = computed<PositionedCell[]>(() => {
  if (!data.value) return []
  const w = effWidth.value
  if (w <= 0) return []
  const out: Cell[] = []
  for (const p of data.value.pillars || []) {
    const g = pillarGeom(p, w)
    if (g && g.end > g.start) {
      out.push({ kind: 'pillar', start: g.start, end: g.end, label: p.label || '挡柱', pillarId: p.id })
    }
  }
  for (const [i, p] of (data.value.placements || []).entries()) {
    out.push({ kind: 'stall', start: p.start_m, end: p.end_m, label: p.vendor_name, color: colors[i % colors.length] })
  }
  // 百分比相对有效右端——主图右端 == 引擎切空右端
  return out
    .sort((a, b) => a.start - b.start)
    .map(c => ({ ...c, leftPct: (c.start / w) * 100, widthPct: Math.max(((c.end - c.start) / w) * 100, 0) }))
})

async function refreshRuns() {
  runs.value = await api<RunMeta[]>('/allocate/runs?segment_id=1')
}

async function run() {
  // 再分始终实时按当前集日设置计算，后端不缓存改前宽度
  loading.value = true
  try {
    data.value = await api<RunData>('/allocate/run?segment_id=1', { method: 'POST' })
    activeRunId.value = data.value.id
    await refreshRuns()
  } finally { loading.value = false }
}

async function openRun(id: number) {
  // 抽屉回看：播放不可变快照，旧运行右端不被新系数回刷
  data.value = await api<RunData>(`/allocate/runs/${id}`)
  activeRunId.value = id
}

function fmtTime(iso: string) { return iso.replace('T', ' ').slice(0, 19) }

onMounted(async () => {
  vendors.value = await api('/vendors')
  const latest = await api<RunData>('/allocate/latest?segment_id=1')
  data.value = latest
  activeRunId.value = latest.id
  await refreshRuns()
})
</script>
<template>
  <div class="ss-street-wrap">
    <h1>街段分配带</h1>
    <p class="sub">沿街一维开间 · 挡柱为竖直阻断 · 底部为摊主排队 · 宽度一律按当次有效宽</p>
    <div style="display:flex;gap:.5rem;align-items:center;flex-wrap:wrap">
      <button class="btn" :disabled="loading" @click="run">{{ loading ? '分配中…' : '重新分配' }}</button>
      <button class="ss-btn-ghost" @click="drawerOpen = true">运行记录</button>
      <span v-if="data" :class="['badge', isRainy ? 'badge-warn' : 'badge-ok']">
        {{ isRainy ? `雨天 ×${data.segment.rain_width_factor}` : '晴天全长' }}
      </span>
      <span v-if="data && isRainy && registeredWidth != null" class="muted">
        登记 {{ registeredWidth }}m → 有效右端 {{ effWidth }}m
      </span>
      <span v-if="data" class="muted">放不下 {{ data.rejected?.length ?? 0 }} 家</span>
    </div>

    <div class="ss-band-ruler" v-if="data" :style="effWidth <= 0 ? { opacity: .5 } : {}">
      <span>0 m</span>
      <span>{{ data.segment.name }} · 有效宽 {{ effWidth }} m{{ effWidth <= 0 ? '（缩宽至 0，全部放不下）' : '' }}</span>
      <span>{{ effWidth }} m</span>
    </div>

    <div class="ss-track" v-if="data">
      <template v-if="effWidth > 0">
        <div
          v-for="(c, i) in cells" :key="(c.pillarId != null ? 'p' + c.pillarId : 's' + i)"
          class="ss-track-cell"
          :class="{ 'ss-track-pillar': c.kind === 'pillar' }"
          :style="{
            left: c.leftPct + '%', width: c.widthPct + '%',
            background: c.kind === 'pillar' ? undefined : c.color,
          }"
        >{{ c.label }}</div>
      </template>
      <p v-else class="muted" style="margin:auto;width:100%;text-align:center;font-weight:700">
        有效宽度为 0 m，没有任何街段参与切空
      </p>
    </div>

    <p v-if="data?.voided_pillars?.length" class="muted" style="margin:.35rem 0">
      作废挡柱（米标超出有效右端 {{ effWidth }}m，整根不参与切空、不出图）：
      <span v-for="p in data.voided_pillars" :key="p.id"
            class="badge badge-bad" style="margin-right:.35rem">{{ p.label }} @{{ p.position_m }}m</span>
    </p>

    <div class="ss-vendor-queue">
      <div v-for="v in vendors" :key="v.id" class="ss-vendor-chip">
        <strong>{{ v.name }}</strong>
        <span>需 {{ v.stall_width_m }} m · 优先 {{ v.priority }}</span>
      </div>
    </div>
    <div class="card" v-if="data">
      <h3 style="margin:.1rem 0 .5rem;font-size:.95rem">
        本次落点 · 右端口径 {{ effWidth }}m
        <span class="muted" style="font-weight:400;font-size:.75rem" v-if="data.created_at">
          （运行 #{{ data.id }} · {{ fmtTime(data.created_at) }}）
        </span>
      </h3>
      <table>
        <thead><tr><th>摊主</th><th>起点</th><th>终点</th><th>宽度</th></tr></thead>
        <tbody>
          <tr v-for="p in data.placements" :key="p.vendor_id">
            <td>{{ p.vendor_name }}</td><td>{{ p.start_m }}</td><td>{{ p.end_m }}</td><td>{{ p.width_m }}</td>
          </tr>
          <tr v-if="!data.placements.length"><td colspan="4" class="muted">无落点</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <template v-if="drawerOpen">
    <div class="ss-drawer-scrim" @click="drawerOpen = false"></div>
    <aside class="ss-drawer">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <h2 style="margin:0;font-size:1.05rem">运行抽屉</h2>
        <button class="ss-btn-ghost" @click="drawerOpen = false">关闭</button>
      </div>
      <p class="sub" style="margin:.5rem 0">每条运行是不可变快照；改系数只影响再分，旧运行右端不回刷。</p>
      <div
        v-for="r in runs" :key="r.id"
        class="ss-run-row" :class="{ active: r.id === activeRunId }"
        @click="openRun(r.id); drawerOpen = false"
      >
        <strong>#{{ r.id }} · {{ fmtTime(r.created_at) }}</strong>
        <div style="margin-top:.25rem">
          <span :class="['badge', r.rainy ? 'badge-warn' : 'badge-ok']">
            {{ r.rainy ? `雨天 ×${r.rain_width_factor}` : '晴天' }}
          </span>
          <span class="muted" style="margin-left:.4rem;font-size:.78rem">
            有效右端 {{ r.effective_width_m }}m<template
              v-if="r.registered_width_m != null && r.registered_width_m !== r.effective_width_m">
              （登记 {{ r.registered_width_m }}m）
            </template>
            · 放 {{ r.placed }} · 放不下 {{ r.rejected }}
          </span>
        </div>
      </div>
      <p v-if="!runs.length" class="muted">尚无运行</p>
    </aside>
  </template>
</template>
