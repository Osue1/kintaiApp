import { definePreset } from '@primeuix/themes'
import Aura from '@primeuix/themes/aura'

/**
 * ブランドの --accent（グリーン）を PrimeVue の primary スケールに展開したプリセット。
 * ダークモードは今のところ設計対象外なので main.ts 側で無効化する。
 */
export const AppTheme = definePreset(Aura, {
  semantic: {
    primary: {
      50: '#eefcf6',
      100: '#d3f6e4',
      200: '#a7edc9',
      300: '#71dcac',
      400: '#3fc491',
      500: '#1aa877',
      600: '#0f8a63',
      700: '#0d6f51',
      800: '#0e5941',
      900: '#0d4936',
      950: '#062a1f',
    },
  },
  components: {
    button: {
      root: { borderRadius: '10px' },
    },
    card: {
      root: { borderRadius: '16px' },
    },
  },
})
