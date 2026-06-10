/** Lightweight i18n — Pixelle-Video inspired ZH/EN bilingual support. */

export type Lang = 'zh' | 'en';

const STORAGE_KEY = 'structforge_lang';

const zh: Record<string, string> = {
  'nav.analyze': '分析台',
  'nav.projects': '项目',
  'nav.history': '历史',
  'nav.settings': '设置',
  'btn.generate': '生成脚本',
  'btn.render': '渲染视频',
  'btn.export': '导出提示词',
  'btn.copy': '复制',
  'btn.save': '保存',
  'btn.cancel': '取消',
  'btn.retry': '重试',
  'btn.refresh': '刷新',
  'btn.test': '测试连接',
  'status.configured': '已配置',
  'status.fallback': '回退模式',
  'status.disabled': '未启用',
  'status.processing': '处理中',
  'status.completed': '已完成',
  'status.failed': '失败',
  'status.draft': '草稿',
  'filter.all': '全部',
  'filter.completed': '已完成',
  'filter.processing': '处理中',
  'filter.draft': '草稿',
  'sort.date': '按日期',
  'sort.name': '按名称',
  'search.placeholder': '搜索...',
  'empty.no_projects': '暂无项目',
  'empty.no_projects_hint': '创建一个项目开始使用',
  'settings.title': '设置',
  'settings.service_status': '服务状态',
  'settings.llm_test': 'LLM 连接测试',
  'settings.config_guide': '配置指引',
  'settings.env_hint': '在 ai-services/.env 中配置以下环境变量:',
  'faq.what': 'StructForge 是什么？',
  'faq.how': '如何使用？',
  'faq.apikey': '需要 API Key 吗？',
  'faq.models': '支持哪些 AI 模型？',
  'faq.quality': '视频质量如何提升？',
  'faq.fail': '生成失败怎么办？',
  'faq.comfyui': '如何配置 ComfyUI RunningHub？',
};

const en: Record<string, string> = {
  'nav.analyze': 'Analyze',
  'nav.projects': 'Projects',
  'nav.history': 'History',
  'nav.settings': 'Settings',
  'btn.generate': 'Generate',
  'btn.render': 'Render',
  'btn.export': 'Export',
  'btn.copy': 'Copy',
  'btn.save': 'Save',
  'btn.cancel': 'Cancel',
  'btn.retry': 'Retry',
  'btn.refresh': 'Refresh',
  'btn.test': 'Test Connection',
  'status.configured': 'Configured',
  'status.fallback': 'Fallback',
  'status.disabled': 'Disabled',
  'status.processing': 'Processing',
  'status.completed': 'Completed',
  'status.failed': 'Failed',
  'status.draft': 'Draft',
  'filter.all': 'All',
  'filter.completed': 'Completed',
  'filter.processing': 'Processing',
  'filter.draft': 'Draft',
  'sort.date': 'By Date',
  'sort.name': 'By Name',
  'search.placeholder': 'Search...',
  'empty.no_projects': 'No projects',
  'empty.no_projects_hint': 'Create a project to get started',
  'settings.title': 'Settings',
  'settings.service_status': 'Service Status',
  'settings.llm_test': 'LLM Connection Test',
  'settings.config_guide': 'Configuration',
  'settings.env_hint': 'Configure these in ai-services/.env:',
  'faq.what': 'What is StructForge?',
  'faq.how': 'How to use?',
  'faq.apikey': 'Do I need an API Key?',
  'faq.models': 'Which AI models are supported?',
  'faq.quality': 'How to improve video quality?',
  'faq.fail': 'What if generation fails?',
  'faq.comfyui': 'How to set up ComfyUI RunningHub?',
};

const locales: Record<Lang, Record<string, string>> = { zh, en };

export function getLang(): Lang {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'en' || stored === 'zh') return stored as Lang;
  } catch {}
  // Detect browser language
  if (typeof navigator !== 'undefined' && navigator.language?.startsWith('en')) {
    return 'en';
  }
  return 'zh';
}

export function setLang(lang: Lang): void {
  try {
    localStorage.setItem(STORAGE_KEY, lang);
  } catch {}
}

export function t(key: string, fallback?: string): string {
  const lang = getLang();
  return locales[lang]?.[key] || fallback || key;
}

export function tWith(lang: Lang, key: string, fallback?: string): string {
  return locales[lang]?.[key] || fallback || key;
}
