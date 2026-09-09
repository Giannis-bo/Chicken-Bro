from server.app.identity.domain import Principal


class InMemoryIdentityRepository:
    def __init__(self):
        self.identities = {}
        self.users = {}
        self.auth_sessions = {}
        self.revocations = []

    def issue_auth_session(self, *, token_hash, user_id, kind, expires_at):
        self.auth_sessions[token_hash] = {
            "user_id": user_id,
            "kind": kind,
            "expires_at": expires_at,
            "revoked_at": None,
        }


    def resolve_auth_session(self, *, token_hash, kind, now):
        record = self.auth_sessions.get(token_hash)
        if (
            record is None
            or record["kind"] != kind
            or record["expires_at"] <= now
            or record["revoked_at"] is not None
        ):
            return None
        return Principal(user_id=record["user_id"], session_kind=kind)


    def revoke_auth_session(self, *, token_hash, kind, now):
        record = self.auth_sessions.get(token_hash)
        if record is not None and record["kind"] == kind:
            record["revoked_at"] = now
            self.revocations.append((token_hash, kind))


    def get_public_user(self, user_id):
        return self.users.get(user_id)

