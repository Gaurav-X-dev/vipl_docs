# RBAC

Roles and permissions are database-driven. Seed roles include Super Admin, Admin, Manager, Investigator, HR, Reviewer and Data Entry Operator. API dependencies enforce granular permissions such as `case.assign`, `import.create`, `document.generate` and `audit.view`. Investigators receive least-privileged access and case queries scope them to their own assignments unless an explicit view-all permission exists.
