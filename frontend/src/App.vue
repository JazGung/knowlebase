<template>
  <el-container style="height: 100vh">
    <el-header style="background: #409eff; color: white; display: flex; align-items: center; padding: 0 20px;">
      <el-icon :size="24" style="margin-right: 12px"><Files /></el-icon>
      <span style="font-size: 18px; font-weight: bold;">知识库管理系统</span>
    </el-header>
    <el-main style="padding: 20px;">
      <DocumentList />
    </el-main>
  </el-container>
</template>

<script setup>
import { Files } from '@element-plus/icons-vue'
import DocumentList from './views/DocumentList.vue'
</script>

<style>
body {
  margin: 0;
  padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}
</style>
