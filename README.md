# Mongo Query Router

A natural-language analytics API that converts user questions into structured MongoDB aggregation queries and returns readable analytical results through a FastAPI-powered dashboard.

## Overview

Mongo Query Router allows users to ask questions about products, customers, orders, revenue, inventory, and reviews in plain English. Instead of manually writing MongoDB aggregation pipelines, the application routes each question to an appropriate analytics pipeline and executes it against MongoDB.

The project combines natural-language query routing, database aggregation, result summarization, automated testing, and an interactive web dashboard.

## Key Features

- **Natural-language query routing:** Maps user questions to the appropriate analytics pipeline.
- **MongoDB aggregation:** Performs analytical operations directly on MongoDB collections.
- **Revenue analytics:** Analyzes category revenue, monthly trends, and customer spending.
- **Inventory monitoring:** Identifies products with stock below a specified threshold.
- **Product review analytics:** Ranks products by average rating with a minimum review count.
- **Price distribution:** Groups products into price bands.
- **Dashboard summary:** Combines key revenue, order, and product metrics.
- **Interactive web interface:** Displays answers, selected pipelines, parameters, returned rows, and raw results.
- **Automated testing:** Includes tests for query routing, pipeline selection, parameters, and application behavior.

## Technology Stack

- **Language:** Python
- **Backend API:** FastAPI
- **Database:** MongoDB
- **Database Driver:** PyMongo
- **Environment Configuration:** python-dotenv
- **Testing:** pytest
- **Frontend:** HTML, CSS, JavaScript

## Architecture

```text
             User Question
                   |
                   v
        FastAPI Application
                   |
                   v
          Query Router
                   |
                   v
       Pipeline and Parameter
              Selection
                   |
                   v
       MongoDB Aggregation
                   |
                   v
         Query Execution
                   |
                   v
        Result Summarization
                   |
                   v
         Dashboard Response
```

## Supported Analytics Pipelines

| Pipeline | Purpose |
|---|---|
| `revenue_by_category` | Calculates revenue by product category |
| `top_customers` | Identifies customers with the highest spending |
| `monthly_revenue_trend` | Summarizes revenue by month |
| `order_status_summary` | Summarizes orders by status |
| `low_stock_alert` | Finds products below a stock threshold |
| `product_ratings` | Ranks products using review ratings |
| `price_band_distribution` | Analyzes product price ranges |
| `dashboard_summary` | Provides an overview of important business metrics |

The project also contains a private benchmark pipeline, `revenue_by_category_naive`, used for internal evaluation.

## Prerequisites

Install the following before running the application:

- Python 3.10 or a compatible Python version
- MongoDB running locally or a reachable MongoDB instance
- Git
- pip

## Installation and Setup

### 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd mongo-query-router
```

Replace the placeholder with your actual GitHub repository URL after creating the repository.

### 2. Create a virtual environment

**Windows PowerShell:**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install dependencies

If the project contains a `requirements.txt` file:

```powershell
pip install -r requirements.txt
```

Otherwise, install the required packages:

```powershell
pip install fastapi uvicorn pymongo python-dotenv pytest
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```dotenv
MONGODB_URI=mongodb://localhost:27017
API_DB_NAME=mongo_query_router_api_dev
```

Adjust the MongoDB URI if you use a remote database.

**Security:** Never commit `.env` or publish database credentials. Keep `.env` excluded through `.gitignore`.

### 5. Start MongoDB

Ensure your MongoDB server is running and accessible through the configured connection string.

### 6. Start the API

```powershell
uvicorn app.api.main:app --reload
```

Open the dashboard at:

http://127.0.0.1:8000

FastAPI's interactive API documentation is available at:

http://127.0.0.1:8000/docs

## Example Questions

Try these questions in the dashboard:

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

Date-range queries use an inclusive start date and an exclusive end date. Revenue analytics count delivered orders, while order-status analytics can include other order statuses.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves the dashboard |
| `GET` | `/health` | Checks application health |
| `POST` | `/api/query` | Processes a natural-language analytics question |

The query endpoint accepts a question through the application's request schema and returns the analytical response. Refer to `/docs` for the exact request and response models.

## Running Tests

Run the automated test suite from the project root:

```powershell
python -m pytest -q
```

The current recorded test result is **76 passed**. Run the suite again after making changes to verify the current state.

## Database Collections

The demo database uses the following collections:

- `orders` — order details, customer references, dates, statuses, and totals.
- `products` — product information, prices, stock, and category references.
- `categories` — product category information.
- `users` — customer information.
- `reviews` — product ratings and review data.

The application uses `mongo_query_router_api_dev` as its default API database unless overridden by configuration.

## Project Structure

```text
mongo-query-router/
├── app/
│   ├── api/
│   │   └── main.py
│   └── db.py
├── tests/
├── .env                  # Local configuration; do not commit
├── .gitignore
├── requirements.txt
├── seed_demo_data.py
└── README.md
```

This is a representative structure. Retain the actual filenames and folders present in your project when updating this section.

## Git Safety

Before pushing the project to GitHub, ensure that `.gitignore` excludes at least:

```gitignore
.env
venv/
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
```

Do not commit database credentials, private keys, virtual environments, or unrelated personal files.

## Future Improvements

- Add authentication and authorization.
- Add query execution limits and request validation.
- Improve handling of ambiguous natural-language questions.
- Add structured logging and performance monitoring.
- Expand analytics pipelines and evaluation coverage.
- Deploy the API and dashboard to a production environment.

## License

No license has been specified yet. Add a license before permitting others to reuse or distribute the project.

---

**Mongo Query Router** — turning natural-language business questions into actionable MongoDB analytics.
