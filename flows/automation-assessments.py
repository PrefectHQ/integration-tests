import asyncio
from typing import Any
from uuid import uuid4

from prefect import flow, get_client, get_run_logger
from prefect.events import Event
from prefect.events.clients import PrefectCloudEventsClient, PrefectCloudEventSubscriber
from prefect.events.filters import EventFilter, EventNameFilter, EventResourceFilter


async def create_or_replace_automation(automation: dict[str, Any]) -> dict[str, Any]:
    logger = get_run_logger()

    async with get_client() as prefect:
        response = await prefect._client.post("/automations/filter")
        response.raise_for_status()
        for existing in response.json():
            if existing["name"] == automation["name"]:
                await prefect._client.delete(f"/automations/{existing['id']}")

        response = await prefect._client.post("/automations", json=automation)
        response.raise_for_status()

        automation = response.json()
        logger.info("Created automation %s", automation["id"])
        return automation


async def wait_for_event(event: str, resource_id: str) -> Event:
    logger = get_run_logger()

    filter = EventFilter(
        event=EventNameFilter(name=[]),
        resource=EventResourceFilter(id=[resource_id]),
    )
    async with PrefectCloudEventSubscriber(filter=filter) as subscriber:
        async for event in subscriber:
            logger.info(event)
            return event

    raise Exception("Disconnected without an event")


@flow
async def assess_reactive_automation():
    expected_resource = {"prefect.resource.id": f"integration:reactive:{uuid4()}"}
    automation = await create_or_replace_automation(
        {
            "name": "reactive-automation",
            "trigger": {
                "posture": "Reactive",
                "expect": ["integration.example.event"],
                "match": expected_resource,
                "threshold": 5,
                "within": 60,
            },
            "actions": [{"type": "do-nothing"}],
        }
    )

    listener = asyncio.create_task(
        wait_for_event(
            "prefect-cloud.automation.triggered",
            f"prefect-cloud.automation.{automation['id']}",
        )
    )

    async with PrefectCloudEventsClient() as events:
        for i in range(5):
            await events.emit(
                Event(
                    event="integration.example.event",
                    resource=expected_resource,
                    payload={"iteration": i},
                )
            )

    # Wait until we see the automation triggered event, or fail if it takes longer
    # than 60 seconds.  The reactive trigger should fire almost immediately.
    async with asyncio.timeout(60):
        await listener


@flow
async def assess_proactive_automation():
    expected_resource = {"prefect.resource.id": f"integration:proactive:{uuid4()}"}
    automation = await create_or_replace_automation(
        {
            "name": "proactive-automation",
            "trigger": {
                "posture": "Proactive",
                "expect": ["integration.example.event"],
                # Doing it for_each resource ID should prevent it from firing endlessly
                # while the integration tests are _not_ running
                "for_each": ["prefect.resource.id"],
                "match": expected_resource,
                "threshold": 5,
                "within": 15,
            },
            "actions": [{"type": "do-nothing"}],
        }
    )

    listener = asyncio.create_task(
        wait_for_event(
            "prefect-cloud.automation.triggered",
            f"prefect-cloud.automation.{automation['id']}",
        )
    )

    async with PrefectCloudEventsClient() as events:
        for i in range(2):  # not enough events to close the automation
            await events.emit(
                Event(
                    event="integration.example.event",
                    resource=expected_resource,
                    payload={"iteration": i},
                )
            )

    # Wait until we see the automation triggered event, or fail if it takes longer
    # than 60 seconds.  The proactive trigger should take a little over 15s to fire.
    async with asyncio.timeout(60):
        await listener


@flow
async def assess_compound_automation():
    expected_resource = {"prefect.resource.id": f"integration:compound:{uuid4()}"}
    automation = await create_or_replace_automation(
        {
            "name": "compound-automation",
            "trigger": {
                "type": "compound",
                "require": "all",
                "within": 60,
                "triggers": [
                    {
                        "posture": "Reactive",
                        "expect": ["integration.example.event.A"],
                        "match": expected_resource,
                        "threshold": 5,
                        "within": 60,
                    },
                    {
                        "posture": "Reactive",
                        "expect": ["integration.example.event.B"],
                        "match": expected_resource,
                        "threshold": 5,
                        "within": 60,
                    },
                ],
            },
            "actions": [{"type": "do-nothing"}],
        }
    )

    listener = asyncio.create_task(
        wait_for_event(
            "prefect-cloud.automation.triggered",
            f"prefect-cloud.automation.{automation['id']}",
        )
    )

    async with PrefectCloudEventsClient() as events:
        for i in range(5):
            await events.emit(
                Event(
                    event="integration.example.event.A",
                    resource=expected_resource,
                    payload={"iteration": i},
                )
            )
            await events.emit(
                Event(
                    event="integration.example.event.B",
                    resource=expected_resource,
                    payload={"iteration": i},
                )
            )

    # Wait until we see the automation triggered event, or fail if it takes longer
    # than 60 seconds.  The compound trigger should fire almost immediately.
    async with asyncio.timeout(60):
        await listener


@flow
async def assess_sequence_automation():
    expected_resource = {"prefect.resource.id": f"integration:sequence:{uuid4()}"}
    automation = await create_or_replace_automation(
        {
            "name": "sequence-automation",
            "trigger": {
                "type": "sequence",
                "within": 60,
                "triggers": [
                    {
                        "posture": "Reactive",
                        "expect": ["integration.example.event.A"],
                        "match": expected_resource,
                        "threshold": 5,
                        "within": 60,
                    },
                    {
                        "posture": "Reactive",
                        "expect": ["integration.example.event.B"],
                        "match": expected_resource,
                        "threshold": 5,
                        "within": 60,
                    },
                ],
            },
            "actions": [{"type": "do-nothing"}],
        }
    )

    listener = asyncio.create_task(
        wait_for_event(
            "prefect-cloud.automation.triggered",
            f"prefect-cloud.automation.{automation['id']}",
        )
    )

    async with PrefectCloudEventsClient() as events:
        for i in range(5):
            await events.emit(
                Event(
                    event="integration.example.event.A",
                    resource=expected_resource,
                    payload={"iteration": i},
                )
            )

    # give some space between events to make sure the sequence is clear
    await asyncio.sleep(5)

    async with PrefectCloudEventsClient() as events:
        for i in range(5):
            await events.emit(
                Event(
                    event="integration.example.event.B",
                    resource=expected_resource,
                    payload={"iteration": i},
                )
            )

    # Wait until we see the automation triggered event, or fail if it takes longer
    # than 60 seconds.  The compound trigger should fire almost immediately.
    async with asyncio.timeout(60):
        await listener


if __name__ == "__main__":
    # asyncio.run(assess_reactive_automation())
    # asyncio.run(assess_proactive_automation())
    # asyncio.run(assess_compound_automation())
    asyncio.run(assess_sequence_automation())
