# Agent Instructions

You're working inside the **WAT framework** (Workflows, Agents, Tools). This architecture separates concerns so that probabilistic AI handles reasoning while deterministic code handles execution. That separation is what makes this system reliable.

## The WAT Architecture

**Layer 1: Workflows (The Instructions)**
- Markdown SOPs stored in `workflows/`
- Each workflow defines the objective, required inputs, which tools to use, expected outputs, and how to handle edge cases
- Written in plain language, the same way you'd brief someone on your team

**Layer 2: Agents (The Decision-Maker)**
- This is your role. You're responsible for intelligent coordination.
- Read the relevant workflow, run tools in the correct sequence, handle failures gracefully, and ask clarifying questions when needed
- You connect intent to execution without trying to do everything yourself
- Example: If you need to pull data from a website, don't attempt it directly. Read `workflows/scrape_website.md`, figure out the required inputs, then execute `tools/scrape_single_site.py`

**Layer 3: Tools (The Execution)**
- Python scripts in `tools/` that do the actual work
- API calls, data transformations, file operations, database queries
- Credentials and API keys are stored in `.env`
- These scripts are consistent, testable, and fast

**Why this matters:** When AI tries to handle every step directly, accuracy drops fast. If each step is 90% accurate, you're down to 59% success after just five steps. By offloading execution to deterministic scripts, you stay focused on orchestration and decision-making where you excel.

## How to Operate

**1. Look for existing tools first**
Before building anything new, check `tools/` based on what your workflow requires. Only create new scripts when nothing exists for that task.

**2. Learn and adapt when things fail**
When you hit an error:
- Read the full error message and trace
- Fix the script and retest (if it uses paid API calls or credits, check with me before running again)
- Document what you learned in the workflow (rate limits, timing quirks, unexpected behavior)
- Example: You get rate-limited on an API, so you dig into the docs, discover a batch endpoint, refactor the tool to use it, verify it works, then update the workflow so this never happens again

**3. Keep workflows current**
Workflows should evolve as you learn. When you find better methods, discover constraints, or encounter recurring issues, update the workflow. That said, don't create or overwrite workflows without asking unless I explicitly tell you to. These are your instructions and need to be preserved and refined, not tossed after one use.

## The Self-Improvement Loop

Every failure is a chance to make the system stronger:
1. Identify what broke
2. Fix the tool
3. Verify the fix works
4. Update the workflow with the new approach
5. Move on with a more robust system

This loop is how the framework improves over time.

## File Structure

**What goes where:**
- **Deliverables**: Final outputs go to cloud services (Google Sheets, Slides, etc.) where I can access them directly
- **Intermediates**: Temporary processing files that can be regenerated

**Directory layout:**
.tmp/  # Temporary files (scraped data, intermediate exports). Regenerated as needed.
tools/  # Python scripts for deterministic execution
workflows/  # Markdown SOPs defining what to do and how
.env  # API keys and environment variables (NEVER store secrets anywhere else)
credentials.json, token.json  # Google OAuth (gitignored)

**Core principle:** Local files are just for processing. Anything I need to see or use lives in cloud services. Everything in `.tmp/` is disposable.

## Bottom Line

You sit between what I want (workflows) and what actually gets done (tools). Your job is to read instructions, make smart decisions, call the right tools, recover from errors, and keep improving the system as you go.

Stay pragmatic. Stay reliable. Keep learning.

---

## Menu Maker — Project Context

**Stack:** Flask + Flask-SQLAlchemy + Flask-Login + Google Gemini (`gemini-2.5-flash-lite`) + SQLite
**Port:** localhost:5001
**Design:** Dark luxury (goud #C9A84C op donker #0F0F0F), fonts: Playfair Display + Inter

### Blueprints (app.py)
| Blueprint | File | Prefix |
|-----------|------|--------|
| `auth_bp` | auth.py | /login, /logout |
| `onboarding_bp` | onboarding.py | /register, /onboarding/* |
| `segment_bp` | segment_routes.py | /segment/* |
| `menu_bp` | menu_routes.py | /menu/* |
| `trend_bp` | trend_routes.py | /trends/* |

### Database Models (models.py)
Organisatie, Gebruiker, Menu, Gerecht, MenuSegment, TrendAnalyse, TrendGeheugen, TrendConfig, MenuAnnotatie, KassaboekEntry

### Tools (tools/)
| Tool | Functie | Input → Output |
|------|---------|----------------|
| `segment_analyzer.py` | Keten-analyse via Gemini+Search | naam+locatie → segment JSON |
| `logo_extractor.py` | Logo ophalen via Clearbit/scraping | bedrijfsnaam → logo bestand |
| `menu_parser.py` | PDF/afbeelding/tekst → menu JSON | bestand/tekst → categorieën+gerechten |
| `trend_researcher.py` | Web trendresearch via Gemini+Search | segment+config → trends JSON |
| `trend_combiner.py` | Geheugen-evolutie (difflib matching) | analyse+geheugen → bijgewerkt geheugen |
| `menu_annotator.py` | Per-gerecht annotaties via Gemini | menu+geheugen+segment → annotaties lijst |

### Key Patterns
- **Lazy Gemini client:** `_get_client()` in elk tool (niet op module-level, voorkomt import errors)
- **JSON extractie:** Strip markdown code blocks, `json.loads` met fallback
- **Checkbox grids:** `.checkbox-grid` + `.checkbox-item` met `:has(input:checked)`, "Anders" tekstveld
- **Loading pages:** Auto-POST via hidden form + geanimeerde stappen (onboarding_scan, trend_scan, annotatie_scan)
- **Theme:** `static/theme.css` + `static/theme.js`, localStorage key `menu-maker-theme`
- **Fuzzy name matching:** Annotaties → Gerecht koppeling via exact lowercase + substring fallback
- **Error handlers:** Branded 404/403/500 pagina's via `@app.errorhandler`
- **Security headers:** X-Content-Type-Options, X-Frame-Options, Referrer-Policy via `@app.after_request`

### Hosting
- **Development:** `python app.py` (Flask dev server, debug=True, localhost:5001)
- **Productie:** `python run.py` (Waitress WSGI server, 4 threads)
- Flags: `--port`, `--host 0.0.0.0` (netwerk), `--debug` (dev mode)

### Bouwstatus
- Fase 1 (Fundament): COMPLEET
- Fase 2 (Onboarding + Menusegment): COMPLEET
- Fase 3 (Menu Upload): COMPLEET
- Fase 4 (Trendsysteem): COMPLEET
- Fase 5 (Annotaties): COMPLEET
- Fase 6 (Polish + Local Hosting): COMPLEET
