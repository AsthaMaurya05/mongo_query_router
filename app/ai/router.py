
"""Natural-language analytics router.

The LLM chooses a public, registered pipeline and its parameters.
It never writes or executes MongoDB queries.
"""

import json
import os
from datetime import date

from dotenv import load_dotenv
from groq import Groq

from app.pipelines.registry import (
    list_public_pipelines,
    validate_params,
    run_pipeline,
)


load_dotenv()

DEFAULT_MODEL = "llama-3.3-70b-versatile"


class RouterError(Exception):
    """Base exception for user-friendly router errors."""


class RouterConfigurationError(RouterError):
    """Raised when router configuration is missing."""


class RouterUnavailableError(RouterError):
    """Raised when the Groq API cannot be reached."""


class RouterOutputError(RouterError):
    """Raised when the model cannot produce a valid route."""


def _public_menu():
    """Return only information the model needs; omit Python builders."""
    menu = {}

    for name, config in list_public_pipelines().items():
        menu[name] = {
            "description": config["description"],
            "params": config["params"],
        }

    return menu


class QueryRouter:
    """Choose and validate an existing public analytics pipeline."""

    def __init__(self, client=None, model=None):
        self.model = model or os.getenv("GROQ_MODEL", DEFAULT_MODEL)
        self.client = client
        self.menu = _public_menu()

    def _get_client(self):
        """Create the real API client only when it is needed."""
        if self.client is not None:
            return self.client

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RouterConfigurationError(
                "GROQ_API_KEY is missing. Add it to your .env file."
            )

        self.client = Groq(api_key=api_key)
        return self.client

    def _build_messages(self, question, retry_error=None):
        today = date.today().isoformat()

        system_prompt = f"""
You are a query router for a MongoDB shop analytics application.

Today's date is {today}. Use this date to interpret relative dates,
including "today", "last month", and "this year".

Choose exactly one pipeline from the public menu below, or use null
if the request is not a supported shop analytics question.

PUBLIC PIPELINE MENU:
{json.dumps(self.menu, indent=2, default=str)}

Return only a JSON object with exactly these keys:
{{
  "pipeline": "public_pipeline_name_or_null",
  "params": {{}}
}}

Rules:
- Never write MongoDB queries, aggregation stages, Python, or code.
- Never invent a pipeline name or parameter.
- Include all required parameters.
- Do not include parameters absent from the selected pipeline's schema.
- Use ISO dates in YYYY-MM-DD format for date parameters.
- Treat date ranges as start-inclusive and end-exclusive.
- For "last month", use the first day of the previous month as start
  and the first day of the current month as end.
- Use null for pipeline and an empty object for params when the
  question is not supported by the menu.
- Do not answer the user's question; only select the pipeline.

The JSON must contain no extra keys or Markdown fences.
""".strip()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]

        if retry_error:
            messages.append({
                "role": "user",
                "content": (
                    "Your previous output was rejected. Correct it using "
                    "this validation error: " + retry_error
                ),
            })

        return messages

    def _call_model(self, messages):
        try:
            response = self._get_client().chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0,
                response_format={"type": "json_object"},
            )
        except RouterError:
            raise
        except Exception as error:
            # Avoid exposing credentials, request headers, or a traceback.
            raise RouterUnavailableError(
                "The Groq API request failed. Check your internet connection, "
                "API key, and Groq service status, then try again."
            ) from error

        try:
            return response.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as error:
            raise RouterOutputError(
                "Groq returned an empty or unexpected response."
            ) from error

    def _parse_and_validate(self, raw_output):
        try:
            result = json.loads(raw_output)
        except (json.JSONDecodeError, TypeError) as error:
            raise ValueError("The response was not valid JSON.") from error

        if not isinstance(result, dict):
            raise ValueError("The response must be a JSON object.")

        if set(result) != {"pipeline", "params"}:
            raise ValueError(
                "The JSON must contain exactly 'pipeline' and 'params'."
            )

        pipeline_name = result["pipeline"]
        params = result["params"]

        if pipeline_name is None:
            if params != {}:
                raise ValueError(
                    "When pipeline is null, params must be an empty object."
                )
            return {"pipeline": None, "params": {}}

        if not isinstance(pipeline_name, str):
            raise ValueError("pipeline must be a string or null.")

        # Enforce the public menu before calling the broader registry
        # validator, which also knows about private benchmark pipelines.
        if pipeline_name not in self.menu:
            raise ValueError(
                f"Pipeline '{pipeline_name}' is not in the public menu."
            )

        validated = validate_params(pipeline_name, params)

        return {
            "pipeline": pipeline_name,
            "params": validated,
        }

    def route(self, question):
        """Return a validated route without executing any database query."""
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a non-empty string.")

        retry_error = None

        for attempt in range(2):
            raw_output = self._call_model(
                self._build_messages(question.strip(), retry_error)
            )

            try:
                return self._parse_and_validate(raw_output)
            except ValueError as error:
                retry_error = str(error)

                if attempt == 1:
                    raise RouterOutputError(
                        "The router could not produce a valid route after "
                        f"two attempts. Last validation error: {retry_error}"
                    ) from error

        # Defensive fallback; the loop normally returns or raises.
        raise RouterOutputError("The router could not produce a valid route.")

    def execute(self, db, question):
        """Route the question, then execute only the approved pipeline."""
        route = self.route(question)

        if route["pipeline"] is None:
            return {
                "pipeline": None,
                "params": {},
                "rows": [],
                "message": (
                    "I can help with shop analytics, such as revenue, "
                    "top customers, stock alerts, product ratings, "
                    "and order summaries."
                ),
            }

        rows = run_pipeline(
            db,
            route["pipeline"],
            route["params"],
        )

        return {
            "pipeline": route["pipeline"],
            "params": route["params"],
            "rows": rows,
            "message": None,
        }
