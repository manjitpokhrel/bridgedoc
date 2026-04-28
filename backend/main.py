import uuid
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv


from core.tmt_client import TMTClient

from core.segmenter import TrilingualSentenceSegmenter
from core.quality import TranslationQualityChecker
from processors.pdf_processor import PDFProcessor
from processors.docx_processor import DOCXProcessor
from processors.csv_processor import CSVProcessor
from utils.validators import validate_file

load_dotenv()

app = FastAPI(title="BridgeDoc API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory task store
tasks: dict = {}

TEMP_DIR = Path(tempfile.gettempdir()) / "bridgedoc"
TEMP_DIR.mkdir(exist_ok=True)


@app.get("/")
async def root():
    return {"message": "BridgeDoc API running", "version": "1.0.0"}


@app.post("/translate")
async def translate_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    direction: str = Form(...),
    api_key: str = Form(...),
    quality_check: bool = Form(False),
):
    content = await file.read()
    error = validate_file(content, file.filename)
    if error:
        raise HTTPException(status_code=400, detail=error)

    task_id = str(uuid.uuid4())
    task_dir = TEMP_DIR / task_id
    task_dir.mkdir(exist_ok=True)

    input_path = task_dir / file.filename
    with open(input_path, "wb") as f:
        f.write(content)

    tasks[task_id] = {
        "status": "running",
        "step": "parsing",
        "progress": 0,
        "message": "Initializing...",
        "count": "",
        "stats": {},
        "quality": None,
        "output_path": None,
        "output_filename": None,
    }

    background_tasks.add_task(
        run_translation_pipeline,
        task_id,
        input_path,
        direction,
        api_key,
        quality_check,
        task_dir,
    )

    return {"task_id": task_id}


@app.get("/status/{task_id}")
async def get_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks[task_id]


@app.get("/download/{task_id}")
async def download_result(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id]

    if task["status"] == "error":
        raise HTTPException(status_code=400, detail=task.get("message", "Translation failed"))

    if task["status"] != "complete":
        raise HTTPException(status_code=400, detail="Translation not complete yet")

    output_path = task.get("output_path")

    if not output_path:
        raise HTTPException(status_code=404, detail="Output path not set")

    output_file = Path(output_path)

    if not output_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Output file not found at {output_path}"
        )

    if output_file.stat().st_size == 0:
        raise HTTPException(status_code=500, detail="Output file is empty")

    return FileResponse(
        path=str(output_file),
        filename=task["output_filename"],
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename={task['output_filename']}"
        }
    )


async def run_translation_pipeline(
    task_id: str,
    input_path: Path,
    direction: str,
    api_key: str,
    quality_check: bool,
    task_dir: Path,
):
    task = tasks[task_id]

    def update(step=None, progress=None, message=None, count=None):
        if step is not None:
            task["step"] = step
        if progress is not None:
            task["progress"] = progress
        if message is not None:
            task["message"] = message
        if count is not None:
            task["count"] = count

    try:
        ext = input_path.suffix.lower()
        output_filename = f"translated_{input_path.name}"
        output_path = task_dir / output_filename

        client = TMTClient(api_key)
        segmenter = TrilingualSentenceSegmenter()

        update(step="parsing", progress=5, message="Parsing document structure...")

        # ── FORMAT PROCESSOR SELECTION ───────────────────────────────────────
        if ext == ".pdf":
            processor = PDFProcessor()
            doc_data = processor.extract(str(input_path))

        elif ext == ".docx":
            processor = DOCXProcessor()
            doc_data = processor.extract(str(input_path))

        elif ext in [".csv", ".tsv"]:
            processor = CSVProcessor()
            doc_data = processor.extract(str(input_path))

        else:
            raise ValueError(f"Unsupported file format: {ext}")

        # ── HANDLE PROCESSOR-LEVEL FAILURES FOR ALL FORMATS ──────────────────
        if not doc_data.get("can_translate", True):
            raise ValueError(
                doc_data.get("message", "This document cannot be translated.")
            )

        all_units = doc_data.get("translation_units", [])
        if not all_units:
            raise ValueError("No extractable text found in this document.")

        update(step="segmenting", progress=20, message="Segmenting text...")

        # ── SEGMENT ───────────────────────────────────────────────────────────
        all_sentences = []
        for unit in all_units:
            segs = segmenter.segment(unit["text"])
            unit["sentences"] = segs
            all_sentences.extend(segs)

        unique_sentences = list(dict.fromkeys(s for s in all_sentences if s.strip()))

        if not unique_sentences:
            raise ValueError("No translatable text found after segmentation.")

        update(
            step="translating",
            progress=30,
            message=f"Translating {len(unique_sentences)} sentences...",
            count=f"0 / {len(unique_sentences)}",
        )

        # ── TRANSLATE ────────────────────────────────────────────────────────
        async def progress_cb(current, total_count):
            pct = 30 + int((current / max(total_count, 1)) * 50)
            update(
                progress=pct,
                message="Translating sentences via TMT API...",
                count=f"{current} / {total_count}",
            )

        results = await client.translate_batch(
            unique_sentences,
            direction,
            progress_cb,
        )

        translated_map = {}
        failed = 0

        for r in results:
            if r.success:
                translated_map[r.original] = r.translated
            else:
                translated_map[r.original] = r.original
                failed += 1

        # ── OPTIONAL QUALITY CHECK ───────────────────────────────────────────
        quality_result = None
        if quality_check:
            update(progress=82, message="Running quality verification...")
            checker = TranslationQualityChecker(client)

            sample_originals = unique_sentences[: min(10, len(unique_sentences))]
            sample_translations = [translated_map.get(s, s) for s in sample_originals]

            quality_result = await checker.check_batch(
                sample_originals,
                sample_translations,
                direction,
            )

        # ── APPLY TRANSLATIONS TO UNITS ──────────────────────────────────────
        update(step="rebuilding", progress=85, message="Reconstructing document...")

        for unit in all_units:
            translated_sentences = [translated_map.get(s, s) for s in unit["sentences"]]
            unit["translated"] = " ".join(translated_sentences).strip()

        # ── REBUILD OUTPUT ────────────────────────────────────────────────────
        if ext == ".pdf":
            stats = processor.rebuild(doc_data, str(output_path))

        elif ext == ".docx":
            stats = processor.rebuild(doc_data, str(output_path))

        elif ext in [".csv", ".tsv"]:
            stats = processor.rebuild(doc_data, translated_map, str(output_path))

        else:
            raise ValueError(f"Unsupported file format during rebuild: {ext}")

        update(progress=100, message="Complete!", count="")

        task["status"] = "complete"
        task["output_path"] = str(output_path)
        task["output_filename"] = output_filename
        task["stats"] = {
            "total_sentences": len(unique_sentences),
            "translated": len(unique_sentences) - failed,
            "failed": failed,
            **stats,
        }

        warning = doc_data.get("warning")
        if warning:
            task["stats"]["warning"] = warning

        task["quality"] = quality_result

    except Exception as e:
        task["status"] = "error"
        task["message"] = str(e)
        task["progress"] = 100