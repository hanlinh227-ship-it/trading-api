"""Federated Free Storage Mesh - adapter boundaries.

An adapter is the thin edge between the mesh's pure control plane and something
outside the process. Nothing in this package creates an account, a project, a
bucket, a table or a credential, and nothing in it opens a connection on its
own: every adapter takes its transport by injection at runtime and is simply
unhealthy until it has one. That is not a placeholder - it is the honest state
of a mesh whose providers have not been probed and whose connected Supabase
account has no projects (Spec S25). Provisioning is a human action requiring
explicit authorization (``policy.yaml``
``metadata_service.project_creation_requires_explicit_approval``).

Importing this package performs no I/O.
"""

from __future__ import annotations

AUTHORITY = False

#: Stated at the package level so that it is true of every adapter added later,
#: not only of the one that happens to be here today.
CREATES_EXTERNAL_RESOURCES = False
PROVISIONING_AUTHORIZED = False

__all__ = ["AUTHORITY", "CREATES_EXTERNAL_RESOURCES", "PROVISIONING_AUTHORIZED"]
