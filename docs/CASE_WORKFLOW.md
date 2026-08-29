# Case Workflow

Typical flow: `Imported/Unassigned → Assigned → Accepted → In Progress → Report In Progress → Submitted by Investigator → Under Review → Verified → Completed`. Correction, rejection and cancellation branches are guarded centrally. Every change records the actor, timestamp, old/new status and comment; completion requires the appropriate review/outcome state.
