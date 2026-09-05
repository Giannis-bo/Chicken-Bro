"""Reserved test owners: never map them to real WeChat identities."""
from uuid import NAMESPACE_URL, uuid5


TEST_ACCOUNT_IDS = {
    account: uuid5(NAMESPACE_URL, f"https://chickenbro.cloud/test-accounts/{account}")
    for account in ("A", "B")
}
