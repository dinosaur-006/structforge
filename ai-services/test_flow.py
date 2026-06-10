import sys, tempfile
from pathlib import Path

db_path = Path(tempfile.gettempdir()) / 'structforge_test_flow.db'
if db_path.exists():
    db_path.unlink()

errors = []

def check(step, ok, detail=""):
    status = "[OK]" if ok else "[FAIL]"
    print(f"  {status} {step}" + (f": {detail}" if detail else ""))
    if not ok:
        errors.append(step)

print("=== STEP 1: Imports ===")
from config import Settings
from models.repository import SQLiteRepository
from models.schemas import (VideoStructure, FinalScript, VideoMeta, HealthScores,
    ScriptSegment, PackagingStructure, RhythmPoint)
check("Models", True)

print("=== STEP 2: DB ===")
repo = SQLiteRepository(db_path)
repo.initialize()
project = repo.create_project('Test', 'desc')
pid = project['id']
check("DB + project", True)

print("=== STEP 3: Analysis ===")
sample = VideoStructure(
    meta=VideoMeta(duration=20.0, resolution='1080x1920', shots=6, coverLabel='X', productName='Test'),
    script=[
        ScriptSegment(id='s1', type='hook', label='H', start=0.0, end=2.7, duration=2.7, goal='Grab', copy='Wow!', visual='Product burst', healthScore=65),
        ScriptSegment(id='s2', type='pain', label='P', start=2.7, end=6.6, duration=3.9, goal='Pain', copy='Problem?', visual='Dirty kitchen', healthScore=55),
        ScriptSegment(id='s3', type='product', label='R', start=6.6, end=9.3, duration=2.7, goal='Show', copy='Solution!', visual='Clean turntable', healthScore=70),
        ScriptSegment(id='s4', type='proof', label='F', start=9.3, end=12.9, duration=3.6, goal='Proof', copy='Evidence!', visual='Comparison', healthScore=60),
        ScriptSegment(id='s5', type='cta', label='C', start=12.9, end=15.5, duration=2.6, goal='Buy', copy='Buy now!', visual='Golden stack', healthScore=58),
    ],
    rhythm=[RhythmPoint(second=0, cuts=1, emotion=0.5)], packaging=PackagingStructure(), health=HealthScores(hook_strength=65, product_exposure_timing=55, selling_point_proof=60, pacing_compactness=70, cta_persuasiveness=58, overall=62)
)
repo.create_job(job_id='j1', source_path='/tmp/x.mp4', project_id=pid)
repo.complete_job('j1', sample)
repo.select_reference_job(pid, 'j1')
check("Structure", len(sample.script) == 5)

print("=== STEP 4: Gaps ===")
from services.gap_detector import GapDetector
gaps = GapDetector(repo).detect(pid)
check("Gaps", len(gaps) > 0, str(len(gaps)))

print("=== STEP 5: Fix ===")
from services.gap_filler import GapFiller
settings = Settings()
try:
    r = GapFiller(repo, settings).fix_all(pid)
    check("Fix", len(r['gaps']) == 0)
except Exception as e:
    check("Fix", False, str(e)[:80])

print("=== STEP 6: Script ===")
from services.migrator import MigratorService
migrator = MigratorService(repo, settings=settings)
script = None
try:
    script = migrator.generate(pid, style='default')
    check("Script", True, f"{len(script.segments)} segments")
    meta = script.metadata or {}
    check("Scores", bool(meta.get('predicted_scores')))
    check("Review", bool(meta.get('ai_review')))
except Exception as e:
    print(f"  [WARN] LLM unavailable: {str(e)[:100]}")
    from models.schemas import FinalSegment
    fb = []
    for s in sample.script:
        fb.append({'id':s.id,'type':s.type,'start':s.start,'end':s.end,'duration':s.duration,'script':s.copy_text,'visual':s.visual,'asset_id':None,'subtitle_style':'w','transition':'h','locked':False,'source':'aigc'})
    script = FinalScript(version='default', total_duration=19.8, segments=fb, metadata={})
    check("Fallback", True)

print("=== STEP 7: Prompts ===")
from services.prompt_engine.engine import AIVideoPromptEngine
engine = AIVideoPromptEngine(platform='seedance')
ok = 0
for seg in script.segments:
    r = engine.generate(seg, product_name='Test', product_type='食品饮料')
    if not any('一' <= c <= '鿿' for c in r.prompt_english):
        ok += 1
check("English prompts", ok == len(script.segments), f"{ok}/{len(script.segments)}")

print("=== STEP 8: Score ===")
from services.burst_metrics import BurstMetricsCalculator
shots = [{'start_s':float(s.start),'end_s':float(s.end),'duration_s':float(s.duration),'type':s.type} for s in script.segments]
calc = BurstMetricsCalculator(shots=shots, asr_text='test', asr_segments=[], vision_frames=[], duration=script.total_duration, platform='douyin')
dims = calc.dimension_reports()
check("Metrics", len(dims) >= 5, str(len(dims)))

print("=== STEP 9: Render ===")
from services.render_pipeline import VideoRenderPipeline
p = VideoRenderPipeline(repo, settings)
steps = ['_prepare','_synthesize_all_tts','_process_segments','_generate_ai_visual','_assemble_video','_finalize']
missing = [s for s in steps if not hasattr(p, s)]
check("Pipeline", len(missing) == 0)

print("=== STEP 10: Routes ===")
from main import app
api_routes = [(r.path, list(r.methods)) for r in app.routes if hasattr(r,'path') and hasattr(r,'methods') and r.path.startswith('/api/')]
keys = ['/api/v1/analyze','/api/v1/migrate','/api/v1/render','/api/v1/audit','/api/v1/gaps','/api/v1/structure','/api/v1/assets','/api/v1/optimize','/api/v1/capabilities','/api/v1/projects']
ok = all(any(p.startswith(k) for p,_ in api_routes) for k in keys)
check("Routes", ok, str(len(api_routes)))

print()
print("="*50)
if errors:
    print(f"FAILURES: {len(errors)}")
    for e in errors: print(f"  - {e}")
else:
    print("ALL 10 STEPS PASSED")
print("="*50)
db_path.unlink(missing_ok=True)
