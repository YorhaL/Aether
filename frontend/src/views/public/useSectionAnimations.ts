import { computed, type Ref, type CSSProperties } from 'vue'
import { SECTIONS } from './home-config'

// Animation configuration constants
const ANIMATION_CONFIG = {
  delays: {
    badge: 0,
    title: 0.1,
    desc: 0.2,
    buttons: 0.3,
    scrollIndicator: 0.4,
    cardBase: 0.25,
    cardIncrement: 0.1,
    featureCardBase: 0.2,
    featureCardIncrement: 0.15
  },
  translateY: {
    home: 30,
    cli: 10,
    badge: 8,
    featureCard: 30
  },
  translateX: {
    badge: 24,
    title: 32,
    desc: 28,
    buttons: 24,
    card: 20
  }
} as const

// Get horizontal direction based on section layout
// Claude(1) and Gemini(3) content on right, slide from right
// Codex(2) content on left, slides from left
function getDirectionMultiplier(index: number): number {
  if (index === SECTIONS.CLAUDE || index === SECTIONS.GEMINI) return 1
  if (index === SECTIONS.CODEX) return -1
  return 0
}

function getHorizontalOffset(index: number, distance: number, progress: number): number {
  const direction = getDirectionMultiplier(index)
  if (direction === 0) return 0
  return (1 - progress) * distance * direction
}

export function useSectionAnimations(sectionVisibility: Ref<number[]>) {
  const { delays, translateY, translateX } = ANIMATION_CONFIG

  // Style generators for different elements
  const getBadgeStyle = (index: number): CSSProperties => {
    const visibility = sectionVisibility.value[index]
    const opacity = Math.min(1, visibility * 3)
    const progress = Math.min(1, visibility * 2)
    const direction = getDirectionMultiplier(index)
    const offsetX = getHorizontalOffset(index, translateX.badge, progress)
    const offsetY = direction === 0 ? (1 - progress) * translateY.badge : 0
    return {
      opacity,
      transform: `translate(${offsetX}px, ${offsetY}px)`
    }
  }

  const getTitleStyle = (index: number): CSSProperties => {
    const visibility = sectionVisibility.value[index]
    const adjustedVisibility = Math.max(0, visibility - delays.title) / (1 - delays.title)
    const progress = Math.min(1, adjustedVisibility * 2)
    const yBase = getDirectionMultiplier(index) === 0 ? translateY.home : translateY.cli
    const offsetY = (1 - progress) * yBase
    const offsetX = getHorizontalOffset(index, translateX.title, progress)
    return {
      opacity: progress,
      transform: `translate(${offsetX}px, ${offsetY}px)`
    }
  }

  const getDescStyle = (index: number): CSSProperties => {
    const visibility = sectionVisibility.value[index]
    const adjustedVisibility = Math.max(0, visibility - delays.desc) / (1 - delays.desc)
    const progress = Math.min(1, adjustedVisibility * 2)
    const yBase = getDirectionMultiplier(index) === 0 ? translateY.home : translateY.badge
    const offsetY = (1 - progress) * yBase
    const offsetX = getHorizontalOffset(index, translateX.desc, progress)
    return {
      opacity: progress,
      transform: `translate(${offsetX}px, ${offsetY}px)`
    }
  }

  const getButtonsStyle = (index: number): CSSProperties => {
    const visibility = sectionVisibility.value[index]
    const adjustedVisibility = Math.max(0, visibility - delays.buttons) / (1 - delays.buttons)
    const progress = Math.min(1, adjustedVisibility * 2)
    const yBase = getDirectionMultiplier(index) === 0 ? 20 : translateY.badge
    const offsetY = (1 - progress) * yBase
    const offsetX = getHorizontalOffset(index, translateX.buttons, progress)
    return {
      opacity: progress,
      transform: `translate(${offsetX}px, ${offsetY}px)`
    }
  }

  const getScrollIndicatorStyle = (index: number): CSSProperties => {
    const visibility = sectionVisibility.value[index]
    const adjustedVisibility = Math.max(0, visibility - delays.scrollIndicator) / (1 - delays.scrollIndicator)
    const opacity = Math.min(1, adjustedVisibility * 2)
    return { opacity }
  }

  const getCardStyle = (sectionIndex: number, cardIndex: number): CSSProperties => {
    const visibility = sectionVisibility.value[sectionIndex]
    const totalDelay = delays.cardBase + cardIndex * delays.cardIncrement
    const adjustedVisibility = Math.max(0, visibility - totalDelay) / (1 - totalDelay)
    const progress = Math.min(1, adjustedVisibility * 2)
    const yBase = getDirectionMultiplier(sectionIndex) === 0 ? 20 : translateY.cli
    const offsetY = (1 - progress) * yBase
    const offsetX = getHorizontalOffset(sectionIndex, translateX.card, progress)
    return {
      opacity: progress,
      transform: `translate(${offsetX}px, ${offsetY}px)`
    }
  }

  const getFeatureCardStyle = (sectionIndex: number, cardIndex: number): CSSProperties => {
    const visibility = sectionVisibility.value[sectionIndex]
    const totalDelay = delays.featureCardBase + cardIndex * delays.featureCardIncrement
    const adjustedVisibility = Math.max(0, visibility - totalDelay) / (1 - totalDelay)
    const opacity = Math.min(1, adjustedVisibility * 2)
    const offsetY = (1 - Math.min(1, adjustedVisibility * 2)) * translateY.featureCard
    const scale = 0.9 + Math.min(1, adjustedVisibility * 2) * 0.1
    return {
      opacity,
      transform: `translateY(${offsetY}px) scale(${scale})`
    }
  }

  return {
    getBadgeStyle,
    getTitleStyle,
    getDescStyle,
    getButtonsStyle,
    getScrollIndicatorStyle,
    getCardStyle,
    getFeatureCardStyle
  }
}

// Fixed logo position style based on current section
export function useLogoPosition(
  currentSection: Ref<number>,
  windowWidth: Ref<number>
) {
  const fixedLogoStyle = computed(() => {
    const section = currentSection.value
    const isDesktop = windowWidth.value >= 768
    let transform = ''
    let opacity = 1

    if (section === SECTIONS.HOME) {
      transform = 'scale(1.1) translateY(-12vh)'
      opacity = 0.25
    } else if (section === SECTIONS.CLAUDE) {
      // Mobile: move logo higher and reduce opacity to avoid blocking content
      transform = isDesktop ? 'translateX(-25vw) scale(1)' : 'translateY(-32vh) scale(0.6)'
      opacity = isDesktop ? 1 : 0.2
    } else if (section === SECTIONS.CODEX) {
      transform = isDesktop ? 'translateX(25vw) scale(1)' : 'translateY(-32vh) scale(0.6)'
      opacity = isDesktop ? 1 : 0.2
    } else if (section === SECTIONS.GEMINI) {
      transform = isDesktop ? 'translateX(-25vw) scale(1)' : 'translateY(-32vh) scale(0.6)'
      opacity = isDesktop ? 1 : 0.2
    } else {
      transform = isDesktop ? 'translateX(0) scale(1)' : 'translateY(-20vh) scale(0.8)'
      opacity = 0.15
    }

    return {
      transform,
      opacity,
      transition: 'transform 0.8s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.6s ease-out'
    }
  })

  return { fixedLogoStyle }
}

// Logo transition name based on scroll direction
export function useLogoTransition(
  currentSection: Ref<number>,
  previousSection: Ref<number>
) {
  const logoTransitionName = computed(() => {
    if (currentSection.value === SECTIONS.HOME || previousSection.value === SECTIONS.HOME) {
      return 'logo-scale'
    }
    if (currentSection.value > previousSection.value) {
      return 'logo-slide-left'
    }
    return 'logo-slide-right'
  })

  return { logoTransitionName }
}
