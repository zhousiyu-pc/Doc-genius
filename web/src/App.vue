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
/* ── CSS 变量：浅色主题（GPT 风格） ────────────────────── */
:root, [data-theme="light"] {
  --bg-primary: #ffffff;
  --bg-secondary: #f7f7f8;
  --bg-hover: #f0f0f0;
  --bg-active: #ececec;
  --bg-input: #ffffff;
  --bg-bubble-user: #ffffff;
  --bg-bubble-ai: #f7f7f8;
  --bg-bubble-system: #f7f7f8;
  --bg-code: #f6f8fa;
  --border-primary: #e5e5e5;
  --border-light: #efefef;
  --text-primary: #1a1a1a;
  --text-secondary: #374151;
  --text-tertiary: #6b7280;
  --text-muted: #8e8ea0;
  --text-bubble-user: #1a1a1a;
  --shadow-card: 0 2px 6px rgba(0, 0, 0, 0.05);
}

/* ── CSS 变量：深色主题（GPT 风格） ────────────────────── */
[data-theme="dark"] {
  --bg-primary: #343541;
  --bg-secondary: #444654;
  --bg-hover: #4e4f60;
  --bg-active: #565869;
  --bg-input: #40414f;
  --bg-bubble-user: #343541;
  --bg-bubble-ai: #444654;
  --bg-bubble-system: #444654;
  --bg-code: #2d2d3a;
  --border-primary: #4e4f60;
  --border-light: #444654;
  --text-primary: #ececf1;
  --text-secondary: #d1d5db;
  --text-tertiary: #9ca3af;
  --text-muted: #8e8ea0;
  --text-bubble-user: #ececf1;
  --shadow-card: 0 2px 6px rgba(0, 0, 0, 0.3);
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
