# StructForge Frontend Mock MVP Design

Date: 2026-05-21
Status: Approved direction, awaiting written-spec review

## Goal

Build a complete, product-feeling frontend Mock MVP for StructForge: an AI-assisted short-video structure migration tool. The MVP must be usable without backend APIs and should demonstrate the full user loop:

1. Manage projects.
2. Upload and analyze a reference video.
3. Edit/migrate the extracted structure using assets and gap repair.
4. Preview generated result variants and export outputs.

The implementation should be ready for later API integration by centralizing mock state in Zustand actions rather than scattering per-page mock fetch logic.

## Product Scope

The MVP includes four routes:

- `/projects`: project list and project creation/deletion.
- `/analyze`: sample analysis studio with upload, simulated progress, and structure visualization.
- `/migrate/:projectId`: migration studio with assets, editable structure timeline, segment drawer, and material-gap repair.
- `/result/:projectId`: result studio with version switching, preview, result timeline, radar comparison, and export dialog.

The root route redirects to `/projects`. Unknown routes show a friendly not-found state with a route back to the product.

## Technical Stack

- React 19 + TypeScript + Vite.
- Tailwind CSS 3.4.
- react-router-dom v6.
- Zustand with persistence for durable UI state and mock product state.
- lucide-react for all structural icons.
- Recharts for rhythm and radar visualizations.
- dnd-kit for sortable timeline and draggable assets.

If shadcn/ui is not already installed, local Tailwind components should mimic the shadcn/Radix interaction model for Modal, Drawer, Tabs, Badge, Toast, and basic controls. The MVP should not block on shadcn installation.

## Visual System

The UI uses a dark, high-density AI creation-workbench aesthetic. It should feel like a serious operational tool for marketers and creators rather than a marketing landing page.

Design tokens:

- Primary: `#7C3AED`.
- Accent: `#06B6D4`.
- Surface: `#0F0F23`.
- Card: `#1A1A2E`.
- Sidebar: `#13132A`.
- Border: `#2D2D44`.
- Text primary: `#F1F5F9`.
- Text secondary: `#94A3B8`.
- Success: `#10B981`.
- Warning: `#F59E0B`.
- Error: `#EF4444`.

Rules:

- Use Lucide icons, not emoji, for navigation, tools, status icons, and structural controls.
- Preserve color meaning with labels or icons so color is not the only signal.
- Cards use consistent dark surfaces and visible borders.
- Motion is restrained: 150-300ms for state transitions, opacity/transform only.
- Touch targets and icon buttons should be at least 44px high/wide where practical.
- Avoid a one-note purple UI: purple is primary action and selection; cyan is data/interactive accent; green/yellow/red are health and risk states.

## Global Architecture

Use a shared store layout with clear slices:

- App: sidebar collapsed/open state, mobile sidebar state, global route loading.
- Projects: project list, add project, update project, remove project, validate project ID.
- Analysis: selected video, analysis progress, stage, completed `VideoStructure`.
- Migration: current structure, assets, selected segment, drawer state, gaps, repair status, undo/redo history.
- Result: selected version, export options, export progress.
- Toasts: transient success/error messages.

Mock data should live under `src/mocks/`. Shared domain types should live under `src/shared/types.ts`.

The future API boundary should be action-based: pages call store actions such as `startAnalysis`, `setStructure`, `fixGaps`, `setVersion`, and `exportResult`. Later these actions can call real APIs without rewriting UI components.

## Layout

`AppLayout` owns the shell:

- Fixed left sidebar on desktop, `w-60` expanded and `w-16` collapsed.
- Mobile sidebar is hidden by default and opens as an overlay drawer.
- Top of sidebar shows Wand2 icon and StructForge text; collapsed mode shows icon only.
- Navigation includes `/projects` and `/analyze`.
- Bottom includes user placeholder, settings affordance, and collapse button.
- Main content uses a scrollable workspace with responsive padding and a max comfortable content width only where it helps scanning.

Use lazy-loaded route pages and a lightweight top progress bar for route transitions or long mock operations.

## Projects Page

Purpose: make the product feel complete and give users a starting point.

Features:

- Header with the Chinese project-list title and a primary create-project button matching the user-provided copy.
- Mock project grid with 3-5 projects.
- Project cards show thumbnail placeholder, name, status badge, updated time, and actions menu.
- Card click navigates to `/migrate/:projectId`.
- Create dialog accepts project name and optional description.
- Delete requires a confirmation-style interaction or clear destructive affordance.
- Empty state guides users to create the first project.

Status badges should cover `draft`, `analyzing`, `editing`, `rendering`, and `completed`.

## Analyze Page

Purpose: answer "I uploaded a reference video; what did the AI extract?"

Sections:

- Page header with Chinese title/subtitle copy, an export-JSON action, and a next-step action.
- Video uploader with drag/drop and click upload.
- File validation for video-like inputs; invalid files show an error alert and recovery path.
- Uploaded state with filename, mocked metadata, preview placeholder, reupload, and start-analysis action.
- Analysis progress with stages: extracting frames, identifying key frames, analyzing script structure, scoring health.
- Completion reveals analysis results and enables next navigation.

Result components:

- Video info cards: duration, resolution, shot count, cover.
- Structure tabs: script, rhythm, packaging, health.
- Script timeline with proportional segment widths and selectable details.
- Rhythm AreaChart with highlight markers and stat cards.
- Packaging grid for subtitle style, transitions, and overlays.
- Health RadarChart plus dimension score cards.

The next-step action writes the completed analysis into project/migration state and routes to `/migrate/:projectId`.

## Migrate Page

Purpose: answer "How can I adapt this structure to my own assets and fix gaps?"

Route guard:

- If `projectId` is missing or unknown, show a project-not-found error state with a return button.

Layout:

- Header with project name, preview-result action, and generate-video action.
- Toolbar with save, undo, redo, reset, and style selector.
- Desktop body uses left asset panel, central timeline editor, and right drawer overlay.
- Mobile uses stacked content, horizontally scrollable or vertical timeline, and full-screen drawer/modal.

Asset panel:

- Upload affordance.
- Mock asset cards with type, tag, thumbnail/icon, and match badge.
- Draggable asset list using dnd-kit.
- Empty state if no assets.

Timeline editor:

- Sortable segment blocks using dnd-kit.
- Each segment shows type, duration, score, lock state, and gap marker if applicable.
- Health color: green >= 80, yellow 60-79, red < 60.
- Segment click opens drawer.
- Time ruler shows seconds and total duration.
- Duration resizing can be deferred to drawer numeric input for MVP.

Segment drawer:

- Segment type select.
- Duration input.
- Script textarea.
- Visual description textarea.
- Matched asset select.
- Subtitle preset select.
- Transition select.
- BGM beat-align switch.
- Lock switch.
- Apply and cancel buttons.

State changes push undo history, capped at 20 snapshots. Undo/redo are available from toolbar and keyboard shortcuts where practical.

Gap panel:

- Accordion-like bottom panel, default open.
- Shows gap count and each gap severity.
- Expanded gap reveals strategy radio choices: structure reorder, packaging completion, AIGC generation mock, asset recomposition.
- One-click repair simulates progress, marks gaps repaired, updates affected segment health, and removes timeline gap markers.
- Toast feedback confirms save and repair actions.

## Result Page

Purpose: answer "What did I get, how did it improve, and how do I export it?"

Route guard:

- Unknown project IDs show the same project-not-found error state.

Sections:

- Header with title, project/version context, export-video action, and export-report action.
- Version tabs: original, conservative repair, strong hook, strong conversion.
- Video preview area with custom controls and chapter markers.
- Version metric panel: total score delta, hook timing, product exposure timing, invalid fragment reduction, CTA duration.
- Result timeline with source legend: original asset, structure reorder, AIGC generated, packaging completion.
- Clickable segments seek the mock video time.
- Compare radar overlays original and current version.
- Export dialog with MP4 resolution, SRT, PDF report, and JSON template options.
- Export action simulates generation and provides success feedback.

## Shared Components

Required shared components:

- `ErrorBoundary`.
- `ErrorAlert`.
- `EmptyState`.
- `Modal`.
- `Drawer`.
- `Tabs`.
- `Badge`.
- `Button` or button utility styles.
- `Toast`.
- `Skeleton`.
- `TopProgress`.
- `Version`.

These should be small, typed, and style-consistent. Components should not depend on page-specific mock data.

## Data Model

Core types:

- `Project`: id, name, description, status, updatedAt, thumbnail optional.
- `VideoStructure`: metadata, script segments, rhythm data, packaging data, health scores.
- `ScriptSegment`: id, type, start, end, duration, goal, copy, visual, healthScore, locked, assetId optional.
- `Asset`: id, name, type, tag, matchStatus, matchScore, thumbnail optional.
- `MaterialGap`: id, segmentId, severity, description, requiredSlot, strategies, status.
- `ResultVersion`: id, name, score, videoUrl optional, metrics, timeline segments, health scores.

Use stable IDs in mock data so routing, selection, and state updates are predictable.

## Responsiveness

Minimum breakpoints to verify:

- 375px mobile.
- 768px tablet.
- 1280px desktop.

Rules:

- Mobile sidebar becomes an overlay menu.
- Project grid becomes one column on small screens.
- Analysis info cards become one column or two compact columns.
- Migration layout stacks vertically on mobile.
- Timeline remains usable through horizontal scrolling or vertical segment cards.
- Segment drawer becomes full-screen on mobile.
- Charts keep fixed minimum heights and do not overflow parent containers.

## Error, Loading, and Empty States

The app must avoid white screens and dead ends:

- Invalid file upload shows a clear error and retry path.
- Missing project route shows project-not-found state.
- Chart/data failures use `ErrorAlert` rather than empty panels.
- All async mock operations disable active buttons and show progress.
- Empty project list and empty asset list use `EmptyState`.
- `ErrorBoundary` wraps the app root.

## Accessibility

Requirements:

- Interactive icon buttons have `aria-label`.
- Modal and drawer close buttons are keyboard reachable.
- Inputs have visible labels.
- Focus rings are visible.
- Status changes such as repair completion and export completion use toast with polite live-region behavior.
- Health and source indicators include text labels, not only color.
- Motion should respect `prefers-reduced-motion` in CSS where feasible.

## Implementation Order

1. Initialize Vite React TypeScript app, Tailwind, dependencies, routes, layout, and app store.
2. Build shared UI components and mock data scaffolding.
3. Build projects page.
4. Build analyze upload/progress flow.
5. Build analyze result visualizations.
6. Build migrate timeline, asset panel, drawer, and history.
7. Build migrate gap panel and repair simulation.
8. Build result page, version switcher, video mock, timeline, radar, and export dialog.
9. Add global error/loading states, responsive passes, and polish.
10. Run build/lint where available and manually inspect desktop/tablet/mobile.

## Verification Plan

Functional checks:

- App launches and redirects `/` to `/projects`.
- Sidebar collapses, persists, and routes highlight correctly.
- Projects can be created and deleted.
- Unknown project route shows friendly error state.
- Analyze upload accepts video files and rejects unsupported files.
- Analysis progresses through stages and reveals all tabs.
- Migrate timeline can reorder segments, edit a segment, and undo/redo.
- Gap repair removes gap markers and updates UI feedback.
- Result versions switch all dependent panels.
- Export dialog simulates progress and completes.

Visual checks:

- 375px, 768px, and 1280px layouts do not overlap or horizontally overflow unexpectedly.
- Chart panels have stable dimensions.
- Text fits inside buttons/cards.
- Dark contrast remains readable.
- Structural icons are Lucide icons.

Build checks:

- TypeScript build passes.
- Production build completes.
- Any available lint command passes or known warnings are documented.

## Out of Scope

- Real backend/API integration.
- Real video analysis, rendering, or file upload persistence.
- Authentication and multi-user permissions.
- Real AIGC generation.
- Full shadcn/ui installation if it would slow down the Mock MVP.
- Pixel-perfect video frame extraction.

## Notes

The current workspace was empty and not a git repository when this spec was written. The design document can be committed after a repository is initialized or after the app scaffold creates the project structure.
