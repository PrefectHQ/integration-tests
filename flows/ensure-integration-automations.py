import asyncio
import textwrap
from typing import Any

from prefect import flow, get_client, get_run_logger


async def create_or_replace_automation(automation: dict[str, Any]):
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


@flow
async def ensure_integrations_automations():
    NOTIFICATION_BLOCK = "29d35854-71ee-4381-bc97-1a97731c43aa"

    await create_or_replace_automation(
        {
            "name": "integration-flows-failed",
            "description": (
                "Notifies when any flow run that is expected to succeed has failed "
                "[created by the integration-tests]"
            ),
            "trigger": {
                "posture": "Reactive",
                "expect": ["prefect.flow-run.Failed", "prefect.flow-run.Crashed"],
                "threshold": 1,
                "within": 0,
                "match_related": {
                    "prefect.resource.id": "prefect.tag.expected:success",
                    "prefect.resource.role": "tag",
                },
            },
            "actions": [
                {
                    "type": "send-notification",
                    "block_document_id": NOTIFICATION_BLOCK,
                    "subject": "Prefect flow run failed",
                    "body": textwrap.dedent(
                        """
                        Flow run {{ flow.name }}/{{ flow_run.name }} observed in state `{{ flow_run.state.name }}` at {{ flow_run.state.timestamp }}.
                        Flow ID: {{ flow_run.flow_id }}
                        Flow run ID: {{ flow_run.id }}
                        Flow run URL: {{ flow_run|ui_url }}
                        State message: {{ flow_run.state.message }}
                    """
                    ).strip(),
                }
            ],
        }
    )

    await create_or_replace_automation(
        {
            "name": "integration-flows-succeeded",
            "description": (
                "Notifies when any flow run that is expected to fail has succeeded "
                "[created by the integration-tests]"
            ),
            "trigger": {
                "posture": "Reactive",
                "expect": ["prefect.flow-run.Completed"],
                "threshold": 1,
                "within": 0,
                "match_related": {
                    "prefect.resource.id": "prefect.tag.expected:failure",
                    "prefect.resource.role": "tag",
                },
            },
            "actions": [
                {
                    "type": "send-notification",
                    "block_document_id": NOTIFICATION_BLOCK,
                    "subject": "Prefect flow run failed",
                    "body": textwrap.dedent(
                        """
                        Flow run {{ flow.name }}/{{ flow_run.name }} observed in state `{{ flow_run.state.name }}` at {{ flow_run.state.timestamp }}.
                        Flow ID: {{ flow_run.flow_id }}
                        Flow run ID: {{ flow_run.id }}
                        Flow run URL: {{ flow_run|ui_url }}
                        State message: {{ flow_run.state.message }}
                    """
                    ).strip(),
                }
            ],
        }
    )

    await create_or_replace_automation(
        {
            "name": "integration-flows-stuck-pending",
            "description": (
                "Notifies when any flow run has been stuck Pending [created by the "
                "integration-tests]"
            ),
            "trigger": {
                "posture": "Proactive",
                "after": ["prefect.flow-run.Pending"],
                "expect": [
                    "prefect.flow-run.Running",
                    "prefect.flow-run.Crashed",
                    "prefect.flow-run.Failed",
                    "prefect.flow-run.Completed",
                    "prefect.flow-run.Paused",
                ],
                "for_each": ["prefect.resource.id"],
                "threshold": 1,
                "within": 60,
            },
            "actions": [
                {
                    "type": "send-notification",
                    "block_document_id": NOTIFICATION_BLOCK,
                    "subject": "Prefect flow run stuck pending",
                    "body": textwrap.dedent(
                        """
                        Flow run {{ flow.name }}/{{ flow_run.name }} observed in state `{{ flow_run.state.name }}` at {{ flow_run.state.timestamp }}.
                        Flow ID: {{ flow_run.flow_id }}
                        Flow run ID: {{ flow_run.id }}
                        Flow run URL: {{ flow_run|ui_url }}
                        State message: {{ flow_run.state.message }}
                    """
                    ).strip(),
                }
            ],
        }
    )

    await create_or_replace_automation(
        {
            "name": "integration-flows-stuck-running",
            "description": (
                "Notifies when any flow run has been stuck Running [created by the "
                "integration-tests]"
            ),
            "trigger": {
                "posture": "Proactive",
                "after": ["prefect.flow-run.Running"],
                "expect": [
                    "prefect.flow-run.Crashed",
                    "prefect.flow-run.Failed",
                    "prefect.flow-run.Completed",
                    "prefect.flow-run.Paused",
                ],
                "for_each": ["prefect.resource.id"],
                "threshold": 1,
                "within": 600,
            },
            "actions": [
                {
                    "type": "send-notification",
                    "block_document_id": NOTIFICATION_BLOCK,
                    "subject": "Prefect flow run stuck running",
                    "body": textwrap.dedent(
                        """
                        Flow run {{ flow.name }}/{{ flow_run.name }} observed in state `{{ flow_run.state.name }}` at {{ flow_run.state.timestamp }}.
                        Flow ID: {{ flow_run.flow_id }}
                        Flow run ID: {{ flow_run.id }}
                        Flow run URL: {{ flow_run|ui_url }}
                        State message: {{ flow_run.state.message }}
                    """
                    ).strip(),
                }
            ],
        }
    )

    await create_or_replace_automation(
        {
            "name": "integration-work-pool-not-ready",
            "description": (
                "Notifies when a work pool has stayed not-ready for too long [created by the "
                "integration-tests]"
            ),
            "trigger": {
                "posture": "Proactive",
                "after": ["prefect.work-pool.not_ready"],
                "expect": ["prefect.work-pool.ready"],
                "for_each": ["prefect.resource.id"],
                "threshold": 1,
                "within": 600,
            },
            "actions": [
                {
                    "type": "send-notification",
                    "block_document_id": NOTIFICATION_BLOCK,
                    "subject": "Prefect work pool '{{ work_pool.name }}' has entered status '{{ work_pool.status }}'",
                    "body": textwrap.dedent(
                        """
                        Name: {{ work_pool.name }}
                        Status: {{ work_pool.status }}
                        URL: {{ work_pool|ui_url }}
                    """
                    ).strip(),
                }
            ],
        }
    )


if __name__ == "__main__":
    asyncio.run(ensure_integrations_automations())
