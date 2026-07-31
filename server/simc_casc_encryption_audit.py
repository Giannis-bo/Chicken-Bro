"""Redacted instrumentation for SimC BLTE encryption handling."""

from __future__ import annotations

from typing import Any


def install_blte_encryption_audit(
    casc_module: Any,
    keyfile_module: Any,
) -> dict[str, Any]:
    chunk_type = getattr(casc_module, "BLTEChunk", None)
    method_name = "_BLTEChunk__process_encrypted"
    original = getattr(chunk_type, method_name, None)
    if chunk_type is None or not callable(original):
        raise ValueError("SimC BLTE encrypted-chunk handler is unavailable")
    if getattr(chunk_type, "_codex_encryption_audit_installed", False):
        raise ValueError("SimC BLTE encryption audit is already installed")
    state: dict[str, Any] = {
        "salsa20Available": (
            getattr(casc_module, "NO_DECRYPT", None) is False
        ),
        "events": [],
    }

    def instrumented(chunk: Any, data: bytes) -> Any:
        key_name = b""
        if isinstance(data, bytes) and len(data) >= 2:
            key_name_length = data[1]
            if (
                key_name_length == 8
                and len(data) >= 2 + key_name_length
            ):
                key_name = data[2:2 + key_name_length]
        key_available = (
            bool(key_name)
            and keyfile_module.find(key_name) is not None
        )
        result = original(chunk, data)
        state["events"].append(
            {
                "keyId": key_name.hex(),
                "outputBytes": int(
                    getattr(chunk, "output_length", 0)
                ),
                "keyAvailable": key_available,
                "decrypted": bool(
                    getattr(chunk, "is_decrypted", False)
                ),
                "extractionResult": bool(result),
            }
        )
        return result

    setattr(chunk_type, method_name, instrumented)
    setattr(chunk_type, "_codex_encryption_audit_installed", True)
    return state


def summarize_blte_encryption_audit(
    state: Any,
) -> dict[str, Any]:
    if (
        not isinstance(state, dict)
        or not isinstance(state.get("salsa20Available"), bool)
        or not isinstance(state.get("events"), list)
        or not all(isinstance(row, dict) for row in state["events"])
    ):
        raise ValueError("SimC BLTE encryption audit state is invalid")
    key_audits: dict[str, dict[str, Any]] = {}
    for event in state["events"]:
        key_id = str(event.get("keyId") or "")
        row = key_audits.setdefault(
            key_id,
            {
                "keyId": key_id,
                "chunkCount": 0,
                "outputBytes": 0,
                "keyAvailableChunkCount": 0,
                "decryptedChunkCount": 0,
            },
        )
        row["chunkCount"] += 1
        row["outputBytes"] += int(event.get("outputBytes") or 0)
        row["keyAvailableChunkCount"] += bool(
            event.get("keyAvailable")
        )
        row["decryptedChunkCount"] += bool(event.get("decrypted"))
    encrypted_chunk_count = len(state["events"])
    key_available_chunk_count = sum(
        bool(row.get("keyAvailable"))
        for row in state["events"]
    )
    decrypted_chunk_count = sum(
        bool(row.get("decrypted"))
        for row in state["events"]
    )
    return {
        "salsa20Available": state["salsa20Available"],
        "encryptedChunkCount": encrypted_chunk_count,
        "keyAvailableChunkCount": key_available_chunk_count,
        "decryptedChunkCount": decrypted_chunk_count,
        "zeroFallbackChunkCount": (
            encrypted_chunk_count - decrypted_chunk_count
        ),
        "keyAudits": [
            key_audits[key_id]
            for key_id in sorted(key_audits)
        ],
    }
