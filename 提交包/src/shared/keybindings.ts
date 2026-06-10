export const keybindingMap = {
  undo: { keys: ['Ctrl', 'Z'], label: 'Ctrl+Z', description: '撤销上一步操作' },
  redo: { keys: ['Ctrl', 'Shift', 'Z'], label: 'Ctrl+Shift+Z', description: '重做已撤销操作' },
  save: { keys: ['Ctrl', 'S'], label: 'Ctrl+S', description: '保存当前结构' },
  deleteSegment: { keys: ['Delete'], label: 'Delete', description: '删除选中的分镜' },
  toggleDrawer: { keys: ['Space'], label: 'Space', description: '打开/关闭分镜编辑' },
  closeDrawer: { keys: ['Escape'], label: 'Esc', description: '关闭抽屉或取消选择' },
  nextSegment: { keys: ['Tab'], label: 'Tab', description: '选择下一个分镜' },
  prevSegment: { keys: ['Shift', 'Tab'], label: 'Shift+Tab', description: '选择上一个分镜' },
  playPause: { keys: ['Space'], label: 'Space', description: '播放/暂停视频预览' },
  exportDialog: { keys: ['Ctrl', 'E'], label: 'Ctrl+E', description: '打开导出对话框' },
  seekBack: { keys: ['ArrowLeft'], label: '←', description: '后退5秒' },
  seekForward: { keys: ['ArrowRight'], label: '→', description: '前进5秒' },
  nlEdit: { keys: ['Ctrl', 'K'], label: 'Ctrl+K', description: '打开自然语言编辑面板' },
} as const;

export type KeybindingId = keyof typeof keybindingMap;

/** Returns true if the keyboard event matches all required keys for the given shortcut. */
export function matchKeybinding(event: KeyboardEvent, id: KeybindingId): boolean {
  const binding = keybindingMap[id];
  if (!binding) return false;
  const pressed = binding.keys;

  // Modifier requirements (case-insensitive comparison).
  const ctrlRequired = pressed.some((k) => k.toLowerCase() === 'ctrl');
  const shiftRequired = pressed.some((k) => k.toLowerCase() === 'shift');
  const altRequired = pressed.some((k) => k.toLowerCase() === 'alt');
  const metaRequired = pressed.some((k) => k.toLowerCase() === 'meta');

  if (event.ctrlKey !== ctrlRequired) return false;
  if (event.shiftKey !== shiftRequired) return false;
  if (event.altKey !== altRequired) return false;
  if (event.metaKey !== metaRequired) return false;

  // The actual key (non-modifier).
  const mainKey = pressed.find((k) => !['ctrl', 'shift', 'alt', 'meta'].includes(k.toLowerCase()));
  if (!mainKey) return false;

  // Normalize: "Space" matches event.key === " ", "ArrowLeft" etc.
  const normalized = mainKey === 'Space' ? ' ' : mainKey;
  return event.key === normalized || event.key.toLowerCase() === mainKey.toLowerCase();
}

/** Human-readable grouped list for the shortcut reference modal. */
export const keybindingGroups = [
  {
    title: '编辑操作',
    shortcuts: [
      keybindingMap.undo,
      keybindingMap.redo,
      keybindingMap.save,
      keybindingMap.deleteSegment,
    ],
  },
  {
    title: '分镜导航',
    shortcuts: [
      keybindingMap.toggleDrawer,
      keybindingMap.closeDrawer,
      keybindingMap.nextSegment,
      keybindingMap.prevSegment,
    ],
  },
  {
    title: '结果页操作',
    shortcuts: [
      keybindingMap.playPause,
      keybindingMap.seekBack,
      keybindingMap.seekForward,
      keybindingMap.exportDialog,
    ],
  },
  {
    title: 'AI 辅助',
    shortcuts: [
      keybindingMap.nlEdit,
    ],
  },
];
