"""
Generate two deep-dive PDFs:
  - FastAPI: complete documentation from HTTP basics to production
  - LangGraph: complete documentation from agents to multi-agent systems

Run: python generate_deep_pdfs.py
Output: learning_pdfs/
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
    KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

OUT_DIR = Path(__file__).parent / "learning_pdfs"
OUT_DIR.mkdir(exist_ok=True)

W, H = A4
MARGIN = 1.8 * cm

C_DARK   = colors.HexColor("#0D1B2A")
C_BLUE   = colors.HexColor("#1565C0")
C_DBLUE  = colors.HexColor("#0A3D6B")
C_LBLUE  = colors.HexColor("#E3F2FD")
C_GREEN  = colors.HexColor("#1B5E20")
C_LGREEN = colors.HexColor("#E8F5E9")
C_ORANGE = colors.HexColor("#BF360C")
C_LORNG  = colors.HexColor("#FBE9E7")
C_PURPLE = colors.HexColor("#4A148C")
C_LPURP  = colors.HexColor("#F3E5F5")
C_LGRAY  = colors.HexColor("#F0F4F8")
C_MGRAY  = colors.HexColor("#CFD8DC")
C_GRAY   = colors.HexColor("#78909C")
C_WHITE  = colors.white
C_BLACK  = colors.HexColor("#1A1A1A")


def make_styles():
    base = getSampleStyleSheet()
    s = {}
    s["h1"] = ParagraphStyle("H1",
        fontSize=28, textColor=C_DARK, spaceAfter=4, spaceBefore=0,
        fontName="Helvetica-Bold", leading=34)
    s["h2"] = ParagraphStyle("H2",
        fontSize=17, textColor=C_DBLUE, spaceAfter=4, spaceBefore=16,
        fontName="Helvetica-Bold", leading=22,
        borderPad=0, leftIndent=0)
    s["h3"] = ParagraphStyle("H3",
        fontSize=13, textColor=C_GREEN, spaceAfter=3, spaceBefore=10,
        fontName="Helvetica-Bold", leading=17)
    s["h4"] = ParagraphStyle("H4",
        fontSize=11, textColor=C_PURPLE, spaceAfter=2, spaceBefore=8,
        fontName="Helvetica-Bold", leading=15)
    s["body"] = ParagraphStyle("Body",
        fontSize=10.5, leading=15.5, spaceAfter=5, alignment=TA_JUSTIFY,
        fontName="Helvetica")
    s["bullet"] = ParagraphStyle("Bullet",
        fontSize=10.5, leading=14.5, leftIndent=14, spaceAfter=3,
        bulletIndent=4, fontName="Helvetica")
    s["code"] = ParagraphStyle("Code",
        fontSize=8.5, leading=12, leftIndent=6, fontName="Courier",
        backColor=C_LGRAY, borderPadding=(5, 7, 5, 7), spaceAfter=6)
    s["note"] = ParagraphStyle("Note",
        fontSize=9.5, leading=13.5, leftIndent=10, rightIndent=10,
        backColor=C_LBLUE, borderPadding=(5,8,5,8), spaceAfter=6,
        fontName="Helvetica-Oblique")
    s["warn"] = ParagraphStyle("Warn",
        fontSize=9.5, leading=13.5, leftIndent=10, rightIndent=10,
        backColor=C_LORNG, borderPadding=(5,8,5,8), spaceAfter=6,
        fontName="Helvetica-Oblique")
    s["tip"] = ParagraphStyle("Tip",
        fontSize=9.5, leading=13.5, leftIndent=10, rightIndent=10,
        backColor=C_LGREEN, borderPadding=(5,8,5,8), spaceAfter=6,
        fontName="Helvetica-Oblique")
    s["subtitle"] = ParagraphStyle("Subtitle",
        fontSize=14, textColor=C_GRAY, spaceAfter=2, alignment=TA_CENTER,
        fontName="Helvetica-Oblique")
    s["center"] = ParagraphStyle("Center",
        fontSize=10.5, leading=15, alignment=TA_CENTER, fontName="Helvetica")
    s["toc"] = ParagraphStyle("TOC",
        fontSize=11, leading=18, leftIndent=8, fontName="Helvetica")
    s["toc2"] = ParagraphStyle("TOC2",
        fontSize=10, leading=16, leftIndent=24, fontName="Helvetica")
    return s


S = make_styles()


def code_block(text):
    return [Preformatted(text, S["code"]), Spacer(1, 4)]


def note(text):
    return [Paragraph(f"<b>Note:</b> {text}", S["note"]), Spacer(1, 3)]


def warn(text):
    return [Paragraph(f"<b>Important:</b> {text}", S["warn"]), Spacer(1, 3)]


def tip(text):
    return [Paragraph(f"<b>Tip:</b> {text}", S["tip"]), Spacer(1, 3)]


def hr():
    return [HRFlowable(width="100%", thickness=1, color=C_MGRAY, spaceAfter=5)]


def h2(text):
    return hr() + [Paragraph(text, S["h2"])]


def h3(text):
    return [Paragraph(text, S["h3"])]


def h4(text):
    return [Paragraph(text, S["h4"])]


def p(text):
    return [Paragraph(text, S["body"]), Spacer(1, 2)]


def b(text):
    return [Paragraph(f"• {text}", S["bullet"])]


def tbl(data, col_widths=None):
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_DBLUE),
        ("TEXTCOLOR",  (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("GRID",       (0, 0), (-1, -1), 0.4, C_GRAY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_LGRAY, C_WHITE]),
        ("PADDING",    (0, 0), (-1, -1), 5),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
    ]))
    return [t, Spacer(1, 8)]


def cover(title, subtitle, num, color=C_DBLUE):
    story = []
    story.append(Spacer(1, 2.5 * cm))
    story.append(Paragraph(f"Deep Dive — Module {num}", S["subtitle"]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(title, S["h1"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(subtitle, S["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=3, color=color, spaceBefore=10, spaceAfter=10))
    story.append(Paragraph("content-automation-bot — Backend Deep-Dive Series", S["center"]))
    story.append(Paragraph("Complete Documentation | Zero Prerequisites to Production Code", S["center"]))
    story.append(PageBreak())
    return story


def section_break(title):
    return [
        Spacer(1, 0.2 * cm),
        HRFlowable(width="100%", thickness=2, color=C_DBLUE, spaceBefore=4, spaceAfter=6),
        Paragraph(title, ParagraphStyle("SB", fontSize=13, textColor=C_DBLUE,
                                        fontName="Helvetica-Bold", spaceAfter=4)),
        HRFlowable(width="100%", thickness=2, color=C_DBLUE, spaceBefore=0, spaceAfter=8),
    ]


def build_pdf(filename, story):
    path = OUT_DIR / filename
    doc = SimpleDocTemplate(
        str(path), pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title=filename.replace(".pdf", ""),
    )
    doc.build(story)
    print(f"  OK  {path.name}  ({path.stat().st_size // 1024} KB)")


# ===========================================================================
# PDF A — FastAPI Complete Documentation
# ===========================================================================
def pdf_fastapi_deep():
    story = cover(
        "FastAPI — Complete Documentation",
        "Every feature, every pattern, from HTTP to production deployment",
        "A", color=C_DBLUE,
    )

    # ── TABLE OF CONTENTS ───────────────────────────────────────────────────
    story += section_break("Table of Contents")
    toc_items = [
        ("1", "How HTTP Works — The Foundation"),
        ("2", "FastAPI vs Flask vs Django"),
        ("3", "Installation & Project Structure"),
        ("4", "Your First App & Running the Server"),
        ("5", "Path Parameters"),
        ("6", "Query Parameters"),
        ("7", "Request Body with Pydantic"),
        ("8", "Response Models & Status Codes"),
        ("9", "Headers, Cookies & Form Data"),
        ("10", "File Uploads"),
        ("11", "Error Handling & HTTPException"),
        ("12", "Dependency Injection (Depends)"),
        ("13", "Nested Dependencies & Class-Based Dependencies"),
        ("14", "APIRouter — Splitting Your App"),
        ("15", "Middleware"),
        ("16", "CORS"),
        ("17", "Background Tasks"),
        ("18", "WebSockets"),
        ("19", "Security — API Keys, OAuth2, JWT"),
        ("20", "Lifespan — Startup & Shutdown"),
        ("21", "Custom Responses & Streaming"),
        ("22", "Database Integration (Supabase/SQLAlchemy)"),
        ("23", "Testing with TestClient"),
        ("24", "OpenAPI & Interactive Docs"),
        ("25", "Deployment (Docker + Uvicorn + Gunicorn)"),
        ("26", "content-automation-bot — Full API Walkthrough"),
    ]
    for num, title in toc_items:
        story += [Paragraph(f"{num}. {title}", S["toc"]), Spacer(1, 2)]
    story.append(PageBreak())

    # ── 1. HOW HTTP WORKS ──────────────────────────────────────────────────
    story += h2("1. How HTTP Works — The Foundation")
    story += p("HTTP (HyperText Transfer Protocol) is the language of the web. Every time your "
               "browser loads a page, your React app fetches data, or your mobile app logs in, "
               "it sends an HTTP <b>request</b> and receives an HTTP <b>response</b>.")

    story += h3("1.1 Anatomy of an HTTP Request")
    story += code_block(
"""POST /api/users HTTP/1.1
Host: api.example.com
Content-Type: application/json
Authorization: Bearer eyJhbGc...
Content-Length: 42

{"name": "Alice", "email": "alice@example.com"}

^---- Method  ^---- Path  ^---- Protocol version
              ^---- Headers (key: value pairs)

              ^---- Body (the data you're sending)""")
    story += p("The <b>method</b> tells the server what action you want:")
    story += tbl([
        ["Method", "Meaning", "Has Body?", "Example"],
        ["GET",    "Read data", "No",  "GET /users/42"],
        ["POST",   "Create new resource", "Yes", "POST /users"],
        ["PUT",    "Replace entire resource", "Yes", "PUT /users/42"],
        ["PATCH",  "Partially update resource", "Yes", "PATCH /users/42"],
        ["DELETE", "Remove resource", "Usually no", "DELETE /users/42"],
    ], col_widths=[2.5*cm, 5*cm, 3*cm, 6.5*cm])

    story += h3("1.2 Anatomy of an HTTP Response")
    story += code_block(
"""HTTP/1.1 201 Created
Content-Type: application/json
Location: /api/users/123

{"id": 123, "name": "Alice", "email": "alice@example.com"}

^---- Status code (201 = Created)
     ^---- Headers
           ^---- Body (JSON data)""")
    story += p("Common status codes:")
    story += tbl([
        ["Code", "Meaning", "When to use"],
        ["200 OK",           "Success",               "GET, PUT, PATCH succeeded"],
        ["201 Created",      "Resource created",      "POST succeeded"],
        ["204 No Content",   "Success, no body",      "DELETE succeeded"],
        ["400 Bad Request",  "Client sent bad data",  "Validation error, missing field"],
        ["401 Unauthorized", "Not authenticated",     "No/invalid token"],
        ["403 Forbidden",    "Authenticated but no permission", "Wrong role"],
        ["404 Not Found",    "Resource missing",      "ID doesn't exist"],
        ["422 Unprocessable","Validation failed",     "FastAPI default for body errors"],
        ["429 Too Many Req", "Rate limited",          "Slow down"],
        ["500 Server Error", "Your code crashed",     "Unexpected exception"],
    ], col_widths=[4.5*cm, 5*cm, 7.5*cm])

    story += h3("1.3 ASGI vs WSGI — Why FastAPI is Faster")
    story += p("Old frameworks (Django, Flask) use <b>WSGI</b> — one thread per request. "
               "FastAPI uses <b>ASGI</b> — one process can handle thousands of requests "
               "concurrently using asyncio. For I/O-bound work (database calls, external APIs), "
               "ASGI is drastically more efficient.")

    # ── 2. FASTAPI VS FLASK VS DJANGO ──────────────────────────────────────
    story += h2("2. FastAPI vs Flask vs Django")
    story += tbl([
        ["Feature", "FastAPI", "Flask", "Django"],
        ["Type", "ASGI, async-first", "WSGI, sync", "WSGI, sync (async support added)"],
        ["Auto docs", "Yes (Swagger + ReDoc)", "No", "No"],
        ["Data validation", "Built-in (Pydantic)", "Manual", "Forms only"],
        ["ORM", "None (use SQLAlchemy)", "None", "Django ORM (built-in)"],
        ["Admin panel", "No", "No", "Yes (built-in)"],
        ["Learning curve", "Low-medium", "Low", "High"],
        ["Best for", "APIs, microservices, ML", "Simple APIs, prototypes", "Full-stack web apps"],
    ], col_widths=[4*cm, 4.5*cm, 3.5*cm, 5*cm])
    story += note("For a pure REST API backend (like content-automation-bot), FastAPI is the clear winner: "
                  "fastest, auto-documentation, type safety, and async support out of the box.")

    # ── 3. INSTALLATION & PROJECT STRUCTURE ───────────────────────────────
    story += h2("3. Installation & Project Structure")
    story += code_block(
"""# Create and activate virtual environment
python -m venv .venv
.venv\\Scripts\\activate          # Windows
source .venv/bin/activate         # macOS/Linux

# Install FastAPI + Uvicorn (ASGI server)
pip install fastapi uvicorn[standard]

# For production installs, also add:
pip install pydantic[email] python-multipart httpx""")

    story += p("Recommended project layout for a medium-sized API:")
    story += code_block(
"""myapi/
  app/
    __init__.py
    main.py           # FastAPI instance, lifespan, include routers
    config.py         # settings (pydantic-settings)
    deps.py           # shared dependencies (get_db, verify_token)
    models.py         # Pydantic request/response models
    db/
      __init__.py
      client.py       # database connection
      models.py       # ORM models (if using SQLAlchemy)
    routers/
      __init__.py
      users.py        # /users/* endpoints
      items.py        # /items/* endpoints
      auth.py         # /auth/* endpoints
  tests/
    test_users.py
    test_items.py
  .env
  requirements.txt
  Dockerfile""")

    # ── 4. FIRST APP ───────────────────────────────────────────────────────
    story += h2("4. Your First App & Running the Server")
    story += code_block(
"""# app/main.py
from fastapi import FastAPI

app = FastAPI(
    title="My API",
    description="A sample FastAPI application",
    version="1.0.0",
)

@app.get("/")
def root():
    return {"message": "Hello, World!"}

@app.get("/health")
def health_check():
    return {"status": "ok"}""")
    story += code_block(
"""# Run for development (auto-reloads on file changes):
uvicorn app.main:app --reload --port 8000

# Run for production:
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# With Gunicorn (for production, multi-process):
gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8000""")
    story += p("Once running, visit:")
    story += b("http://localhost:8000 — your API")
    story += b("http://localhost:8000/docs — Swagger UI (interactive docs)")
    story += b("http://localhost:8000/redoc — ReDoc (cleaner docs)")
    story += b("http://localhost:8000/openapi.json — raw OpenAPI schema")

    # ── 5. PATH PARAMETERS ─────────────────────────────────────────────────
    story += h2("5. Path Parameters")
    story += p("Path parameters are parts of the URL path that vary per request. "
               "FastAPI reads the type annotation to validate and convert automatically.")
    story += code_block(
"""from fastapi import FastAPI
from enum import Enum

app = FastAPI()

# Basic path parameter — auto-converted to int
@app.get("/users/{user_id}")
def get_user(user_id: int):
    return {"user_id": user_id}  # user_id is already an int here
# GET /users/42    → {"user_id": 42}
# GET /users/abc   → 422 Validation Error (abc is not an int)

# String path parameter
@app.get("/files/{file_path:path}")  # :path captures slashes too
def get_file(file_path: str):
    return {"file_path": file_path}
# GET /files/images/photo.jpg → {"file_path": "images/photo.jpg"}

# Enum path parameter — constrains valid values
class Status(str, Enum):
    active   = "active"
    inactive = "inactive"
    all      = "all"

@app.get("/users/status/{status}")
def users_by_status(status: Status):
    return {"status": status.value}
# GET /users/status/active   → OK
# GET /users/status/deleted  → 422 (not in enum)

# Multiple path parameters
@app.get("/orgs/{org_id}/repos/{repo_id}")
def get_repo(org_id: int, repo_id: int):
    return {"org": org_id, "repo": repo_id}""")
    story += warn("Order matters: FastAPI matches routes top to bottom. If you have both "
                  "/users/me and /users/{user_id}, put /users/me FIRST — otherwise 'me' "
                  "gets matched as a user_id string.")

    # ── 6. QUERY PARAMETERS ────────────────────────────────────────────────
    story += h2("6. Query Parameters")
    story += p("Query parameters appear after ? in the URL. Any function parameter that is "
               "NOT a path parameter is treated as a query parameter.")
    story += code_block(
"""from fastapi import FastAPI, Query
from typing import Optional

app = FastAPI()

# Basic query parameters
@app.get("/items")
def list_items(
    skip: int = 0,          # ?skip=10
    limit: int = 20,        # ?limit=5
    q: Optional[str] = None # ?q=hello  (optional)
):
    return {"skip": skip, "limit": limit, "query": q}
# GET /items?skip=5&limit=10&q=laptop

# Query with validation using Query()
@app.get("/products")
def list_products(
    min_price: float = Query(default=0.0, ge=0.0),
    max_price: float = Query(default=10000.0, le=100000.0),
    category: str    = Query(default="all", min_length=2, max_length=50),
    tags: list[str]  = Query(default=[]),  # ?tags=a&tags=b → ["a", "b"]
):
    return {"min": min_price, "max": max_price, "category": category, "tags": tags}

# Required query parameter (no default)
@app.get("/search")
def search(q: str):   # required — 422 if missing
    return {"results": [q]}

# Deprecated parameter (shows in docs but warns users)
@app.get("/old-search")
def old_search(search: str = Query(default=None, deprecated=True)):
    return {"results": [search]}""")

    # ── 7. REQUEST BODY ────────────────────────────────────────────────────
    story += h2("7. Request Body with Pydantic")
    story += p("When you need to receive structured data (JSON), define a Pydantic model "
               "and use it as a type annotation. FastAPI automatically reads the request "
               "body, validates it, and gives you a populated model instance.")
    story += code_block(
"""from fastapi import FastAPI
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

app = FastAPI()

# ── Request model (what the client sends) ──
class UserCreate(BaseModel):
    name:     str          = Field(..., min_length=2, max_length=100)
    email:    EmailStr                      # validated email format
    age:      int          = Field(..., ge=18, le=120)
    bio:      Optional[str] = None          # optional field

# ── Response model (what we return) ──
class UserResponse(BaseModel):
    id:         int
    name:       str
    email:      str
    created_at: datetime

@app.post("/users", response_model=UserResponse, status_code=201)
def create_user(user: UserCreate):
    # user.name, user.email, user.age are all validated and typed
    new_user = save_to_db(user)     # your DB logic
    return new_user                 # serialised using UserResponse

# ── Combining path params + body ──
@app.put("/users/{user_id}")
def update_user(user_id: int, user: UserCreate):
    # user_id from path, user from body
    return {"user_id": user_id, "updated": user.name}

# ── Multiple bodies (less common) ──
class Item(BaseModel):
    name: str
    price: float

class Order(BaseModel):
    item: Item
    quantity: int

@app.post("/orders")
def create_order(order: Order):
    return {"total": order.item.price * order.quantity}""")

    story += h3("7.1 Nested Models")
    story += code_block(
"""from pydantic import BaseModel
from typing import list

class Address(BaseModel):
    street: str
    city:   str
    pin:    str

class Company(BaseModel):
    name:    str
    address: Address     # nested model
    tags:    list[str]   # list of strings

@app.post("/companies")
def create_company(company: Company):
    # company.address.city  — nested access works naturally
    return company.model_dump()

# JSON body expected:
# {
#   "name": "Growthvine Capital",
#   "address": {"street": "MG Road", "city": "Mumbai", "pin": "400001"},
#   "tags": ["finance", "amfi", "sebi"]
# }""")

    story += h3("7.2 Body with Extra Fields via Field()")
    story += code_block(
"""from pydantic import BaseModel, Field
from typing import Optional
import uuid

class IdeaCreate(BaseModel):
    # Required fields
    angle:    str   = Field(..., min_length=10, description="Content angle")
    platform: str   = Field(..., pattern="^(linkedin|twitter|blog|email)$")

    # Optional with defaults
    score:    float = Field(default=5.0, ge=0.0, le=10.0)
    tags:     list[str] = Field(default_factory=list)

    # Alias: JSON field name differs from Python attribute name
    agent_id: str   = Field(default_factory=lambda: str(uuid.uuid4()),
                             alias="agentId")

    class Config:
        populate_by_name = True   # allow both 'agent_id' and 'agentId'""")

    # ── 8. RESPONSE MODELS ─────────────────────────────────────────────────
    story += h2("8. Response Models & Status Codes")
    story += code_block(
"""from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

class UserDB(BaseModel):     # what's in the database
    id:             int
    name:           str
    email:          str
    hashed_password: str     # SECRET — should not be returned

class UserOut(BaseModel):    # what we return to the client
    id:    int
    name:  str
    email: str
    # hashed_password omitted — the response_model filters it out!

@app.get("/users/{user_id}", response_model=UserOut, status_code=200)
def get_user(user_id: int) -> UserDB:
    user = fetch_from_db(user_id)   # returns UserDB (with password)
    return user                     # FastAPI filters to UserOut fields

# ── Multiple response types ──
from typing import Union

class AdminOut(UserOut):
    role: str

@app.get("/users/{user_id}/full",
         response_model=Union[AdminOut, UserOut])
def get_user_full(user_id: int):
    ...

# ── response_model_exclude_none ──
@app.get("/items/{item_id}",
         response_model=ItemOut,
         response_model_exclude_none=True)  # omit None fields from response
def get_item(item_id: int):
    ...

# ── Return a plain dict when no model needed ──
@app.get("/ping")
def ping():
    return {"status": "ok", "timestamp": "2026-06-03"}""")

    # ── 9. HEADERS, COOKIES, FORM DATA ────────────────────────────────────
    story += h2("9. Headers, Cookies & Form Data")
    story += code_block(
"""from fastapi import FastAPI, Header, Cookie
from typing import Optional

app = FastAPI()

# ── Reading headers ──
@app.get("/items")
def get_items(
    user_agent: Optional[str] = Header(default=None),
    x_request_id: Optional[str] = Header(default=None),
    # Header names are auto-converted: x_request_id → X-Request-Id
):
    return {"user_agent": user_agent, "request_id": x_request_id}

# ── Reading cookies ──
@app.get("/me")
def get_me(session_token: Optional[str] = Cookie(default=None)):
    return {"session": session_token}

# ── Setting cookies in response ──
from fastapi.responses import JSONResponse

@app.post("/login")
def login(response: JSONResponse):
    response.set_cookie(key="session_token", value="abc123",
                        httponly=True, max_age=3600)
    return {"status": "logged in"}

# ── Form data (HTML forms) ──
# pip install python-multipart
from fastapi import Form

@app.post("/login-form")
def login_form(username: str = Form(...), password: str = Form(...)):
    return {"username": username}""")

    # ── 10. FILE UPLOADS ───────────────────────────────────────────────────
    story += h2("10. File Uploads")
    story += code_block(
"""from fastapi import FastAPI, File, UploadFile
from typing import list

app = FastAPI()

# ── Single file upload ──
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    content = await file.read()   # read file bytes
    return {
        "filename":     file.filename,
        "content_type": file.content_type,
        "size_bytes":   len(content),
    }

# ── Multiple files ──
@app.post("/upload/multiple")
async def upload_multiple(files: list[UploadFile] = File(...)):
    results = []
    for file in files:
        content = await file.read()
        results.append({"name": file.filename, "size": len(content)})
    return results

# ── Save file to disk ──
import shutil
from pathlib import Path

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@app.post("/upload/save")
async def save_file(file: UploadFile = File(...)):
    dest = UPLOAD_DIR / file.filename
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)   # stream — memory efficient
    return {"saved": str(dest)}

# ── File + form fields together ──
@app.post("/upload/with-metadata")
async def upload_with_metadata(
    file:        UploadFile = File(...),
    description: str        = Form(...),
    tags:        str        = Form(default=""),
):
    return {"file": file.filename, "desc": description}""")

    # ── 11. ERROR HANDLING ─────────────────────────────────────────────────
    story += h2("11. Error Handling & HTTPException")
    story += code_block(
"""from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import http_exception_handler

app = FastAPI()

# ── Basic HTTPException ──
@app.get("/users/{user_id}")
def get_user(user_id: int):
    user = db.get(user_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail=f"User {user_id} not found",
            headers={"X-Error": "not-found"},   # optional custom headers
        )
    return user

# ── Custom exception class ──
class InsufficientFunds(Exception):
    def __init__(self, balance: float, required: float):
        self.balance  = balance
        self.required = required

# ── Custom exception handler ──
@app.exception_handler(InsufficientFunds)
async def insufficient_funds_handler(request: Request, exc: InsufficientFunds):
    return JSONResponse(
        status_code=402,
        content={
            "error": "insufficient_funds",
            "balance":  exc.balance,
            "required": exc.required,
        }
    )

@app.post("/pay")
def pay(amount: float):
    balance = get_balance()
    if balance < amount:
        raise InsufficientFunds(balance=balance, required=amount)
    return {"paid": amount}

# ── Override FastAPI's default 422 validation error response ──
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,   # change 422 → 400 if you prefer
        content={"errors": exc.errors(), "body": str(exc.body)},
    )""")

    # ── 12. DEPENDENCY INJECTION ───────────────────────────────────────────
    story += h2("12. Dependency Injection (Depends)")
    story += p("Dependencies are reusable functions (or classes) that FastAPI calls automatically "
               "before your route handler. They are great for: authentication, database sessions, "
               "pagination parameters, and any shared logic.")
    story += code_block(
"""from fastapi import FastAPI, Depends, HTTPException, Header
from typing import Optional

app = FastAPI()

# ── Simple dependency ──
def get_pagination(skip: int = 0, limit: int = 20):
    # This function runs before the route handler
    # Its return value is injected as the 'pagination' argument
    return {"skip": skip, "limit": limit}

@app.get("/items")
def list_items(pagination: dict = Depends(get_pagination)):
    # pagination = {"skip": 0, "limit": 20} (from query params)
    return {"items": [], **pagination}

# ── Auth dependency ──
async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != "secret-123":
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key   # returned value available if the route needs it

@app.get("/protected")
def protected(api_key: str = Depends(verify_api_key)):
    return {"message": "access granted", "key": api_key}

# ── Dependency with yield — for DB sessions ──
def get_db():
    db = SessionLocal()   # open DB session
    try:
        yield db          # inject into route handler
    finally:
        db.close()        # always close, even on error

@app.get("/users/{user_id}")
def get_user(user_id: int, db = Depends(get_db)):
    return db.query(User).filter(User.id == user_id).first()""")

    story += h3("12.1 Applying Dependencies to All Routes in a Router")
    story += code_block(
"""from fastapi import APIRouter, Depends
from app.deps import verify_api_key

# Apply auth to every route in this router
router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(verify_api_key)],
)

@router.get("/stats")         # auth applied automatically
def admin_stats(): ...

@router.delete("/users/{id}") # auth applied automatically
def delete_user(id: int): ...""")

    # ── 13. NESTED & CLASS-BASED DEPENDENCIES ──────────────────────────────
    story += h2("13. Nested Dependencies & Class-Based Dependencies")
    story += code_block(
"""from fastapi import Depends

# ── Nested dependency (dep A depends on dep B) ──
def get_settings():
    return {"api_url": "https://api.example.com", "timeout": 30}

def get_http_client(settings: dict = Depends(get_settings)):
    return httpx.Client(base_url=settings["api_url"],
                        timeout=settings["timeout"])

@app.get("/data")
def get_data(client = Depends(get_http_client)):
    return client.get("/resource").json()
# FastAPI automatically resolves: get_settings → get_http_client → get_data

# ── Class-based dependency (callable class) ──
class Pagination:
    def __init__(self, page: int = 1, page_size: int = 20, max_page_size: int = 100):
        if page_size > max_page_size:
            raise HTTPException(400, detail=f"page_size cannot exceed {max_page_size}")
        self.skip  = (page - 1) * page_size
        self.limit = page_size
        self.page  = page

@app.get("/products")
def list_products(pagination: Pagination = Depends(Pagination)):
    # pagination.skip, pagination.limit, pagination.page all available
    return {"skip": pagination.skip, "limit": pagination.limit}

# ── Security dependency with scopes ──
from fastapi.security import SecurityScopes

class RoleChecker:
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, user = Depends(get_current_user)):
        if user.role not in self.allowed_roles:
            raise HTTPException(403, detail="Insufficient permissions")

require_admin = RoleChecker(allowed_roles=["admin", "superuser"])
require_user  = RoleChecker(allowed_roles=["admin", "superuser", "user"])

@app.delete("/users/{id}", dependencies=[Depends(require_admin)])
def delete_user(id: int): ...""")

    # ── 14. APIROUTER ─────────────────────────────────────────────────────
    story += h2("14. APIRouter — Splitting Your App into Modules")
    story += code_block(
"""# routers/users.py
from fastapi import APIRouter, Depends, HTTPException
from app.deps import verify_api_key, get_db
from app.models import UserCreate, UserOut

router = APIRouter(
    prefix="/users",          # all routes start with /users
    tags=["Users"],           # grouping in Swagger docs
    dependencies=[Depends(verify_api_key)],  # auth for all routes
)

@router.get("/", response_model=list[UserOut])
def list_users(db = Depends(get_db)):
    return db.query(User).all()

@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    return user

@router.post("/", response_model=UserOut, status_code=201)
def create_user(user: UserCreate, db = Depends(get_db)):
    db_user = User(**user.model_dump())
    db.add(db_user)
    db.commit()
    return db_user

@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, db = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    db.delete(user)
    db.commit()""")

    story += code_block(
"""# app/main.py — include all routers
from fastapi import FastAPI
from app.routers import users, items, auth, admin

app = FastAPI()

app.include_router(auth.router)                  # /auth/*
app.include_router(users.router)                 # /users/*
app.include_router(items.router, prefix="/api")  # /api/items/*
app.include_router(admin.router,
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(require_admin)],
)""")

    # ── 15. MIDDLEWARE ─────────────────────────────────────────────────────
    story += h2("15. Middleware")
    story += p("Middleware runs on EVERY request and response. Common uses: logging, "
               "request ID injection, rate limiting, response time headers.")
    story += code_block(
"""from fastapi import FastAPI, Request
from fastapi.middleware.base import BaseHTTPMiddleware
import time, uuid

app = FastAPI()

# ── Method 1: @app.middleware decorator ──
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id

    start = time.time()
    response = await call_next(request)   # run the actual route
    duration = time.time() - start

    response.headers["X-Request-Id"]    = request_id
    response.headers["X-Response-Time"] = f"{duration:.3f}s"
    return response

# ── Method 2: Class-based middleware ──
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 100):
        super().__init__(app)
        self.max_requests = max_requests
        self._counts: dict[str, int] = {}

    async def dispatch(self, request: Request, call_next):
        ip = request.client.host
        self._counts[ip] = self._counts.get(ip, 0) + 1
        if self._counts[ip] > self.max_requests:
            from fastapi.responses import JSONResponse
            return JSONResponse({"error": "rate limited"}, status_code=429)
        return await call_next(request)

app.add_middleware(RateLimitMiddleware, max_requests=100)""")

    # ── 16. CORS ──────────────────────────────────────────────────────────
    story += h2("16. CORS — Cross-Origin Resource Sharing")
    story += p("Browsers block cross-origin requests by default. CORS headers tell the browser "
               "which origins are allowed to talk to your API.")
    story += code_block(
"""from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# ── Development (permissive) ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,     # allow cookies to be sent
    allow_methods=["*"],        # GET, POST, PUT, DELETE, etc.
    allow_headers=["*"],        # Authorization, Content-Type, etc.
)

# ── Production (strict) ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com", "https://app.yourdomain.com"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    max_age=600,    # browser can cache preflight for 10 minutes
)""")
    story += warn("allow_origins=['*'] with allow_credentials=True is INVALID. Either specify "
                  "exact origins with credentials, or use ['*'] without credentials.")

    # ── 17. BACKGROUND TASKS ───────────────────────────────────────────────
    story += h2("17. Background Tasks")
    story += p("Background tasks run after the response is sent — useful for sending emails, "
               "triggering webhook notifications, or logging without delaying the response.")
    story += code_block(
"""from fastapi import FastAPI, BackgroundTasks

app = FastAPI()

def send_welcome_email(email: str, name: str):
    # Runs AFTER the response is returned
    import smtplib
    print(f"Sending welcome email to {email}")
    # ... actual email logic ...

def log_event(event_type: str, data: dict):
    print(f"Logging: {event_type} — {data}")

@app.post("/users", status_code=201)
async def create_user(user: UserCreate, background_tasks: BackgroundTasks):
    new_user = save_user_to_db(user)    # synchronous — save first

    # Schedule tasks to run after response is sent
    background_tasks.add_task(send_welcome_email, user.email, user.name)
    background_tasks.add_task(log_event, "user_created", {"id": new_user.id})

    return new_user   # response sent immediately""")
    story += note("BackgroundTasks is simple and synchronous. For heavy, long-running, or "
                  "reliable background work, use a proper job queue like arq + Redis "
                  "(see Module 03 in this series).")

    # ── 18. WEBSOCKETS ────────────────────────────────────────────────────
    story += h2("18. WebSockets")
    story += p("WebSockets provide full-duplex (two-way) communication over a single connection. "
               "Used for real-time features: chat, live notifications, streaming AI responses.")
    story += code_block(
"""from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

# ── Simple echo WebSocket ──
@app.websocket("/ws/echo")
async def echo(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        print("Client disconnected")

# ── WebSocket with connection manager ──
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)

    async def broadcast(self, message: str):
        for ws in self.active:
            await ws.send_text(message)

manager = ConnectionManager()

@app.websocket("/ws/chat/{room}")
async def chat(websocket: WebSocket, room: str):
    await manager.connect(websocket)
    try:
        while True:
            msg = await websocket.receive_text()
            await manager.broadcast(f"[{room}] {msg}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ── Streaming AI responses (SSE-like pattern) ──
@app.websocket("/ws/ai")
async def ai_stream(websocket: WebSocket):
    await websocket.accept()
    msg = await websocket.receive_text()
    async for chunk in stream_from_claude(msg):   # your streaming LLM call
        await websocket.send_text(chunk)
    await websocket.send_text("[DONE]")""")

    # ── 19. SECURITY ──────────────────────────────────────────────────────
    story += h2("19. Security — API Keys, OAuth2, JWT")
    story += h4("API Key Authentication")
    story += code_block(
"""from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

VALID_KEYS = {"secret-key-123", "another-valid-key"}

async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key not in VALID_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key""")

    story += h4("JWT Authentication (Full Example)")
    story += code_block(
"""pip install python-jose[cryptography] passlib[bcrypt]

from jose import jwt, JWTError
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

SECRET_KEY = "your-secret-key-here-keep-this-safe"
ALGORITHM  = "HS256"
TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise HTTPException(401, "Invalid token")
    except JWTError:
        raise HTTPException(401, "Invalid token")
    user = db.get(user_id)
    if not user:
        raise HTTPException(401, "User not found")
    return user

@app.post("/auth/token")
def login(form: OAuth2PasswordRequestForm = Depends()):
    user = db.get_by_email(form.username)
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(401, "Incorrect credentials")
    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer"}

@app.get("/me")
def get_me(current_user = Depends(get_current_user)):
    return current_user""")

    # ── 20. LIFESPAN ──────────────────────────────────────────────────────
    story += h2("20. Lifespan — Startup & Shutdown")
    story += code_block(
"""from contextlib import asynccontextmanager
from fastapi import FastAPI
from typing import AsyncIterator

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # ──────────────── STARTUP ────────────────
    print("Starting up...")

    # Initialize database connection pool
    app.state.db_pool = await asyncpg.create_pool(DATABASE_URL)

    # Connect to Redis
    app.state.redis = await aioredis.create_redis_pool(REDIS_URL)

    # Load ML model into memory (once — not per-request)
    app.state.model = load_my_ml_model()

    # Create arq job pool
    import arq
    from app.queue.worker import WorkerSettings
    app.state.arq_pool = await arq.create_pool(WorkerSettings.redis_settings)

    print("Startup complete")

    yield   # ← application is running here, serving requests

    # ──────────────── SHUTDOWN ────────────────
    print("Shutting down...")
    await app.state.arq_pool.close()
    await app.state.redis.close()
    await app.state.db_pool.close()
    print("Shutdown complete")

app = FastAPI(lifespan=lifespan)

# Accessing shared state in a dependency:
def get_db(request: Request):
    return request.app.state.db_pool

def get_arq(request: Request):
    return request.app.state.arq_pool""")

    # ── 21. CUSTOM RESPONSES & STREAMING ──────────────────────────────────
    story += h2("21. Custom Responses & Streaming")
    story += code_block(
"""from fastapi import FastAPI
from fastapi.responses import (
    JSONResponse,
    HTMLResponse,
    PlainTextResponse,
    RedirectResponse,
    FileResponse,
    StreamingResponse,
)

app = FastAPI()

# ── JSON with custom status ──
@app.get("/custom")
def custom():
    return JSONResponse(
        content={"hello": "world"},
        status_code=202,
        headers={"X-Custom-Header": "value"},
    )

# ── HTML response ──
@app.get("/page", response_class=HTMLResponse)
def page():
    return "<html><body><h1>Hello</h1></body></html>"

# ── Redirect ──
@app.get("/old-url")
def old_url():
    return RedirectResponse(url="/new-url", status_code=301)

# ── File download ──
@app.get("/download/{filename}")
def download(filename: str):
    return FileResponse(
        path=f"files/{filename}",
        media_type="application/pdf",
        filename=filename,        # Content-Disposition: attachment
    )

# ── Streaming response (large files / generated data) ──
import asyncio

async def generate_csv():
    yield "id,name,score\\n"
    for i in range(1000):
        await asyncio.sleep(0)   # yield control
        yield f"{i},Item {i},{i * 1.5}\\n"

@app.get("/export.csv")
def export():
    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=export.csv"},
    )

# ── Server-Sent Events (SSE) for AI streaming ──
async def stream_ai_response(prompt: str):
    async for chunk in call_claude_streaming(prompt):
        yield f"data: {chunk}\\n\\n"   # SSE format
    yield "data: [DONE]\\n\\n"

@app.get("/ai/stream")
def ai_stream(prompt: str):
    return StreamingResponse(
        stream_ai_response(prompt),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )""")

    # ── 22. DATABASE INTEGRATION ───────────────────────────────────────────
    story += h2("22. Database Integration")
    story += h4("With Supabase (as used in content-automation-bot)")
    story += code_block(
"""# app/db/client.py
from supabase import create_client, Client
from functools import lru_cache
from app.config import get_settings

@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_key)

# app/deps.py — dependency for routes
from fastapi import Depends
from supabase import Client

def get_db() -> Client:
    return get_supabase_client()

# In a route:
@app.get("/ideas")
def list_ideas(db: Client = Depends(get_db)):
    resp = db.table("ideas").select("*").eq("approval_status", "pending_approval").execute()
    return resp.data""")

    story += h4("With SQLAlchemy (traditional ORM approach)")
    story += code_block(
"""from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

DATABASE_URL = "postgresql://user:pass@localhost/mydb"
engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ── ORM model ──
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func

class User(Base):
    __tablename__ = "users"
    id         = Column(Integer, primary_key=True)
    name       = Column(String, nullable=False)
    email      = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

# ── Dependency ──
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ── Route ──
@app.get("/users/{id}")
def get_user(id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(404, "User not found")
    return user""")

    # ── 23. TESTING ───────────────────────────────────────────────────────
    story += h2("23. Testing with TestClient")
    story += code_block(
"""pip install httpx pytest pytest-asyncio

# tests/test_users.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# ── Basic tests ──
def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello, World!"}

def test_get_user_not_found():
    response = client.get("/users/9999")
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"

def test_create_user():
    response = client.post("/users", json={
        "name": "Alice",
        "email": "alice@example.com",
        "age": 25,
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Alice"
    assert "id" in data

def test_create_user_invalid_email():
    response = client.post("/users", json={"name": "Bob", "email": "not-an-email", "age": 30})
    assert response.status_code == 422   # validation error

# ── With auth header ──
def test_protected_endpoint():
    response = client.get("/admin", headers={"X-API-Key": "secret-123"})
    assert response.status_code == 200

    response = client.get("/admin", headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401

# ── Override dependencies in tests ──
def override_get_db():
    db = TestingSessionLocal()  # use a test DB
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Run tests: pytest tests/ -v""")

    # ── 24. OPENAPI DOCS ──────────────────────────────────────────────────
    story += h2("24. OpenAPI & Interactive Docs")
    story += code_block(
"""# Customising the docs
app = FastAPI(
    title="ContentAutomation API",
    description=(
        "## Content Automation System\\n"
        "- Gate 1: Approve/reject content ideas\\n"
        "- Gate 2: Approve/reject drafts\\n"
        "- Triggers: Run research, scoring, creation agents"
    ),
    version="0.1.0",
    docs_url="/docs",     # Swagger UI
    redoc_url="/redoc",   # ReDoc
    openapi_url="/openapi.json",
    contact={"name": "Himanshu", "email": "hi@growthvine.in"},
    license_info={"name": "Proprietary"},
)

# Add descriptions to routes
@app.get(
    "/ideas/{idea_id}",
    summary="Get a content idea",
    description="Retrieve a single content idea by its UUID.",
    response_description="The idea with all fields",
    tags=["Ideas"],
    operation_id="get_idea_by_id",
)
def get_idea(idea_id: str):
    ...

# Exclude endpoints from docs (e.g. internal routes)
@app.get("/internal/health", include_in_schema=False)
def internal_health():
    return {"ok": True}""")

    # ── 25. DEPLOYMENT ─────────────────────────────────────────────────────
    story += h2("25. Deployment — Docker + Uvicorn + Gunicorn")
    story += code_block(
"""# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# For production: Gunicorn manages Uvicorn workers
CMD ["gunicorn", "app.main:app",
     "-k", "uvicorn.workers.UvicornWorker",
     "-w", "4",           # 4 worker processes
     "-b", "0.0.0.0:8000",
     "--timeout", "120",
     "--graceful-timeout", "30"]

# Build and run:
# docker build -t myapi .
# docker run -p 8000:8000 --env-file .env myapi""")

    story += code_block(
"""# docker-compose.yml — API + worker together
version: "3.9"
services:
  api:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [redis]

  worker:
    build: .
    command: python -m arq app.queue.worker.WorkerSettings
    env_file: .env
    depends_on: [redis]

  redis:
    image: redis:alpine
    ports: ["6379:6379"]""")

    # ── 26. CONTENTAUTOMATION2 WALKTHROUGH ────────────────────────────────
    story += h2("26. content-automation-bot — Full API Walkthrough")
    story += p("Here is how all 7 routers fit together in content-automation-bot:")
    story += code_block(
"""# All routers and what they do:

GET  /ideas                         → list pending ideas
GET  /ideas/{idea_id}               → get one idea + source article
PATCH /ideas/{idea_id}/approve      → Gate 1: approve with optional angle edit
PATCH /ideas/{idea_id}/reject       → Gate 1: reject + record reason

GET  /drafts                        → list pending drafts
GET  /drafts/{draft_id}             → get full draft + finance flags
PATCH /drafts/{draft_id}/approve    → Gate 2: approve + set scheduled_at
PATCH /drafts/{draft_id}/reject     → Gate 2: reject

POST /triggers/research             → start research agent
POST /triggers/scoring              → start scoring agent
POST /triggers/creation             → start creation agent for idea_ids

GET  /tables/raw-content            → all scraped articles (paginated)
GET  /tables/published-posts        → all published posts
GET  /tables/run-logs               → all agent run logs
GET  /tables/cost-log               → daily token costs
GET  /tables/site-health            → per-site success/failure history
GET  /tables/analytics              → content performance metrics

POST /knowledge-base/upload         → upload PDF/TXT file to KB
GET  /knowledge-base/files          → list KB files

GET  /unsubscribe?token=...         → unsubscribe from email list (public)

WS   /orchestrator/chat             → streaming WebSocket chat with AI""")

    build_pdf("A_FastAPI_Complete.pdf", story)


# ===========================================================================
# PDF B — LangGraph Complete Documentation
# ===========================================================================
def pdf_langgraph_deep():
    story = cover(
        "LangGraph — Complete Documentation",
        "From LangChain basics to multi-agent systems and production deployment",
        "B", color=C_PURPLE,
    )

    # TOC
    story += section_break("Table of Contents")
    toc_items = [
        ("1",  "What is LangChain? What is LangGraph?"),
        ("2",  "Messages — The Communication Protocol"),
        ("3",  "Chat Models — Talking to LLMs"),
        ("4",  "Prompt Templates"),
        ("5",  "Tools — What Agents Can Do"),
        ("6",  "Tool Calling — How the LLM Uses Tools"),
        ("7",  "State — The Agent's Memory"),
        ("8",  "StateGraph — Building the Graph"),
        ("9",  "Nodes — Units of Work"),
        ("10", "Edges — Connecting Nodes"),
        ("11", "Conditional Edges — Branching Logic"),
        ("12", "Compiling and Running Graphs"),
        ("13", "Streaming — Watching the Agent Think"),
        ("14", "Checkpointers — Persistence and Memory"),
        ("15", "Human-in-the-Loop — Interrupts and Approvals"),
        ("16", "Prebuilt ReAct Agent — Fast Start"),
        ("17", "ToolNode — Automatic Tool Execution"),
        ("18", "Multi-Agent Systems — Supervisor Pattern"),
        ("19", "Subgraphs — Modular Architectures"),
        ("20", "Error Handling in Graphs"),
        ("21", "LangGraph + FastAPI — Full Integration"),
        ("22", "content-automation-bot — Orchestrator Walkthrough"),
        ("23", "Testing LangGraph Agents"),
        ("24", "Debugging & Tracing with LangSmith"),
    ]
    for num, title in toc_items:
        story += [Paragraph(f"{num}. {title}", S["toc"]), Spacer(1, 2)]
    story.append(PageBreak())

    # ── 1. WHAT IS LANGGRAPH ───────────────────────────────────────────────
    story += h2("1. What is LangChain? What is LangGraph?")
    story += p("<b>LangChain</b> is a Python framework for building LLM-powered applications. "
               "It provides abstractions for: chat models, prompts, tools, output parsers, "
               "document loaders, vector stores, and memory. Think of it as the standard library "
               "for LLM applications.")
    story += p("<b>LangGraph</b> is built on top of LangChain. It adds structured, stateful "
               "workflows. Instead of just calling an LLM in a linear chain, LangGraph lets you "
               "build cyclic graphs where the LLM can reason, call tools, observe results, "
               "and decide what to do next — an indefinite number of times.")
    story += p("The key insight: an <b>agent</b> is a loop. LangGraph makes that loop explicit, "
               "controllable, and observable.")

    story += code_block(
"""pip install langgraph langchain langchain-anthropic

# LangGraph core concepts:
# - StateGraph: the graph itself
# - State: a dict that persists across all nodes
# - Node: a Python function that transforms the state
# - Edge: a connection from one node to another
# - Conditional edge: routes to different nodes based on state
# - Checkpointer: saves state so the graph can be resumed""")

    # ── 2. MESSAGES ────────────────────────────────────────────────────────
    story += h2("2. Messages — The Communication Protocol")
    story += p("LangGraph agents communicate using a list of <b>messages</b>. Every message has "
               "a role (who sent it) and content (what was said).")
    story += code_block(
"""from langchain_core.messages import (
    HumanMessage,    # from the user
    AIMessage,       # from the LLM
    SystemMessage,   # system instructions
    ToolMessage,     # result from a tool call
)

# Create messages
human = HumanMessage(content="What is the repo interest rate?")
system = SystemMessage(content="You are an expert in Indian finance.")
ai = AIMessage(content="The repo rate is currently 6.50%.")

# ToolMessage — returned after executing a tool
tool_result = ToolMessage(
    content='{"rate": 6.50, "date": "2026-06-01"}',
    tool_call_id="call_abc123",   # must match the ID from AIMessage
)

# AIMessage with tool_calls — LLM is requesting a tool
ai_with_tool = AIMessage(
    content="",                   # empty when requesting a tool
    tool_calls=[{
        "id":   "call_abc123",
        "name": "get_rbi_rate",
        "args": {"date": "latest"},
    }]
)

# Full conversation flow:
messages = [
    SystemMessage(content="You help with Indian finance questions."),
    HumanMessage(content="What's the repo rate?"),
    ai_with_tool,               # LLM decides to call get_rbi_rate
    tool_result,                # tool result injected back
    AIMessage(content="The repo rate is 6.50%."),  # LLM final answer
]""")

    # ── 3. CHAT MODELS ─────────────────────────────────────────────────────
    story += h2("3. Chat Models — Talking to LLMs")
    story += code_block(
"""from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

# Create the model
llm = ChatAnthropic(
    model="claude-sonnet-4-6",
    api_key="YOUR_API_KEY",
    max_tokens=4096,
    temperature=0,              # 0 = deterministic, 1 = creative
)

# Simple call — invoke with a list of messages
response = llm.invoke([
    SystemMessage(content="Be concise."),
    HumanMessage(content="What is SEBI?"),
])
print(response.content)         # "SEBI is Securities..."
print(type(response))           # AIMessage

# Async call
response = await llm.ainvoke([HumanMessage(content="Hello")])

# Streaming
for chunk in llm.stream([HumanMessage(content="Tell me about RBI")]):
    print(chunk.content, end="", flush=True)

# Async streaming
async for chunk in llm.astream([HumanMessage(content="Tell me about RBI")]):
    print(chunk.content, end="", flush=True)

# Batch calls (multiple prompts at once)
responses = llm.batch([
    [HumanMessage(content="Question 1")],
    [HumanMessage(content="Question 2")],
])""")

    # ── 4. PROMPT TEMPLATES ────────────────────────────────────────────────
    story += h2("4. Prompt Templates")
    story += code_block(
"""from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# ── Static template ──
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert in {domain}. Be concise."),
    ("human", "Explain {concept} in simple terms."),
])

# Render with values
messages = prompt.format_messages(domain="Indian finance", concept="repo rate")

# ── With conversation history placeholder ──
prompt = ChatPromptTemplate.from_messages([
    ("system", "You help users understand {topic}."),
    MessagesPlaceholder("history"),   # inject full message history here
    ("human", "{input}"),
])

messages = prompt.format_messages(
    topic="Indian stocks",
    history=[HumanMessage("Tell me about NIFTY"), AIMessage("NIFTY is...")],
    input="What drove the rally today?",
)

# ── Chaining prompt → model ──
chain = prompt | llm
response = chain.invoke({
    "topic": "Indian stocks",
    "history": [],
    "input": "What is the NIFTY 50?",
})""")

    # ── 5. TOOLS ──────────────────────────────────────────────────────────
    story += h2("5. Tools — What Agents Can Do")
    story += p("A tool is a Python function that the LLM can decide to call. The LLM sees "
               "the tool's name and description (from the docstring) and chooses when to use it.")
    story += code_block(
"""from langchain_core.tools import tool
from typing import Optional

# ── @tool decorator — simplest way to create a tool ──
@tool
def get_stock_price(ticker: str) -> str:
    \"\"\"Get the current stock price for an Indian stock ticker.
    ticker: NSE ticker symbol (e.g. 'RELIANCE', 'INFY', 'TCS')\"\"\"
    # Your actual API call here
    return f"{ticker}: INR 2450.75"

# LangChain reads:
print(get_stock_price.name)           # "get_stock_price"
print(get_stock_price.description)    # the docstring
print(get_stock_price.args_schema)    # {"ticker": {"type": "string", ...}}

# ── Tool with multiple parameters ──
@tool
def search_ideas(
    status: str = "pending_approval",
    platform: Optional[str] = None,
    limit: int = 10,
) -> str:
    \"\"\"Browse content ideas from the database.
    status: 'pending_approval', 'approved', or 'rejected'.
    platform: filter by 'linkedin', 'twitter', 'blog', or 'email'.
    limit: max number of results (default 10).\"\"\"
    results = db.table("ideas").select("*").eq("approval_status", status).limit(limit).execute()
    return str(results.data)

# ── Async tool ──
@tool
async def trigger_agent(agent_name: str) -> str:
    \"\"\"Trigger an agent task in the background.
    agent_name: 'research', 'scoring', or 'creation'\"\"\"
    job = await arq_pool.enqueue_job(f"{agent_name}_agent_task")
    return f"Triggered {agent_name} (job_id={job.job_id})"

# ── Tool with pydantic schema (explicit, more reliable) ──
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool

class StockInput(BaseModel):
    ticker:    str   = Field(description="NSE ticker symbol")
    exchange:  str   = Field(default="NSE", description="NSE or BSE")

def get_price(ticker: str, exchange: str = "NSE") -> str:
    return f"{exchange}:{ticker} = INR 2450.75"

stock_tool = StructuredTool.from_function(
    func=get_price,
    name="get_stock_price",
    description="Get the current stock price",
    args_schema=StockInput,
)""")

    story += h3("5.1 Tool Closures — Injecting Shared State")
    story += code_block(
"""# Problem: tools need a database client, but can't accept it as an LLM arg
# Solution: define tools INSIDE a factory function (closure)

from supabase import Client
from arq import ArqRedis

def make_tools(supabase: Client, arq_pool: ArqRedis) -> list:

    @tool
    async def get_ideas(status: str = "pending_approval") -> str:
        \"\"\"Browse content ideas. status: pending_approval, approved, rejected.\"\"\"
        # 'supabase' is captured from the outer scope — this is a closure!
        resp = supabase.table("ideas").select("*").eq("approval_status", status).execute()
        ideas = resp.data or []
        lines = [f"[{i['platform']}] score={i.get('score','?')} | {i['angle']}" for i in ideas]
        return "\\n".join(lines) if lines else "No ideas found."

    @tool
    async def approve_idea(idea_id: str, edited_angle: Optional[str] = None) -> str:
        \"\"\"Approve a content idea at Gate 1.
        idea_id: UUID from get_ideas. edited_angle: optional revised angle.\"\"\"
        payload = {"approval_status": "approved"}
        if edited_angle:
            payload["edited_angle"] = edited_angle
        resp = supabase.table("ideas").update(payload).eq("id", idea_id).execute()
        return f"Approved idea {idea_id[:8]}..."

    @tool
    async def run_research(topic: Optional[str] = None) -> str:
        \"\"\"Trigger the research agent to scrape news sites.\"\"\"
        # 'arq_pool' is also captured from the outer scope
        job = await arq_pool.enqueue_job("research_agent_task", topic=topic)
        return f"Research started (job_id={job.job_id})"

    return [get_ideas, approve_idea, run_research]

# At startup:
tools = make_tools(supabase_client, arq_pool_instance)""")

    # ── 6. TOOL CALLING ────────────────────────────────────────────────────
    story += h2("6. Tool Calling — How the LLM Uses Tools")
    story += code_block(
"""from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

llm = ChatAnthropic(model="claude-sonnet-4-6")
tools = [get_stock_price, search_ideas, approve_idea]

# Bind tools to the model — the LLM now knows they exist
llm_with_tools = llm.bind_tools(tools)

# Invoke — the LLM may or may not call a tool
response = await llm_with_tools.ainvoke([
    HumanMessage("Show me pending LinkedIn ideas with score above 7")
])

# Check if the LLM wants to call a tool
if response.tool_calls:
    for call in response.tool_calls:
        print(f"Tool:  {call['name']}")
        print(f"Args:  {call['args']}")
        print(f"ID:    {call['id']}")
else:
    # LLM answered directly without needing a tool
    print(f"Answer: {response.content}")""")

    story += h3("6.1 Manually Executing Tool Calls")
    story += code_block(
"""from langchain_core.messages import ToolMessage

# Build a tool lookup dict
tool_map = {t.name: t for t in tools}

async def execute_tool_calls(ai_message: AIMessage) -> list[ToolMessage]:
    results = []
    for call in ai_message.tool_calls:
        tool = tool_map[call["name"]]
        # Invoke the tool with the args the LLM chose
        if asyncio.iscoroutinefunction(tool.func):
            result = await tool.ainvoke(call["args"])
        else:
            result = tool.invoke(call["args"])
        results.append(ToolMessage(
            content=str(result),
            tool_call_id=call["id"],   # must match the call ID
        ))
    return results

# Simple manual agent loop:
messages = [HumanMessage("Show pending ideas")]
for _ in range(10):   # max 10 iterations
    response = await llm_with_tools.ainvoke(messages)
    messages.append(response)

    if not response.tool_calls:
        print("Final answer:", response.content)
        break

    tool_results = await execute_tool_calls(response)
    messages.extend(tool_results)""")

    # ── 7. STATE ──────────────────────────────────────────────────────────
    story += h2("7. State — The Agent's Memory")
    story += p("State is the data that persists across all nodes in the graph. Every node "
               "receives the current state and returns an update to it. LangGraph merges "
               "the update into the state using the reducer functions you define.")
    story += code_block(
"""from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
import operator

# ── Basic state with message accumulation ──
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    # operator.add means: new messages are ADDED to existing ones
    # (not replaced) — this is the standard pattern

# ── Extended state with more fields ──
class OrchestratorState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    user_id:  str           # who is chatting
    session:  str           # conversation session ID
    context:  dict          # extra context passed around

# ── Custom reducer (replace instead of add) ──
def last_item_reducer(current, update):
    return update   # always replace with latest

class MyState(TypedDict):
    messages: Annotated[list, operator.add]   # accumulate
    last_result: Annotated[dict, last_item_reducer]  # overwrite

# ── Reading and updating state in a node ──
async def my_node(state: AgentState) -> dict:
    messages = state["messages"]   # read current messages
    # Return ONLY the keys you want to update
    # LangGraph merges this with the existing state
    return {"messages": [AIMessage(content="I processed your request")]}""")

    # ── 8. STATEGRAPH ─────────────────────────────────────────────────────
    story += h2("8. StateGraph — Building the Graph")
    story += code_block(
"""from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage
import operator

# Define state
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]

# Create graph
graph = StateGraph(AgentState)

# Add nodes (functions)
graph.add_node("llm_node",  call_llm_function)
graph.add_node("tool_node", execute_tools_function)

# Set entry point — where execution starts
graph.set_entry_point("llm_node")

# Add edges
graph.add_edge("tool_node", "llm_node")   # after tools, go back to LLM

# Add conditional edge — routing based on state
graph.add_conditional_edges(
    "llm_node",           # from this node
    route_function,       # call this to decide next step
    {
        "use_tool": "tool_node",   # route name → node name
        "end":      END,
    }
)

# Compile — validates the graph and returns a runnable
agent = graph.compile()""")

    # ── 9. NODES ──────────────────────────────────────────────────────────
    story += h2("9. Nodes — Units of Work")
    story += p("A node is any Python function (sync or async) that takes the state dict "
               "and returns a dict of updates. The function name becomes the node name.")
    story += code_block(
"""from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage

llm = ChatAnthropic(model="claude-sonnet-4-6")
tools = make_tools(supabase, arq_pool)
llm_with_tools = llm.bind_tools(tools)

# ── Node 1: LLM node ──
async def call_llm(state: AgentState) -> dict:
    messages = state["messages"]
    response = await llm_with_tools.ainvoke(messages)
    return {"messages": [response]}   # add AI response to history

# ── Node 2: Tool execution node ──
from langchain_core.messages import ToolMessage

async def call_tools(state: AgentState) -> dict:
    last_message = state["messages"][-1]   # the AIMessage requesting tools
    tool_map = {t.name: t for t in tools}
    results = []
    for call in last_message.tool_calls:
        tool = tool_map[call["name"]]
        try:
            result = await tool.ainvoke(call["args"])
        except Exception as e:
            result = f"Error: {e}"
        results.append(ToolMessage(
            content=str(result),
            tool_call_id=call["id"],
        ))
    return {"messages": results}

# ── Node 3: A simple transformation node ──
def format_output(state: AgentState) -> dict:
    last = state["messages"][-1]
    formatted = f"## Agent Response\\n\\n{last.content}"
    return {"messages": [AIMessage(content=formatted)]}

# Register all nodes:
graph = StateGraph(AgentState)
graph.add_node("llm",   call_llm)
graph.add_node("tools", call_tools)
graph.add_node("format", format_output)""")

    # ── 10. EDGES ─────────────────────────────────────────────────────────
    story += h2("10. Edges — Connecting Nodes")
    story += code_block(
"""from langgraph.graph import StateGraph, END

graph = StateGraph(AgentState)
graph.add_node("a", node_a)
graph.add_node("b", node_b)
graph.add_node("c", node_c)

# ── Entry point ──
graph.set_entry_point("a")      # execution starts here

# ── Simple (unconditional) edges ──
graph.add_edge("a", "b")        # after a → always go to b
graph.add_edge("b", "c")        # after b → always go to c

# ── END edge — finish execution ──
graph.add_edge("c", END)        # after c → done

# ── Multiple edges from one node ──
graph.add_edge("a", "b")        # INVALID for StateGraph — can only have
                                # one unconditional edge from a node
                                # use conditional edges for branching

# ── Parallel edges (fan-out) — available in some graph types ──
# Use conditional edges routing to different nodes instead""")

    # ── 11. CONDITIONAL EDGES ──────────────────────────────────────────────
    story += h2("11. Conditional Edges — Branching Logic")
    story += code_block(
"""from langgraph.graph import END
from langchain_core.messages import AIMessage

# ── Routing function — decides next node ──
def should_use_tools(state: AgentState) -> str:
    last_message = state["messages"][-1]

    # If last message is AIMessage with tool_calls → use tools
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "use_tools"

    # Otherwise → done
    return "end"

# ── Register conditional edge ──
graph.add_conditional_edges(
    "llm",                    # FROM this node
    should_use_tools,         # CALL this function with current state
    {
        "use_tools": "tools", # if it returns "use_tools" → go to "tools"
        "end": END,           # if it returns "end" → stop
    }
)

# ── More complex routing ──
def route(state: AgentState) -> str:
    last = state["messages"][-1]
    if not isinstance(last, AIMessage):
        return "continue"
    if last.tool_calls:
        return "tools"
    if "ERROR" in (last.content or ""):
        return "handle_error"
    if len(state["messages"]) > 20:  # too many turns
        return "force_end"
    return "end"

graph.add_conditional_edges("llm", route, {
    "tools":        "tools",
    "handle_error": "error_handler",
    "force_end":    "summarise",
    "end":          END,
    "continue":     "llm",   # loop back
})""")

    # ── 12. COMPILING AND RUNNING ──────────────────────────────────────────
    story += h2("12. Compiling and Running Graphs")
    story += code_block(
"""from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage

# Build the graph
graph = StateGraph(AgentState)
graph.add_node("llm",   call_llm)
graph.add_node("tools", call_tools)
graph.set_entry_point("llm")
graph.add_conditional_edges("llm", should_use_tools, {"use_tools": "tools", "end": END})
graph.add_edge("tools", "llm")

# Compile
agent = graph.compile()

# ── Run (synchronous) ──
result = agent.invoke({
    "messages": [HumanMessage(content="Show me pending ideas")]
})
final_message = result["messages"][-1]
print(final_message.content)

# ── Run (async) ──
result = await agent.ainvoke({
    "messages": [HumanMessage(content="Approve idea abc-123")]
})

# ── Stream output ──
async for event in agent.astream({
    "messages": [HumanMessage(content="Tell me about the latest run")]
}):
    # event is a dict: {node_name: state_update}
    for node_name, state_update in event.items():
        print(f"[{node_name}]:", state_update)

# ── Stream just the messages ──
async for event in agent.astream_events({
    "messages": [HumanMessage(content="What articles did we scrape today?")]
}, version="v2"):
    if event["event"] == "on_chat_model_stream":
        chunk = event["data"]["chunk"]
        print(chunk.content, end="", flush=True)""")

    # ── 13. STREAMING ─────────────────────────────────────────────────────
    story += h2("13. Streaming — Watching the Agent Think")
    story += code_block(
"""# There are 4 levels of streaming in LangGraph:

# 1. Stream graph updates (node-level)
async for chunk in agent.astream(initial_state):
    # chunk = {"node_name": {...state_changes...}}
    for node, changes in chunk.items():
        if "messages" in changes:
            last_msg = changes["messages"][-1]
            print(f"[{node}] {type(last_msg).__name__}: {str(last_msg.content)[:80]}")

# 2. Stream token-by-token (sub-graph level) via astream_events
async for event in agent.astream_events(initial_state, version="v2"):
    kind = event["event"]
    if kind == "on_chat_model_stream":
        token = event["data"]["chunk"].content
        if token:
            print(token, end="", flush=True)
    elif kind == "on_tool_start":
        print(f"\\nCalling tool: {event['name']} with {event['data']['input']}")
    elif kind == "on_tool_end":
        print(f"\\nTool result: {event['data']['output']}")

# 3. Stream over WebSocket (FastAPI integration)
from fastapi import WebSocket

@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    await websocket.accept()
    user_message = await websocket.receive_text()

    config = {"configurable": {"thread_id": "ws_session_1"}}
    initial = {"messages": [HumanMessage(content=user_message)]}

    async for event in agent.astream_events(initial, config=config, version="v2"):
        if event["event"] == "on_chat_model_stream":
            token = event["data"]["chunk"].content
            if token:
                await websocket.send_text(token)

    await websocket.send_text("[DONE]")""")

    # ── 14. CHECKPOINTERS ─────────────────────────────────────────────────
    story += h2("14. Checkpointers — Persistence and Memory")
    story += p("Checkpointers save the graph state after every node execution. This enables: "
               "resuming interrupted conversations, human-in-the-loop pauses, and cross-session memory.")
    story += code_block(
"""# ── In-memory checkpointer (lost on restart) ──
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
agent = graph.compile(checkpointer=checkpointer)

# Thread ID separates conversations
config = {"configurable": {"thread_id": "user_123_session_1"}}

# Turn 1
await agent.ainvoke(
    {"messages": [HumanMessage("Show me pending ideas")]},
    config=config,
)

# Turn 2 — agent REMEMBERS turn 1 because of thread_id
await agent.ainvoke(
    {"messages": [HumanMessage("Approve the top one")]},
    config=config,
)

# ── SQLite checkpointer (survives restarts) ──
from langgraph.checkpoint.sqlite import SqliteSaver

with SqliteSaver.from_conn_string("checkpoints.db") as checkpointer:
    agent = graph.compile(checkpointer=checkpointer)
    # Now state persists across server restarts

# ── PostgreSQL checkpointer (production) ──
from langgraph.checkpoint.postgres import PostgresSaver

with PostgresSaver.from_conn_string(DATABASE_URL) as checkpointer:
    checkpointer.setup()   # creates tables — run once
    agent = graph.compile(checkpointer=checkpointer)""")

    story += h3("14.1 Getting State History")
    story += code_block(
"""# Inspect what happened in a thread
config = {"configurable": {"thread_id": "user_123_session_1"}}

# Get current state
state = agent.get_state(config)
print("Current state:", state.values)
print("Next node:", state.next)

# Get full history
for state_snapshot in agent.get_state_history(config):
    print(f"Step {state_snapshot.step}: {state_snapshot.values['messages'][-1].content[:50]}")

# Replay from a specific checkpoint
to_replay = list(agent.get_state_history(config))[3]  # 4th checkpoint
result = await agent.ainvoke(None, config=to_replay.config)

# Update state manually (inject a correction)
agent.update_state(
    config,
    {"messages": [HumanMessage("Actually, approve idea xyz-456 instead")]},
)""")

    # ── 15. HUMAN-IN-THE-LOOP ─────────────────────────────────────────────
    story += h2("15. Human-in-the-Loop — Interrupts and Approvals")
    story += p("interrupt_before and interrupt_after cause the graph to PAUSE at specific nodes. "
               "Execution freezes, the state is saved, and you can inspect/modify the state "
               "before resuming. This is how you build approval gates.")
    story += code_block(
"""from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# Compile with interrupts
checkpointer = MemorySaver()
agent = graph.compile(
    checkpointer=checkpointer,
    interrupt_before=["publish_to_twitter"],  # pause BEFORE publishing
    # interrupt_after=["generate_draft"],     # pause AFTER generating
)

config = {"configurable": {"thread_id": "approval_flow_1"}}

# Step 1: Run until the interrupt
for event in agent.stream(
    {"messages": [HumanMessage("Generate and publish a tweet about SEBI")]},
    config=config,
):
    print(event)

# ← Execution PAUSED before publish_to_twitter
# ← State is saved in checkpointer

# Step 2: Inspect what's about to be published
state = agent.get_state(config)
print("Next node:", state.next)              # ("publish_to_twitter",)
draft = state.values["messages"][-1].content
print("Draft tweet:", draft)

# Step 3a: Approve — resume with no changes
if user_approves(draft):
    for event in agent.stream(None, config=config):   # None = resume
        print(event)

# Step 3b: Reject — modify state then resume
else:
    agent.update_state(
        config,
        {"messages": [HumanMessage("Change the tweet to be more formal")]},
        as_node="llm",   # inject the correction as if it came from user
    )
    for event in agent.stream(None, config=config):
        print(event)""")

    # ── 16. PREBUILT REACT AGENT ───────────────────────────────────────────
    story += h2("16. Prebuilt ReAct Agent — Fast Start")
    story += p("LangGraph includes a prebuilt ReAct (Reason + Act) agent that handles the "
               "LLM → tool → LLM loop automatically. Great for simple agents without custom routing.")
    story += code_block(
"""from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

llm = ChatAnthropic(model="claude-sonnet-4-6")
tools = [get_stock_price, search_ideas, approve_idea]

# Create a prebuilt ReAct agent
checkpointer = MemorySaver()
agent = create_react_agent(
    model=llm,
    tools=tools,
    checkpointer=checkpointer,
    state_modifier="You are a helpful AI that manages an Indian finance content pipeline.",
)

# Run it
config = {"configurable": {"thread_id": "session_1"}}
result = await agent.ainvoke(
    {"messages": [HumanMessage("Show me the top 5 pending ideas for LinkedIn")]},
    config=config,
)
print(result["messages"][-1].content)

# The prebuilt agent automatically:
# 1. Calls the LLM with tools bound
# 2. Detects tool calls in the response
# 3. Executes the tools
# 4. Feeds results back to the LLM
# 5. Repeats until the LLM gives a final answer""")

    # ── 17. TOOLNODE ──────────────────────────────────────────────────────
    story += h2("17. ToolNode — Automatic Tool Execution")
    story += code_block(
"""from langgraph.prebuilt import ToolNode

tools = [get_stock_price, search_ideas, approve_idea, run_research]

# ToolNode automatically executes whatever tools the LLM calls
tool_node = ToolNode(tools)

# Add it as a node in your graph
graph = StateGraph(AgentState)
graph.add_node("llm",   call_llm)
graph.add_node("tools", tool_node)   # ← ToolNode handles everything
graph.set_entry_point("llm")
graph.add_conditional_edges("llm", should_use_tools, {"use_tools": "tools", "end": END})
graph.add_edge("tools", "llm")

# ToolNode does the following automatically:
# 1. Reads tool_calls from the last AIMessage
# 2. Finds matching tools by name
# 3. Calls each tool with the provided args
# 4. Returns ToolMessages with the results
# 5. Handles errors gracefully (returns error message, doesn't crash)

# Custom error handling in ToolNode
from langgraph.prebuilt import ToolNode
from langgraph.utils.runnable import RunnableCallable

def handle_tool_error(state: AgentState) -> dict:
    error = state.get("error")
    last = state["messages"][-1]
    return {"messages": [ToolMessage(
        content=f"Tool failed: {error}",
        tool_call_id=last.tool_calls[0]["id"],
    )]}

tool_node = ToolNode(tools, handle_tool_errors=handle_tool_error)""")

    # ── 18. MULTI-AGENT SYSTEMS ────────────────────────────────────────────
    story += h2("18. Multi-Agent Systems — Supervisor Pattern")
    story += p("In a multi-agent system, one <b>supervisor</b> agent orchestrates multiple "
               "<b>worker</b> agents. Each worker specialises in a domain. The supervisor "
               "decides which worker to invoke based on the task.")
    story += code_block(
"""from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

llm = ChatAnthropic(model="claude-sonnet-4-6")

# ── Worker agents ──
research_agent = create_react_agent(llm, tools=[scrape_web, extract_article])
scoring_agent  = create_react_agent(llm, tools=[score_headline, generate_idea])
writing_agent  = create_react_agent(llm, tools=[write_post, check_compliance])

# ── Supervisor agent ──
from pydantic import BaseModel
from typing import Literal

class Route(BaseModel):
    next: Literal["research", "scoring", "writing", "FINISH"]

supervisor_llm = llm.with_structured_output(Route)

async def supervisor_node(state: AgentState) -> dict:
    system = \"\"\"You manage a content pipeline. Route tasks:
- research: for finding new articles
- scoring: for evaluating content ideas
- writing: for creating posts
- FINISH: when the task is complete\"\"\"
    route = await supervisor_llm.ainvoke(
        [{"role": "system", "content": system}] + state["messages"]
    )
    return {"next": route.next}

# ── Build the supervisor graph ──
from langgraph.graph import StateGraph, END
from typing import Annotated
import operator

class SupervisorState(TypedDict):
    messages: Annotated[list, operator.add]
    next:     str

graph = StateGraph(SupervisorState)
graph.add_node("supervisor", supervisor_node)
graph.add_node("research",   lambda s: research_agent.invoke(s))
graph.add_node("scoring",    lambda s: scoring_agent.invoke(s))
graph.add_node("writing",    lambda s: writing_agent.invoke(s))

graph.set_entry_point("supervisor")

# All workers route back to supervisor after completion
for worker in ["research", "scoring", "writing"]:
    graph.add_edge(worker, "supervisor")

# Supervisor routes to workers or finishes
graph.add_conditional_edges(
    "supervisor",
    lambda s: s["next"],
    {"research": "research", "scoring": "scoring",
     "writing": "writing", "FINISH": END}
)""")

    # ── 19. SUBGRAPHS ─────────────────────────────────────────────────────
    story += h2("19. Subgraphs — Modular Architectures")
    story += code_block(
"""# Subgraphs let you use one compiled graph as a node inside another

# ── Define a subgraph ──
sub_graph = StateGraph(SubState)
sub_graph.add_node("step1", do_step1)
sub_graph.add_node("step2", do_step2)
sub_graph.set_entry_point("step1")
sub_graph.add_edge("step1", "step2")
sub_graph.add_edge("step2", END)

sub_agent = sub_graph.compile()   # compile the subgraph

# ── Use it as a node in the main graph ──
main_graph = StateGraph(MainState)
main_graph.add_node("main_step",  main_node)
main_graph.add_node("subprocess", sub_agent)  # subgraph as a node!
main_graph.set_entry_point("main_step")
main_graph.add_edge("main_step", "subprocess")
main_graph.add_edge("subprocess", END)

main_agent = main_graph.compile()""")

    # ── 20. ERROR HANDLING ─────────────────────────────────────────────────
    story += h2("20. Error Handling in Graphs")
    story += code_block(
"""# ── Try/except inside nodes ──
async def safe_tool_node(state: AgentState) -> dict:
    last = state["messages"][-1]
    results = []
    for call in last.tool_calls:
        try:
            result = await tool_map[call["name"]].ainvoke(call["args"])
        except Exception as e:
            result = f"Error calling {call['name']}: {str(e)}"
        results.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
    return {"messages": results}

# ── Retry logic in a node ──
import asyncio

async def robust_llm_node(state: AgentState) -> dict:
    for attempt in range(3):
        try:
            response = await llm_with_tools.ainvoke(state["messages"])
            return {"messages": [response]}
        except Exception as e:
            if attempt == 2:
                raise
            await asyncio.sleep(2 ** attempt)  # 1s, 2s, 4s

# ── Fallback node ──
def error_handler_node(state: AgentState) -> dict:
    return {"messages": [AIMessage(
        content="I encountered an error. Please try again or rephrase your request."
    )]}

graph.add_node("error_handler", error_handler_node)

def route_on_error(state: AgentState) -> str:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and "Error" in (last.content or ""):
        return "handle_error"
    return "continue"

graph.add_conditional_edges("llm", route_on_error,
    {"handle_error": "error_handler", "continue": "tools"})""")

    # ── 21. LANGGRAPH + FASTAPI ────────────────────────────────────────────
    story += h2("21. LangGraph + FastAPI — Full Integration")
    story += code_block(
"""# app/agents/orchestrator/agent.py
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage

from app.agents.orchestrator.tools import make_tools

def create_orchestrator(supabase, arq_pool, settings) -> tuple:
    llm = ChatAnthropic(
        model=settings.claude_model_heavy,
        api_key=settings.anthropic_api_key,
    )

    tools = make_tools(
        supabase=supabase,
        arq_pool=arq_pool,
        tavily_api_key=settings.tavily_api_key,
        anthropic_api_key=settings.anthropic_api_key,
    )
    llm_with_tools = llm.bind_tools(tools)

    class State(TypedDict):
        messages: Annotated[list, operator.add]

    SYSTEM = SystemMessage(content=\"\"\"You manage the content-automation-bot pipeline.
You have tools to: browse ideas and drafts, approve/reject them, trigger agents,
search the web, generate posts, and manage the knowledge base.
Always explain what you are doing before calling a tool.\"\"\")

    async def call_llm(state: State) -> dict:
        messages = [SYSTEM] + state["messages"]
        response = await llm_with_tools.ainvoke(messages)
        return {"messages": [response]}

    def should_tool(state: State) -> str:
        last = state["messages"][-1]
        return "tools" if (hasattr(last, "tool_calls") and last.tool_calls) else "end"

    graph = StateGraph(State)
    graph.add_node("llm",   call_llm)
    graph.add_node("tools", ToolNode(tools))
    graph.set_entry_point("llm")
    graph.add_conditional_edges("llm", should_tool, {"tools": "tools", "end": END})
    graph.add_edge("tools", "llm")

    checkpointer = MemorySaver()
    agent = graph.compile(checkpointer=checkpointer)
    return agent, checkpointer""")

    story += code_block(
"""# app/api/routers/orchestrator.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from langchain_core.messages import HumanMessage
from app.api.deps import verify_api_key
from app.agents.orchestrator.agent import create_orchestrator

router = APIRouter(prefix="/orchestrator", tags=["Orchestrator"])

@router.websocket("/chat")
async def orchestrator_chat(websocket: WebSocket):
    await websocket.accept()

    supabase = get_supabase_client()
    settings = get_settings()
    agent, _ = create_orchestrator(supabase, app.state.arq_pool, settings)

    thread_id = f"ws_{id(websocket)}"
    config = {"configurable": {"thread_id": thread_id}}

    try:
        while True:
            user_message = await websocket.receive_text()
            initial = {"messages": [HumanMessage(content=user_message)]}

            # Stream tokens back to browser
            async for event in agent.astream_events(
                initial, config=config, version="v2"
            ):
                if event["event"] == "on_chat_model_stream":
                    token = event["data"]["chunk"].content
                    if token:
                        await websocket.send_text(token)
                elif event["event"] == "on_tool_start":
                    await websocket.send_text(
                        f"\\n[Using tool: {event['name']}...]\\n"
                    )

            await websocket.send_text("\\n[DONE]")

    except WebSocketDisconnect:
        pass""")

    # ── 22. CONTENTAUTOMATION2 WALKTHROUGH ────────────────────────────────
    story += h2("22. content-automation-bot — Orchestrator Walkthrough")
    story += p("The orchestrator is the brain of the system. It sits at the intersection of "
               "every pipeline stage and gives the human operator a natural language interface "
               "to control everything.")
    story += code_block(
"""# What happens when a user says:
# "Show me the top 3 pending LinkedIn ideas and approve the best one"

# 1. HumanMessage added to state
# 2. call_llm node invoked → Claude sees the message + all tools
# 3. Claude returns AIMessage with tool_call: get_ideas(status='pending_approval', platform='linkedin', limit=3)
# 4. ToolNode executes get_ideas → returns formatted list of ideas
# 5. ToolMessage with results added to state
# 6. call_llm invoked again → Claude sees ideas + user intent
# 7. Claude returns AIMessage with tool_call: approve_idea(idea_id='abc-123')
# 8. ToolNode executes approve_idea → updates DB
# 9. ToolMessage with success message added to state
# 10. call_llm invoked → Claude formulates final answer
# 11. Claude returns: "I've approved idea 'abc-123' — LinkedIn post about SEBI rate change"
# 12. No more tool_calls → graph ends
# 13. Final AIMessage streamed token by token to the frontend WebSocket

# Tools available to the orchestrator (30+ tools):
# Pipeline control: trigger_research, trigger_scoring, trigger_creation, login_to_site
# Ideas (Gate 1): get_ideas, approve_idea, reject_idea, bulk_reject_ideas, send_ideas_to_creation
# Drafts (Gate 2): get_drafts, approve_draft, reject_draft
# Brand: add_brand_memory, list_brand_memory
# Subscribers: list_subscribers, add_email_subscriber, remove_email_subscriber
# Analytics: get_analytics_summary, get_topic_performance, get_run_logs
# Browse: get_decision_summaries, get_recent_articles, get_published_posts, list_kb_files
# Sites: add_curated_site, remove_curated_site, list_curated_sites
# Web: search_web, search_and_scrape, generate_post, save_draft""")

    # ── 23. TESTING ───────────────────────────────────────────────────────
    story += h2("23. Testing LangGraph Agents")
    story += code_block(
"""import pytest
from unittest.mock import AsyncMock, MagicMock
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

# ── Test a single node ──
async def test_call_llm_node():
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = AIMessage(content="Here are the ideas...")

    state = {"messages": [HumanMessage("Show ideas")]}
    result = await call_llm(state)
    assert "messages" in result
    assert isinstance(result["messages"][-1], AIMessage)

# ── Test a tool function ──
async def test_get_ideas_tool():
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value\
        .eq.return_value.limit.return_value.execute.return_value\
        .data = [{"id": "1", "angle": "Test angle", "platform": "linkedin", "score": 7.5}]

    tools = make_tools(supabase=mock_supabase, arq_pool=None)
    get_ideas = next(t for t in tools if t.name == "get_ideas")

    result = await get_ideas.ainvoke({"status": "pending_approval"})
    assert "Test angle" in result

# ── Integration test with full agent ──
async def test_full_agent_conversation():
    from langgraph.checkpoint.memory import MemorySaver

    # Use real or mocked tools
    tools = make_tools(supabase=mock_supabase, arq_pool=mock_arq)
    agent = create_react_agent(mock_llm, tools, checkpointer=MemorySaver())

    result = await agent.ainvoke(
        {"messages": [HumanMessage("Show pending ideas")]},
        config={"configurable": {"thread_id": "test_1"}}
    )
    assert len(result["messages"]) > 1
    assert isinstance(result["messages"][-1], AIMessage)""")

    # ── 24. DEBUGGING ─────────────────────────────────────────────────────
    story += h2("24. Debugging & Tracing with LangSmith")
    story += code_block(
"""# LangSmith traces every LLM call, tool call, and state change

# 1. Sign up at smith.langchain.com (free tier available)
# 2. Set environment variables:
import os
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"]    = "your_langsmith_api_key"
os.environ["LANGCHAIN_PROJECT"]    = "content-automation"

# That's it! All LangGraph/LangChain calls are automatically traced.
# Go to smith.langchain.com to see:
# - Full conversation threads
# - Token usage per call
# - Tool call inputs and outputs
# - Latency breakdown per node
# - Errors with full stack traces

# ── Local debugging without LangSmith ──
# Print state at each step:
async for event in agent.astream(initial_state, config=config):
    print("=" * 50)
    for node, state_delta in event.items():
        print(f"NODE: {node}")
        if "messages" in state_delta:
            for msg in state_delta["messages"]:
                role = type(msg).__name__
                content = str(msg.content)[:100] if msg.content else "[tool call]"
                print(f"  {role}: {content}")

# ── Visualise the graph ──
from IPython.display import Image
img = agent.get_graph().draw_mermaid_png()
with open("agent_graph.png", "wb") as f:
    f.write(img)
# Or in Jupyter: Image(agent.get_graph().draw_mermaid_png())""")

    build_pdf("B_LangGraph_Complete.pdf", story)


# ── MAIN ──
if __name__ == "__main__":
    print(f"Generating deep-dive PDFs in: {OUT_DIR}\n")
    pdf_fastapi_deep()
    pdf_langgraph_deep()
    print(f"\nDone!")
