import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import * as Lucide from 'lucide-vue-next'

const app = createApp(App)
app.config.globalProperties.$lucide = Lucide
app.mount('#app')
