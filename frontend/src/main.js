import { createApp } from 'vue'
import { ElMessageBox } from 'element-plus'
import 'element-plus/theme-chalk/base.css'
import 'element-plus/theme-chalk/el-overlay.css'
import 'element-plus/theme-chalk/el-icon.css'
import 'element-plus/theme-chalk/el-button.css'
import 'element-plus/theme-chalk/el-message-box.css'
import 'leaflet/dist/leaflet.css'
import './style.css'
import App from './App.vue'

createApp(App).use(ElMessageBox).mount('#app')
import 'element-plus/theme-chalk/el-dialog.css'
