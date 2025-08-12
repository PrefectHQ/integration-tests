# AGENTS.md

This file provides guidance to AI coding assistants when working with code in this repository.

Note: CLAUDE.md is symlinked to this file to support multiple coding agents (Claude, Cursor, Copilot, etc.) while maintaining a single source of truth.

## Repository Overview

This repository contains integration test flows for Prefect, designed to evaluate the health of Prefect systems across different environments (dev, stg, prd). The tests run on regular intervals and report failures to relevant channels.

## Common Development Commands

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Code Quality
```bash
# Run all pre-commit hooks (includes ruff, shellcheck, actionlint, etc.)
pre-commit run --all-files
```

### Local Testing

Start local Prefect OSS instance:
```bash
docker compose up -d
```

Configure local profile:
```bash
prefect profile create local
prefect profile use local
prefect profile set PREFECT_API_URL="http://localhost:4200/api"
```

Start workers for local testing:
```bash
prefect worker start --pool "kubernetes-prd-internal-tools"
prefect worker start --pool "managed-work-pool"
```

### Running Individual Flows

Flows can be run directly:
```bash
python flows/hello-world.py
python flows/task-bursts.py
```

## Project Structure

### Key Files
- `prefect.yaml`: Defines all deployments, schedules, work pools, and flow configurations
- `flows/`: Contains all integration test flow implementations
- `.github/workflows/`: GitHub Actions for automatic deployment to different environments

### Deployment Configuration
- Deployments are defined in `prefect.yaml` with YAML anchors for reusable configurations
- Most flows run on 5-minute intervals (`*/5 * * * *`)
- Flows are tagged with `expected:success` or `expected:failure` based on intended behavior
- Work pools: `kubernetes-prd-internal-tools` (main), `managed-work-pool` (managed flows), and `helm` work queue for Helm chart testing

### Flow Patterns
- All flows use `@flow` decorator from Prefect
- Entry points follow naming convention: `{flow_name}_entry`
- Flows use `get_run_logger()` for logging
- Automation assessment flows use asyncio and have timeout configurations

## Environment-Specific Notes

### Production
- Automations Tracer runs every 30 seconds
- Helm integration tests run in separate namespace
- Managed work pool tests validate Prefect managed infrastructure

### Dev/Staging
- Full suite of automation assessments (compound, proactive, reactive, sequence)
- Event streaming tests
- Flow and task retry tests with various configurations

## Testing Considerations
- Integration test timeout is set to 4 minutes (5-minute interval - 60 seconds buffer)
- Event timeout is 3 minutes for automation assessments
- Flows automatically clean up old automations to prevent accumulation
- Use concurrency controls to prevent test overlap
