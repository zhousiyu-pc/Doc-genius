<template>
  <el-config-provider :locale="locale">
    <router-view />
  </el-config-provider>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import { useThemeStore } from '@/stores/theme'

const locale = zhCn
const themeStore = useThemeStore()

onMounted(() => {
  themeStore.init()
})
</script>

<style>
/* ── CSS 变量：浅色主题 ────────────────────── */
:root, [data-theme="light"] {
  --bg-primary: #f8fafc;
  --bg-secondary: #ffffff;
  --bg-hover: #f0f4ff;
  --bg-active: #e8f0fe;
  --bg-input: #ffffff;
  --bg-bubble-user: #409eff;
  --bg-bubble-ai: #ffffff;
  --bg-bubble-system: #f5f5f5;
  --bg-code: #f6f8fa;
  --border-primary: #e8ecf1;
  --border-light: #f0f0f0;
  --text-primary: #0f172a;
  --text-secondary: #333;
  --text-tertiary: #666;
  --text-muted: #999;
  --text-bubble-user: #ffffff;
  --shadow-card: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
}

/* ── CSS 变量：深色主题 ────────────────────── */
[data-theme="dark"] {
  --bg-primary: #0f172a;
  --bg-secondary: #1e293b;
  --bg-hover: #334155;
  --bg-active: #1e3a5f;
  --bg-input: #1e293b;
  --bg-bubble-user: #2563eb;
  --bg-bubble-ai: #1e293b;
  --bg-bubble-system: #1e293b;
  --bg-code: #0f172a;
  --border-primary: #334155;
  --border-light: #1e293b;
  --text-primary: #f1f5f9;
  --text-secondary: #e2e8f0;
  --text-tertiary: #94a3b8;
  --text-muted: #64748b;
  --text-bubble-user: #ffffff;
  --shadow-card: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background-color: var(--bg-primary);
  color: var(--text-primary);
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  transition: background-color 0.3s, color 0.3s;
}

#app {
  width: 100%;
  min-height: 100vh;
}

.el-card {
  border: none !important;
  box-shadow: var(--shadow-card) !important;
  border-radius: 16px !important;
}

.el-button {
  border-radius: 8px !important;
  font-weight: 500 !important;
}

.el-input__wrapper, .el-textarea__inner {
  border-radius: 12px !important;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05) !important;
}
</style>
