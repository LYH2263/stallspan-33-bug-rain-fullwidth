<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'

interface DayRow {
  id: number
  name: string
  day: string
  rainy: boolean
  rain_width_factor: number | null
}

const rows = ref<DayRow[]>([])
// 草稿与服务器值分开：保存被拒绝时整行回滚，不留半截状态。
const draftRainy = ref<Record<number, boolean>>({})
const draftFactor = ref<Record<number, string>>({})
const saving = ref<number | null>(null)
const error = ref<string>('')
const okMsg = ref<string>('')

function factorText(d: DayRow): string {
  const v = draftFactor.value[d.id]
  if (v !== undefined) return v
  return d.rain_width_factor == null ? '' : d.rain_width_factor.toString()
}

function isDirty(d: DayRow): boolean {
  const r = draftRainy.value[d.id]
  const rainy = r === undefined ? d.rainy : r
  if (rainy !== d.rainy) return true
  if (rainy) {
    const f = (draftFactor.value[d.id] ?? '').trim()
    if (f === '') return true
    if (Number(f) !== Number(d.rain_width_factor)) return true
  }
  return false
}

async function save(d: DayRow) {
  error.value = ''; okMsg.value = ''
  const rainy = draftRainy.value[d.id] ?? d.rainy
  const raw = (draftFactor.value[d.id] ?? '').trim()
  const factor = raw === '' ? null : Number(raw)
  saving.value = d.id
  try {
    const saved = await api<DayRow>(`/days/${d.id}`, {
      method: 'PUT',
      body: JSON.stringify({ rainy, rain_width_factor: rainy ? factor : null }),
    })
    const i = rows.value.findIndex(r => r.id === d.id)
    if (i >= 0) rows.value[i] = saved
    // 清空草稿，使重开/当前显示都以服务器为准
    delete draftRainy.value[d.id]
    delete draftFactor.value[d.id]
    okMsg.value = `${saved.name}：已保存（雨天 ${saved.rainy ? `缩宽 ×${saved.rain_width_factor}` : '关闭，按晴天全长'}）`
  } catch (e: any) {
    // 后端 400：集日页、主图、放不下保持改前，主图不会半截缩短
    let detail = e?.message || '保存被拒绝'
    try { detail = JSON.parse(detail).detail || detail } catch { /* 非 JSON 正文 */ }
    error.value = `已拒绝保存，保持改前状态：${detail}`
    rollback(d)
  } finally {
    saving.value = null
  }
}

function rollback(d: DayRow) {
  delete draftRainy.value[d.id]
  delete draftFactor.value[d.id]
}

onMounted(async () => { rows.value = await api('/days') })
</script>
<template>
  <h1>集日</h1>
  <p class="sub">开市日程 · 雨天缩宽登记（有效宽度系数 0 到 1，仅雨天生效；非雨天按晴天全长）</p>
  <p v-if="error" class="card" style="border-color:var(--ss-bad);color:var(--ss-bad)">{{ error }}</p>
  <p v-if="okMsg" class="muted">{{ okMsg }}</p>
  <div class="card">
    <table>
      <thead>
        <tr><th>名称</th><th>日期</th><th>雨天</th><th>有效宽度系数</th><th></th></tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id">
          <td>{{ r.name }}</td>
          <td>{{ r.day }}</td>
          <td>
            <label style="display:flex;align-items:center;gap:.35rem;cursor:pointer">
              <input
                type="checkbox"
                :checked="draftRainy[r.id] ?? r.rainy"
                @change="draftRainy[r.id] = ($event.target as HTMLInputElement).checked"
              />
              <span :class="(draftRainy[r.id] ?? r.rainy) ? 'badge badge-warn' : 'badge badge-ok'">
                {{ (draftRainy[r.id] ?? r.rainy) ? '雨天' : '晴天' }}
              </span>
            </label>
          </td>
          <td>
            <input
              type="number" class="ss-factor-input" min="0" max="1" step="0.05"
              placeholder="0 到 1"
              :disabled="!(draftRainy[r.id] ?? r.rainy)"
              :value="factorText(r)"
              @input="draftFactor[r.id] = ($event.target as HTMLInputElement).value"
            />
          </td>
          <td>
            <button class="btn" :disabled="!isDirty(r) || saving === r.id" @click="save(r)">
              {{ saving === r.id ? '保存中…' : '保存' }}
            </button>
            <button
              v-if="isDirty(r)" class="ss-btn-ghost"
              @click="rollback(r)" style="margin-left:.4rem"
            >还原</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
  <p class="muted">
    雨天为真但系数缺失或不在 0–1 时，保存会被拒绝；改系数后请到「分配带」点重新分配，主图右端、放不下、运行记录会统一按新有效宽。
  </p>
</template>
