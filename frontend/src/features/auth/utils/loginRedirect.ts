import { isNavigationFailure, NavigationFailureType, type Router } from 'vue-router'

export type LoginNavigationResult = 'router' | 'already-there' | 'document'

type DocumentNavigate = (targetPath: string) => void

function defaultDocumentNavigate(targetPath: string) {
  window.location.assign(targetPath)
}

export async function navigateAfterLogin(
  router: Router,
  targetPath: string,
  documentNavigate: DocumentNavigate = defaultDocumentNavigate,
): Promise<LoginNavigationResult> {
  try {
    const navigationFailure = await router.push(targetPath)

    if (isNavigationFailure(navigationFailure, NavigationFailureType.duplicated)) {
      return 'already-there'
    }

    if (navigationFailure) {
      documentNavigate(targetPath)
      return 'document'
    }

    return 'router'
  } catch {
    documentNavigate(targetPath)
    return 'document'
  }
}
