## Problem

Operations employees must switch between company documents, analytics databases, and CRM systems to answer questions and complete routine tasks. This creates delays, inconsistent results, and security risks when information access and system changes are not properly controlled.

## Primary User

An Operations Analyst who needs to retrieve authorized company information, query operational metrics, and propose CRM ticket actions through a single controlled interface.

## Core Workflows

a) **Knowledge Research:** The user asks a question, and the system retrieves authorized documents and returns an answer with citations.

b) **Analytics Query:** The user asks a business question, and the system calls a read-only SQL tool to retrieve relevant metrics.

c) **CRM Ticket Action:** The user asks to create or update a ticket. The system prepares the action and waits for human approval before executing it.

d) **Stakeholder Report:** The system combines document evidence and analytics results into a cited report.

## Shared MVP Features

- Role-aware user access
- Chat interface with LangGraph workflow routing
- MCP integration for analytics and CRM tools

## MVP Features: Knowledge Research

- Permission-aware document retrieval
- Grounded answers with citations
- “Insufficient evidence” response when no authorized source supports the answer

### MVP Features: Analytics Query

- Read-only SQL analytics tool
- Access limited to approved analytics views
- Plain-language summary of query results

### MVP Features: CRM Ticket Action

- CRM ticket tool that creates or updates simulated tickets
- Human approval before any ticket write action
- Audit record of the proposed action, approval decision, and result

### MVP Features: Stakeholder Report

- Generate a report from a user-selected topic or question
- Combine authorized document evidence and read-only analytics results
- Include citations for document-based claims

## Safety Controls

- **Role-based access:** The system retrieves only documents and analytics data authorized for the signed-in user.

- **Read-only analytics:** The SQL tool can query only approved views and rejects write operations.

- **Human approval for CRM writes:** Ticket changes execute only after user approval; changed details require new approval.

- **Audit logging:** The system records CRM action requests, approval decisions, and execution outcomes.

## Draft Demo Summary

An Operations Analyst signs in and asks a question about company policy. The copilot retrieves only documents authorized for that user and returns a cited answer.

The analyst can then ask for an operational metric. The copilot uses a read-only SQL tool to retrieve and summarize the result.

Finally, the analyst can request a CRM ticket action. The copilot prepares the ticket details, waits for approval, and executes the action only after approval.

## High-Level Architecture

```mermaid
flowchart TD
    User[Operations Analyst] --> UI[Web UI]
    UI --> API[Application API]
    API --> Agent[LangGraph Orchestrator]

    Agent --> RAG[Knowledge Retrieval]
    Agent --> SQL[Read-Only Analytics Tool]
    Agent --> CRM[CRM Ticket Tool]
    CRM --> Approval[Human Approval]

    RAG --> DB[(PostgreSQL + pgvector)]
    SQL --> DB
    CRM --> DB

    CRM --> Audit[Audit Log]
    Approval --> Audit