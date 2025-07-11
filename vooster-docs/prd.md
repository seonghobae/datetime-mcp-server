# 제품 요구 사항 문서 (PRD)

## 1. Overview

This project aims to develop an MCP (Model Context Protocol) server that provides **pure date calculation tools** for LLMs. Instead of parsing natural language date expressions, this MCP server offers precise mathematical date operations that LLMs can call when they need accurate temporal calculations. The server implements the MCP protocol and provides various date/time calculation tools, formatting utilities, and simple note management functionality. Key features include current datetime retrieval, date arithmetic operations, business day calculations, timezone handling, and date range computations. The server is developed as a fork of [https://github.com/bossjones/datetime-mcp-server](https://github.com/bossjones/datetime-mcp-server) ([https://github.com/seonghobae/datetime-mcp-server](https://github.com/seonghobae/datetime-mcp-server)), with the goal of merging with the upstream repository. It is distributable as a Docker/Podman container and is designed for easy integration and operation by LLM DevOps engineers.

## 2. Problem Statement

1. LLMs need reliable, accurate date calculations but should not rely on built-in date logic that may be incorrect or inconsistent.
2. For RAG queries involving time ranges, LLMs need precise date arithmetic tools to calculate "3 months ago from today" or "next business day after 2024-12-25".
3. Re-implementing date calculation logic across teams leads to productivity loss and calculation errors, especially with edge cases like leap years, timezone transitions, and business day rules.

## 3. Goals & Objectives

- Primary Goal: Provide MCP protocol tools for precise date/time calculations that LLMs can call when needed. (No natural language parsing; only mathematical date operations.)
- Secondary Goal: Offer comprehensive timezone, business day, and formatting support for enterprise use cases.
- Success Metrics
    - Tool response time ≤ 50ms (p95) - faster than parsing-based approaches
    - Calculation accuracy 100% (mathematical precision, not parsing accuracy)
    - GitHub ⭐ 50, 10 forks, 1 merged upstream PR

## 4. Target Users

### Primary Users

- LLM DevOps / MLOps engineers: Enhance LLM capabilities with reliable date calculation tools

### Secondary Users

- Data scientists, backend developers, RAG solution vendors, enterprise developers needing precise temporal logic

## 5. User Stories

- As an LLM operator, I want the LLM to call precise date calculation tools so that it can provide accurate temporal information without hallucination.
- As a search engineer, I want LLMs to calculate exact date ranges (e.g., "90 days before 2024-07-15") for precise query generation.
- As a business application developer, I want reliable business day calculations that account for weekends and holidays.

## 6. Feature Requirements

### Core Features

1. **MCP Protocol Resources**
    - `datetime://current`: Returns the current date and time in multiple formats
    - `datetime://timezone-info`: Returns current timezone information and offset
    - `datetime://supported-timezones`: Lists all supported timezone identifiers

    - Acceptance criteria: Resource listing returns all current note and datetime resources; datetime resources must include current, timezone-info, and supported-timezones.

2. **MCP Date Calculation Tools**
    - `get-current-datetime`: Get current date/time in specified timezone and format
    - `calculate-date`: Add/subtract days, weeks, months, years from a given date
    - `calculate-date-range`: Calculate start and end dates for periods like "last 3 months"
    - `format-date`: Convert dates between different formats (ISO, RFC3339, Unix timestamp, etc.)
    - `calculate-business-days`: Calculate business days between dates, excluding weekends and holidays

    - Input example: `calculate-date-range("2024-07-15", "last", 3, "months")` → Output: `{ "start": "2024-04-15", "end": "2024-07-15" }`
    - Input example: `calculate-business-days("2024-12-20", "2024-12-31", ["2024-12-25"])` → Output: `{ "business_days": 7 }`

3. **Note Management Tools**
    - `add-note`: Adds a new note with a name and content
    - `get-note`: Retrieves a note by name
    - `list-notes`: Lists all available notes
    - `delete-note`: Removes a note by name

4. **MCP Prompts for LLM Guidance**
    - `datetime-calculation-guide`: Provides examples of when and how to use date calculation tools
    - `business-day-rules`: Explains business day calculation rules and holiday handling
    - `timezone-best-practices`: Guidelines for timezone-aware date operations

5. **Advanced Features**
    - Timezone-aware calculations with DST handling
    - Customizable business day rules (different weekend patterns, holiday calendars)
    - High-precision datetime operations for financial and scientific applications

### Non-Core Features (Future)
- SSE stream response option for bulk calculations
- Custom holiday calendar management
- Recurring date pattern calculations

## 7. Non-Functional Requirements

- **Performance**: p95 ≤ 50ms (faster than parsing-based approaches), linear scalability up to 1000 QPS
- **Accuracy**: 100% mathematical precision for all date calculations (no parsing ambiguity)
- **Security**: HTTPS required, input validation, OWASP Top10 compliance
- **Usability**: Clear MCP tool signatures, comprehensive examples in prompts
- **Scalability**: Multi-instance scale-out, stateless design
- **Compatibility**: Python 3.12+, AMD64/ARM64 containers, MCP 1.0 protocol compliance

## 8. Technical Considerations

- **Architecture**: Pure Python MCP server implementation, asyncio-based
- **MCP Protocol**: Implements resources, tools, and prompts interfaces (see `server.py`)
- **Date Calculation Engine**: Uses Python standard library `datetime`, `zoneinfo`, and `calendar` for precise calculations
- **No External Parsing**: No dateparser or NLP libraries - all operations are mathematical
- **Note Management**: In-memory key-value storage for simple notes; extensible for persistent storage
- **Tool Implementation**: All tools are deterministic mathematical functions with clear input/output contracts
- **CLI Client**: Async Python client supporting tool invocation, Claude API integration, interactive chat loop (see `client.py`)
- **Dependency Management**: Uses `uv`, `pydantic`, `dotenv`; minimal dependencies for reliability
- **Examples & Tests**: Includes acceptance and integration tests (pytest), Makefile tasks for development

## 9. Success Metrics & KPIs

- **Technical KPIs**: p95 response time ≤ 50ms, 100% calculation accuracy, 99.9% availability
- **Product KPIs**: 1M monthly tool calls (MAU)
- **Community KPIs**: GitHub stars, number of submitted PRs

## 10. Timeline & Milestones

- 2025-07-15 M0: Requirements freeze, repository setup
- 2025-08-15 M1: Core MCP tools implementation (get-current-datetime, calculate-date)
- 2025-09-01 M2: Advanced tools (business days, timezone handling), CLI client beta
- 2025-09-15 M3: Container image, comprehensive prompts, performance optimization
- 2025-10-01 M4: Upstream PR submission and review, v1.0 release

## 11. Risks & Mitigations

- Library license changes → Use only standard library components, maintain MIT license
- Timezone data updates → Regular Python updates, fallback to UTC for unknown zones
- Upstream PR rejection → Maintain independent repository, demonstrate clear value proposition

## 12. Future Extensions

- Custom business day calendars for different countries/industries
- Advanced recurring date calculations (e.g., "third Friday of each month")
- Integration with external calendar systems (Google Calendar, Outlook)
- GraphQL interface for complex date queries
- Native LLM plugin support (e.g., OpenAI function calling)