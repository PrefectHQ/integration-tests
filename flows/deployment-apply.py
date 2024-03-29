import anyio
import prefect
from packaging.version import Version
from prefect.deployments import Deployment
from prefect.utilities.callables import parameter_schema


@prefect.flow
def deployment_apply_entry(name: str = "world"):
    prefect.get_run_logger().info(f"Hello {name}!")


async def apply_deployment(deployment):
    async with prefect.get_client() as client:
        flow_id = await client.create_flow_from_name(deployment.flow_name)
        await client.create_deployment(flow_id=flow_id, name=deployment.name)


if __name__ == "__main__":
    # Create deployment
    if Version(prefect.__version__) < Version("2.1.0"):
        deployment = Deployment(
            name="test-deployment",
            flow_name=deployment_apply_entry.name,
            parameter_openapi_schema=parameter_schema(deployment_apply_entry),
        )
        anyio.run(apply_deployment, deployment)
    else:
        deployment = Deployment.build_from_flow(
            flow=deployment_apply_entry, name="test-deployment"
        )
        deployment.apply()

    # Update deployment
    deployment.tags = ["test"]
    if Version(prefect.__version__) >= Version("2.1.0"):
        deployment.apply()
