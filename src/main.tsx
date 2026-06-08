import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

// ── 全局未捕获异常处理，防止异步错误导致白屏 ──
function _showErrorToast(message: string) {
  const existing = document.getElementById('__structforge_error_toast');
  if (existing) existing.remove();
  const toast = document.createElement('div');
  toast.id = '__structforge_error_toast';
  toast.style.cssText =
    'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);' +
    'background:#3D1414;color:#FCA5A5;padding:12px 24px;border-radius:10px;' +
    'z-index:99999;font-family:system-ui,sans-serif;font-size:14px;' +
    'border:1px solid rgba(220,38,38,0.3);box-shadow:0 4px 24px rgba(0,0,0,0.5);' +
    'backdrop-filter:blur(8px);max-width:90vw;text-align:center;';
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 6000);
}

window.addEventListener('unhandledrejection', (event) => {
  console.error('[StructForge] Unhandled Rejection:', event.reason);
  _showErrorToast('系统遇到意外错误，请刷新页面重试');
});

window.addEventListener('error', (event) => {
  // Only handle runtime errors, not resource load errors
  if (event.error) {
    console.error('[StructForge] Unhandled Error:', event.error);
    _showErrorToast('系统遇到意外错误，请刷新页面重试');
  }
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
