import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator
from uuid import uuid4

from pydantic import SecretStr
from prefect import flow, get_client, get_run_logger
from prefect.blocks.webhook import Webhook
from prefect.concurrency.asyncio import concurrency
from prefect.events import Event
from prefect.events.clients import get_events_client, get_events_subscriber
from prefect.events.filters import (
    EventFilter,
    EventNameFilter,
    EventOccurredFilter,
    EventResourceFilter,
)

# The integration tests are scheduled to run every 5 minutes, so we should be timing
# out more quickly than that to avoid multiple runs stacking up
INTEGRATION_TEST_INTERVAL = 5 * 60
INTEGRATION_TEST_TIMEOUT = INTEGRATION_TEST_INTERVAL - 60


async def setup_webhook() -> tuple[str, str]:
    """Set up webhook and webhook block. Returns (webhook_id, block_id)."""
    logger = get_run_logger()
    webhook_name = "integration-test-webhook"
    block_name = "integration-test-webhook-block"
    expected_template = """{
                    "event": "integration.webhook.called",
                    "resource": {
                        "prefect.resource.id": "{{ body.resource_id | default('unknown') }}",
                        "prefect.resource.name": "Integration Test Webhook"
                    }
                }"""

    async with get_client() as prefect:
        # Check if webhook exists and is configured correctly
        webhook_id = None
        webhook_slug = None
        response = await prefect._client.post("/webhooks/filter")
        response.raise_for_status()
        for webhook in response.json():
            if webhook["name"] == webhook_name:
                # Found existing webhook, check if it's configured correctly
                if webhook.get("template") == expected_template:
                    webhook_id = webhook["id"]
                    webhook_slug = webhook["slug"]
                    logger.info("Using existing webhook: %s", webhook_id)
                else:
                    # Template is wrong, delete and recreate
                    await prefect._client.delete(f"/webhooks/{webhook['id']}")
                    logger.info("Deleted webhook with incorrect template")
                break

        # Create webhook if it doesn't exist
        if not webhook_id:
            response = await prefect._client.post(
                "/webhooks/",
                json={
                    "name": webhook_name,
                    "template": expected_template,
                    "description": "Integration test webhook for validating automation actions",
                },
            )
            response.raise_for_status()
            webhook = response.json()
            webhook_id = webhook["id"]
            webhook_slug = webhook["slug"]
            logger.info("Created webhook: %s", webhook_id)

        # Get API host for webhook URL
        from urllib.parse import urlparse

        api_url = str(prefect._client.base_url)
        parsed = urlparse(api_url)
        webhook_url = f"{parsed.scheme}://{parsed.netloc}/hooks/{webhook_slug}"

        # Create/update webhook block
        webhook_block = Webhook(url=SecretStr(webhook_url), method="POST")
        await webhook_block.save(name=block_name, overwrite=True)

        # Get block ID
        response = await prefect._client.post(
            "/block_documents/filter",
            json={"block_documents": {"name": {"any_": [block_name]}}},
        )
        response.raise_for_status()
        block_id = response.json()[0]["id"]
        logger.info("Webhook block ready: %s", block_id)

        return webhook_id, block_id


@asynccontextmanager
async def setup_automation(
    resource_id: str, webhook_block_id: str
) -> AsyncGenerator[str, None]:
    """Create automation with webhook action. Returns automation_id."""
    logger = get_run_logger()
    name_prefix = "actions-test-automation"

    async with get_client() as prefect:
        # Clean up old automations
        response = await prefect._client.post("/automations/filter")
        response.raise_for_status()
        for existing in response.json():
            if str(existing["name"]).startswith(name_prefix):
                created = datetime.fromisoformat(
                    existing["created"].replace("Z", "+00:00")
                )
                age = datetime.now(timezone.utc) - created
                if age > timedelta(seconds=INTEGRATION_TEST_INTERVAL * 3):
                    await prefect._client.delete(f"/automations/{existing['id']}")
                    logger.info("Deleted old automation: %s", existing["name"])

        # Create new automation
        automation_config = {
            "name": f"{name_prefix}:{uuid4()}",
            "description": "Tests that automation actions (webhooks) are working",
            "trigger": {
                "posture": "Reactive",
                "expect": ["integration.test.trigger"],
                "match": {"prefect.resource.id": resource_id},
                "threshold": 1,
                "within": 0,
            },
            "actions": [
                {
                    "type": "call-webhook",
                    "block_document_id": webhook_block_id,
                    "payload": {
                        "resource_id": resource_id,
                        "test": "automation-actions",
                    },
                }
            ],
        }

        response = await prefect._client.post("/automations", json=automation_config)
        response.raise_for_status()
        automation = response.json()
        automation_id = automation["id"]
        logger.info("Created automation: %s", automation_id)

        # Wait for automation to be loaded
        logger.info("Waiting 5s for automation to be loaded...")
        await asyncio.sleep(5)

        try:
            yield automation_id
        finally:
            response = await prefect._client.delete(f"/automations/{automation['id']}")
            if response.status_code == 404:
                logger.info("Automation %s already deleted", automation["id"])
                return
            response.raise_for_status()


async def wait_for_event(
    event_names: list[str], resource_filter: list[str] | None = None, timeout: int = 30
) -> Event | None:
    """Generic event waiter. Returns the first matching event or None on timeout."""
    filter = EventFilter(
        occurred=EventOccurredFilter(since=datetime.now(timezone.utc)),
        event=EventNameFilter(name=event_names),
    )

    if resource_filter:
        filter.resource = EventResourceFilter(id=resource_filter)

    async with get_events_subscriber(filter=filter) as subscriber:
        try:
            async with asyncio.timeout(timeout):
                async for event in subscriber:
                    return event
        except asyncio.TimeoutError:
            return None

    return None


@flow(timeout_seconds=INTEGRATION_TEST_TIMEOUT)
async def assess_automation_actions():
    """
    Test that automations → actions → webhooks work end-to-end.

    Flow:
    1. Create webhook that emits events
    2. Create automation that calls webhook on trigger
    3. Emit trigger event
    4. Verify: trigger fired → action executed → webhook called
    """
    logger = get_run_logger()

    async with concurrency(
        "assess_automation_actions", timeout_seconds=INTEGRATION_TEST_TIMEOUT
    ):
        # Test setup
        test_id = str(uuid4())
        resource_id = f"integration:actions:{test_id}"
        logger.info("Starting test run: %s", test_id)

        # Create webhook and block
        webhook_id, webhook_block_id = await setup_webhook()

        # Create automation with webhook action
        async with setup_automation(resource_id, webhook_block_id) as automation_id:
            # Start event listeners
            trigger_task = asyncio.create_task(
                wait_for_event(
                    ["prefect-cloud.automation.triggered"],
                    [f"prefect-cloud.automation.{automation_id}"],
                    timeout=30,
                )
            )

            action_task = asyncio.create_task(
                wait_for_event(
                    [
                        "prefect-cloud.automation.action.executed",
                        "prefect-cloud.automation.action.failed",
                    ],
                    [f"prefect-cloud.automation.{automation_id}"],
                    timeout=30,
                )
            )

            webhook_task = asyncio.create_task(
                wait_for_event(
                    ["integration.webhook.called", "prefect-cloud.webhook.failed"],
                    [resource_id, f"prefect-cloud.webhook.{webhook_id}"],
                    timeout=60,
                )
            )

            # Emit trigger event
            logger.info("Emitting trigger event...")
            async with get_events_client() as events:
                await events.emit(
                    Event(
                        event="integration.test.trigger",
                        resource={"prefect.resource.id": resource_id},
                        payload={"test": "automation-actions"},
                    )
                )

            # Collect results
            logger.info("Waiting for events...")
            trigger_event = await trigger_task
            action_event = await action_task
            webhook_event = await webhook_task

            # Validate results
            if not trigger_event:
                raise Exception(
                    "❌ Automation never triggered. Check trigger configuration."
                )
            logger.info("✓ Automation triggered")

            if not action_event:
                raise Exception(
                    "❌ Action never executed after trigger. "
                    "The actions subsystem may be down."
                )

            if action_event.event == "prefect-cloud.automation.action.failed":
                reason = (
                    action_event.payload.get("reason", "Unknown")
                    if action_event.payload
                    else "Unknown"
                )
                status = (
                    action_event.payload.get("status_code", "Unknown")
                    if action_event.payload
                    else "Unknown"
                )
                raise Exception(f"❌ Action failed (HTTP {status}): {reason}")
            logger.info("✓ Action executed")

            if not webhook_event:
                raise Exception(
                    "❌ Webhook never responded. Check webhook configuration."
                )

            if webhook_event.event == "prefect-cloud.webhook.failed":
                error = (
                    webhook_event.payload.get("error", "Unknown")
                    if webhook_event.payload
                    else "Unknown"
                )
                raise Exception(f"❌ Webhook failed: {error}")
            logger.info("✓ Webhook called")

            logger.info("✅ SUCCESS! Automation → Action → Webhook chain validated")


if __name__ == "__main__":
    asyncio.run(assess_automation_actions())
