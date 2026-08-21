const { createApp, ref, onMounted, defineComponent } = Vue;

const RunTable = defineComponent({
  props: { runs: { type: Array, required: true } },
  emits: ['view-log'],
  template: `<div class="table-wrap"><table><thead><tr><th>任务</th><th>状态</th><th>开始时间</th><th>退出码</th><th>错误</th><th>操作</th></tr></thead><tbody><tr v-for="item in runs" :key="item.id"><td class="strong">{{ item.task_name }}</td><td><span :class="['status', item.status.toLowerCase()]">{{ item.status }}</span></td><td>{{ item.started_at }}</td><td>{{ item.exit_code ?? '-' }}</td><td class="error-text">{{ item.error || '-' }}</td><td><button class="action" @click="$emit('view-log', item)">查看日志</button></td></tr><tr v-if="!runs.length"><td colspan="6" class="empty">暂无执行记录</td></tr></tbody></table></div>`
});

createApp({
  components: { RunTable },
  setup() {
    const view = ref('overview');
    const scripts = ref([]); const tasks = ref([]); const runs = ref([]); const notice = ref(''); const noticeType = ref(''); const loading = ref(false);
    const logPanel = ref({ open: false, loading: false, item: null, content: '' });
    const taskForm = ref({ name: '', script_id: '', schedule: '', timeout_seconds: 600 });
    const titles = { overview: '工作台', scripts: '脚本管理', tasks: '任务管理', runs: '执行记录', settings: 'AI 配置' };
    async function request(url, options) { const response = await fetch(url, options); const data = await response.json(); if (!response.ok) throw new Error(data.detail || '请求失败'); return data; }
    function showNotice(message, type = '') { notice.value = message; noticeType.value = type; }
    async function loadAll() { loading.value = true; try { [scripts.value, tasks.value, runs.value] = await Promise.all([request('/api/scripts'), request('/api/tasks'), request('/api/executions')]); } catch (error) { showNotice(`数据加载失败：${error.message}`, 'error'); } finally { loading.value = false; } }
    async function importScript(event) { const file = event.target.files[0]; if (!file) return; const form = new FormData(); form.append('package', file); try { await request('/api/scripts/import', { method: 'POST', body: form }); showNotice('脚本导入成功'); await loadAll(); } catch (error) { showNotice(error.message, 'error'); } event.target.value = ''; }
    async function createTask() { try { const form = new FormData(); Object.entries(taskForm.value).forEach(([key, value]) => form.append(key, value)); await request('/api/tasks', { method: 'POST', body: form }); taskForm.value = { name: '', script_id: '', schedule: '', timeout_seconds: 600 }; showNotice('任务创建成功'); await loadAll(); } catch (error) { showNotice(error.message, 'error'); } }
    async function runTask(id) { try { const result = await request(`/api/tasks/${id}/run`, { method: 'POST' }); showNotice(result.status === 'SUCCESS' ? '任务执行成功' : `任务失败：${result.error || '请查看执行记录'}`, result.status === 'SUCCESS' ? '' : 'error'); await loadAll(); } catch (error) { showNotice(error.message, 'error'); } }
    async function toggleTask(item) { const form = new FormData(); form.append('enabled', !item.enabled); try { await request(`/api/tasks/${item.id}/enabled`, { method: 'PUT', body: form }); await loadAll(); } catch (error) { showNotice(error.message, 'error'); } }
    async function viewLog(item) { logPanel.value = { open: true, loading: true, item, content: '' }; try { const result = await request(`/api/executions/${item.id}/log`); logPanel.value.content = result.content; } catch (error) { logPanel.value.content = `日志加载失败：${error.message}`; } finally { logPanel.value.loading = false; } }
    function closeLog() { logPanel.value.open = false; }
    function format(value) { return value ? new Date(value).toLocaleString('zh-CN') : '-'; }
    onMounted(loadAll);
    return { view, scripts, tasks, runs, notice, noticeType, loading, taskForm, titles, logPanel, loadAll, importScript, createTask, runTask, toggleTask, viewLog, closeLog, format };
  }
}).mount('#app');
