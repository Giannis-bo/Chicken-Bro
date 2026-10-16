"""Account-owned character shortcuts. Snapshots and simulation history stay immutable."""
import re
from urllib.parse import quote
from uuid import uuid4

from server.app.simulation.domain import SourceProvider, SourceReadiness


REGIONS = frozenset({"cn", "us", "eu", "kr", "tw"})


def character_source_url(name: str, realm: str, region: str = "cn") -> str:
    from server.app.simulation.application import SimulationApplicationError

    values = (name, realm, region)
    if (any(not isinstance(value, str) or re.search(r"[\x00-\x1f\x7f/\\?#%|]", value) for value in values)
            or not 1 <= len(name.strip()) <= 64 or not 1 <= len(realm.strip()) <= 128
            or region.strip().lower() not in REGIONS):
        raise SimulationApplicationError("INVALID_CHARACTER", "请填写有效的角色名称、服务器和地区")
    return "https://raider.io/characters/" + "/".join(
        quote(value.strip(), safe="-_.~") for value in (region.lower(), realm, name)
    )


class CharacterBindings:
    def __init__(self, repository):
        self._repository = repository

    def read(self, principal):
        return self._repository.read_characters(principal.user_id)

    def bind(self, principal, snapshot):
        from server.app.simulation.application import SimulationApplicationError

        if snapshot.user_id != principal.user_id:
            raise SimulationApplicationError("SNAPSHOT_NOT_FOUND", "snapshot not found")
        character = snapshot.snapshot.get("character", {})
        if (snapshot.provider is not SourceProvider.RAIDERIO
                or snapshot.readiness not in {SourceReadiness.READY_FOR_SIMC, SourceReadiness.INCOMPLETE_FOR_SIMC}
                or any(not isinstance(character.get(key), str) or not character[key].strip()
                       for key in ("name", "realm", "region"))
                or character["region"].lower() not in REGIONS):
            raise SimulationApplicationError("CHARACTER_UNAVAILABLE", "读取到角色资料后才能绑定")
        item = {
            "id": str(uuid4()), "name": character["name"][:64],
            "realm": character["realm"][:128], "region": character["region"].lower(),
            "sourceUrl": snapshot.source_url,
        }
        def operation(state):
            existing = next((row for row in state["items"] if all(
                row[key].casefold() == item[key].casefold() for key in ("name", "realm", "region"))), None)
            if existing:
                return {"items": state["items"], "selectedId": existing["id"]}
            if len(state["items"]) >= 3:
                raise SimulationApplicationError("CHARACTER_LIMIT_REACHED", "最多绑定 3 个角色，请先解绑一个角色")
            return {"items": [*state["items"], item], "selectedId": item["id"]}
        return self._repository.mutate_characters(principal.user_id, operation)

    def change(self, principal, character_id, *, unbind=False):
        from server.app.simulation.application import SimulationApplicationError

        key = str(character_id)
        def operation(state):
            if not any(item["id"] == key for item in state["items"]):
                raise SimulationApplicationError("CHARACTER_NOT_BOUND", "绑定角色不存在")
            if not unbind:
                return {**state, "selectedId": key}
            remaining = [item for item in state["items"] if item["id"] != key]
            selected = state["selectedId"]
            if selected == key:
                selected = remaining[0]["id"] if remaining else None
            return {"items": remaining, "selectedId": selected}
        return self._repository.mutate_characters(principal.user_id, operation)
