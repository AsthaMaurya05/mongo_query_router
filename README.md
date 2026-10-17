# Mongo Query Router

Mongo Query Router is a FastAPI application that turns natural-language business questions into validated MongoDB aggregation pipelines. It routes each question to an analytics pipeline, executes the query, and returns both structured results and a readable summary in an interactive dashboard.

## Features

- Natural-language routing for common shop analytics questions
- MongoDB aggregation pipelines for revenue, customers, orders, inventory, ratings, and prices
- Groq-powered query routing and result summarization
- Request validation and MongoDB collection validators
- Interactive dashboard and FastAPI OpenAPI documentation
- Service-layer CRUD operations for users, products, orders, and reviews
- Pipeline and index benchmarks with generated reports
- Automated tests for routing, pipelines, validation, and services

## Technology stack

- Python 3.10+
- FastAPI and Uvicorn
- MongoDB and PyMongo
- Groq
- Pydantic
- pytest and Faker

## Prerequisites

Install the following before running the project:

- Python 3.10 or newer
- A running MongoDB instance
- A Groq API key
- Git and pip

## Installation

Clone the repository and create a virtual environment:

```powershell
git clone https://github.com/AsthaMaurya05/mongo_query_router.git
cd mongo_query_router
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the pinned project dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root:

```dotenv
MONGODB_URI=mongodb://localhost:27017
API_DB_NAME=mongo_query_router_api_dev
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=llama-3.1-8b-instant
```

`MONGODB_URI` defaults to `mongodb://localhost:27017`. The API uses `API_DB_NAME` (default: `mongo_query_router_api_dev`) for its demo data. `GROQ_MODEL` is optional; the application uses its configured default when it is omitted.

Never commit `.env`, API keys, database credentials, or private keys. The repository `.gitignore` excludes local environment files and Python build/test artifacts.

## Load demo data

Make sure MongoDB is running, then seed the dedicated API database:

```powershell
python seed_demo.py
```

The seed script refuses to modify a non-empty database. An equivalent guarded script is available at `seed_demo_data.py`.

## Run the API

Start the development server from the repository root:

```powershell
python -m uvicorn app.api.main:app --reload
```

Open the dashboard at <http://127.0.0.1:8000>. The interactive API documentation is available at <http://127.0.0.1:8000/docs>.

### API endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/` | Serves the analytics dashboard |
| `GET` | `/health` | Checks API and MongoDB availability |
| `POST` | `/api/query` | Routes and executes an analytics question |

Example request:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/query `
  -ContentType "application/json" `
  -Body '{"question":"Show the top 5 product categories by revenue from September 1 to October 1, 2026."}'
```

## Supported analytics

| Pipeline | Purpose |
| --- | --- |
| `revenue_by_category` | Calculates revenue by product category |
| `top_customers` | Finds customers with the highest spending |
| `monthly_revenue_trend` | Summarizes revenue by month |
| `order_status_summary` | Summarizes orders by status |
| `low_stock_alert` | Finds products below a stock threshold |
| `product_ratings` | Ranks products by average rating |
| `price_band_distribution` | Groups products into price bands |
| `dashboard_summary` | Combines key business metrics |

The private `revenue_by_category_naive` pipeline is retained for benchmark comparisons and is not exposed to normal AI routing.

Date-range filters use an inclusive start date and an exclusive end date. Revenue analytics count delivered orders; order-status analytics can include other statuses.

Example questions:

```text
Show the top 5 product categories by revenue from September 1 to October 1, 2026.
Who are the top 5 customers by spending between September 1 and October 1, 2026?
Show products with stock below 10.
Rank products by average rating with at least 2 reviews.
Show the distribution of product prices.
Show monthly revenue from September 1, 2026 to November 1, 2026.
Give me a dashboard summary from September 1, 2026 to October 1, 2026.
Summarize order statuses from September 1 to October 1, 2026.
```

## Scripts and benchmarks

Run the CRUD service-layer demonstration against a temporary database:

```powershell
python -m scripts.demo_crud
```

The script creates validators and indexes, demonstrates insert/read/update/delete operations, and drops its temporary database when it finishes. It does not use `shop_db`.

Other useful scripts include:

| Script | Purpose |
| --- | --- |
| `scripts.setup_collections` | Creates validated `shop_db` collections |
| `scripts.seed_data` | Seeds the larger service-layer dataset |
| `scripts.create_indexes` | Creates application indexes |
| `scripts.benchmark_category_pipelines` | Compares category-revenue pipelines |
| `scripts.benchmark_indexes` | Measures query plans and index impact |
| `scripts.collect_report_facts` | Collects reproducible, read-only project facts |

Benchmark results are stored in [docs/category_pipeline_benchmark.md](docs/category_pipeline_benchmark.md) and [docs/index_benchmark_results.md](docs/index_benchmark_results.md).

## Tests

Run the complete test suite:

```powershell
python -m pytest -q
```

The test suite covers query routing, pipeline selection and parameters, schema validation, and service behavior. Test results can vary if the local environment or database fixtures change.

## Database collections

The application works with these collections:

- `orders`: order details, customer references, dates, statuses, totals, and item snapshots
- `products`: product names, prices, stock, tags, and category references
- `categories`: product categories
- `users`: customer information
- `reviews`: product ratings and review data

## Project structure

```text
mongo-query-router/
|-- app/
|   |-- ai/              # Query routing and result summarization
|   |-- api/             # FastAPI application and dashboard
|   |-- pipelines/       # Analytics pipeline registry and definitions
|   |-- schemas/         # MongoDB validators
|   `-- services/        # CRUD service layer
|-- docs/                # Benchmark reports and explain output
|-- scripts/             # Setup, seed, benchmark, and demo utilities
|-- tests/               # Automated tests and router evaluation helpers
|-- requirements.txt
|-- seed_demo.py
|-- seed_demo_data.py
`-- README
```

## License

No license has been specified yet. Add a license before permitting others to reuse or distribute the project.
