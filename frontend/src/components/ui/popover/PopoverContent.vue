<script setup lang="ts">
import { PopoverContent, PopoverPortal } from 'radix-vue'
import { cn } from '@/lib/utils'

const props = withDefaults(defineProps<{
  class?: string
  align?: 'start' | 'center' | 'end'
  side?: 'top' | 'right' | 'bottom' | 'left'
  sideOffset?: number
  alignOffset?: number
}>(), {
  align: 'center',
  side: 'bottom',
  sideOffset: 4,
  alignOffset: 0,
})
</script>

<template>
  <PopoverPortal>
    <PopoverContent
      :class="cn(
        'z-50 w-72 rounded-md border bg-popover p-4 text-popover-foreground shadow-md outline-none',
        'data-[state=open]:animate-in data-[state=closed]:animate-out',
        'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
        'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
        'data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2',
        'data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2',
        props.class
      )"
      :align="props.align"
      :side="props.side"
      :side-offset="props.sideOffset"
      :align-offset="props.alignOffset"
    >
      <slot />
    </PopoverContent>
  </PopoverPortal>
</template>
