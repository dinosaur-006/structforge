import { Circle, Film, MoreVertical, Plus, Trash2, Video } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import { Modal } from '../components/ui/Modal';
import { SectionHeader } from '../components/ui/SectionHeader';
import { copy } from '../shared/copy';
import { formatRelativeTime } from '../shared/format';
import { projectStatusMeta } from '../shared/status';
import { useAppStore } from '../store';

const labels = {
  name: '\u9879\u76ee\u540d\u79f0',
  description: '\u63cf\u8ff0',
  create: '\u521b\u5efa',
  cancel: '\u53d6\u6d88',
  emptyTitle: '\u8fd8\u6ca1\u6709\u9879\u76ee',
  emptyDescription: '\u521b\u5efa\u7b2c\u4e00\u4e2a\u7ed3\u6784\u8fc1\u79fb\u9879\u76ee',
  delete: '\u5220\u9664\u9879\u76ee',
};

export default function ProjectListPage() {
  const navigate = useNavigate();
  const projects = useAppStore((state) => state.projects);
  const addProject = useAppStore((state) => state.addProject);
  const removeProject = useAppStore((state) => state.removeProject);
  const [modalOpen, setModalOpen] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const createProject = () => {
    if (!name.trim()) return;
    addProject(name.trim(), description.trim());
    setName('');
    setDescription('');
    setModalOpen(false);
  };

  return (
    <section className="mx-auto max-w-[1240px] space-y-6">
      <SectionHeader
        title={copy.projectsTitle}
        description={'\u7ba1\u7406\u4f60\u7684\u89c6\u9891\u7ed3\u6784\u8fc1\u79fb\u5de5\u4f5c\u6d41'}
        action={
          <Button variant="primary" onClick={() => setModalOpen(true)}>
            <Plus className="h-4 w-4" />
            {copy.newProject}
          </Button>
        }
      />

      {projects.length === 0 ? (
        <EmptyState
          icon={<Film className="h-8 w-8" />}
          title={labels.emptyTitle}
          description={labels.emptyDescription}
          action={
            <Button variant="primary" onClick={() => setModalOpen(true)}>
              <Plus className="h-4 w-4" />
              {copy.newProject}
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {projects.map((project) => {
            const meta = projectStatusMeta[project.status];
            return (
              <article
                key={project.id}
                className="group cursor-pointer rounded-lg border border-border bg-card p-4 shadow-sm transition-colors duration-200 hover:border-primary/40 hover:bg-sidebar/50 hover:shadow-md"
                onClick={() => navigate(`/migrate/${project.id}`)}
              >
                <div className="relative mb-4 grid aspect-video place-items-center overflow-hidden rounded-lg border border-border bg-sidebar">
                  <Video className="h-10 w-10 text-primary" />
                  <button
                    type="button"
                    aria-label={labels.delete}
                    className="absolute right-2 top-2 grid h-9 w-9 place-items-center rounded-lg border border-border bg-card text-text-secondary opacity-0 shadow-sm transition hover:text-error group-hover:opacity-100"
                    onClick={(event) => {
                      event.stopPropagation();
                      removeProject(project.id);
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h2 className="truncate text-lg font-semibold">{project.name}</h2>
                    <p className="mt-1 line-clamp-2 text-sm text-text-secondary">{project.description}</p>
                  </div>
                  <MoreVertical className="h-5 w-5 flex-none text-text-secondary" />
                </div>
                <div className="mt-4 flex items-center justify-between gap-3">
                  <Badge tone={meta.tone} icon={<Circle className="h-2 w-2 fill-current" />}>{meta.label}</Badge>
                  <span className="text-xs text-text-secondary">{formatRelativeTime(project.updatedAt)}</span>
                </div>
              </article>
            );
          })}
        </div>
      )}

      <Modal
        open={modalOpen}
        title={copy.newProject}
        onClose={() => setModalOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setModalOpen(false)}>
              {labels.cancel}
            </Button>
            <Button variant="primary" onClick={createProject} disabled={!name.trim()}>
              {labels.create}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <label className="block text-sm font-semibold text-text-primary">
            {labels.name}
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="mt-2 h-11 w-full rounded-lg border border-border bg-card px-3 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/30"
              autoFocus
            />
          </label>
          <label className="block text-sm font-semibold text-text-primary">
            {labels.description}
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              className="mt-2 min-h-24 w-full resize-none rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/30"
            />
          </label>
        </div>
      </Modal>
    </section>
  );
}
