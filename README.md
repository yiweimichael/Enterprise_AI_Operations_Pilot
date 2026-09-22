# Enterprise_AI_Operations_Pilot
A secure, permission-aware AI operations copilot for enterprise knowledge search, read-only analytics, and human-approved CRM actions.

## Architecture

```mermaid
flowchart TB
    UI["Web UI: chat, citations, approvals, reports"] --> API["FastAPI: API, roles, validation"]
    API --> LG["LangGraph: workflow routing"]

    LG --> K["Knowledge retrieval"]
    LG --> A["Read-only SQL analytics"]
    LG --> T["CRM ticket proposal"]
    LG --> R["Stakeholder report"]

    K -->|"cited evidence"| R
    A -->|"metrics"| R

    T --> P["Human approval"]
    P -->|"approved action"| C["Simulated CRM create/update"]

    K --> DB["PostgreSQL + pgvector"]
    A --> DB
    P --> DB
    C --> DB
```

Knowledge retrieval uses authorized documents, and analytics queries use approved read-only views. Ticket details are validated before approval; if they change afterward, the action requires reapproval. Requests, decisions, executions, and outcomes are recorded in the audit log.

## Project Structure

```text
frontend/       Minimal chat and approval interface
backend/        FastAPI API, LangGraph workflows, RAG, and approvals
mcp_server/     Analytics and CRM MCP tools
data/           Sample documents and analytics data
tests/           Unit and security tests
docs/            Architecture documentation
