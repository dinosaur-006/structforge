import { Circle, Film, MoreVertical, Plus, Trash2, Video } from 'lucide-react';
import { useEffect, useState } from 'react';
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
import type { Project, ProjectBrief } from '../shared/types';

const labels = {
  name: '\u9879\u76ee\u540d\u79f0',
  description: '\u63cf\u8ff0',
  productName: '\u5546\u54c1\u540d\u79f0',
  sellingPoints: '\u6838\u5fc3\u5356\u70b9',
  targetAudience: '\u76ee\u6807\u4eba\u7fa4',
  offer: '\u4f18\u60e0\u4fe1\u606f',
  tone: '\u8868\u8fbe\u8bed\u6c14',
  mandatoryClaims: '\u5fc5\u5907\u58f0\u660e',
  create: '\u521b\u5efa',
  cancel: '\u53d6\u6d88',
  emptyTitle: '\u8fd8\u6ca1\u6709\u9879\u76ee',
  emptyDescription: '\u521b\u5efa\u7b2c\u4e00\u4e2a\u7ed3\u6784\u8fc1\u79fb\u9879\u76ee',
  delete: '\u5220\u9664\u9879\u76ee',
};

export default function ProjectListPage() {
  const navigate = useNavigate();
  const projects = useAppStore((state) => state.projects);
  const fetchProjects = useAppStore((state) => state.fetchProjects);
  const addProject = useAppStore((state) => state.addProject);
  const removeProject = useAppStore((state) => state.removeProject);
  const [modalOpen, setModalOpen] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [productName, setProductName] = useState('');
  const [sellingPoints, setSellingPoints] = useState('');
  const [targetAudience, setTargetAudience] = useState('');
  const [offer, setOffer] = useState('');
  const [tone, setTone] = useState('');
  const [mandatoryClaims, setMandatoryClaims] = useState('');

  useEffect(() => {
    void fetchProjects();
  }, [fetchProjects]);

  const createProject = async () => {
    if (!name.trim()) return;
    const brief: ProjectBrief = {
      productName: productName.trim(),
      sellingPoints: listFromText(sellingPoints),
      targetAudience: targetAudience.trim(),
      offer: offer.trim(),
      tone: tone.trim(),
      mandatoryClaims: listFromText(mandatoryClaims),
    };
    const projectId = await addProject(name.trim(), description.trim(), brief);
    setName('');
    setDescription('');
    setProductName('');
    setSellingPoints('');
    setTargetAudience('');
    setOffer('');
    setTone('');
    setMandatoryClaims('');
    setModalOpen(false);
    if (projectId) navigate(`/analyze?projectId=${projectId}`);
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
                onClick={() => navigate(projectDestination(project))}
              >
                <div className="relative mb-4 grid aspect-video place-items-center overflow-hidden rounded-lg border border-border bg-sidebar">
                  <Video className="h-10 w-10 text-primary" />
                  <button
                    type="button"
                    aria-label={labels.delete}
                    className="absolute right-2 top-2 grid h-9 w-9 place-items-center rounded-lg border border-border bg-card text-text-secondary opacity-0 shadow-sm transition hover:text-error group-hover:opacity-100"
                    onClick={(event) => {
                      event.stopPropagation();
                      void removeProject(project.id);
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
            <Button variant="primary" onClick={() => void createProject()} disabled={!name.trim()}>
              {labels.create}
            </Button>
          </>
        }
      >
        <div className="max-h-[65vh] space-y-4 overflow-y-auto pr-1">
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
          <p className="border-t border-border pt-4 text-xs font-semibold uppercase text-text-secondary">{'\u521b\u4f5c\u7b80\u62a5'}</p>
          <div className="grid gap-4 sm:grid-cols-2">
            <BriefInput label={labels.productName} value={productName} onChange={setProductName} />
            <BriefInput label={labels.targetAudience} value={targetAudience} onChange={setTargetAudience} />
            <BriefInput label={labels.offer} value={offer} onChange={setOffer} />
            <BriefInput label={labels.tone} value={tone} onChange={setTone} />
          </div>
          <BriefTextArea label={labels.sellingPoints} value={sellingPoints} onChange={setSellingPoints} placeholder={'\u6bcf\u884c\u4e00\u4e2a\u5356\u70b9'} />
          <BriefTextArea label={labels.mandatoryClaims} value={mandatoryClaims} onChange={setMandatoryClaims} placeholder={'\u6bcf\u884c\u4e00\u6761\u5fc5\u987b\u4fdd\u7559\u7684\u8868\u8fbe'} />
        </div>
      </Modal>
    </section>
  );
}

function listFromText(value: string): string[] {
  return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
}

function projectDestination(project: Project): string {
  if (project.status === 'draft' || project.status === 'analyzing') {
    return `/analyze?projectId=${project.id}`;
  }
  return `/migrate/${project.id}`;
}

function BriefInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block text-sm font-semibold text-text-primary">
      {label}
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 h-11 w-full rounded-lg border border-border bg-card px-3 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/30"
      />
    </label>
  );
}

function BriefTextArea({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (value: string) => void; placeholder: string }) {
  return (
    <label className="block text-sm font-semibold text-text-primary">
      {label}
      <textarea
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 min-h-20 w-full resize-none rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/30"
      />
    </label>
  );
}
