# Data Agent

An intelligent multi-agent system built with LangGraph that automatically routes data requests to specialized agents. The system intelligently determines whether queries require SQL data extraction or ETL operations.

## Features

- **Intelligent Routing**: Automatically routes queries to SQL or ETL agents based on request type
- **Multi-Agent Architecture**: Specialized agents for different data operations
  - **SQL Analyst**: Handles database queries and structured data extraction
  - **ETL Analyst**: Handles API data extraction, transformation, and loading
- **LangGraph Integration**: Robust workflow orchestration with conditional routing
- **LLM-Powered Router**: Uses language models to intelligently classify requests

## Project Structure

```
data_agent/
├── __init__.py                # Package initialization
├── config.py                  # Configuration settings
├── main.py                    # Application entry point
├── README.md                  # This file
│
├── agents/                    # Specialized agent implementations
│   ├── __init__.py
│   ├── data_analyst.py       # Main orchestrator with routing logic
│   ├── etl_analyst.py        # ETL operations (extract, transform, load)
│   └── sql_analyst.py        # SQL queries and database operations
│
├── agentschemas/             # Pydantic schemas for data validation
│   ├── __init__.py
│   ├── agent.py              # Agent-specific schemas
│   ├── data.py               # DataSchema with messages and routing
│   ├── etl.py                # ETL operation schemas
│   ├── judge.py              # Judgment/validation schemas
│   └── router.py             # RouterSchema for LLM routing decisions
│
├── models/                   # SQLAlchemy ORM models
│   ├── __init__.py
│   ├── base.py               # Base model configuration
│   ├── user.py               # User model
│   ├── vehicle.py            # Vehicle model
│   ├── ride.py               # Ride model
│   ├── payment.py            # Payment model
│   └── rating.py             # Rating model
│
├── schemas/                  # Pydantic request/response schemas
│   ├── __init__.py
│   ├── user.py               # User schemas
│   ├── vehicle.py            # Vehicle schemas
│   ├── ride.py               # Ride schemas
│   ├── payment.py            # Payment schemas
│   └── rating.py             # Rating schemas
│
├── utils/                    # Utility modules
│   ├── __init__.py
│   ├── llm_pick.py          # LLM selection and initialization
│   ├── database.py          # Database connection and utilities
│   └── etl_tools.py         # ETL utility functions
│
├── data/                     # Data storage directory
│   └── extract/              # Extracted data storage
│
└── migrations/               # Database migration files (Alembic)
    ├── env.py               # Migration environment setup
    ├── script.py.mako       # Migration template for new migrations
    ├── README               # Alembic README
    └── versions/            # Database migration versions
        ├── a86b191887cf_insert_csv_data_for_all_tables.py
        └── c8e2638fcf8a_create_ride_sharing_tables.py
```

## Installation

### Option 1: Using UV (Recommended - Faster)

[UV](https://docs.astral.sh/uv/) is a fast Python package installer written in Rust.

1. Clone the repository:
```bash
git clone <repository-url>
cd data_agent
```

2. Install UV (if not already installed):
```bash
# On Windows
curl -LsSf https://astral.sh/uv/install.ps1 | powershell -c -

# On macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

3. Create virtual environment and install dependencies:
```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

### Option 2: Using pip

1. Clone the repository:
```bash
git clone <repository-url>
cd data_agent
```

2. Create and activate virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Example

```python
from langchain_core.messages import HumanMessage
from agents.data_analyst import data_analyst

response = data_analyst.invoke({
    "messages": [HumanMessage(content="Extract data from the Pokemon API and save to CSV")]
})

print(response)
```

### Routing Examples

The system automatically routes based on query type:

- **ETL Route**: "Extract data from API endpoint..."
- **SQL Route**: "Query the database for...", "Get sales data where..."

## Architecture

### Data Flow

```
User Query
    ↓
[START] → router_node (LLM decides route)
    ↓
    ├─→ [sql_node] → SQL Analyst → Database
    │
    └─→ [etl_node] → ETL Analyst → API/External Source
    ↓
Response
```

### Key Components

**router_node**: Uses LLM with RouterSchema to classify incoming requests as "sql" or "etl"

**sql_node**: Executes SQL queries with:
- Query generation and validation
- Safety checks
- Execution against database

**etl_node**: Handles data extraction with:
- API connectivity
- Data transformation
- File saving operations

## Schemas

### Agent Schemas (`agentschemas/`)
Pydantic models used for LLM orchestration and validation:

- **DataSchema**: Main workflow state with messages and routing decisions
- **RouterSchema**: LLM output for routing decisions ("sql" or "etl")
- **ETLSchema**: ETL operation parameters and results
- **AgentSchema**: Agent configuration and metadata
- **JudgeSchema**: Validation and quality checking

### Data Models (`models/`)
SQLAlchemy ORM models representing core business entities:

- **User**: User profiles and authentication
- **Vehicle**: Vehicle information and metadata
- **Ride**: Ride bookings and history
- **Payment**: Payment transactions
- **Rating**: Ride ratings and reviews

### API Schemas (`schemas/`)
Pydantic request/response schemas for API endpoints:

- **User Schemas**: Create, read, update operations
- **Vehicle Schemas**: Vehicle management
- **Ride Schemas**: Ride booking and tracking
- **Payment Schemas**: Payment processing
- **Rating Schemas**: Rating submissions

## Schemas

### DataSchema
Main state schema for the workflow:
- `messages`: List of conversation messages
- `route_response`: Routing decision ("sql" or "etl")

### RouterSchema
LLM output schema for routing decisions:
- `answer`: The routing decision

## Development

### Quick Reference - UV Commands

```bash
# Create virtual environment
uv venv

# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate      # Windows

# Install dependencies
uv pip install -r requirements.txt

# Add a new package
uv pip install <package-name>

# Update dependencies
uv pip install --upgrade -r requirements.txt

# Freeze current dependencies
uv pip freeze > requirements.txt
```

### Running Tests
```bash
pytest tests/
```

### Database Migrations

This project uses [Alembic](https://alembic.sqlalchemy.org/) for database migrations.

**View migration status:**
```bash
alembic current
```

**Run all pending migrations:**
```bash
alembic upgrade head
```

**Create a new migration:**
```bash
alembic revision --autogenerate -m "Description of changes"
```

**Rollback to previous migration:**
```bash
alembic downgrade -1
```

**View migration history:**
```bash
alembic history
```

### Visualizing the Graph
The system generates a graph visualization:
```bash
python agents/data_analyst.py
# Generates: data_agent_graph.png
```

## Recent Changes

- Fixed Pydantic validation error in DataSchema by making `route_response` field optional with default value
- Improved agent integration and error handling

## Dependencies

- **langchain**: LLM framework
- **langgraph**: Graph-based workflow orchestration
- **pydantic**: Data validation
- Python 3.10+

## Contributing

1. Create a feature branch
2. Make changes and test thoroughly
3. Submit a pull request

## License

[Add license information here]

## Contact

For questions or issues, please open an issue in the repository.
