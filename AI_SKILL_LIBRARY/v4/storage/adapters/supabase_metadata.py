"""Federated Free Storage Mesh - the Supabase metadata adapter.

Supabase is the mesh's metadata and object index (Spec S17/S18,
``policy.yaml`` ``metadata_service``). It is not a bulk object backend and it is
not an authority: GitHub stays canonical, and Spec S18 exists precisely so that
losing this service degrades the mesh instead of stopping it.

What this module deliberately does **not** do is the larger half of it.

**It creates nothing.** No project, no table, no bucket, no credential, at
import time, at construction time or at any other time. Spec S25 records that
the connected Supabase account currently has no projects, and ``policy.yaml``
records that creating one requires explicit approval which has not been given.
There is therefore no ``provision``, ``create_table``, ``ensure_table`` or
``migrate`` method to call by accident, no database driver imported, and no DDL
that this process could execute. The table contract below is *documentation for
a human who has been authorized to provision* - a shape to create by hand, not
a statement this code runs.

**It holds no credential.** The project URL is a bounded, validated string; the
key is never a parameter and never an attribute. What the constructor takes is
a zero-argument ``credential_provider``, called at the moment of a request and
never at import or construction, so the secret lives in the runtime secret
store and passes through a call frame rather than resting on an object that a
repr, a log line, a pickle or a debugger dump would spill. Spec S22 keeps keys
out of metadata table values, repository files, logs and checkpoints; the
cheapest way to honour that is to never be holding one.

**It opens no connection.** There is no HTTP client here. All I/O goes through
an injected ``transport`` callable, and without one the store is simply
unhealthy - which means every write and every read fails closed through the
base class, and ``can_perform_destructive_lifecycle`` answers ``False``. That
is not a stub standing in for a real implementation: it is the accurate state
of a metadata service that does not exist yet, and a mesh that reported
otherwise would be fabricating runtime evidence.

Validation is not repeated here. ``MetadataStore`` validates on the way in and
again on the way out, including rows this adapter receives from the transport -
a metadata table is a shared surface and a row is not trustworthy for having
been found.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from AI_SKILL_LIBRARY.v4.storage import AUTHORITY_FLAGS, CANONICAL_AUTHORITY
from AI_SKILL_LIBRARY.v4.storage import metadata as _metadata

AUTHORITY = False
ENCRYPTION_IMPLEMENTED_HERE = False

#: Spec S18/S25 and ``policy.yaml`` ``metadata_service``. Supabase is an index.
IS_CANONICAL_AUTHORITY = False
ROLE = "metadata_and_object_index_only"
BULK_OBJECT_BACKEND_ALLOWED = False
PROVIDER_ID = "supabase"

#: Nothing external is created by this module, and no approval to create
#: anything has been given. Stated as constants so that a test can assert it
#: rather than a reviewer having to read for it.
CREATES_EXTERNAL_RESOURCES = False
PROVISIONING_AUTHORIZED = False
PROJECT_EXISTS_VERIFIED = False

#: A metadata row is an index entry. The cap is the record bound from
#: ``metadata.py`` and not one byte more: Supabase stores pointers about
#: objects, never object content (Spec S17 "bulk object storage is not its main
#: role", ``policy.yaml`` ``bulk_object_backend_allowed: false``).
MAX_ROW_BYTES = _metadata.MAX_RECORD_BYTES

MAX_PROJECT_URL = 128

#: A project URL and nothing else: scheme, project ref, Supabase host. No
#: userinfo, so ``https://user:key@ref.supabase.co`` cannot smuggle a
#: credential into a field that gets logged; no path and no query, so
#: ``?apikey=`` has nowhere to live. ``\Z`` rather than ``$``, because Python's
#: ``$`` also matches before a trailing newline.
_PROJECT_URL_RE = re.compile(r"^https://[a-z0-9][a-z0-9-]{2,62}\.supabase\.(?:co|in)\Z")

#: The shape a human with provisioning authorization would create by hand. It is
#: a string in a docstring's role, never something this process runs: there is
#: no database driver imported here and no code path that could execute it.
#: ``manifest`` is the validated record and ``object_id`` its content-derived
#: key, which is why the primary key carries no name, path or private text.
TABLE_CONTRACT = """\
-- Provisioning is a human action requiring explicit authorization
-- (policy.yaml metadata_service.project_creation_requires_explicit_approval).
-- This is the contract to create by hand at that point. It is documentation:
-- nothing in this repository executes it.
storage_objects(
  object_id   text primary key,
  manifest    jsonb not null,
  updated_at  timestamptz not null
)
-- object_id is 'obj_' + SHA-256 of the content, so the key carries no name,
-- path or private text. manifest holds a validated metadata record and never
-- object content, credentials or key material (Spec S18/S22).
"""

#: The operations the adapter asks a transport to perform. A closed vocabulary:
#: an adapter that could ask for an arbitrary operation is an adapter through
#: which an arbitrary statement could be sent.
OPERATIONS = ("health", "upsert", "select", "select_all")


class SupabaseMetadataStore(_metadata.MetadataStore):
    """A metadata store backed by a Supabase project that does not exist yet.

    ``project_url`` and ``credential_provider`` arrive by runtime injection.
    ``transport`` is the only way out of this process; without it the store is
    unhealthy and every operation fails closed.
    """

    def __init__(self, *, project_url, credential_provider, transport=None):
        self._project_url = self._validated_url(project_url)
        if not callable(credential_provider):
            raise ValueError(
                "credential_provider must be a zero-argument callable that "
                "fetches the key from the runtime secret store at call time. A "
                "literal key is refused: a secret passed as a value becomes an "
                "attribute, and an attribute reaches a repr, a log and a "
                "traceback (Spec S22)")
        if transport is not None and not callable(transport):
            raise ValueError("transport must be a callable or None")
        #: Held as a callable, never as a value. Nothing is fetched here.
        self._credential_provider = credential_provider
        self._transport = transport

    @staticmethod
    def _validated_url(project_url):
        if not isinstance(project_url, str):
            raise ValueError(
                f"project_url must be a string, got {type(project_url).__name__}")
        if len(project_url) > MAX_PROJECT_URL:
            raise ValueError(
                f"project_url is {len(project_url)} characters, over the "
                f"{MAX_PROJECT_URL}-character bound; a URL field long enough to "
                "hold a token is a URL field that will one day hold one")
        if not _PROJECT_URL_RE.match(project_url):
            raise ValueError(
                "project_url must be https://<project-ref>.supabase.co with no "
                "userinfo, path or query: 'https://user:key@ref.supabase.co' "
                "and '...?apikey=...' are exactly how a credential ends up in a "
                "config file and then in a log")
        return project_url

    def __repr__(self):
        transport = "injected" if self._transport is not None else "none"
        return (f"<SupabaseMetadataStore project={self._project_url} "
                f"transport={transport}>")

    # -- transport -----------------------------------------------------------

    def _call(self, operation, payload):
        if operation not in OPERATIONS:
            raise ValueError(f"unknown metadata operation {operation!r}")
        if self._transport is None:
            raise _metadata.MetadataStoreUnavailable(
                "no transport is injected, so this metadata store cannot be "
                "reached. Spec S25: the connected Supabase account has no "
                "projects and none is created here; an index that does not "
                "exist is unhealthy rather than empty")
        # The credential is fetched at call time and handed straight to the
        # transport as a keyword argument. It is never placed in the payload,
        # which is the thing a transport is most likely to log.
        return self._transport(operation, payload,
                               project_url=self._project_url,
                               credential=self._credential_provider())

    # -- MetadataStore hooks --------------------------------------------------

    def _probe_healthy(self):
        if self._transport is None:
            return False
        return self._call("health", {}) is True

    def _put_record(self, object_id, record):
        row = {"object_id": object_id, "record": record}
        self._call("upsert", row)

    def _get_record(self, object_id):
        row = self._call("select", {"object_id": object_id})
        if row is None:
            return None
        if not isinstance(row, Mapping):
            raise _metadata.MetadataStoreError(
                f"the transport returned {type(row).__name__} where a metadata "
                "row was expected")
        return row

    def _all_records(self):
        rows = self._call("select_all", {})
        if not isinstance(rows, list):
            raise _metadata.MetadataStoreError(
                f"the transport returned {type(rows).__name__} where a list of "
                "metadata rows was expected; an unrecognised answer is not an "
                "empty index")
        return rows


__all__ = [
    "AUTHORITY", "AUTHORITY_FLAGS", "CANONICAL_AUTHORITY",
    "ENCRYPTION_IMPLEMENTED_HERE", "IS_CANONICAL_AUTHORITY", "ROLE",
    "PROVIDER_ID", "BULK_OBJECT_BACKEND_ALLOWED", "CREATES_EXTERNAL_RESOURCES",
    "PROVISIONING_AUTHORIZED", "PROJECT_EXISTS_VERIFIED", "MAX_ROW_BYTES",
    "MAX_PROJECT_URL", "TABLE_CONTRACT", "OPERATIONS", "SupabaseMetadataStore",
]
