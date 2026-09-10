"""Real MCP -> loopback HTTP -> gateway admission; counted fixture upstream only."""
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from server.app.chickenbro.source_gateway import ChickenbroSourceGateway
from server.app.chickenbro.worker_gateway import WorkerToolServer
from server.chickenbro_native_mcp import query_source_gateway


class CountedSource:
    def __init__(self):
        self.calls = []

    def query(self, provider, target, options=None):
        self.calls.append((provider, target))
        return {"status": "source_reference", "facts": []}


class Recorder:
    def execute(self, operation, arguments, invoke):
        return invoke()


source = CountedSource()
host = WorkerToolServer(18794)
host.start()
gateway = host.register(ChickenbroSourceGateway(query_service=source), Recorder(), "source")
url = "http://127.0.0.1:18794/api/v2/internal/chickenbro/source-query"
os.environ["CHICKENBRO_SOURCE_GATEWAY_URL"] = url
tokens = []
try:
    token = gateway.issue_capability()
    tokens.append(token)
    os.environ["CHICKENBRO_SOURCE_GATEWAY_TOKEN"] = token
    for n in range(10):
        result = query_source_gateway("raiderio", f"https://raider.io/characters/us/area-52/fixture{n}")
        assert result["status"] == "source_reference"
    for provider, target, options in (
        ("raiderio", "https://raider.io/characters/us/area-52/eleventh", {}),
        ("warcraftlogs_character", "character", {"region": "us", "realm": "area-52", "name": "eleventh"}),
    ):
        result = query_source_gateway(provider, target, options)
        assert result["errorCode"] == "RESEARCH_BUDGET_EXCEEDED"
    assert len(source.calls) == 10
    other = gateway.issue_capability()
    tokens.append(other)
    os.environ["CHICKENBRO_SOURCE_GATEWAY_TOKEN"] = other
    assert query_source_gateway("raiderio", "https://raider.io/characters/us/area-52/eleventh")["status"] == "source_reference"
    assert len(source.calls) == 11
    for n in range(5):
        assert query_source_gateway("public_web", f"https://example.com/{n}")["status"] == "source_reference"
    result = query_source_gateway("public_web", "https://example.com/sixth")
    assert result["errorCode"] == "RESEARCH_BUDGET_EXCEEDED"
    assert len(source.calls) == 16
    gateway.revoke(other)
    request = Request(url, data=b'{"provider":"raiderio","target":"unused"}',
                      headers={"Content-Type": "application/json", "X-Chickenbro-Source-Gateway": other})
    try:
        urlopen(request, timeout=5)
        raise AssertionError("Revoked capability accepted")
    except HTTPError as error:
        assert error.code == 401
    assert len(source.calls) == 16
    result = {"passed": True, "transport": "real MCP source client and WorkerToolServer loopback HTTP",
              "upstream": "counted fixture; no external requests", "upstreamCalls": 16,
              "checks": ["ten admitted", "eleventh blocked before upstream", "cross-provider budget shared",
                         "independent capability admitted", "sixth web page blocked", "revoked capability HTTP 401"]}
    Path(__file__).with_suffix(".json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
finally:
    for token in tokens:
        gateway.revoke(token)
    host.close()
