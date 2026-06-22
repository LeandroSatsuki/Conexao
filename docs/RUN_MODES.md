# Run Modes

Preferenza Connector supports two operational modes.

## Mode 1: On-Demand

Use this mode when the tool is used only occasionally and you want to start it only when needed.

### Recommended flow
1. Start the stack.
2. Run migrations.
3. Run validation or integration.
4. Review the report and logs.
5. Stop the stack.

### Why use it
- Lower operational cost.
- Lower exposure surface.
- Lower complexity.
- Better fit for occasional homologation runs.

## Mode 2: Optional Online Service

Use this mode when the platform becomes frequent enough to justify always-on operation.

### Recommended flow
1. Keep the stack running.
2. Keep the worker running.
3. Process jobs continuously.
4. Add metrics and alerts later if the usage pattern requires it.

### Why keep it available
- Scheduled integrations may appear later.
- Continuous monitoring may become necessary later.
- API consumers may need a persistent service later.

## Current recommendation

The current recommended mode is **on-demand**.

The service mode remains supported by the current Docker Compose stack and can be prioritized later without redesigning the platform.

## Safety rule

Before any future Sankhya write stage, the read-only validation flow must be executed and approved.
