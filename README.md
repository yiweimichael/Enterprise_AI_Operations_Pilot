# Enterprise_AI_Operations_Pilot
A secure, permission-aware AI operations pilot for enterprise knowledge search, read-only analytics, and human-approved CRM actions.

## Architecture

```mermaid
flowchart TB
    UI["Next.js UI: chat, citations, approvals, reports"] --> API["FastAPI: auth, roles, validation"]
    API --> LG["LangGraph: workflow routing"]
    LG --> LLM["LLM API"]

    LG --> K["Knowledge retrieval (role-filtered)"]
    LG --> T["CRM ticket proposal"]
    LG --> R["Stakeholder report"]
    LG -->|"MCP"| MCP["MCP server"]
    MCP --> A["Read-only SQL analytics"]

    K -->|"cited evidence"| R
    A -->|"metrics"| R

    T --> P["Human approval"]
    P -->|"approved action (hash-checked)"| MCP
    MCP --> C["Simulated CRM create/update"]

    K --> DB[("PostgreSQL + pgvector")]
    A -->|"read-only role"| DB
    P --> DB
    C --> DB
    P --> AU["Audit log"]
    C --> AU
```

Knowledge retrieval uses authorized documents, and analytics queries use approved read-only views. Ticket details are validated before approval; if they change afterward, the action requires reapproval. Approved payloads are hash-checked before execution. Requests, decisions, executions, and outcomes are recorded in the audit log.

## Project Structure

```text
frontend/            Minimal chat and approval interface
backend/             FastAPI API, LangGraph workflows, RAG, and approvals
backend/tests/       Backend unit and security tests
mcp_server/          Analytics and CRM MCP tools
mcp_server/tests/    MCP tool and safety tests
data/                Sample documents and analytics data
docs/                Architecture documentation
```
