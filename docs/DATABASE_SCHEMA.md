# Database Schema

The initial Alembic revision creates 40+ normalized tables covering users/sessions/login attempts, roles/permissions, employees/HR, companies/case types, cases/assignments/status history, form templates/sections/fields/values/history, import templates/batches/rows, evidence/generated documents, notifications, settings and audit/timeline events.

UUID primary keys are used for business entities. Case numbers use a locked yearly sequence table rather than `max(id)`. Foreign keys define explicit delete behavior; lookup and operational paths have indexes. JSONB is selected on PostgreSQL for configurable mappings and structured answers, with portable JSON in tests.
