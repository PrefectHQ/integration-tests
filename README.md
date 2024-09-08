# Integration Tests

We run an assortment of `integration tests` flows for the purpose of evaluating the health of our systems. Defined below are the locations in which certain flows run.

## Prefect Dev/Stg - integration-tests workspace

We run several flows on a regular interval in both the dev & stg environments. Unexpected failures are reported to the relevant environment channel `#alerts-ENV-cloud2`.

## Prefect Prd - integration-tests workspace

We utilize two work queues for test flows in our production environment:
  - integration-tests
  - helm

The `integration-tests` work queue runs our typical test flows.

The `helm` work queue runs a few simple flows against the latest version of a prefect worker. We automatically deploy the latest helm chart version upon it's release to this environement. This helps to ensure that the `worker` chart is always in a working state.

## Prefect Server

Similarly to the `helm` work queue, we run the latest prefect server & worker, automatically updated upon release. We run a similar set of test flows here to ensure the latest release of the `server` chart is is always in a working state.


To re-register all of these flows, first adjust your prefect profile to contain the following:
```
[profiles.server]
PREFECT_API_URL = "http://server.private.prefect.cloud/api"
```

Then run:
```shell
prefect profiles use server
prefect --no-prompt deploy --name "Flow Pauses" --name "Flow Results" --name "Flow Retries With Subflows" --name "Flow Retries" --name "Hello Tasks" --name "Secret Block" --name "Task Burst" --name "Task Results" --name "Task Retries"
```
