<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
const seg = ref<any>(null)
const runId = ref<number | null>(null)
onMounted(async () => {
  // 与主图同一个最新运行快照：放不下集合与有效右端严格同源
  const data = await api('/allocate/latest?segment_id=1')
  rows.value = data.rejected || []
  seg.value = data.segment || null
  runId.value = data.id
})
</script>
<template>
  <h1>放不下</h1>
  <p class="sub">无法在连续空档内安置且不跨越挡柱的摊位 · 口径与主图、引擎一致</p>
  <div class="card" v-if="seg">
    <span :class="['badge', seg.rainy ? 'badge-warn' : 'badge-ok']">
      {{ seg.rainy ? `雨天 ×${seg.rain_width_factor}` : '晴天全长' }}
    </span>
    <strong style="margin-left:.5rem">{{ seg.name }}</strong>
    <span class="muted" style="margin-left:.5rem">
      有效右端 {{ seg.effective_width_m ?? seg.width_m }} m
      <template v-if="seg.registered_width_m != null && seg.registered_width_m !== (seg.effective_width_m ?? seg.width_m)">
        （登记 {{ seg.registered_width_m }}m）
      </template>
      · 运行 #{{ runId }}
    </span>
  </div>
  <div class="card">
    <table>
      <thead><tr><th>摊主</th><th>需求宽度</th><th>原因</th></tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.vendor_id">
          <td>{{ r.vendor_name }}</td><td>{{ r.width_m }}</td><td>{{ r.reason }}</td>
        </tr>
      </tbody>
    </table>
    <p v-if="!rows.length" class="muted">全部放下</p>
  </div>
</template>
