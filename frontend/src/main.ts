import dayjs from 'dayjs'
import 'dayjs/locale/ja'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { AppTheme } from './theme'
import 'primeicons/primeicons.css'

dayjs.locale('ja')

const app = createApp(App)
app.use(createPinia())
app.use(PrimeVue, {
  theme: { preset: AppTheme, options: { darkModeSelector: false } },
  locale: { firstDayOfWeek: 0 },
})
app.use(ToastService)
app.use(router)
app.mount('#app')
