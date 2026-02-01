import uuid


_GUID_NAMESPACE = uuid.UUID("8b6d4c3e-6d50-4a11-9f2e-0a5e0f6a0c93")


def hash_guid(kind, event_id, key):
    name = f"{kind}:{event_id}:{key}"
    return str(uuid.uuid5(_GUID_NAMESPACE, name))
