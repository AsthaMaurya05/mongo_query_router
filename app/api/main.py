
"""FastAPI application for the MongoDB Query Router."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from pymongo.errors import PyMongoError

from app.ai.router import QueryRouter, RouterError
from app.ai.summarizer import summarize
from app.db import client, get_db


# Keep API demos separate from the main shop database.
API_DB_NAME = os.getenv(
    "API_DB_NAME",
    "mongo_query_router_api_dev",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Check MongoDB availability when the API starts."""
    try:
        client.admin.command("ping")
    except PyMongoError as exc:
        raise RuntimeError(
            "MongoDB is unavailable. Start MongoDB and restart the API."
        ) from exc

    yield


app = FastAPI(
    title="MongoDB Query Router",
    description="Natural-language shop analytics API",
    version="1.0.0",
    lifespan=lifespan,
)

router = QueryRouter()


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


@app.get("/health")
def health():
    """Return basic API and database health."""
    try:
        client.admin.command("ping")
    except PyMongoError as exc:
        raise HTTPException(
            status_code=503,
            detail="MongoDB is unavailable.",
        ) from exc

    return {
        "status": "ok",
        "database": API_DB_NAME,
    }


@app.post("/api/query")
def query_analytics(request: QueryRequest):
    """Route, execute, and summarize an analytics question."""
    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=422,
            detail="Please enter a non-empty question.",
        )

    try:
        db = get_db(API_DB_NAME)
        result = router.execute(db, question)

        if result["pipeline"] is None:
            return {
                **result,
                "answer": result["message"],
            }

        answer = summarize(question, result["rows"])

        return {
            **result,
            "answer": answer,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except RouterError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc
    except PyMongoError as exc:
        raise HTTPException(
            status_code=503,
            detail="The database query failed. Please try again.",
        ) from exc


@app.get("/", response_class=HTMLResponse)
def home():
    """Render the natural-language analytics dashboard."""
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MongoDB Query Router</title>

  <style>
    :root {
      color-scheme: dark;
      --background: #0b1020;
      --panel: #151e32;
      --input: #0d1528;
      --border: #2b3955;
      --text: #f1f5ff;
      --muted: #9cadd0;
      --accent: #8998ff;
      --button: #202c45;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      padding: 28px;
      background: var(--background);
      color: var(--text);
      font-family: Inter, "Segoe UI", Arial, sans-serif;
      line-height: 1.65;
    }

    .container {
      max-width: 1200px;
      margin: 0 auto;
    }

    header {
      margin-bottom: 26px;
    }

    h1 {
      margin-bottom: 6px;
      font-size: clamp(28px, 4vw, 40px);
      letter-spacing: -1px;
    }

    .subtitle,
    .muted {
      color: var(--muted);
    }

    .panel {
      margin-bottom: 26px;
      padding: 28px;
      border: 1px solid var(--border);
      border-radius: 24px;
      background: var(--panel);
    }

    .section-title {
      margin-bottom: 14px;
      font-size: 21px;
      font-weight: 700;
    }

    textarea {
      display: block;
      width: 100%;
      min-height: 150px;
      resize: vertical;
      padding: 18px;
      border: 1px solid var(--border);
      border-radius: 16px;
      outline: none;
      background: var(--input);
      color: var(--text);
      font: inherit;
      font-size: 19px;
    }

    textarea:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 2px #8998ff30;
    }

    button {
      padding: 13px 18px;
      border: 1px solid var(--border);
      border-radius: 14px;
      background: var(--button);
      color: var(--text);
      font: inherit;
      cursor: pointer;
      transition: border-color 0.15s, opacity 0.15s;
    }

    button:hover {
      border-color: var(--accent);
    }

    button:disabled {
      cursor: wait;
      opacity: 0.6;
    }

    .primary {
      border-color: transparent;
      background: var(--accent);
      color: #10162d;
      font-weight: 700;
      font-size: 18px;
    }

    .actions,
    .examples,
    .metadata {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
    }

    .actions {
      margin-top: 18px;
    }

    .examples {
      margin-top: 24px;
    }

    .example.active {
      border-color: var(--accent);
    }

    #answer {
      margin: 0 0 18px;
      font-size: 21px;
      overflow-wrap: anywhere;
    }

    .metadata {
      gap: 10px;
    }

    .pill {
      display: inline-block;
      max-width: 100%;
      padding: 8px 14px;
      border-radius: 999px;
      background: #24314e;
      overflow-wrap: anywhere;
      font-size: 14px;
    }

    details {
      margin-top: 22px;
    }

    summary {
      color: var(--accent);
      font-weight: 700;
      cursor: pointer;
    }

    pre {
      max-height: 420px;
      overflow: auto;
      padding: 16px;
      border: 1px solid var(--border);
      border-radius: 12px;
      background: var(--input);
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }

    footer {
      padding: 10px 0;
      color: var(--muted);
    }

    a {
      color: var(--accent);
    }

    @media (max-width: 600px) {
      body {
        padding: 14px;
      }

      .panel {
        padding: 18px;
        border-radius: 18px;
      }

      .actions button {
        flex: 1;
      }

      #status {
        width: 100%;
      }
    }
  </style>
</head>

<body>
  <main class="container">
    <header>
      <h1>MongoDB Query Router</h1>
      <div class="subtitle">
        Ask questions about shop data in natural language.
      </div>
    </header>

    <section class="panel">
      <div class="section-title">What would you like to know?</div>

      <textarea
        id="question"
        maxlength="1000"
        placeholder="Example: Show monthly revenue from September 1 to October 1, 2026"
        aria-label="Analytics question"
      ></textarea>

      <div class="actions">
        <button class="primary" id="run" type="button">
          Run query →
        </button>
        <button id="clear" type="button">Clear</button>
        <span id="status" class="muted" role="status" aria-live="polite">
          Ready for your question.
        </span>
      </div>

      <div class="examples">
        <button class="example" type="button"
          data-question="Show the top 5 product categories by revenue from September 1 to October 1, 2026">
          Category revenue
        </button>

        <button class="example" type="button"
          data-question="Who are the top 5 customers by spending between September 1 and October 1, 2026?">
          Top customers
        </button>

        <button class="example" type="button"
          data-question="Show products with stock below 10">
          Low stock
        </button>

        <button class="example" type="button"
          data-question="Rank products by average rating with at least 2 reviews">
          Product ratings
        </button>

        <button class="example" type="button"
          data-question="Show the distribution of product prices">
          Price distribution
        </button>

        <button class="example" type="button"
          data-question="Show monthly revenue from September 1, 2026 to November 1, 2026">
          Monthly revenue
        </button>

        <button class="example" type="button"
          data-question="Give me a dashboard summary from September 1, 2026 to October 1, 2026">
          Dashboard summary
        </button>

        <button class="example" type="button"
          data-question="Summarize order statuses from September 1 to October 1, 2026">
          Order status
        </button>
      </div>
    </section>

    <section class="panel" id="result" aria-live="polite">
      <div class="section-title">Answer</div>
      <p id="answer">Your analytics answer will appear here.</p>

      <div class="metadata" id="metadata"></div>

      <details id="raw-details" hidden>
        <summary>View raw analytics results</summary>
        <pre id="raw"></pre>
      </details>
    </section>

    <footer>
      MongoDB Query Router · Development dashboard ·
      <a href="/docs" target="_blank" rel="noopener">API documentation</a>
    </footer>
  </main>

  <script>
    const questionInput = document.getElementById("question");
    const runButton = document.getElementById("run");
    const clearButton = document.getElementById("clear");
    const statusText = document.getElementById("status");
    const answerElement = document.getElementById("answer");
    const metadataElement = document.getElementById("metadata");
    const rawDetails = document.getElementById("raw-details");
    const rawElement = document.getElementById("raw");
    const exampleButtons = document.querySelectorAll(".example");

    function setStatus(message) {
      statusText.textContent = message;
    }

    function addPill(label, value) {
      const pill = document.createElement("span");
      pill.className = "pill";
      pill.textContent = label + ": " + value;
      metadataElement.appendChild(pill);
    }

    async function runQuery() {
      const question = questionInput.value.trim();

      if (!question) {
        setStatus("Please enter a question first.");
        questionInput.focus();
        return;
      }

      runButton.disabled = true;
      setStatus("Running query...");
      answerElement.textContent = "Working on your question...";
      metadataElement.replaceChildren();
      rawDetails.hidden = true;
      rawElement.textContent = "";

      try {
        const response = await fetch("/api/query", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ question })
        });

        const data = await response.json();

        if (!response.ok) {
          const message = typeof data.detail === "string"
            ? data.detail
            : "The request failed. Please try again.";
          throw new Error(message);
        }

        answerElement.textContent =
          data.answer || data.message || "Query completed.";

        if (data.pipeline) {
          addPill("Pipeline", data.pipeline);
        }

        if (data.params !== undefined) {
          addPill("Parameters", JSON.stringify(data.params));
        }

        const rows = Array.isArray(data.rows) ? data.rows : [];
        addPill("Rows returned", rows.length);

        rawElement.textContent = JSON.stringify(data, null, 2);
        rawDetails.hidden = false;
        setStatus("Query completed.");

      } catch (error) {
        answerElement.textContent = error.message;
        setStatus("Query failed.");
      } finally {
        runButton.disabled = false;
      }
    }

    runButton.addEventListener("click", runQuery);

    questionInput.addEventListener("keydown", function(event) {
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        runQuery();
      }
    });

    exampleButtons.forEach(function(button) {
      button.addEventListener("click", function() {
        questionInput.value = button.dataset.question;

        exampleButtons.forEach(function(item) {
          item.classList.remove("active");
        });

        button.classList.add("active");
        runQuery();
      });
    });

    clearButton.addEventListener("click", function() {
      questionInput.value = "";
      answerElement.textContent =
        "Your analytics answer will appear here.";
      metadataElement.replaceChildren();
      rawElement.textContent = "";
      rawDetails.hidden = true;

      exampleButtons.forEach(function(button) {
        button.classList.remove("active");
      });

      setStatus("Ready for your question.");
      questionInput.focus();
    });
  </script>
</body>
</html>
"""
