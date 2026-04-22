import { createRouter, createWebHistory } from 'vue-router'
import DocumentList from '../views/DocumentList.vue'
import VersionList from '../views/VersionList.vue'

const routes = [
  {
    path: '/',
    redirect: '/documents',
  },
  {
    path: '/documents',
    name: 'documents',
    component: DocumentList,
  },
  {
    path: '/versions',
    name: 'versions',
    component: VersionList,
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
