<template>
  <el-container style="height: 100vh">
    <!-- 侧边栏 -->
    <el-aside width="200px" style="background: #304156;">
      <div style="height: 60px; display: flex; align-items: center; justify-content: center; background: #263445; color: white; font-size: 16px; font-weight: bold;">
        <el-icon :size="20" style="margin-right: 8px;"><Files /></el-icon>
        知识库管理
      </div>
      <el-menu
        :default-active="activeMenu"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
        router
      >
        <el-menu-item index="/documents">
          <el-icon><Document /></el-icon>
          <span>文档管理</span>
        </el-menu-item>
        <el-menu-item index="/versions">
          <el-icon><Connection /></el-icon>
          <span>版本管理</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- 主内容区 -->
    <el-container>
      <el-header style="background: #fff; border-bottom: 1px solid #e6e6e6; display: flex; align-items: center; padding: 0 20px;">
        <span style="font-size: 16px; font-weight: 500; color: #303133;">{{ currentPageTitle }}</span>
      </el-header>
      <el-main style="padding: 20px; background: #f5f7fa;">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Files, Document, Connection } from '@element-plus/icons-vue'

const route = useRoute()

const activeMenu = computed(() => route.path)

const currentPageTitle = computed(() => {
  const titles = {
    '/documents': '文档管理',
    '/versions': '版本管理',
  }
  return titles[route.path] || '知识库管理系统'
})
</script>

<style>
body {
  margin: 0;
  padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}
</style>
