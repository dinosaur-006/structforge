"""Test LLM-generated Flux prompts vs RunningHub ComfyUI."""
import asyncio, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from config import Settings
from services.llm_client import RobustLLMClient
from services.comfyui_service import create_comfyui_service

settings = Settings()

# ── Check config ──
if not settings.doubao_llm_api_key:
    print("ERROR: STRUCTFORGE_DOUBAO_LLM_API_KEY not set")
    sys.exit(1)
if not settings.runninghub_api_key:
    print("ERROR: STRUCTFORGE_RUNNINGHUB_API_KEY not set")
    sys.exit(1)

# ── Test product data ──
product = {
    "name": "趣多多巧克力曲奇",
    "type": "食品饮料",
    "points": ["真实巧克力豆", "香浓酥脆", "趣味包装"],
    "vision_tags": ["食物特写", "饼干", "巧克力块", "金黄色", "酥脆质感"],
    "vision_colors": ["#D2691E", "#8B4513", "#FFD700"],
}

segments = [
    {
        "type": "hook", "camera": "快推", "emotion": "惊讶", "duration": 2.8,
        "script": "你绝对没吃过的趣多多新口味！",
        "visual": "产品从黑暗中爆出，金色饼干碎屑飞溅，强烈光影对比",
    },
    {
        "type": "product", "camera": "缓推", "emotion": "兴奋", "duration": 3.5,
        "script": "真实巧克力豆超多，一口咬下去酥脆香浓",
        "visual": "白色背景下饼干缓慢旋转，巧克力豆在光线下闪烁，微观特写",
    },
]

# ── LLM prompt for generating Flux prompts ──
FLUX_SYSTEM = """You are an expert AI image prompt engineer specializing in Flux/Stable Diffusion prompts.
Generate a single, dense, comma-separated English prompt under 200 words.
Include: subject description, lighting setup, camera angle, texture details, quality keywords.
Output ONLY the prompt text, no explanations or markdown."""

def build_llm_request(seg, prod):
    """Build a request for the LLM to generate a Flux prompt."""
    vision_hint = ""
    if prod.get("vision_tags"):
        vision_hint = f"Product image analysis: {', '.join(prod['vision_tags'])}, colors: {', '.join(prod['vision_colors'][:3])}"

    return f"""{FLUX_SYSTEM}

Product: {prod['name']} ({prod['type']})
Key features: {', '.join(prod['points'])}
{vision_hint}

Segment type: {seg['type']}
Camera: {seg['camera']}
Mood: {seg['emotion']}
Duration: {seg['duration']}s
Voiceover: "{seg['script']}"
Visual description: {seg['visual']}

Generate the Flux prompt for this segment (English only, comma-separated):"""


async def test_prompt(seg, prod, label):
    """Generate prompt via LLM, then generate image via ComfyUI."""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")

    # Step 1: LLM generates prompt
    print(f"  [1/3] Calling LLM for prompt generation...")
    t0 = time.monotonic()
    client = RobustLLMClient(
        str(settings.doubao_llm_endpoint),
        str(settings.doubao_llm_api_key),
        str(settings.doubao_llm_model),
    )
    llm_prompt = client.complete_text(build_llm_request(seg, prod), max_tokens=512)
    llm_prompt = llm_prompt.strip().strip('"').strip("'")
    t1 = time.monotonic()
    print(f"  [OK] LLM response in {t1-t0:.1f}s")
    print(f"  Prompt: {llm_prompt[:200]}...")

    # Step 2: ComfyUI generates image
    print(f"  [2/3] Sending to RunningHub Flux...")
    comfyui = create_comfyui_service(settings)
    if not comfyui.available:
        print("  [FAIL] ComfyUI not configured")
        return None, llm_prompt

    try:
        result = await asyncio.wait_for(
            comfyui.generate_image(prompt=llm_prompt, width=1080, height=1920),
            timeout=120,
        )
        t2 = time.monotonic()
        url = result.get("url", "")
        if url:
            print(f"  [OK] Image generated in {t2-t1:.1f}s")
            print(f"  URL: {url}")
            return url, llm_prompt
        else:
            print(f"  [FAIL] No URL returned")
            return None, llm_prompt
    except asyncio.TimeoutError:
        print(f"  [FAIL] Timed out after 120s")
        return None, llm_prompt
    except Exception as e:
        print(f"  [FAIL] {e}")
        return None, llm_prompt


async def test_video(image_url, prompt, label):
    """Generate video from image via WAN 2.2."""
    print(f"\n  [3/3] Sending to RunningHub WAN 2.2 (video)...")
    comfyui = create_comfyui_service(settings)
    try:
        # Download image first
        import httpx, tempfile
        tmp = Path(tempfile.gettempdir()) / f"test_flux_{label}.png"
        resp = httpx.get(image_url, headers={"Authorization": f"Bearer {settings.runninghub_api_key}"}, follow_redirects=True, timeout=30)
        tmp.write_bytes(resp.content)
        print(f"  Downloaded image: {tmp.stat().st_size} bytes")

        result = await asyncio.wait_for(
            comfyui.generate_video(
                prompt=prompt,
                image_path=str(tmp),
                width=1080, height=1920, duration=3.0,
            ),
            timeout=300,
        )
        url = result.get("url", "")
        dur = result.get("duration", 0)
        if url:
            print(f"  [OK] Video generated ({dur}s)")
            print(f"  URL: {url}")
        else:
            print(f"  [FAIL] No video URL")
        tmp.unlink(missing_ok=True)
    except asyncio.TimeoutError:
        print(f"  [FAIL] Video timed out after 300s")
    except Exception as e:
        print(f"  [FAIL] {e}")


async def main():
    print("=" * 60)
    print("  LLM → Flux Prompt → RunningHub Image Test")
    print("=" * 60)
    print(f"  Product: {product['name']}")
    print(f"  LLM: {settings.doubao_llm_model}")

    # Test image generation for both segments
    image_urls = []
    for i, seg in enumerate(segments):
        url, prompt = await test_prompt(seg, product, f"Segment {i+1}: {seg['type'].upper()}")
        if url:
            image_urls.append((url, prompt, seg['type']))

    # Test video generation for the first successful image
    if image_urls:
        print(f"\n{'='*60}")
        print(f"  Testing WAN 2.2 Video Generation")
        print(f"{'='*60}")
        url, prompt, seg_type = image_urls[0]
        await test_video(url, prompt, seg_type)

    print(f"\n{'='*60}")
    print(f"  TEST COMPLETE")
    print(f"  Images: {len(image_urls)}/{len(segments)}")
    print(f"{'='*60}")

asyncio.run(main())
