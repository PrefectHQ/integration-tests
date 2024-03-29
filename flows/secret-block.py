from prefect import flow, task
from prefect.blocks.system import Secret


@task
def save_secret(name, value):
    Secret(value=value).save(name=name, overwrite=True)


@task
def load_secret(name):
    return Secret.load(name)


@flow
def secret_block_entry():
    save_secret("my-super-secret", "super secret contents")

    secret: Secret = load_secret("my-super-secret")
    assert secret.get() == "super secret contents", secret


if __name__ == "__main__":
    secret_block_entry()
