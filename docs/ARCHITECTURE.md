# Architecture

The React SPA calls versioned FastAPI endpoints through a centralized Axios client. FastAPI endpoints enforce database-driven permissions, delegate business rules to services, and use async SQLAlchemy repositories/queries. PostgreSQL is the source of truth; Alembic owns schema evolution. Files are stored outside the database with checksums and auditable metadata.

Core boundaries are authentication/RBAC, staff/HR, company masters, shared case engine, import pipeline, dynamic form engine, document rendering, dashboard/reporting and audit. Investigation and Death Claim share infrastructure but retain category-specific workflows and detail models.
