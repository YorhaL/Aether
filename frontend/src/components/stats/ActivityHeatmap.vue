<template>
  <div class="space-y-4 w-full overflow-visible">
    <div
      v-if="showHeader"
      class="flex items-center justify-between gap-4"
    >
      <div class="flex-shrink-0">
        <p class="text-sm font-semibold">
          {{ title }}
        </p>
        <p
          v-if="subtitle"
          class="text-xs text-muted-foreground"
        >
          {{ subtitle }}
        </p>
      </div>
      <div
        v-if="weekColumns.length > 0"
        class="flex items-center gap-1 text-[11px] text-muted-foreground flex-shrink-0"
      >
        <span class="flex-shrink-0">少</span>
        <div
          v-for="(level, index) in legendLevels"
          :key="index"
          class="w-3 h-3 rounded-[3px] flex-shrink-0"
          :style="getLegendStyle(level)"
        />
        <span class="flex-shrink-0">多</span>
      </div>
    </div>

    <div
      v-if="weekColumns.length > 0"
      class="flex w-full gap-3 overflow-visible"
    >
      <div
        class="flex flex-col text-[10px] text-muted-foreground flex-shrink-0"
        :style="verticalGapStyle"
      >
        <!-- Placeholder to align with month markers -->
        <div class="text-[10px] mb-3 invisible">
          M
        </div>
        <span
          :style="dayLabelStyle"
          class="flex items-center invisible"
        >周日</span>
        <span
          :style="dayLabelStyle"
          class="flex items-center"
        >一</span>
        <span
          :style="dayLabelStyle"
          class="flex items-center invisible"
        >周二</span>
        <span
          :style="dayLabelStyle"
          class="flex items-center"
        >三</span>
        <span
          :style="dayLabelStyle"
          class="flex items-center invisible"
        >周四</span>
        <span
          :style="dayLabelStyle"
          class="flex items-center"
        >五</span>
        <span
          :style="dayLabelStyle"
          class="flex items-center invisible"
        >周六</span>
      </div>
      <div class="flex-1 min-w-[240px] overflow-visible">
        <div
          ref="heatmapWrapper"
          class="relative block w-full"
        >
          <div
            v-if="tooltip.visible && tooltip.day"
            class="fixed z-10 rounded-lg border border-border/70 bg-background px-3 py-2 text-xs shadow-lg backdrop-blur pointer-events-none"
            :style="tooltipStyle"
          >
            <p class="font-medium">
              {{ tooltip.day.date }}
            </p>
            <p class="mt-0.5">
              {{ tooltip.day.requests }} 次请求 · {{ formatTokens(tooltip.day.total_tokens) }}
            </p>
            <p class="text-[11px] text-muted-foreground">
              成本 {{ formatCurrency(tooltip.day.total_cost) }}
            </p>
          </div>
          <div
            class="flex text-[10px] text-muted-foreground/80 mb-3"
            :style="horizontalGapStyle"
          >
            <div
              v-for="(week, weekIndex) in weekColumns"
              :key="`month-${weekIndex}`"
              :style="monthCellStyle"
              class="text-center"
            >
              <span v-if="monthMarkers[weekIndex]">{{ monthMarkers[weekIndex] }}</span>
            </div>
          </div>
          <div
            class="flex"
            :style="horizontalGapStyle"
          >
            <div
              v-for="(week, weekIndex) in weekColumns"
              :key="weekIndex"
              class="flex flex-col"
              :style="verticalGapStyle"
            >
              <div
                v-for="(day, dayIndex) in week"
                :key="dayIndex"
                class="relative group"
              >
                <div
                  v-if="day"
                  class="rounded-[4px] transition-all duration-200 hover:shadow-lg cursor-pointer cell-emerge"
                  :style="[cellSquareStyle, getCellStyle(day.requests), getCellAnimationDelay(weekIndex, dayIndex)]"
                  :title="buildTooltip(day)"
                  @mouseenter="handleHover(day, $event)"
                  @mouseleave="clearHover"
                />
                <div
                  v-else
                  :style="cellSquareStyle"
                  class="rounded-[4px] bg-transparent"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <p
      v-else
      class="text-xs text-muted-foreground"
    >
      暂无活跃数据
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { ActivityHeatmap, ActivityHeatmapDay } from '@/types/activity'
import { formatCurrency, formatTokens } from '@/utils/format'

const props = withDefaults(defineProps<{
  data?: ActivityHeatmap | null
  title?: string
  subtitle?: string
  showHeader?: boolean
}>(), {
  data: undefined,
  title: undefined,
  subtitle: undefined,
  showHeader: true
})

const legendLevels = [0.08, 0.25, 0.45, 0.65, 0.85]

type DayWithMeta = ActivityHeatmapDay & { dateObj: Date }
const heatmapWrapper = ref<HTMLElement | null>(null)
const heatmapWidth = ref(0)
const cellSize = ref(10)
const cellGap = ref(4)
const tooltip = ref<{ day: ActivityHeatmapDay | null; x: number; y: number; visible: boolean; below: boolean }>({
  day: null,
  x: 0,
  y: 0,
  visible: false,
  below: false,
})
const tooltipStyle = computed(() => ({
  top: `${tooltip.value.y}px`,
  left: `${tooltip.value.x}px`,
  transform: tooltip.value.below ? 'translate(-50%, 0)' : 'translate(-50%, -100%)',
}))

const cellSquareStyle = computed(() => ({
  width: `${cellSize.value}px`,
  height: `${cellSize.value}px`,
}))

const dayLabelStyle = computed(() => ({
  height: `${cellSize.value}px`,
  lineHeight: `${cellSize.value}px`,
}))

const monthCellStyle = computed(() => ({
  width: `${cellSize.value}px`,
}))

const horizontalGapStyle = computed(() => ({
  gap: `${cellGap.value}px`,
}))

const verticalGapStyle = computed(() => ({
  rowGap: `${cellGap.value}px`,
}))

const weekColumns = computed(() => {
  if (!props.data || !props.data.days || props.data.days.length === 0) {
    return []
  }

  const dayEntries: DayWithMeta[] = props.data.days.map(day => ({
    ...day,
    dateObj: new Date(`${day.date}T00:00:00Z`)
  }))

  const firstDay = dayEntries[0]?.dateObj
  const padding: (DayWithMeta | null)[] = []
  if (firstDay) {
    const weekday = firstDay.getUTCDay() // 周日=0, 周一=1, ..., 周六=6
    for (let i = 0; i < weekday; i++) {
      padding.push(null)
    }
  }

  const paddedDays: (DayWithMeta | null)[] = [...padding, ...dayEntries]
  const remainder = paddedDays.length % 7
  if (remainder !== 0) {
    for (let i = remainder; i < 7; i++) {
      paddedDays.push(null)
    }
  }

  const chunked: (DayWithMeta | null)[][] = []
  for (let i = 0; i < paddedDays.length; i += 7) {
    chunked.push(paddedDays.slice(i, i + 7))
  }

  // Trim trailing empty weeks (weeks with all null cells)
  let lastIndex = chunked.length - 1
  while (lastIndex >= 0) {
    const week = chunked[lastIndex]
    const hasAnyDay = week.some(day => day !== null)
    if (hasAnyDay) {
      break
    }
    lastIndex--
  }

  return chunked.slice(0, lastIndex + 1)
})

const monthMarkers = computed(() => {
  const markers: Record<number, string> = {}
  const columns = weekColumns.value
  let lastMonth: number | null = null

  columns.forEach((week, index) => {
    const firstValid = week.find((day): day is DayWithMeta => day !== null)
    if (!firstValid) {
      return
    }
    const month = firstValid.dateObj.getUTCMonth()
    if (month === lastMonth) {
      return
    }
    markers[index] = `${month + 1}月`
    lastMonth = month
  })

  return markers
})

let resizeObserver: ResizeObserver | null = null
let mediaQuery: MediaQueryList | null = null
let mediaQueryHandler: ((event?: MediaQueryListEvent) => void) | null = null

const recalcCellSize = () => {
  const columnCount = weekColumns.value.length
  if (!columnCount || !heatmapWidth.value) {
    return
  }

  const totalGap = Math.max(columnCount - 1, 0) * cellGap.value
  const availableSpace = Math.max(heatmapWidth.value - totalGap, 0)
  const rawSize = availableSpace / columnCount
  // 不设置上限，让格子填满可用空间
  cellSize.value = rawSize > 0 ? rawSize : 8
}

watch(
  [() => heatmapWidth.value, () => weekColumns.value.length, () => cellGap.value],
  () => {
    recalcCellSize()
  },
  { immediate: true }
)

watch(
  () => heatmapWrapper.value,
  el => {
    resizeObserver?.disconnect()
    if (el && typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(entries => {
        if (!entries.length) {
          return
        }
        heatmapWidth.value = entries[0].contentRect.width
        recalcCellSize()
      })
      resizeObserver.observe(el)
    } else {
      heatmapWidth.value = 0
    }
  },
  { immediate: true }
)

onMounted(() => {
  if (typeof window === 'undefined') {
    return
  }
  mediaQuery = window.matchMedia('(min-width: 640px)')
  const updateGap = () => {
    cellGap.value = mediaQuery && mediaQuery.matches ? 4 : 2
    recalcCellSize()
  }
  mediaQueryHandler = () => updateGap()
  updateGap()
  mediaQuery?.addEventListener('change', mediaQueryHandler)
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  if (mediaQuery && mediaQueryHandler) {
    mediaQuery.removeEventListener('change', mediaQueryHandler)
  }
})

function handleHover(day: ActivityHeatmapDay, event: MouseEvent) {
  const cellRect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  const tooltipWidth = 200
  const tooltipHeight = 72

  // Calculate horizontal position (centered on cell)
  let left = cellRect.left + cellRect.width / 2
  const minLeft = tooltipWidth / 2 + 8
  const maxLeft = window.innerWidth - tooltipWidth / 2 - 8
  left = Math.min(Math.max(left, minLeft), maxLeft)

  // Calculate vertical position
  let top = cellRect.top - 12
  let below = false

  // If tooltip would go above viewport, show it below the cell
  if (top - tooltipHeight < 0) {
    top = cellRect.bottom + 12
    below = true
  }

  tooltip.value = {
    day,
    x: left,
    y: top,
    visible: true,
    below,
  }
}

function clearHover() {
  tooltip.value.visible = false
}

function getLegendStyle(alpha: number) {
  return {
    backgroundColor: `rgba(var(--color-primary-rgb), ${alpha})`
  }
}

function getCellStyle(requests: number) {
  const max = props.data?.max_requests || 1
  if (!requests || max === 0) {
    return {
      backgroundColor: `rgba(var(--color-primary-rgb), 0.08)`
    }
  }

  const ratio = Math.min(1, requests / max)
  const minAlpha = 0.2
  const maxAlpha = 0.95
  const alpha = minAlpha + (maxAlpha - minAlpha) * ratio
  return {
    backgroundColor: `rgba(var(--color-primary-rgb), ${alpha})`
  }
}

function buildTooltip(day: ActivityHeatmapDay): string {
  const dateLabel = day.date
  const costLabel = formatCurrency(day.total_cost || 0)
  const parts = [`${dateLabel}`, `${day.requests} 次请求`, `${formatTokens(day.total_tokens)} tokens`, costLabel]
  if (day.actual_total_cost !== undefined) {
    parts.push(`倍率: ${formatCurrency(day.actual_total_cost)}`)
  }
  return parts.join(' · ')
}

// 生成完全随机的动画延迟，每个格子独立随机弹出
const cellDelayMap = new Map<string, number>()

function getCellAnimationDelay(weekIndex: number, dayIndex: number) {
  const key = `${weekIndex}-${dayIndex}`
  if (!cellDelayMap.has(key)) {
    // 完全随机延迟，范围 0-800ms
    cellDelayMap.set(key, Math.random() * 800)
  }
  return {
    animationDelay: `${cellDelayMap.get(key)}ms`
  }
}
</script>

<style scoped>
.cell-emerge {
  opacity: 0;
  animation: cellEmerge 0.35s ease-out forwards;
}

@keyframes cellEmerge {
  0% {
    opacity: 0;
  }
  100% {
    opacity: 1;
  }
}
</style>
