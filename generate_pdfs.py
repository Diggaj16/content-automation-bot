"""
Generate 12 learning PDFs covering every backend & system design concept
used in the content-automation-bot project.

Run from any directory with Python:
    python generate_pdfs.py

Output: learning_pdfs/ folder next to this file.
"""
import os
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, HRFlowable, Preformatted,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

OUT_DIR = Path(__file__).parent / "learning_pdfs"
OUT_DIR.mkdir(exist_ok=True)

W, H = A4
MARGIN = 2 * cm

# ── Colour palette ──────────────────────────────────────────────────────────
C_DARK   = colors.HexColor("#1a1a2e")
C_BLUE   = colors.HexColor("#1565C0")
C_LBLUE  = colors.HexColor("#E3F2FD")
C_GREEN  = colors.HexColor("#2E7D32")
C_LGREEN = colors.HexColor("#E8F5E9")
C_ORANGE = colors.HexColor("#E65100")
C_LGRAY  = colors.HexColor("#F5F5F5")
C_GRAY   = colors.HexColor("#9E9E9E")
C_WHITE  = colors.white

# ── Style helpers ────────────────────────────────────────────────────────────
def make_styles():
    base = getSampleStyleSheet()
    s = {}
    s["h1"] = ParagraphStyle("H1", parent=base["Heading1"],
        fontSize=26, textColor=C_DARK, spaceAfter=6, spaceBefore=0,
        fontName="Helvetica-Bold")
    s["h2"] = ParagraphStyle("H2", parent=base["Heading2"],
        fontSize=16, textColor=C_BLUE, spaceAfter=4, spaceBefore=14,
        fontName="Helvetica-Bold")
    s["h3"] = ParagraphStyle("H3", parent=base["Heading3"],
        fontSize=13, textColor=C_GREEN, spaceAfter=3, spaceBefore=10,
        fontName="Helvetica-Bold")
    s["body"] = ParagraphStyle("Body", parent=base["Normal"],
        fontSize=11, leading=16, spaceAfter=6, alignment=TA_JUSTIFY,
        fontName="Helvetica")
    s["bullet"] = ParagraphStyle("Bullet", parent=base["Normal"],
        fontSize=11, leading=15, leftIndent=16, spaceAfter=3,
        bulletIndent=4, fontName="Helvetica")
    s["code"] = ParagraphStyle("Code", parent=base["Code"],
        fontSize=9, leading=13, leftIndent=8, fontName="Courier",
        backColor=C_LGRAY, borderPadding=(4, 6, 4, 6))
    s["note"] = ParagraphStyle("Note", parent=base["Normal"],
        fontSize=10, leading=14, leftIndent=12, rightIndent=12,
        backColor=C_LBLUE, borderPadding=6, spaceAfter=8,
        fontName="Helvetica-Oblique")
    s["warn"] = ParagraphStyle("Warn", parent=base["Normal"],
        fontSize=10, leading=14, leftIndent=12, rightIndent=12,
        backColor=colors.HexColor("#FFF8E1"),
        borderPadding=6, spaceAfter=8, fontName="Helvetica-Oblique")
    s["subtitle"] = ParagraphStyle("Subtitle", parent=base["Normal"],
        fontSize=14, textColor=C_GRAY, spaceAfter=2, alignment=TA_CENTER,
        fontName="Helvetica-Oblique")
    s["center"] = ParagraphStyle("Center", parent=base["Normal"],
        fontSize=11, leading=16, alignment=TA_CENTER, fontName="Helvetica")
    s["toc"] = ParagraphStyle("TOC", parent=base["Normal"],
        fontSize=12, leading=20, leftIndent=10, fontName="Helvetica")
    return s


S = make_styles()


def code_block(text: str) -> list:
    """Return a list of flowables rendering a shaded code block."""
    return [Preformatted(text, S["code"]), Spacer(1, 6)]


def note(text: str) -> list:
    return [Paragraph(f"<b>Note:</b> {text}", S["note"]), Spacer(1, 4)]


def warn(text: str) -> list:
    return [Paragraph(f"<b>Tip:</b> {text}", S["warn"]), Spacer(1, 4)]


def hr():
    return [HRFlowable(width="100%", thickness=1, color=C_GRAY, spaceAfter=6)]


def h2(text): return [Paragraph(text, S["h2"])]
def h3(text): return [Paragraph(text, S["h3"])]
def p(text):  return [Paragraph(text, S["body"]), Spacer(1, 2)]
def b(text):  return [Paragraph(f"• {text}", S["bullet"])]


def cover_page(title: str, subtitle: str, num: int) -> list:
    story = []
    story.append(Spacer(1, 3 * cm))
    story.append(Paragraph(f"Module {num:02d}", S["subtitle"]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(title, S["h1"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(subtitle, S["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=2, color=C_BLUE, spaceBefore=10, spaceAfter=10))
    story.append(Paragraph("content-automation-bot — Backend Learning Series", S["center"]))
    story.append(Paragraph("Zero Prerequisites → Production-Ready Code", S["center"]))
    story.append(PageBreak())
    return story


def build_pdf(filename: str, story: list) -> None:
    path = OUT_DIR / filename
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title=filename.replace(".pdf", ""),
    )
    doc.build(story)
    print(f"  OK  {path.name}")


# ============================================================================
# PDF 01 — FastAPI
# ============================================================================
def pdf_01_fastapi():
    story = cover_page("FastAPI", "Build async REST APIs from zero to production", 1)

    story += h2("1. What is a Web Framework?")
    story += p("When a user's browser or app talks to your backend, it sends an HTTP request "
               "(think: a letter with an address and a message). Your backend reads it, does some work, "
               "and sends back an HTTP response (the reply). A <b>web framework</b> is the library that "
               "handles all the boring plumbing — reading the request, parsing the URL, routing it to "
               "the right function, and sending the response back.")
    story += p("FastAPI is Python's modern async-first web framework. It is built on top of "
               "<b>Starlette</b> (the ASGI server layer) and <b>Pydantic</b> (data validation). "
               "Compared to Flask it is faster and has built-in type safety. Compared to Django "
               "it is lighter and requires far less boilerplate.")

    story += h2("2. Install &amp; First Endpoint")
    story += code_block(
"""# Install (inside your venv)
pip install fastapi uvicorn

# hello.py
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Hello, world!"}

# Run it:
# uvicorn hello:app --reload --port 8000
# Visit http://localhost:8000  →  {"message": "Hello, world!"}
# Docs:  http://localhost:8000/docs  (auto-generated Swagger UI)""")
    story += note("FastAPI automatically generates interactive API documentation at /docs — "
                  "you get this for free with zero extra configuration.")

    story += h2("3. HTTP Methods and Path Parameters")
    story += p("REST APIs follow a convention: GET = read, POST = create, PUT/PATCH = update, DELETE = remove.")
    story += code_block(
"""from fastapi import FastAPI

app = FastAPI()

# GET with path parameter
@app.get("/items/{item_id}")
def get_item(item_id: int):        # FastAPI reads {item_id} from URL and casts to int
    return {"id": item_id, "name": f"Item {item_id}"}

# GET with query parameters
@app.get("/search")
def search(q: str, limit: int = 10):   # ?q=hello&limit=5
    return {"query": q, "limit": limit, "results": []}

# POST with a body
from pydantic import BaseModel

class Item(BaseModel):
    name: str
    price: float

@app.post("/items/")
def create_item(item: Item):    # FastAPI reads JSON body → Item object
    return {"created": item.name, "price": item.price}""")

    story += h2("4. Status Codes and Responses")
    story += code_block(
"""from fastapi import FastAPI, HTTPException

app = FastAPI()

fake_db = {1: "Alice", 2: "Bob"}

@app.get("/users/{user_id}")
def get_user(user_id: int):
    if user_id not in fake_db:
        raise HTTPException(status_code=404, detail="User not found")
    return {"name": fake_db[user_id]}

# FastAPI maps Python exceptions to HTTP status codes automatically.""")

    story += h2("5. Routers — Splitting Your API into Modules")
    story += p("As your API grows, one file becomes messy. FastAPI's <b>APIRouter</b> lets you "
               "split routes into separate files and include them in the main app — exactly like "
               "Flask Blueprints.")
    story += code_block(
"""# routers/users.py
from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/")
def list_users():
    return []

@router.post("/")
def create_user():
    return {"created": True}

# ─────────────────────────────────────
# main.py
from fastapi import FastAPI
from routers.users import router as users_router

app = FastAPI()
app.include_router(users_router)   # all /users/* endpoints registered""")

    story += h2("6. Dependency Injection (Depends)")
    story += p("Dependency injection lets you write reusable logic (auth checks, DB sessions, "
               "settings) that FastAPI automatically calls and injects into your route functions.")
    story += code_block(
"""from fastapi import FastAPI, Depends, HTTPException, Header

app = FastAPI()

# ── Dependency: extract and verify API key ──
def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != "secret-key-123":
        raise HTTPException(status_code=401, detail="Invalid API key")

# ── Apply to one route ──
@app.get("/protected", dependencies=[Depends(verify_api_key)])
def protected_route():
    return {"data": "secret data"}

# ── Apply to ALL routes on a router ──
from fastapi import APIRouter
secure_router = APIRouter(dependencies=[Depends(verify_api_key)])

@secure_router.get("/admin")
def admin_route():
    return {"admin": True}""")
    story += note("In content-automation-bot every router except /unsubscribe is protected with "
                  "verify_api_key via Depends — see backend/app/api/main.py:63.")

    story += h2("7. Middleware and CORS")
    story += p("Middleware is code that runs on every request/response, before and after your route "
               "handlers. CORS (Cross-Origin Resource Sharing) middleware tells browsers whether "
               "your frontend (e.g. localhost:3000) is allowed to call your backend API.")
    story += code_block(
"""from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # frontend origin
    allow_credentials=False,
    allow_methods=["*"],    # GET, POST, PUT, DELETE, etc.
    allow_headers=["*"],
)

# Without this, browsers block fetch() calls from your Next.js app.""")

    story += h2("8. Lifespan — Startup &amp; Shutdown Logic")
    story += p("The <b>lifespan</b> context manager runs code when the server starts and when it "
               "shuts down. Use it to open database connections, Redis pools, or load ML models "
               "that you want to share across all requests.")
    story += code_block(
"""from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ──
    app.state.db = await connect_database()
    print("DB connected")

    yield          # server is running — handle requests here

    # ── shutdown ──
    await app.state.db.close()
    print("DB closed")

app = FastAPI(lifespan=lifespan)

@app.get("/items")
async def items(request: Request):
    db = request.app.state.db   # shared DB connection
    ...""")
    story += note("content-automation-bot uses this to create and close the arq Redis pool at startup/shutdown "
                  "(backend/app/api/main.py:18-38).")

    story += h2("9. Async Endpoints")
    story += p("FastAPI supports both sync (<code>def</code>) and async (<code>async def</code>) handlers. "
               "For I/O-bound work (database queries, external API calls) always use <code>async def</code>. "
               "For CPU-bound work use sync functions or run them in a thread pool.")
    story += code_block(
"""import httpx
from fastapi import FastAPI

app = FastAPI()

@app.get("/weather")
async def get_weather(city: str):
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"https://api.weather.com/{city}")
        data = resp.json()
    return {"city": city, "temp": data["temp"]}

# Notice: no blocking — the event loop handles other requests
# while we wait for the weather API to respond.""")

    story += h2("10. How content-automation-bot Uses FastAPI")
    story += p("The backend has one FastAPI app created in <code>backend/app/api/main.py</code>. "
               "It is split across 7 routers:")
    for r in [
        "ideas — Gate 1 approval (approve/reject content ideas)",
        "drafts — Gate 2 approval (approve/reject content drafts)",
        "triggers — trigger research/scoring/creation agents",
        "tables — read-only views of every DB table for the admin panel",
        "subscribers — unsubscribe endpoint (public, no auth required)",
        "knowledge_base — upload and list KB files",
        "orchestrator — streaming WebSocket chat with the AI orchestrator",
    ]:
        story += b(r)

    story += h2("11. Practice Exercises")
    story += p("Build these in order — each one teaches a new FastAPI concept:")
    for i, ex in enumerate([
        "Create a FastAPI app with a GET /hello/{name} that returns 'Hello, {name}!'",
        "Add a POST /items endpoint that accepts {name: str, price: float} and returns the item",
        "Add a verify_api_key dependency and apply it to POST /items",
        "Split GET /items and POST /items into a separate router in items.py",
        "Add CORS middleware allowing http://localhost:3000",
        "Add a lifespan that prints 'Server starting' and 'Server stopped'",
        "Add an async GET /fetch that calls any public API using httpx and returns results",
    ], 1):
        story += b(f"Exercise {i}: {ex}")

    build_pdf("01_FastAPI.pdf", story)


# ============================================================================
# PDF 02 — Python asyncio
# ============================================================================
def pdf_02_asyncio():
    story = cover_page("Python asyncio", "Concurrency without threads — event loops, coroutines, and async patterns", 2)

    story += h2("1. Why Do We Need Concurrency?")
    story += p("Imagine your program fetches data from 10 websites. If done one at a time it might "
               "take 10 × 2 seconds = 20 seconds. If you could do all 10 at once, it would take ~2 seconds. "
               "There are three main ways to achieve this in Python:")

    tbl_data = [
        ["Approach", "How it works", "Best for"],
        ["Threads", "OS runs multiple threads in parallel", "I/O-bound (many blocking calls)"],
        ["Processes", "OS runs separate Python processes", "CPU-bound (heavy computation)"],
        ["asyncio", "One thread, cooperative switching", "I/O-bound, very many tasks"],
    ]
    tbl = Table(tbl_data, colWidths=[4*cm, 7*cm, 6*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_BLUE),
        ("TEXTCOLOR",  (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID",       (0, 0), (-1, -1), 0.5, C_GRAY),
        ("BACKGROUND", (0, 1), (-1, -1), C_LGRAY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_LGRAY, C_WHITE]),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("PADDING",    (0, 0), (-1, -1), 6),
    ]))
    story += [tbl, Spacer(1, 10)]

    story += h2("2. Coroutines — The Async Function")
    story += p("A <b>coroutine</b> is a function defined with <code>async def</code>. Calling it does NOT "
               "run it immediately — it returns a coroutine object. You must <code>await</code> it to "
               "actually execute it. The <code>await</code> keyword tells Python: 'pause here and let "
               "other coroutines run while we wait for this I/O.'")
    story += code_block(
"""import asyncio

# Regular function — runs synchronously (blocks)
def slow_sync():
    import time
    time.sleep(2)
    return "done"

# Async function — can be paused, lets others run during the wait
async def slow_async():
    await asyncio.sleep(2)    # yields control to the event loop
    return "done"

# Running a coroutine
async def main():
    result = await slow_async()   # awaiting it actually runs it
    print(result)

asyncio.run(main())   # this is the entry point — starts the event loop""")
    story += note("asyncio.sleep() is non-blocking. time.sleep() is blocking — it freezes the whole program. "
                  "NEVER use time.sleep() inside async code.")

    story += h2("3. asyncio.gather — Run Multiple Tasks at Once")
    story += p("The most powerful asyncio primitive. It runs several coroutines <b>concurrently</b> "
               "and waits for all of them to finish. This is how you fetch 10 websites at the same time.")
    story += code_block(
"""import asyncio

async def fetch(site: str) -> str:
    await asyncio.sleep(1)    # simulating a 1-second network call
    return f"data from {site}"

async def main():
    # Sequential — takes 3 seconds
    r1 = await fetch("site1.com")
    r2 = await fetch("site2.com")
    r3 = await fetch("site3.com")

    # Concurrent with gather — takes ~1 second
    r1, r2, r3 = await asyncio.gather(
        fetch("site1.com"),
        fetch("site2.com"),
        fetch("site3.com"),
    )
    print(r1, r2, r3)

asyncio.run(main())""")
    story += p("You can also use <code>return_exceptions=True</code> to prevent one failure from "
               "cancelling others — individual results can be Exception objects, which you check with "
               "<code>isinstance(result, Exception)</code>.")
    story += code_block(
"""# gather with error handling
results = await asyncio.gather(
    fetch("good-site.com"),
    fetch("broken-site.com"),   # might raise
    return_exceptions=True,
)
for r in results:
    if isinstance(r, Exception):
        print(f"Failed: {r}")
    else:
        print(f"Got: {r}")""")

    story += h2("4. asyncio.Semaphore — Limit Concurrency")
    story += p("Running 1000 tasks at once might crash your server or get you rate-limited. "
               "A <b>Semaphore</b> is a counter that limits how many tasks can run simultaneously.")
    story += code_block(
"""import asyncio

sem = asyncio.Semaphore(3)   # max 3 concurrent tasks

async def fetch(url: str) -> str:
    async with sem:          # waits if 3 tasks are already running
        await asyncio.sleep(1)
        return f"data from {url}"

async def main():
    urls = [f"site{i}.com" for i in range(10)]
    results = await asyncio.gather(*[fetch(u) for u in urls])
    # Even with 10 tasks, only 3 run at a time

asyncio.run(main())""")
    story += note("In content-automation-bot the research agent uses Semaphore(3) to cap concurrent browser "
                  "instances and Semaphore(2) to limit parallel Supabase batch-dedup calls.")

    story += h2("5. asyncio.Lock — Protect Shared State")
    story += p("When multiple coroutines share a variable (like a counter), reads and writes can "
               "interleave in unexpected ways. A <b>Lock</b> ensures only one coroutine touches "
               "the shared variable at a time.")
    story += code_block(
"""import asyncio

lock = asyncio.Lock()
counter = 0

async def increment():
    global counter
    async with lock:
        # Only one coroutine is inside this block at a time
        current = counter
        await asyncio.sleep(0)   # simulate a tiny pause
        counter = current + 1

async def main():
    await asyncio.gather(*[increment() for _ in range(100)])
    print(counter)   # 100 — no race condition

asyncio.run(main())""")

    story += h2("6. asyncio.to_thread — Run Sync Code Without Blocking")
    story += p("Sometimes you must call synchronous code (like a Supabase client that only has a "
               "sync API) from async code. Wrapping it in <code>asyncio.to_thread()</code> runs it "
               "in a separate thread so it doesn't block the event loop.")
    story += code_block(
"""import asyncio

def slow_db_call(query: str) -> list:
    # Pretend this is a synchronous DB call (blocking)
    import time
    time.sleep(0.5)
    return [{"id": 1}, {"id": 2}]

async def main():
    # WRONG — blocks the event loop for 0.5 seconds:
    # data = slow_db_call("SELECT * FROM items")

    # CORRECT — runs in a thread, event loop stays free:
    data = await asyncio.to_thread(slow_db_call, "SELECT * FROM items")
    print(data)

asyncio.run(main())""")
    story += note("content-automation-bot wraps all Supabase calls with asyncio.to_thread() because the "
                  "supabase-py client is synchronous.")

    story += h2("7. asyncio.wait_for — Timeouts")
    story += code_block(
"""import asyncio

async def slow_operation():
    await asyncio.sleep(10)   # takes 10 seconds
    return "result"

async def main():
    try:
        result = await asyncio.wait_for(slow_operation(), timeout=3.0)
    except asyncio.TimeoutError:
        print("Operation timed out after 3 seconds!")

asyncio.run(main())""")

    story += h2("8. nonlocal — Sharing State Inside Closures")
    story += p("When a nested function (like a task handler) needs to modify a variable in the "
               "outer function, use the <code>nonlocal</code> keyword.")
    story += code_block(
"""async def run_pipeline():
    success_count = 0
    failure_count = 0

    async def process_item(item):
        nonlocal success_count, failure_count   # reference outer variables
        try:
            await do_work(item)
            success_count += 1
        except Exception:
            failure_count += 1

    await asyncio.gather(*[process_item(i) for i in range(10)])
    print(f"Success: {success_count}, Failures: {failure_count}")""")
    story += warn("If multiple tasks run concurrently, protect shared counters with a Lock to avoid "
                  "race conditions (see content-automation-bot's _lock pattern in tasks.py).")

    story += h2("9. How content-automation-bot Uses asyncio")
    story += p("The research agent processes 7 news sites in parallel with asyncio.gather. "
               "Each site processing itself fetches multiple articles concurrently (capped by Semaphore). "
               "Supabase (sync) calls are wrapped in asyncio.to_thread. Article fetches have a "
               "90-second hard timeout via asyncio.wait_for.")

    story += h2("10. Practice Exercises")
    for i, ex in enumerate([
        "Write a coroutine fetch(url) that sleeps 1 second and returns the url. Run 5 of them sequentially, measure time.",
        "Now run the same 5 with asyncio.gather — measure the time difference.",
        "Add a Semaphore(2) so only 2 run at once.",
        "Add a shared counter protected by a Lock. Verify the count is always correct.",
        "Wrap time.sleep(1) with asyncio.to_thread and verify the event loop stays free.",
        "Add asyncio.wait_for with a 0.5 second timeout and handle the TimeoutError.",
    ], 1):
        story += b(f"Exercise {i}: {ex}")

    build_pdf("02_Python_Asyncio.pdf", story)


# ============================================================================
# PDF 03 — Redis + arq (Job Queues)
# ============================================================================
def pdf_03_job_queues():
    story = cover_page("Redis + arq (Job Queues)",
                        "Background tasks, cron scheduling, and deferred jobs", 3)

    story += h2("1. What is a Job Queue and Why Do You Need One?")
    story += p("Some tasks take too long to run inside an HTTP request. If a user hits POST /run-research "
               "and the research takes 10 minutes, the HTTP request would time out. Instead, you put "
               "the task into a <b>queue</b> and return immediately. A separate <b>worker</b> process "
               "picks it up and runs it in the background.")
    story += p("Real-world uses: sending emails, processing images, scraping websites, running ML models, "
               "syncing data, generating reports.")

    story += h2("2. Redis — The Queue Backbone")
    story += p("Redis is an in-memory key-value store. It's extremely fast (microsecond operations) "
               "and supports data structures like lists, sets, hashes, and sorted sets. Job queues "
               "use Redis lists as queues: the API <b>pushes</b> job data onto a list; the worker "
               "<b>pops</b> from the list to get the next job.")
    story += code_block(
"""# Install Redis on Windows (easiest: use WSL or Docker)
# docker run -d -p 6379:6379 redis:alpine

# Install Python client
pip install redis

import redis

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

# Basic operations
r.set("name", "Himanshu")          # SET key value
val = r.get("name")                 # GET key  → "Himanshu"
r.lpush("my_queue", "job1")        # push to list (left end)
r.lpush("my_queue", "job2")
job = r.brpop("my_queue", timeout=5)  # blocking pop (right end)
print(job)   # ("my_queue", "job1")""")

    story += h2("3. arq — Async Job Queue for Python")
    story += p("arq (async Redis Queue) is a Python library that wraps Redis and provides a clean "
               "API for defining tasks, enqueueing them, and running a worker that processes them. "
               "It is built for async Python (asyncio).")
    story += code_block(
"""pip install arq

# tasks.py — define your task functions
async def send_email(ctx: dict, to: str, subject: str) -> dict:
    # ctx is injected by arq — holds shared resources
    print(f"Sending email to {to}: {subject}")
    await asyncio.sleep(0.5)   # simulate email sending
    return {"status": "sent", "to": to}

async def resize_image(ctx: dict, image_path: str) -> dict:
    print(f"Resizing {image_path}")
    return {"resized": True}""")

    story += h2("4. WorkerSettings — Registering Tasks")
    story += code_block(
"""# worker.py
from arq.connections import RedisSettings
from tasks import send_email, resize_image

class WorkerSettings:
    # List all your task functions here
    functions = [send_email, resize_image]

    # Where Redis is running
    redis_settings = RedisSettings(host="localhost", port=6379)

    # Max jobs to run simultaneously
    max_jobs = 10

    # Max seconds a job can run before being killed
    job_timeout = 300

    # Run at startup / shutdown (optional)
    async def on_startup(ctx):
        print("Worker starting up...")
        ctx["db"] = await connect_db()   # shared across all tasks

    async def on_shutdown(ctx):
        await ctx["db"].close()

# Run the worker:
# python -m arq worker.WorkerSettings""")

    story += h2("5. Enqueueing Jobs — From Your API or Anywhere")
    story += code_block(
"""import arq
from worker import WorkerSettings

async def main():
    # Create a connection pool to Redis
    pool = await arq.create_pool(WorkerSettings.redis_settings)

    # Enqueue a job — runs as soon as the worker picks it up
    job = await pool.enqueue_job("send_email", to="user@example.com", subject="Hello")
    print(f"Enqueued job: {job.job_id}")

    # Enqueue with a delay (runs after 1 hour)
    from datetime import timedelta
    job2 = await pool.enqueue_job(
        "resize_image",
        image_path="/uploads/photo.jpg",
        _defer_by=timedelta(hours=1),
    )

    await pool.close()""")
    story += note("In content-automation-bot, the FastAPI app creates an arq pool at startup "
                  "(lifespan) and stores it in app.state.arq_pool so all endpoints can enqueue jobs.")

    story += h2("6. Cron Jobs — Scheduled Recurring Tasks")
    story += code_block(
"""from arq import cron
from tasks import send_email, cleanup_db

class WorkerSettings:
    functions = [send_email, cleanup_db]
    redis_settings = RedisSettings()

    cron_jobs = [
        # Run cleanup_db every day at 3 AM
        cron(cleanup_db, hour=3, minute=0),

        # Run send_email every hour at minute 0
        cron(send_email, to="admin@example.com",
             subject="Hourly report", minute=0),

        # Run every 15 minutes
        cron(send_email, to="admin@example.com",
             subject="15-min check", minute={0, 15, 30, 45}),
    ]""")
    story += note("content-automation-bot runs the research agent daily at 6 AM IST (00:30 UTC) and "
                  "the publishing agent every 15 minutes via cron_jobs.")

    story += h2("7. Job Chaining — Triggering the Next Job on Completion")
    story += p("One job can enqueue another job when it finishes. This creates a pipeline: "
               "research → scoring → creation, all triggered automatically.")
    story += code_block(
"""async def research_agent_task(ctx: dict) -> dict:
    # ... do research work ...

    # When done, automatically kick off the scoring agent
    arq_pool = ctx.get("redis")   # arq injects the pool as "redis" in ctx
    if arq_pool is not None:
        await arq_pool.enqueue_job("scoring_agent_task")

    return {"status": "done", "processed": 42}""")

    story += h2("8. The ctx Dict — Shared Resources")
    story += p("Every task receives a <code>ctx</code> dict as its first argument. arq "
               "populates it with shared resources from on_startup. You can store database "
               "connections, settings, or any object there.")
    story += code_block(
"""class WorkerSettings:
    async def on_startup(ctx: dict):
        from myapp.db import get_db_client
        from myapp.config import Settings
        ctx["db"] = get_db_client()         # shared DB client
        ctx["settings"] = Settings()        # app config
        ctx["redis"]   # already injected by arq — the arq connection pool

async def my_task(ctx: dict, item_id: str) -> dict:
    db       = ctx["db"]
    settings = ctx["settings"]
    pool     = ctx["redis"]   # can enqueue more jobs
    ...""")

    story += h2("9. How content-automation-bot Uses arq")
    story += p("The project has 6 task functions: research, scoring, creation, publishing, "
               "analytics, and login_site. The worker is started with "
               "<code>python -m arq app.queue.worker.WorkerSettings</code>. "
               "The FastAPI app enqueues jobs via app.state.arq_pool.")

    story += h2("10. Practice Exercises")
    for i, ex in enumerate([
        "Start Redis with Docker: docker run -d -p 6379:6379 redis:alpine",
        "Write a task add_numbers(ctx, a, b) that returns a+b after 1 second.",
        "Write WorkerSettings that registers add_numbers.",
        "Write a script that enqueues add_numbers(3, 7) and prints the job_id.",
        "Start the worker and watch it process the job.",
        "Add a cron job that runs add_numbers(1, 1) every minute.",
        "Chain: make add_numbers enqueue a log_result task when it finishes.",
    ], 1):
        story += b(f"Exercise {i}: {ex}")

    build_pdf("03_Redis_arq_Job_Queues.pdf", story)


# ============================================================================
# PDF 04 — PostgreSQL + Supabase
# ============================================================================
def pdf_04_postgres_supabase():
    story = cover_page("PostgreSQL + Supabase",
                        "Relational databases, SQL, schema design, and the Supabase Python client", 4)

    story += h2("1. What is a Relational Database?")
    story += p("A relational database stores data in <b>tables</b> (like spreadsheets). Each table "
               "has named <b>columns</b> (schema) and <b>rows</b> (records). Tables can reference "
               "each other via <b>foreign keys</b>. SQL (Structured Query Language) is the universal "
               "language for querying and modifying this data.")
    story += p("PostgreSQL (Postgres) is the most powerful open-source relational database. It supports "
               "JSON columns, full-text search, geospatial queries, and extensions like pgvector for "
               "vector similarity search.")

    story += h2("2. Core SQL Commands")
    story += code_block(
"""-- Create a table
CREATE TABLE users (
    id         SERIAL PRIMARY KEY,     -- auto-incrementing integer
    email      TEXT UNIQUE NOT NULL,
    name       TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert a row
INSERT INTO users (email, name) VALUES ('alice@example.com', 'Alice');

-- Read rows
SELECT id, email, name FROM users;
SELECT * FROM users WHERE email = 'alice@example.com';
SELECT * FROM users ORDER BY created_at DESC LIMIT 10;

-- Update a row
UPDATE users SET name = 'Alice Smith' WHERE id = 1;

-- Delete a row
DELETE FROM users WHERE id = 1;""")

    story += h2("3. Primary Keys, Foreign Keys, and Indexes")
    story += code_block(
"""-- Primary key: unique identifier for each row
CREATE TABLE posts (
    id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title   TEXT NOT NULL,
    body    TEXT,
    user_id INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Index: makes lookups fast (like a book index)
CREATE INDEX idx_posts_user_id ON posts(user_id);

-- Without the index: Postgres scans every row (slow for large tables)
-- With the index: Postgres jumps directly to matching rows (fast)

-- Unique constraint: no two rows can have the same value
ALTER TABLE users ADD CONSTRAINT unique_email UNIQUE (email);""")

    story += h2("4. What is Supabase?")
    story += p("Supabase is a hosted Postgres database with extras built on top: REST API auto-generated "
               "from your schema, auth, realtime subscriptions, and storage. You get a fully managed "
               "Postgres database with a Python client that makes CRUD operations easy without writing "
               "raw SQL every time.")
    story += code_block(
"""pip install supabase

from supabase import create_client, Client

SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-service-role-key"  # from Supabase dashboard

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)""")

    story += h2("5. CRUD with the Supabase Python Client")
    story += code_block(
"""# ── CREATE (INSERT) ──
resp = supabase.table("users").insert({
    "email": "alice@example.com",
    "name": "Alice",
}).execute()
print(resp.data)   # [{"id": "...", "email": "alice@...", "name": "Alice"}]

# ── READ (SELECT) ──
resp = supabase.table("users").select("*").execute()
all_users = resp.data

resp = supabase.table("users").select("id, email").eq("name", "Alice").execute()
matching = resp.data

# ── READ with ordering and limit ──
resp = (supabase.table("users")
        .select("*")
        .order("created_at", desc=True)
        .limit(10)
        .execute())

# ── UPDATE ──
resp = (supabase.table("users")
        .update({"name": "Alice Smith"})
        .eq("email", "alice@example.com")
        .execute())

# ── DELETE ──
resp = (supabase.table("users")
        .delete()
        .eq("email", "old_user@example.com")
        .execute())""")

    story += h2("6. Upsert — Insert or Update")
    story += p("Upsert inserts a row if it doesn't exist, or updates it if it does. This is critical "
               "for idempotent operations (running the same code twice gives the same result).")
    story += code_block(
"""# Upsert: if the email already exists, update name; otherwise insert
resp = supabase.table("users").upsert({
    "email": "alice@example.com",
    "name": "Alice Updated",
}, on_conflict="email").execute()""")

    story += h2("7. Filtering — Where Clauses")
    story += code_block(
"""# Equal
.eq("status", "active")

# Not equal
.neq("status", "deleted")

# In a list
.in_("id", ["id1", "id2", "id3"])

# Less than or equal
.lte("scheduled_at", datetime.utcnow().isoformat())

# Greater than
.gt("score", 4.0)

# Is null
.is_("deleted_at", "null")

# Full example: approved ideas for LinkedIn
resp = (supabase.table("ideas")
        .select("*")
        .eq("approval_status", "approved")
        .eq("platform", "linkedin")
        .order("score", desc=True)
        .limit(5)
        .execute())""")

    story += h2("8. Calling Stored Procedures with .rpc()")
    story += p("Supabase lets you define Postgres functions (stored procedures) that you can "
               "call via the Python client. This is used for vector similarity search with pgvector.")
    story += code_block(
"""# Call a Postgres function: match_knowledge_base(query_embedding, match_count)
resp = supabase.rpc(
    "match_knowledge_base",
    {"query_embedding": [0.1, 0.2, ...], "match_count": 5}
).execute()
results = resp.data   # list of matching KB chunks with similarity scores""")

    story += h2("9. Schema Design — content-automation-bot's 15 Tables")
    story += p("Good schema design follows these rules:")
    story += b("Each table has one clear purpose (single responsibility)")
    story += b("Use UUIDs as primary keys (not sequential integers) for distributed safety")
    story += b("Store status as an enum column, not separate tables")
    story += b("Use JSONB for flexible nested data (metrics, flags, summaries)")
    story += b("Add indexes on columns you filter/sort on frequently")
    story += b("Soft delete: add an 'active' or 'deleted_at' column instead of actually deleting")

    story += h2("10. Practice Exercises")
    for i, ex in enumerate([
        "Create a Supabase project (free at supabase.com), get your URL and service key.",
        "Create a 'tasks' table: id (uuid, pk), title (text), done (bool default false), created_at (timestamptz).",
        "Insert 5 tasks using the Python client.",
        "Query all tasks where done=false, ordered by created_at.",
        "Update task 1 to done=true.",
        "Upsert a task by title — run it twice, verify no duplicates.",
        "Design the schema for a blog: users, posts, comments. Draw the relationships.",
    ], 1):
        story += b(f"Exercise {i}: {ex}")

    build_pdf("04_PostgreSQL_Supabase.pdf", story)


# ============================================================================
# PDF 05 — Vector Embeddings & RAG
# ============================================================================
def pdf_05_embeddings_rag():
    story = cover_page("Vector Embeddings & RAG",
                        "How machines represent meaning — and how to build semantic search", 5)

    story += h2("1. The Problem: Keyword Search is Dumb")
    story += p("If you search a database for 'car', you'll miss articles about 'automobile', "
               "'vehicle', or 'Tesla'. Keyword search matches exact strings. "
               "<b>Semantic search</b> understands meaning — 'car' and 'automobile' are similar. "
               "This is made possible by <b>vector embeddings</b>.")

    story += h2("2. What is a Vector Embedding?")
    story += p("An embedding is a list of numbers (a vector) that represents the meaning of a piece "
               "of text. An embedding model (a neural network) converts any sentence into, say, "
               "768 numbers. Sentences with similar meanings produce vectors that are close to each "
               "other in 768-dimensional space.")
    story += code_block(
"""# Conceptual example (actual vectors are 768 numbers)
"The stock market crashed"   → [0.23, -0.41, 0.88, ...]
"Markets fell sharply today" → [0.25, -0.39, 0.86, ...]   # very similar!
"I like pizza"               → [-0.91, 0.12, -0.33, ...]  # very different""")

    story += h2("3. Cosine Similarity — How Close are Two Vectors?")
    story += p("Cosine similarity measures the angle between two vectors. Score = 1.0 means "
               "identical meaning, 0.0 means unrelated, -1.0 means opposite.")
    story += code_block(
"""import numpy as np

def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    a = np.array(vec_a)
    b = np.array(vec_b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

# Example:
v1 = [1.0, 0.0, 0.0]
v2 = [0.9, 0.1, 0.0]
v3 = [0.0, 1.0, 0.0]

print(cosine_similarity(v1, v2))  # ~0.99 — very similar
print(cosine_similarity(v1, v3))  # 0.0   — completely different""")

    story += h2("4. Generating Embeddings with an API")
    story += code_block(
"""# Option A: Google Gemini text-embedding-004 (API-based, 768 dims)
from google import genai

client = genai.Client(api_key="YOUR_GOOGLE_API_KEY")
result = client.models.embed_content(
    model="models/text-embedding-004",
    contents=["Stock market crashes 10%"],
    config={"task_type": "RETRIEVAL_DOCUMENT"},
)
vector = result.embeddings[0].values   # list of 768 floats

# Option B: Local fastembed BAAI/bge-base-en-v1.5 (no API key, 768 dims)
from fastembed import TextEmbedding

model = TextEmbedding(model_name="BAAI/bge-base-en-v1.5")
vectors = list(model.embed(["Stock market crashes 10%"]))
vector = vectors[0].tolist()""")

    story += h2("5. pgvector — Vector Search in PostgreSQL")
    story += p("pgvector is a Postgres extension that adds a <code>vector</code> column type and "
               "approximate nearest-neighbor search. This means you can store embeddings in "
               "Postgres and query for the most similar ones — no separate vector database needed.")
    story += code_block(
"""-- 1. Enable the extension (run once in Supabase SQL editor)
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Create a table with a vector column
CREATE TABLE knowledge_base (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_file TEXT,
    chunk_index INT,
    content     TEXT,
    embedding   vector(768),   -- 768-dimensional vector
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Index for fast approximate search (HNSW algorithm)
CREATE INDEX ON knowledge_base
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);""")

    story += h2("6. Storing and Querying Embeddings from Python")
    story += code_block(
"""# Storing an embedding
supabase.table("knowledge_base").insert({
    "source_file": "rbi_policy.pdf",
    "chunk_index": 0,
    "content": "RBI raised rates by 25 bps...",
    "embedding": [0.23, -0.41, 0.88, ...],  # 768 floats
}).execute()

# Searching: find 5 most similar chunks to a query
# (uses a Postgres function defined in Supabase)
resp = supabase.rpc(
    "match_knowledge_base",
    {"query_embedding": query_vector, "match_count": 5}
).execute()
results = resp.data""")

    story += code_block(
"""-- The match_knowledge_base function in Postgres:
CREATE OR REPLACE FUNCTION match_knowledge_base(
    query_embedding vector(768),
    match_count     int
)
RETURNS TABLE (id uuid, content text, similarity float)
LANGUAGE SQL
AS $$
    SELECT id, content,
           1 - (embedding <=> query_embedding) AS similarity
    FROM   knowledge_base
    ORDER  BY embedding <=> query_embedding
    LIMIT  match_count;
$$;""")

    story += h2("7. RAG — Retrieval-Augmented Generation")
    story += p("RAG combines semantic search with an LLM. Instead of asking the LLM to answer "
               "from its training data alone (which may be outdated or wrong), you first retrieve "
               "relevant documents from your database, then put them in the LLM's context.")
    story += code_block(
"""# Full RAG pipeline:
def answer_with_rag(question: str) -> str:
    # Step 1: embed the question
    query_vector = embed_text(question)

    # Step 2: retrieve top-5 relevant KB chunks
    resp = supabase.rpc(
        "match_knowledge_base",
        {"query_embedding": query_vector, "match_count": 5}
    ).execute()
    context = "\\n\\n".join(r["content"] for r in resp.data)

    # Step 3: ask the LLM using the retrieved context
    response = anthropic.messages.create(
        model="claude-sonnet-4-6",
        system="Answer only based on the context provided.",
        messages=[{
            "role": "user",
            "content": f"Context:\\n{context}\\n\\nQuestion: {question}",
        }],
        max_tokens=1024,
    )
    return response.content[0].text""")

    story += h2("8. Text Chunking — Splitting Documents for Embedding")
    story += p("LLM context windows and embedding models have token limits. Long documents must "
               "be split into chunks. The strategy matters — split too small and you lose context, "
               "too large and you exceed limits.")
    story += code_block(
"""def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    \"\"\"Split text into overlapping chunks of ~chunk_size words.\"\"\"
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap   # overlap helps with continuity
    return chunks

# Embed all chunks and store in DB
text = "Very long document..."
chunks = chunk_text(text)
for i, chunk in enumerate(chunks):
    vector = embed_text(chunk)
    supabase.table("knowledge_base").insert({
        "source_file": "doc.pdf",
        "chunk_index": i,
        "content": chunk,
        "embedding": vector,
    }).execute()""")

    story += h2("9. The FallbackEmbedder Pattern")
    story += p("content-automation-bot uses a fallback pattern: try Gemini first, fall back to local "
               "fastembed if Gemini fails. This makes the system resilient — it works even without "
               "API access. See backend/app/agents/embedding/client.py.")

    story += h2("10. Practice Exercises")
    for i, ex in enumerate([
        "Install fastembed: pip install fastembed. Embed 5 sentences and print the first 5 values of each vector.",
        "Compute cosine similarity between 'stock market crash' and 'equity markets fell'.",
        "Enable pgvector in Supabase. Create a kb_demo table with a vector(768) column.",
        "Embed 10 sentences and insert them into kb_demo with their vectors.",
        "Create a match_kb_demo Postgres function. Query for the 3 most similar to 'interest rates rise'.",
        "Build the full RAG pipeline: question → embed → retrieve → LLM answer.",
    ], 1):
        story += b(f"Exercise {i}: {ex}")

    build_pdf("05_Vector_Embeddings_RAG.pdf", story)


# ============================================================================
# PDF 06 — Playwright (Browser Automation)
# ============================================================================
def pdf_06_playwright():
    story = cover_page("Playwright — Browser Automation",
                        "Control real browsers programmatically — scraping, testing, and more", 6)

    story += h2("1. What is Browser Automation?")
    story += p("Browser automation means controlling a web browser (Chrome, Firefox, Edge) "
               "programmatically. Instead of you clicking and typing, Python does it. "
               "Use cases: web scraping (when sites block simple HTTP requests), automated testing, "
               "taking screenshots, filling forms, logging into sites.")
    story += p("Playwright is Microsoft's modern browser automation library. It supports Chromium, "
               "Firefox, and WebKit. It is faster and more reliable than Selenium. Crucially, "
               "it has a first-class async Python API.")

    story += h2("2. Install Playwright")
    story += code_block(
"""pip install playwright
playwright install chromium   # download browser binaries (~150 MB)

# For MS Edge specifically:
playwright install msedge""")

    story += h2("3. Your First Script — Open a Page and Extract Text")
    story += code_block(
"""from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    # Launch Chrome headlessly (no visible window)
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # Navigate to a URL
    page.goto("https://example.com")

    # Extract the page title
    title = page.title()
    print(f"Title: {title}")

    # Extract text from a CSS selector
    heading = page.inner_text("h1")
    print(f"Heading: {heading}")

    # Extract all links
    links = page.eval_on_selector_all(
        "a[href]",
        "elements => elements.map(e => ({href: e.href, text: e.textContent.trim()}))"
    )
    for link in links[:5]:
        print(link)

    browser.close()""")

    story += h2("4. Async Playwright — For Use with asyncio")
    story += code_block(
"""from playwright.async_api import async_playwright
import asyncio

async def scrape(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, timeout=30_000)  # 30 second timeout
        content = await page.inner_text("body")
        await browser.close()
        return content

async def main():
    text = await scrape("https://example.com")
    print(text[:200])

asyncio.run(main())""")

    story += h2("5. Sharing One Browser — Multiple Pages")
    story += p("Launching a browser is expensive (~1 second). Launching a page within an existing "
               "browser is cheap (~10ms). For concurrent scraping, launch ONE browser and create "
               "multiple pages/contexts from it.")
    story += code_block(
"""async def scrape_many(urls: list[str]) -> list[str]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        async def fetch_one(url: str) -> str:
            # BrowserContext = isolated session (own cookies, storage)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(url, timeout=30_000)
            text = await page.inner_text("body")
            await context.close()   # releases resources
            return text

        results = await asyncio.gather(*[fetch_one(u) for u in urls])
        await browser.close()
        return results""")
    story += note("content-automation-bot creates one shared browser per research run and uses new "
                  "contexts per article. This avoids fingerprint throttling (same browser = same cookies) "
                  "while keeping browser launch overhead to a minimum.")

    story += h2("6. Selecting Elements")
    story += code_block(
"""# CSS selectors
page.locator("h1")                    # first <h1>
page.locator(".article-title")        # by class
page.locator("#main-content")         # by id
page.locator("a[href*='/article/']")  # attribute contains

# Text content
page.get_by_text("Read more")

# Fill input and click button
await page.fill("input[name='email']", "user@example.com")
await page.click("button[type='submit']")

# Wait for element to appear (useful for SPAs with async loading)
await page.wait_for_selector(".results", timeout=10_000)

# Get all matching elements
articles = await page.query_selector_all(".article-card")
for article in articles:
    title = await article.inner_text(".title")""")

    story += h2("7. Extracting Content — Getting the Article Text")
    story += code_block(
"""async def extract_article(url: str) -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Block images and stylesheets to speed up loading
        await page.route("**/*.{png,jpg,gif,css}", lambda r: r.abort())

        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)

        # Extract what we need
        title = await page.inner_text("h1")

        # Get all paragraphs in the article body
        paragraphs = await page.eval_on_selector_all(
            "article p",
            "els => els.map(e => e.textContent.trim())"
        )
        body = "\\n".join(paragraphs)

        # Get publication date (if available as a meta tag)
        pub_date = await page.get_attribute(
            "meta[property='article:published_time']", "content"
        )

        await browser.close()
        return {"title": title, "body": body, "date": pub_date}""")

    story += h2("8. Persistent Context — Saving Login Sessions")
    story += p("A persistent browser context saves cookies and localStorage to a directory. "
               "This lets you log in once (manually or via automation) and reuse that session "
               "in future runs without logging in again.")
    story += code_block(
"""from playwright.async_api import async_playwright

async def login_and_save():
    async with async_playwright() as p:
        # The profile_dir stores cookies/localStorage across runs
        context = await p.chromium.launch_persistent_context(
            "./session_data/livemint",
            channel="msedge",
            headless=False,   # show the browser so you can log in manually
        )
        page = await context.new_page()
        await page.goto("https://www.livemint.com/login")
        # ... user logs in manually ...
        input("Press Enter after you've logged in")
        await context.close()  # cookies saved automatically

async def use_saved_session():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            "./session_data/livemint",
            channel="msedge",
            headless=True,    # use saved cookies, no login needed
        )
        page = await context.new_page()
        await page.goto("https://www.livemint.com/premium-article")
        # Already logged in — can access premium content""")

    story += h2("9. Handling Dynamic Content (SPAs)")
    story += code_block(
"""# For React/Vue/Angular sites that load content asynchronously:

# Option 1: wait for a specific element
await page.wait_for_selector(".article-body", timeout=15_000)

# Option 2: wait for network to be idle
await page.goto(url, wait_until="networkidle", timeout=30_000)

# Option 3: wait for a condition
await page.wait_for_function(
    "document.querySelectorAll('.article p').length > 3"
)""")

    story += h2("10. Practice Exercises")
    for i, ex in enumerate([
        "Install playwright and chromium. Write a script that opens https://news.ycombinator.com and prints the first 10 story titles.",
        "Extract all href links from any news site.",
        "Block images and CSS before loading — measure the speed difference.",
        "Open a login page visibly (headless=False). Log in, save the session. Then re-run with the session (headless=True) and verify you're logged in.",
        "Write an async scraper that fetches 5 URLs concurrently with gather.",
        "Add a Semaphore(2) to the concurrent scraper.",
        "Extract the publication date from an article's <meta> tag.",
    ], 1):
        story += b(f"Exercise {i}: {ex}")

    build_pdf("06_Playwright_Browser_Automation.pdf", story)


# ============================================================================
# PDF 07 — LLMs + Anthropic SDK
# ============================================================================
def pdf_07_llms_anthropic():
    story = cover_page("LLMs + Anthropic SDK",
                        "From what a language model is to building production AI features", 7)

    story += h2("1. What is a Large Language Model?")
    story += p("A Large Language Model (LLM) is a neural network trained on vast amounts of text. "
               "It learns to predict what comes next in a sequence of words. When you send it a "
               "message, it generates a response one token at a time (a token is roughly 3/4 of a word). "
               "LLMs like Claude or GPT-4 are surprisingly good at following instructions, reasoning, "
               "summarising, translating, and writing code.")
    story += p("LLMs are <b>stateless</b> — they don't remember previous conversations unless you "
               "include them in the current request. The entire conversation history must be sent "
               "every time.")

    story += h2("2. Tokens and Pricing")
    story += p("Pricing is per token (input + output). One token ≈ 0.75 words, or 4 characters. "
               "'Hello, how are you?' is about 5 tokens. Code has more tokens per word because "
               "symbols and indentation each count.")
    story += code_block(
"""# Estimate cost:
# Claude Sonnet 4.6 input: $3 per 1M tokens
# Claude Sonnet 4.6 output: $15 per 1M tokens

# 1000 API calls with:
#   average 500 input tokens  = 500,000 tokens = $1.50
#   average 200 output tokens = 200,000 tokens = $3.00
# Total: $4.50 for 1000 calls""")

    story += h2("3. The Anthropic SDK — Basic Usage")
    story += code_block(
"""pip install anthropic

from anthropic import Anthropic

client = Anthropic(api_key="YOUR_API_KEY")

message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    system="You are a helpful assistant for Indian finance topics.",
    messages=[
        {"role": "user", "content": "What is SEBI?"}
    ],
)

# Extract the text response
from anthropic.types import TextBlock
text = message.content[0].text if isinstance(message.content[0], TextBlock) else ""
print(text)

# Token usage
print(f"Input tokens: {message.usage.input_tokens}")
print(f"Output tokens: {message.usage.output_tokens}")""")

    story += h2("4. Multi-Turn Conversations")
    story += code_block(
"""from anthropic import Anthropic

client = Anthropic(api_key="YOUR_API_KEY")

conversation = []   # keep history manually

def chat(user_message: str) -> str:
    conversation.append({"role": "user", "content": user_message})

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system="You are a concise assistant.",
        messages=conversation,
    )

    assistant_text = response.content[0].text
    conversation.append({"role": "assistant", "content": assistant_text})
    return assistant_text

# Multi-turn example
print(chat("My name is Himanshu"))
print(chat("What is my name?"))   # correctly answers "Himanshu"
# (because the previous exchange is in conversation history)""")

    story += h2("5. Async Client — For FastAPI and asyncio")
    story += code_block(
"""from anthropic import AsyncAnthropic
import asyncio

client = AsyncAnthropic(api_key="YOUR_API_KEY")

async def summarise(text: str) -> str:
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": f"Summarise this in 3 bullets:\\n\\n{text}"
        }],
    )
    return response.content[0].text

async def main():
    # Run 3 summaries concurrently
    texts = ["Long article 1...", "Long article 2...", "Long article 3..."]
    summaries = await asyncio.gather(*[summarise(t) for t in texts])
    for s in summaries:
        print(s)

asyncio.run(main())""")

    story += h2("6. Structured Outputs — Getting JSON from the LLM")
    story += p("The most powerful pattern: ask the LLM to produce structured JSON. "
               "Use a clear schema in your prompt and parse the response.")
    story += code_block(
"""import json
from anthropic import Anthropic

client = Anthropic(api_key="YOUR_API_KEY")

def score_article(title: str, summary: str) -> dict:
    prompt = f\"\"\"Score this article for content potential.
Article title: {title}
Summary: {summary}

Respond in JSON ONLY — no other text:
{{
  "score": <float 1.0-10.0>,
  "reasoning": "<why this score>",
  "angles": ["<angle 1>", "<angle 2>"]
}}\"\"\"

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)

result = score_article("RBI raises rates by 25bps", "...")
print(result["score"], result["angles"])""")
    story += note("content-automation-bot uses this pattern in the scoring agent, summariser, and "
                  "idea generator — the LLM returns structured JSON that is then validated with Pydantic.")

    story += h2("7. Prompt Engineering Patterns")
    story += p("<b>System prompt</b>: sets the model's role, tone, constraints. Keep it stable "
               "across calls for caching benefits.")
    story += p("<b>One-shot / Few-shot</b>: give 1-3 examples of what you want. Far better "
               "than describing it in words.")
    story += code_block(
"""system = \"\"\"You summarise Indian financial news articles into 5 sections.
Always respond in this exact JSON format — no extra text.

Example output:
{
  "story_narrative": "2-3 sentences explaining what happened",
  "key_data_points": ["specific number or fact", "another fact"],
  "mechanism": "why this happened",
  "implications": "what this means for investors",
  "content_angles": ["angle 1", "angle 2"]
}\"\"\" """)

    story += h2("8. Batch API Calls with Semaphore")
    story += code_block(
"""import asyncio
from anthropic import AsyncAnthropic

client = AsyncAnthropic(api_key="YOUR_API_KEY")
sem = asyncio.Semaphore(5)   # max 5 concurrent Claude calls

async def score(title: str) -> float:
    async with sem:
        resp = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=64,
            messages=[{
                "role": "user",
                "content": f"Score this headline 1-10: {title}. Reply: {{\\"score\\": N}}"
            }],
        )
        data = json.loads(resp.content[0].text)
        return data["score"]

async def score_many(titles: list[str]) -> list[float]:
    return await asyncio.gather(*[score(t) for t in titles])""")

    story += h2("9. Token Cost Tracking")
    story += code_block(
"""def calculate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    # Prices per million tokens (as of 2025)
    prices = {
        "claude-sonnet-4-6":         {"in": 3.00,  "out": 15.00},
        "claude-haiku-4-5-20251001": {"in": 0.80,  "out": 4.00},
        "claude-opus-4-8":           {"in": 15.00, "out": 75.00},
    }
    p = prices.get(model, {"in": 3.00, "out": 15.00})
    cost = (input_tokens * p["in"] + output_tokens * p["out"]) / 1_000_000
    return cost""")

    story += h2("10. Practice Exercises")
    for i, ex in enumerate([
        "Make your first Anthropic API call: ask 'What is compound interest?' and print the response.",
        "Build a multi-turn chatbot that remembers the conversation for 5 turns.",
        "Write a function that returns the summary of any article as structured JSON.",
        "Use AsyncAnthropic and gather to score 5 headlines concurrently.",
        "Add a Semaphore(3) and retry logic for rate limit errors.",
        "Track input/output tokens across all calls and print total cost at the end.",
    ], 1):
        story += b(f"Exercise {i}: {ex}")

    build_pdf("07_LLMs_Anthropic_SDK.pdf", story)


# ============================================================================
# PDF 08 — Pydantic
# ============================================================================
def pdf_08_pydantic():
    story = cover_page("Pydantic",
                        "Type-safe data validation and serialisation for Python", 8)

    story += h2("1. The Problem Pydantic Solves")
    story += p("Python is dynamically typed. A function that expects an integer can silently "
               "receive a string and crash much later — far from where the bug was introduced. "
               "Pydantic lets you define <b>data models</b> with types. It validates data when "
               "you create an object, raises clear errors immediately, and serialises/deserialises "
               "to/from JSON automatically.")
    story += code_block(
"""# Without Pydantic — fragile, silent bugs
def create_user(data: dict):
    name = data["name"]   # KeyError if missing
    age  = data["age"]    # might be a string "25" instead of int 25
    # no error here — crashes later when you do arithmetic

# With Pydantic — validated at the boundary
from pydantic import BaseModel

class User(BaseModel):
    name: str
    age:  int

user = User(name="Alice", age=25)     # OK
user = User(name="Alice", age="25")   # also OK — Pydantic coerces "25" → 25
user = User(name="Alice", age="abc")  # ValidationError: 'abc' is not an int""")

    story += h2("2. BaseModel — The Core")
    story += code_block(
"""from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class Article(BaseModel):
    title:            str
    url:              str
    word_count:       int
    published_date:   Optional[datetime] = None   # optional, defaults to None
    is_paywalled:     bool = False                # optional, defaults to False

# Creating from keyword arguments
article = Article(title="RBI Rate Hike", url="https://...", word_count=850)

# Creating from a dict (e.g., parsed JSON or DB row)
data = {"title": "SEBI New Rules", "url": "https://...", "word_count": 600}
article = Article(**data)""")

    story += h2("3. model_dump — Serialise to Dict/JSON")
    story += code_block(
"""article = Article(title="Test", url="https://test.com", word_count=500)

# To a Python dict
d = article.model_dump()
# {"title": "Test", "url": "https://test.com", "word_count": 500,
#  "published_date": None, "is_paywalled": False}

# Exclude None values
d = article.model_dump(exclude_none=True)
# {"title": "Test", "url": "https://test.com", "word_count": 500, "is_paywalled": False}

# Include only specific fields
d = article.model_dump(include={"title", "url"})
# {"title": "Test", "url": "https://test.com"}

# To JSON string
json_str = article.model_dump_json()""")

    story += h2("4. Field — Defaults, Descriptions, Validation")
    story += code_block(
"""from pydantic import BaseModel, Field

class Idea(BaseModel):
    angle:     str   = Field(..., min_length=10, max_length=500)  # required, constrained
    score:     float = Field(default=5.0, ge=0.0, le=10.0)        # 0-10 range
    platform:  str   = Field(default="linkedin",
                              description="Target publishing platform")
    tags:      list[str] = Field(default_factory=list)            # mutable default!
    reasoning: str   = Field(default="", alias="agent_reasoning") # DB column alias

# !! Never use mutable defaults directly — use default_factory:
# BAD:  tags: list[str] = []       # shared across all instances!
# GOOD: tags: list[str] = Field(default_factory=list)""")

    story += h2("5. Nested Models")
    story += code_block(
"""from pydantic import BaseModel
from typing import Optional

class StructuredSummary(BaseModel):
    story_narrative: str
    key_data_points: list[str]
    mechanism:       str
    implications:    str
    content_angles:  list[str]

class RawContent(BaseModel):
    title:              str
    url:                str
    full_text:          str
    structured_summary: Optional[StructuredSummary] = None

# Nested creation — Pydantic validates recursively
content = RawContent(
    title="RBI Rate Hike",
    url="https://...",
    full_text="...",
    structured_summary=StructuredSummary(
        story_narrative="RBI raised rates by 25 bps...",
        key_data_points=["25 bps hike", "6th consecutive hike"],
        mechanism="Inflation above 6% target",
        implications="EMIs will rise",
        content_angles=["Impact on home loans", "How to protect savings"],
    )
)
# Serialises all nested objects correctly
print(content.model_dump_json(indent=2))""")

    story += h2("6. Enums — Constrained String Values")
    story += code_block(
"""from enum import Enum
from pydantic import BaseModel

class Platform(str, Enum):
    LINKEDIN = "linkedin"
    TWITTER  = "twitter"
    BLOG     = "blog"
    EMAIL    = "email"

class ApprovalStatus(str, Enum):
    PENDING  = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"

class Idea(BaseModel):
    platform:        Platform        # must be one of the enum values
    approval_status: ApprovalStatus  # same

# Usage
idea = Idea(platform="linkedin", approval_status="approved")  # strings auto-convert
idea.platform           # Platform.LINKEDIN
idea.platform.value     # "linkedin"  (for DB/JSON insertion)

# This raises ValidationError:
idea = Idea(platform="instagram", approval_status="approved")""")

    story += h2("7. model_construct — Skip Validation (Use With Care)")
    story += p("<code>model_construct()</code> creates a model instance WITHOUT running validators. "
               "Use ONLY when you trust the data source completely (e.g. reading from your own DB "
               "that already enforces constraints).")
    story += code_block(
"""# Slow — validates everything (use for untrusted input)
user = User(name="Alice", age=25)

# Fast — skips validation (use for trusted DB data)
user = User.model_construct(name="Alice", age=25)""")
    story += warn("model_construct skips ALL validation. Only use it for data you completely trust — "
                  "wrong data will silently produce invalid model instances that crash later.")

    story += h2("8. Validators — Custom Validation Logic")
    story += code_block(
"""from pydantic import BaseModel, field_validator

class Article(BaseModel):
    url: str
    word_count: int

    @field_validator("url")
    @classmethod
    def url_must_start_with_https(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("URL must start with https://")
        return v

    @field_validator("word_count")
    @classmethod
    def word_count_positive(cls, v: int) -> int:
        if v < 0:
            raise ValueError("word_count must be non-negative")
        return v""")

    story += h2("9. How content-automation-bot Uses Pydantic")
    story += p("Every database table has corresponding Pydantic models in "
               "<code>backend/app/db/models.py</code>. The pattern is:")
    story += b("<Table> — full DB row (includes id, created_at, DB-generated fields)")
    story += b("<Table>Create — minimal fields needed to INSERT a new row")
    story += b("<Table>Update — all optional fields for PATCH updates")
    story += p("This means the API can validate incoming requests, the agents can produce "
               "structured output, and the DB layer can serialise cleanly — all with the same model.")

    story += h2("10. Practice Exercises")
    for i, ex in enumerate([
        "Define a BlogPost model with: title (str), body (str), tags (list[str]), published (bool default False).",
        "Add Field constraints: title 10-200 chars, tags max 10 items.",
        "Add a nested Author model with name and email fields.",
        "Add a field_validator that ensures the email ends in '@example.com'.",
        "Add a Status enum: DRAFT, PUBLISHED, ARCHIVED.",
        "Create a BlogPostCreate model (only title+body required) and a BlogPost model (adds id, created_at, status).",
        "Serialise a BlogPost to JSON. Parse it back with model_validate_json().",
    ], 1):
        story += b(f"Exercise {i}: {ex}")

    build_pdf("08_Pydantic.pdf", story)


# ============================================================================
# PDF 09 — LangGraph + Agent Orchestration
# ============================================================================
def pdf_09_langgraph():
    story = cover_page("LangGraph + Agent Orchestration",
                        "Building AI agents that use tools, reason, and take actions", 9)

    story += h2("1. What is an AI Agent?")
    story += p("A chatbot just responds to messages. An <b>agent</b> can take <b>actions</b>. "
               "It decides what tool to use (search the web, query a database, send an email), "
               "uses it, observes the result, and decides what to do next. This loop continues "
               "until it has accomplished the goal.")
    story += p("Example: You say 'Show me unprocessed articles from last week'. The agent decides "
               "to call a database query tool, gets the results, formats them, and returns the answer. "
               "You then say 'Approve idea #3'. The agent calls the approve_idea tool.")

    story += h2("2. LangChain Tools — The @tool Decorator")
    story += p("A <b>tool</b> is a Python function that the LLM can decide to call. "
               "LangChain's <code>@tool</code> decorator converts any function into a tool "
               "by reading its name, docstring, and type annotations.")
    story += code_block(
"""from langchain_core.tools import tool
from typing import Optional

@tool
def get_weather(city: str, units: str = "celsius") -> str:
    \"\"\"Get the current weather for a city.
    city: The city name (e.g. 'Mumbai', 'Delhi').
    units: 'celsius' or 'fahrenheit'\"\"\"
    # Call weather API here
    return f"Weather in {city}: 32 degrees {units}"

# LangChain reads the function signature automatically:
print(get_weather.name)          # "get_weather"
print(get_weather.description)   # the docstring above
print(get_weather.args_schema)   # JSON schema of the parameters""")
    story += note("The docstring IS the tool description the LLM sees. Write clear, specific descriptions "
                  "— the LLM uses them to decide WHEN to use each tool.")

    story += h2("3. Tool Closures — Passing State to Tools")
    story += p("A common problem: tools need access to shared state (a database client, an API key, "
               "an arq pool). But tool functions can only receive the arguments the LLM passes. "
               "The solution: define tools inside a factory function using <b>closures</b>.")
    story += code_block(
"""from langchain_core.tools import tool
from supabase import Client

def make_tools(supabase: Client, arq_pool) -> list:
    \"\"\"Factory function — builds tools that close over supabase and arq_pool.\"\"\"

    @tool
    async def get_ideas(status: str = "pending_approval") -> str:
        \"\"\"Browse content ideas by status.\"\"\"
        # supabase is captured from the outer scope (closure)
        resp = supabase.table("ideas").eq("approval_status", status).execute()
        return str(resp.data)

    @tool
    async def trigger_research(topic: Optional[str] = None) -> str:
        \"\"\"Trigger the research agent.\"\"\"
        # arq_pool is captured from the outer scope
        job = await arq_pool.enqueue_job("research_agent_task", topic=topic)
        return f"Enqueued: {job.job_id}"

    return [get_ideas, trigger_research]

# Usage:
tools = make_tools(supabase_client, arq_pool_instance)""")

    story += h2("4. Binding Tools to a Claude Model (LangChain)")
    story += code_block(
"""from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

llm = ChatAnthropic(model="claude-sonnet-4-6", api_key="...")

# Bind tools to the model
tools = make_tools(supabase, arq_pool)
llm_with_tools = llm.bind_tools(tools)

# Now the LLM can decide to call tools
response = await llm_with_tools.ainvoke([
    HumanMessage(content="Show me the 5 top-scoring pending ideas for LinkedIn")
])

# If the LLM called a tool:
if response.tool_calls:
    for call in response.tool_calls:
        print(f"Tool: {call['name']}, Args: {call['args']}")""")

    story += h2("5. LangGraph — State Machine for Agents")
    story += p("LangGraph structures an agent as a directed graph. Each <b>node</b> is a function "
               "that processes the current state. <b>Edges</b> connect nodes — including "
               "<b>conditional edges</b> that route to different nodes based on the state.")
    story += code_block(
"""from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
from typing import TypedDict, Annotated
import operator

# Define the state — what persists across nodes
class AgentState(TypedDict):
    messages: Annotated[list, operator.add]  # messages accumulate

# Build the graph
graph = StateGraph(AgentState)

# ── Node 1: the LLM decides what to do ──
async def call_llm(state: AgentState) -> dict:
    response = await llm_with_tools.ainvoke(state["messages"])
    return {"messages": [response]}

# ── Node 2: execute the tool the LLM chose ──
from langgraph.prebuilt import ToolNode
tool_node = ToolNode(tools)

# ── Conditional routing ──
def should_use_tool(state: AgentState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "call_tool"   # LLM wants to use a tool
    return END               # LLM gave a final answer

# Wire up the graph
graph.add_node("llm",  call_llm)
graph.add_node("tool", tool_node)
graph.set_entry_point("llm")
graph.add_conditional_edges("llm", should_use_tool, {"call_tool": "tool", END: END})
graph.add_edge("tool", "llm")   # after tool call, go back to LLM

agent = graph.compile()

# Run the agent
result = await agent.ainvoke({
    "messages": [HumanMessage(content="Show pending ideas and approve the top one")]
})""")

    story += h2("6. Memory and Conversation History")
    story += code_block(
"""# In-memory checkpointer (lost on restart)
from langgraph.checkpoint.memory import MemorySaver
checkpointer = MemorySaver()
agent = graph.compile(checkpointer=checkpointer)

# Run with a thread_id — state is saved per thread
config = {"configurable": {"thread_id": "user_session_1"}}

await agent.ainvoke(
    {"messages": [HumanMessage("Show me pending ideas")]},
    config=config,
)
# Later in the same thread — agent remembers the conversation
await agent.ainvoke(
    {"messages": [HumanMessage("Approve the third one")]},
    config=config,
)""")

    story += h2("7. Human-in-the-Loop")
    story += p("LangGraph supports pausing the agent at a specific node to wait for human input. "
               "This is the pattern content-automation-bot uses for Gate 1 (idea approval) and "
               "Gate 2 (draft approval) — the agent presents results, a human reviews, then "
               "the agent continues.")
    story += code_block(
"""# Add an interrupt before executing high-stakes tools
graph.compile(
    checkpointer=checkpointer,
    interrupt_before=["publish_to_twitter"],   # pause before this node
)

# The agent runs until the interrupt, then you resume after human approval:
await agent.astream(messages, config)
# ... user reviews ...
await agent.astream(None, config)   # None = resume from where it stopped""")

    story += h2("8. How content-automation-bot Uses LangGraph")
    story += p("The orchestrator agent (backend/app/agents/orchestrator/agent.py) is a LangGraph "
               "graph with ~30 tools. The tools are built using the closure factory in "
               "backend/app/agents/orchestrator/tools.py. Each tool closes over the supabase "
               "client and arq pool. The frontend talks to the agent via a streaming WebSocket.")

    story += h2("9. Practice Exercises")
    for i, ex in enumerate([
        "Create a @tool called get_stock_price(ticker: str) that returns a random price.",
        "Create a second @tool called buy_stock(ticker: str, shares: int) that logs the purchase.",
        "Use make_tools() factory pattern to pass a shared 'portfolio' dict to both tools.",
        "Bind both tools to ChatAnthropic. Ask: 'What is the price of AAPL? Buy 10 shares if it's below 200.'",
        "Build a LangGraph with 2 nodes: call_llm and call_tool. Add conditional routing.",
        "Add a MemorySaver and test a 3-turn conversation where the agent remembers earlier turns.",
    ], 1):
        story += b(f"Exercise {i}: {ex}")

    build_pdf("09_LangGraph_Agent_Orchestration.pdf", story)


# ============================================================================
# PDF 10 — REST APIs & Webhooks
# ============================================================================
def pdf_10_rest_apis():
    story = cover_page("REST APIs & Webhooks",
                        "Consuming third-party APIs, OAuth, and outbound webhooks", 10)

    story += h2("1. What is a REST API?")
    story += p("REST (Representational State Transfer) is a convention for designing APIs. "
               "Resources are accessed via URLs. Operations are expressed with HTTP methods: "
               "GET (read), POST (create), PUT/PATCH (update), DELETE (remove). "
               "Data is exchanged as JSON.")
    story += code_block(
"""# REST API pattern examples:
GET  /users          → list all users
GET  /users/42       → get user with id=42
POST /users          → create a new user  (body: {"name": "Alice"})
PUT  /users/42       → fully replace user 42
PATCH /users/42      → partially update user 42  (body: {"name": "Alice Smith"})
DELETE /users/42     → delete user 42""")

    story += h2("2. Making HTTP Requests with httpx")
    story += p("httpx is the modern Python HTTP client with both sync and async support. "
               "Use it to call external APIs from your backend.")
    story += code_block(
"""pip install httpx

import httpx

# Synchronous
resp = httpx.get("https://api.example.com/users/42")
print(resp.status_code)    # 200
print(resp.json())         # {"id": 42, "name": "Alice"}

# With headers (auth token)
resp = httpx.get(
    "https://api.example.com/protected",
    headers={"Authorization": "Bearer YOUR_TOKEN"}
)

# POST with JSON body
resp = httpx.post(
    "https://api.example.com/users",
    json={"name": "Bob", "email": "bob@example.com"},
    headers={"Authorization": "Bearer YOUR_TOKEN"},
)
print(resp.json())""")

    story += h2("3. Async HTTP Requests")
    story += code_block(
"""import httpx
import asyncio

async def fetch_user(user_id: int) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.example.com/users/{user_id}",
            headers={"Authorization": "Bearer TOKEN"},
            timeout=10.0,   # 10 second timeout
        )
        resp.raise_for_status()   # raises HTTPStatusError for 4xx/5xx
        return resp.json()

async def main():
    # Fetch 10 users concurrently
    results = await asyncio.gather(*[fetch_user(i) for i in range(1, 11)])
    print(results)

asyncio.run(main())""")

    story += h2("4. API Authentication Patterns")
    story += p("<b>API Key</b>: simplest — pass a secret key in a header. Used by most simple APIs.")
    story += code_block(
"""# API key in header
headers = {"X-API-Key": "your-api-key"}

# API key as Bearer token
headers = {"Authorization": "Bearer your-api-key"}

# API key as query parameter (less secure)
resp = httpx.get("https://api.example.com/data?api_key=your-key")""")

    story += p("<b>OAuth 2.0</b>: used by LinkedIn, Twitter, Google. More complex but more secure.")
    story += code_block(
"""# OAuth 2.0 flow (simplified):
# Step 1: Direct user to provider's auth URL
auth_url = "https://linkedin.com/oauth/v2/authorization?client_id=...&scope=w_member_social"

# Step 2: User logs in, provider redirects back to your app with a code
code = "abc123"   # from query string

# Step 3: Exchange code for an access token
resp = httpx.post("https://linkedin.com/oauth/v2/accessToken", data={
    "grant_type": "authorization_code",
    "code": code,
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_SECRET",
    "redirect_uri": "https://yourapp.com/callback",
})
access_token = resp.json()["access_token"]

# Step 4: Use access_token to make API calls
resp = httpx.post(
    "https://api.linkedin.com/v2/ugcPosts",
    headers={"Authorization": f"Bearer {access_token}"},
    json={...},
)""")

    story += h2("5. Twitter/X via Tweepy")
    story += code_block(
"""pip install tweepy

import tweepy

# OAuth 1.1a (for posting as a user account)
client = tweepy.Client(
    consumer_key="...",
    consumer_secret="...",
    access_token="...",
    access_token_secret="...",
)

# Post a tweet
response = client.create_tweet(text="This is an automated tweet! #fintech")
tweet_id = response.data["id"]
print(f"Posted tweet: {tweet_id}")

# Get tweet metrics
tweet = client.get_tweet(
    tweet_id,
    tweet_fields=["public_metrics"]
)
metrics = tweet.data.public_metrics
print(f"Likes: {metrics['like_count']}, Retweets: {metrics['retweet_count']}")""")

    story += h2("6. Exponential Backoff — Retry on Failure")
    story += code_block(
"""import asyncio
import httpx

async def post_with_retry(url: str, json_data: dict, max_retries: int = 3) -> dict:
    delay = 1.0  # start with 1 second delay

    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=json_data)
                resp.raise_for_status()
                return resp.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:   # rate limited
                print(f"Rate limited. Waiting {delay}s (attempt {attempt+1})")
                await asyncio.sleep(delay)
                delay *= 2   # exponential: 1s, 2s, 4s, 8s...
            elif attempt == max_retries:
                raise
            else:
                await asyncio.sleep(delay)
                delay *= 2""")

    story += h2("7. Webhooks — Receiving Events from External Services")
    story += p("A <b>webhook</b> is an HTTP endpoint YOU expose that external services call when "
               "something happens. Instead of polling 'did anything change?', the service pushes "
               "data to you the moment it does.")
    story += code_block(
"""from fastapi import FastAPI, Request, HTTPException
import hmac, hashlib

app = FastAPI()

WEBHOOK_SECRET = "your-secret"

@app.post("/webhook/github")
async def github_webhook(request: Request):
    # Verify the signature to prevent fake requests
    signature = request.headers.get("X-Hub-Signature-256", "")
    body = await request.body()
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    event = request.headers.get("X-GitHub-Event")
    print(f"Got {event} event: {payload.get('action')}")
    return {"status": "received"}""")

    story += h2("8. Outbound Webhooks — Sending to Slack")
    story += code_block(
"""import httpx

def send_slack_alert(webhook_url: str, message: str) -> None:
    \"\"\"Send a message to a Slack channel via Incoming Webhook.\"\"\"
    try:
        resp = httpx.post(
            webhook_url,
            json={"text": message},
            timeout=5.0,
        )
        resp.raise_for_status()
    except Exception as exc:
        print(f"Slack alert failed: {exc}")   # non-fatal

# Usage:
send_slack_alert(
    "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK",
    ":rotating_light: Research agent cost alert: $2.50 this run!"
)""")
    story += note("content-automation-bot sends Slack alerts for cost overruns and site failure events. "
                  "See backend/app/utils/slack.py.")

    story += h2("9. Practice Exercises")
    for i, ex in enumerate([
        "Use httpx to fetch https://jsonplaceholder.typicode.com/posts and print the first 3 titles.",
        "Make the same call async using AsyncClient and asyncio.gather for 5 concurrent requests.",
        "Add a 5-second timeout and handle the TimeoutError gracefully.",
        "Implement post_with_retry with 3 retries and exponential backoff.",
        "Create a FastAPI /webhook endpoint that prints any POST body it receives.",
        "Set up a Slack Incoming Webhook (free from slack.com/apps) and send a test message.",
    ], 1):
        story += b(f"Exercise {i}: {ex}")

    build_pdf("10_REST_APIs_Webhooks.pdf", story)


# ============================================================================
# PDF 11 — System Design (Multi-Agent Pipelines)
# ============================================================================
def pdf_11_system_design():
    story = cover_page("System Design — Multi-Agent Pipelines",
                        "Designing reliable, observable, cost-tracked autonomous systems", 11)

    story += h2("1. What is System Design?")
    story += p("System design is the process of defining the architecture, components, and data flows "
               "of a software system. It answers: how do the pieces fit together? What happens when "
               "something fails? How does the system scale? For content-automation-bot, the key question "
               "was: how do you automate a content pipeline that runs daily, involves LLMs (which are "
               "slow and expensive), and requires human approval at key steps?")

    story += h2("2. Event-Driven Architecture")
    story += p("In an event-driven system, components communicate by publishing and reacting to events, "
               "not by directly calling each other. In content-automation-bot:")
    story += b("Research agent completes → publishes an event → Scoring agent starts automatically")
    story += b("Draft approved → event → Publishing agent picks it up")
    story += b("Post published → event → Analytics agent scheduled for 24h/72h/7d later")
    story += p("This decoupling means each agent can fail, retry, or scale independently. "
               "arq + Redis is the event bus here — 'enqueue_job' IS publishing an event.")

    story += h2("3. Pipeline Architecture — The 6 Agents")
    story += code_block(
"""DAILY PIPELINE:
  [Cron 6 AM IST]
      → Research Agent
          scrapes 7 news sites
          scores headlines with Claude Haiku
          extracts articles with Playwright
          summarises with Claude Sonnet
          writes to raw_content
      → [auto-chains] → Scoring Agent
          reads unprocessed raw_content
          generates content ideas per platform
          checks for recent coverage overlap (vector search)
          writes pending ideas
      → [Gate 1: Human approves ideas]
      → [Orchestrator trigger] → Creation Agent
          reads approved ideas
          retrieves brand voice examples (vector search)
          retrieves KB context (vector search)
          generates drafts with Claude Sonnet
      → [Gate 2: Human approves drafts]

EVERY 15 MINUTES:
  [Cron] → Publishing Agent
      posts approved, due drafts to LinkedIn/Twitter/WordPress/Email
      schedules analytics jobs at 24h, 72h, 7d

AT 24h, 72h, 7d:
  → Analytics Agent
      fetches metrics from platform APIs
      at 7d: updates style_guide and topic_performance_model""")

    story += h2("4. Human-in-the-Loop Design")
    story += p("Fully automated AI content is risky — especially for regulated financial content. "
               "content-automation-bot has <b>two mandatory human approval gates</b>:")
    story += b("Gate 1 (Ideas): Human reviews the idea angle, platform, and source. Can edit angle before approving.")
    story += b("Gate 2 (Drafts): Human reviews full content. Finance-flagged items (company names, investment advice) CANNOT be auto-approved.")
    story += p("This pattern is called Human-in-the-Loop (HITL). It balances automation speed "
               "with human oversight for quality and legal compliance.")

    story += h2("5. Circuit Breakers — Auto-Pause on Repeated Failures")
    story += code_block(
"""# If a news site fails 5 consecutive times, auto-pause it:
def record_site_failure(supabase, site_id, error_msg, threshold=5):
    # Increment consecutive_failures
    supabase.table("curated_sites").rpc("increment_failures", {"site_id": str(site_id)}).execute()

    # Check if threshold exceeded
    resp = supabase.table("curated_sites").select("consecutive_failures").eq("id", str(site_id)).execute()
    failures = resp.data[0]["consecutive_failures"]

    if failures >= threshold:
        # Soft-pause the site
        supabase.table("curated_sites").update({"active": False}).eq("id", str(site_id)).execute()
        # Alert the team
        send_slack_alert(slack_url, f"Site {site_id} auto-paused after {failures} failures")""")
    story += note("content-automation-bot tracks consecutive_failures per site. After 5 failures it "
                  "sets active=false and sends a Slack alert. The human can re-enable it via the admin panel.")

    story += h2("6. Observability — Logging and Run Logs")
    story += p("You can't fix what you can't see. Every agent run writes a structured log to "
               "the <code>run_logs</code> table:")
    story += b("agent_name — which agent ran")
    story += b("trigger_type — cron, event, manual, or orchestrator")
    story += b("processed_count, success_count, failure_count — what happened")
    story += b("duration_seconds — how long it took")
    story += b("reasoning_trace — why the agent made each decision")
    story += b("errors — serialised exception details for debugging")
    story += b("token_cost — input/output tokens and estimated USD per model")

    story += h2("7. Cost Control")
    story += code_block(
"""# Every agent accumulates token costs and writes to cost_log table:
# cost_log: agent_name, date, token_count, estimated_cost_usd

# Upsert: if the agent already ran today, add to the existing row
def upsert_cost_log(supabase, agent_name: str, total_usd: float, token_count: int):
    today = date.today().isoformat()
    supabase.table("cost_log").upsert({
        "agent_name":         agent_name,
        "date":               today,
        "token_count":        token_count,
        "estimated_cost_usd": total_usd,
    }, on_conflict="agent_name,date").execute()

# Alert if a single run costs more than the threshold
if total_usd >= settings.daily_cost_alert_usd:
    send_slack_alert(webhook, f"Cost alert: ${total_usd:.4f}")""")

    story += h2("8. Graceful Degradation")
    story += p("When an external dependency fails, degrade gracefully rather than crashing.")
    story += b("Embedding API fails → fall back to local fastembed model")
    story += b("arq Redis unavailable → API returns 503 but does not crash")
    story += b("Pre-scoring (Claude) fails entirely → proceed with all articles (no score gate)")
    story += b("Single article fetch fails → log and skip, don't abort the whole site")

    story += h2("9. Idempotency — Running the Same Thing Twice")
    story += p("Idempotent operations can be run multiple times with the same result. Critical for "
               "job queues where failures may cause retries.")
    story += code_block(
"""# Idempotent insert: use ON CONFLICT DO NOTHING or DO UPDATE
supabase.table("raw_content").upsert({
    "normalized_url": normalize_url(url),
    "title":          title,
    ...
}, on_conflict="normalized_url").execute()
# Second run with same URL → updates the row, doesn't create a duplicate""")

    story += h2("10. Deployment Considerations")
    story += b("Run FastAPI and arq worker as separate processes (one process each).")
    story += b("Use a process manager (systemd, Docker, or Railway) to restart crashed processes.")
    story += b("Redis should be managed (Upstash free tier) — not self-managed for simplicity.")
    story += b("Store all secrets in environment variables, never in code or git.")
    story += b("Use Docker to containerise the app for consistent deployment.")

    story += h2("11. Practice Exercise — Design Your Own Pipeline")
    story += p("Design a system that:")
    story += b("Monitors 5 job boards for Python developer job postings every 3 hours")
    story += b("Scores jobs on relevance (salary, remote, Python focus)")
    story += b("Sends a daily digest email with the top 10 jobs")
    story += p("Draw the pipeline, identify the agents, define the database tables, "
               "choose the trigger mechanism, add a human-in-the-loop step, and plan for failures.")

    build_pdf("11_System_Design_Multi_Agent_Pipelines.pdf", story)


# ============================================================================
# PDF 12 — Python OOP & Design Patterns
# ============================================================================
def pdf_12_oop_patterns():
    story = cover_page("Python OOP & Design Patterns",
                        "Abstract classes, Factory, Strategy, Singleton, and closures", 12)

    story += h2("1. OOP Refresher — Classes and Inheritance")
    story += code_block(
"""class Animal:
    def __init__(self, name: str):
        self.name = name   # instance attribute

    def speak(self) -> str:
        raise NotImplementedError   # subclass must implement

class Dog(Animal):
    def speak(self) -> str:
        return f"{self.name} says: Woof!"

class Cat(Animal):
    def speak(self) -> str:
        return f"{self.name} says: Meow!"

dog = Dog("Rex")
print(dog.speak())   # "Rex says: Woof!"

# Polymorphism: same method, different behaviour
animals = [Dog("Rex"), Cat("Whiskers"), Dog("Buddy")]
for animal in animals:
    print(animal.speak())   # each calls its own speak()""")

    story += h2("2. Abstract Base Classes (ABC)")
    story += p("Python's <code>ABC</code> module lets you define <b>interfaces</b>: classes that "
               "specify what methods subclasses MUST implement, but don't implement them themselves. "
               "If a subclass doesn't implement an abstract method, Python raises a TypeError "
               "when you try to instantiate it.")
    story += code_block(
"""from abc import ABC, abstractmethod

class EmbedClient(ABC):
    \"\"\"Every embedding provider must implement these methods.\"\"\"

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        \"\"\"Embed a batch of texts. Never raises — returns empty lists on failure.\"\"\"
        ...

    def embed_one(self, text: str) -> list[float]:
        \"\"\"Convenience wrapper — implemented once, works for all subclasses.\"\"\"
        results = self.embed([text])
        return results[0] if results else []

# Subclasses must implement embed():
class GeminiEmbedder(EmbedClient):
    def embed(self, texts: list[str]) -> list[list[float]]:
        # ... call Google Gemini API ...

class LocalEmbedder(EmbedClient):
    def embed(self, texts: list[str]) -> list[list[float]]:
        # ... run local fastembed model ...

# This raises TypeError — abstract method not implemented:
class BrokenEmbedder(EmbedClient):
    pass

e = BrokenEmbedder()   # TypeError!""")
    story += note("content-automation-bot's EmbedClient (backend/app/agents/embedding/client.py:31) is "
                  "exactly this pattern — GeminiEmbedder, LocalEmbedder, FallbackEmbedder, "
                  "and NoOpEmbedder all implement the EmbedClient interface.")

    story += h2("3. Factory Pattern — Choose Which Implementation at Runtime")
    story += p("A factory is a function that decides which concrete class to create based on "
               "configuration or environment. The caller doesn't need to know about the concrete "
               "classes — it just asks the factory for an object that satisfies the interface.")
    story += code_block(
"""from abc import ABC, abstractmethod

class EmbedClient(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...

class GeminiEmbedder(EmbedClient): ...
class LocalEmbedder(EmbedClient): ...
class NoOpEmbedder(EmbedClient): ...

# ── FACTORY FUNCTION ──
def make_embed_client(google_api_key: str | None, local_model: str) -> EmbedClient:
    \"\"\"Returns the best available embedder based on configuration.\"\"\"
    local = None
    try:
        local = LocalEmbedder(local_model)
    except ImportError:
        pass

    if google_api_key:
        gemini = GeminiEmbedder(google_api_key)
        if local:
            return FallbackEmbedder(primary=gemini, fallback=local)  # see Strategy
        return gemini

    return local if local else NoOpEmbedder()

# Caller doesn't know OR care which class it gets:
client = make_embed_client(google_api_key="...", local_model="bge-base")
vectors = client.embed(["Hello"])   # works regardless of which backend""")

    story += h2("4. Strategy Pattern — Swap Algorithms at Runtime")
    story += p("The Strategy pattern defines a family of algorithms, encapsulates each one, "
               "and makes them interchangeable. The caller selects the strategy without "
               "knowing the implementation details.")
    story += code_block(
"""class FallbackEmbedder(EmbedClient):
    \"\"\"Strategy: try primary first, fall back to secondary on failure.\"\"\"

    def __init__(self, primary: EmbedClient, fallback: EmbedClient) -> None:
        self._primary  = primary
        self._fallback = fallback

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            results = self._primary.embed(texts)
            # If ANY vector is empty, treat as full failure
            if any(not v for v in results):
                raise ValueError("Primary returned empty vectors")
            return results
        except Exception:
            return self._fallback.embed(texts)   # fall back to local

# Usage:
gemini = GeminiEmbedder(api_key="...")
local  = LocalEmbedder("bge-base")

# Strategy 1: Gemini only
fast = FallbackEmbedder(primary=gemini, fallback=NoOpEmbedder())

# Strategy 2: Gemini with local fallback (resilient)
resilient = FallbackEmbedder(primary=gemini, fallback=local)""")

    story += h2("5. Singleton Pattern — One Instance for the Whole Process")
    story += p("A singleton ensures a class has only one instance. In content-automation-bot, "
               "the local embedding model is expensive to load (~430 MB download + model init). "
               "The module-level cache is a simple singleton.")
    story += code_block(
"""# Module-level cache (simplest Python singleton)
_local_model_cache: dict[str, object] = {}

class LocalEmbedder:
    def __init__(self, model_name: str):
        self._model = self._load(model_name)

    @staticmethod
    def _load(model_name: str):
        if model_name not in _local_model_cache:
            from fastembed import TextEmbedding
            _local_model_cache[model_name] = TextEmbedding(model_name)
        return _local_model_cache[model_name]   # same object every time

# First call: loads the model (slow, ~5 seconds)
e1 = LocalEmbedder("bge-base")
# Second call in same process: reuses cached model (instant)
e2 = LocalEmbedder("bge-base")
assert e1._model is e2._model   # True — same object""")

    story += h2("6. Closures — Functions That Capture Variables")
    story += p("A closure is a function that remembers the variables from the scope where it "
               "was defined — even after that scope has exited. This is how make_tools() works: "
               "each @tool function captures supabase and arq_pool from the outer scope.")
    story += code_block(
"""def make_multiplier(factor: int):
    \"\"\"Returns a function that multiplies its argument by factor.\"\"\"
    def multiply(x: int) -> int:
        return x * factor   # 'factor' is captured from outer scope

    return multiply

double = make_multiplier(2)
triple = make_multiplier(3)

print(double(5))   # 10
print(triple(5))   # 15
# 'factor' still accessible even though make_multiplier() finished""")
    story += code_block(
"""# Real usage in content-automation-bot:
def make_tools(supabase: Client, arq_pool) -> list:

    @tool
    async def get_ideas(status: str = "pending_approval") -> str:
        # 'supabase' is captured from make_tools() scope — this is a closure!
        resp = supabase.table("ideas").eq("approval_status", status).execute()
        return str(resp.data)

    return [get_ideas]

# Call make_tools once at startup
tools = make_tools(db_client, pool)
# get_ideas now permanently has access to db_client and pool""")

    story += h2("7. dataclasses — Lightweight Data Containers")
    story += code_block(
"""from dataclasses import dataclass, field
from typing import Optional

@dataclass
class FetchResult:
    url:              str
    title:            str
    full_text:        str
    word_count:       int       = 0
    paywall_detected: bool      = False
    publication_date: Optional[str] = None

# Equivalent to a class with __init__, __repr__, and __eq__
result = FetchResult(url="https://...", title="RBI Rate Hike", full_text="...")
print(result)   # FetchResult(url=..., title=..., ...)

# When to use dataclass vs Pydantic:
# - dataclass: simple data containers, no serialisation needed, pure Python
# - Pydantic:  API responses, DB models, anywhere you need validation + JSON""")

    story += h2("8. Putting It All Together — The Embedding System")
    story += p("content-automation-bot's embedding system uses ALL of these patterns:")
    story += b("ABC (EmbedClient) — defines the interface every embedder must satisfy")
    story += b("Factory (make_embed_client) — chooses the right implementation at runtime")
    story += b("Strategy (FallbackEmbedder) — primary + fallback algorithm selection")
    story += b("Singleton (_local_model_cache) — load the model once, reuse everywhere")
    story += p("Each pattern solves a specific problem. Together they produce a system that "
               "is flexible (swap backends), resilient (fallback on failure), and efficient "
               "(no redundant model loading).")

    story += h2("9. Practice Exercises")
    for i, ex in enumerate([
        "Define an abstract Notifier class with an abstract method send(message: str) -> bool.",
        "Implement SlackNotifier and EmailNotifier as concrete classes.",
        "Write a make_notifier(channel: str) factory that returns the right notifier.",
        "Implement FallbackNotifier(primary, fallback) using the Strategy pattern.",
        "Add a module-level cache so NotifierFactory only creates one instance per channel.",
        "Write a make_tools(notifier) closure factory where each tool closes over the notifier.",
        "Chain them: Factory → Strategy → Singleton → Closure. Show the full working example.",
    ], 1):
        story += b(f"Exercise {i}: {ex}")

    build_pdf("12_Python_OOP_Design_Patterns.pdf", story)


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    print(f"Generating PDFs in: {OUT_DIR}")
    pdf_01_fastapi()
    pdf_02_asyncio()
    pdf_03_job_queues()
    pdf_04_postgres_supabase()
    pdf_05_embeddings_rag()
    pdf_06_playwright()
    pdf_07_llms_anthropic()
    pdf_08_pydantic()
    pdf_09_langgraph()
    pdf_10_rest_apis()
    pdf_11_system_design()
    pdf_12_oop_patterns()
    print(f"\nDone! {len(list(OUT_DIR.glob('*.pdf')))} PDFs written to {OUT_DIR.resolve()}")
