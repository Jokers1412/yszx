import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

import App from './App.vue'
import router from './router'
import { getProfile } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { useSiteStore } from '@/stores/site'
import './styles/index.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus)
app.mount('#app')

// 启动即拉取平台公开配置（管理端系统设置同步，04 §3.2；失败回落默认值不影响页面）
useSiteStore().load()

// 已登录则回填用户快照（顶栏昵称/头像刷新后即显；失败静默，401 由请求层续期/踢出）
const auth = useAuthStore()
if (auth.isLoggedIn) {
  getProfile()
    .then((p) =>
      auth.hydrateStudent({
        id: p.id,
        nickname: p.nickname,
        avatarUrl: p.avatarUrl,
        isAdmin: p.isAdmin,
        phone: p.phone,
      }),
    )
    .catch(() => undefined)
}
