<script setup lang="ts">
import { PopoverRoot } from 'radix-vue'

const props = withDefaults(defineProps<{
  defaultOpen?: boolean
  open?: boolean
  modal?: boolean
}>(), {
  defaultOpen: false,
  modal: false,
})

const emit = defineEmits<{
  'update:open': [value: boolean]
}>()
</script>

<template>
  <PopoverRoot
    :default-open="props.defaultOpen"
    :open="props.open"
    :modal="props.modal"
    @update:open="emit('update:open', $event)"
  >
    <slot />
  </PopoverRoot>
</template>
