import { Keyboard } from 'lucide-react';
import { useState } from 'react';
import { Button } from './Button';
import { Modal } from './Modal';
import { keybindingGroups } from '../../shared/keybindings';

export function KeyboardShortcutHint() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button variant="ghost" size="icon" aria-label="键盘快捷键参考" onClick={() => setOpen(true)}>
        <Keyboard className="h-4 w-4" />
      </Button>
      <Modal open={open} title="键盘快捷键参考" onClose={() => setOpen(false)}>
        <div className="space-y-4">
          {keybindingGroups.map((group) => (
            <div key={group.title}>
              <h3 className="mb-2 text-sm font-semibold text-text-primary">{group.title}</h3>
              <div className="space-y-1.5">
                {group.shortcuts.map((shortcut) => (
                  <div key={shortcut.label} className="flex items-center justify-between rounded-md px-2 py-1.5 text-sm">
                    <span className="text-text-secondary">{shortcut.description}</span>
                    <kbd className="ml-4 inline-flex items-center gap-0.5 rounded border border-border bg-sidebar px-2 py-0.5 font-mono text-xs text-text-primary">
                      {shortcut.label}
                    </kbd>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Modal>
    </>
  );
}
