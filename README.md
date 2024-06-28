We run an assortment of `integration tests` flows for the purpose of evaluating the health of our systems. Defined below are the locations in which certain flows run.

## Prefect Dev/Stg - integration-tests workspace
We run the following flows on a regular interval in both the dev & stg environments. Unexpected failures are reported to the relevant environment channel `#alerts-ENV-cloud2`.

flows:
- flow-pauses
- flow-results
- flow-retries-with-subflows
- flow-retries
- hello-tasks
- hello-world
- secret-block
- task-bursts
- task-results
- task-retries


## Prefect Prd - integration-tests workspace

### integration-tests workqueue
flows:
- automations-tracer

### helm workqueue
An always up-to-date worker is polling this workqueue. We run simple flows here to ensure the lastest Helm release of the `worker` chart is functioning as expected

flows:
- hello-tasks
- hello-world

## Prefect Server
Similarly to the `helm` workqueue, we are running an always up-to-date server/worker combo. We run a similar set of test flows here to ensure the latest Helm release of the `server` chart is functioning as expected.

flows:
- flow-pauses
- flow-results
- flow-retries-with-subflows
- flow-retries
- hello-tasks
- hello-world
- secret-block
- task-bursts
- task-results
- task-retries

To re-register all of these flows, first adjust your prefect profile to contain the following:
```
[profiles.server]
PREFECT_API_URL = "http://server.private.prefect.cloud/api"
```

Then run:
```
prefect profiles use server
prefect --no-prompt deploy --name "Flow Pauses" --name "Flow Results" --name "Flow Retries With Subflows" --name "Flow Retries" --name "Hello Tasks" --name "Hello World" --name "Secret Block" --name "Task Burst" --name "Task Results" --name "Task Retries"
```
