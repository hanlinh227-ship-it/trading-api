#!/usr/bin/env python3
"""Deploy an exact, already-validated commit to the existing Railway service.

    railway_deploy_latest.py --sha <commit> --timeout 900

Railway's GitHub integration redeploys this service only when its own source
directory changes, so a main commit that touches nothing under
`crypto-research-gateway/` never reaches production and the running deployment
keeps an older SHA. That is correct behaviour and the repository's canonical CI
already verifies the gateway SOURCE TREE rather than the commit label. This adds
the other half: after canonical validation passes on main, ask Railway to deploy
that exact commit, so the label stops drifting too.

**The API is verified at runtime, not assumed.** Railway's docs are not
reachable from the environment this was written in, so rather than hard-code a
mutation name I might be misremembering, the script introspects the schema,
picks the first mutation from a declared preference list that actually exists
AND accepts a commit argument, and prints what it chose. If none of them exist
it fails closed and prints the deploy-shaped mutations the API does offer, which
is a fixable message rather than an opaque one.

Nothing here creates a service, changes variables, domains, the root directory,
the healthcheck, the port, or the GitHub source connection. It deploys an
existing service instance at a named commit and reports what happened.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ENDPOINT = os.environ.get("RAILWAY_API_URL", "https://backboard.railway.com/graphql/v2")

#: Mutations that deploy an existing service instance, best first. Ordered by
#: how precisely each expresses "deploy THIS commit": a redeploy that takes no
#: commit would redeploy the snapshot already running, which is the thing this
#: script exists to stop doing, so it is not in the list at all.
DEPLOY_MUTATION_PREFERENCE = (
    "serviceInstanceDeployV2",
    "serviceInstanceDeploy",
    "deploymentTriggerCreate",
)

#: Argument names Railway has used for "which commit". Checked against the real
#: schema; a mutation offering none of them cannot express an exact deploy and
#: is skipped rather than called with a guess.
COMMIT_ARG_NAMES = ("commitSha", "commit", "sha")

_SHA_RE = re.compile(r"^[0-9a-f]{40}\Z")

#: Sent on every request, including the anonymous control.
#:
#: urllib defaults to "Python-urllib/3.x", which edge layers - Cloudflare among
#: them, and Railway's API sits behind one - routinely answer with a blanket 403
#: before the request ever reaches the application. That is indistinguishable in
#: the log from "your token was rejected", and it is what two different tokens
#: failing identically pointed at. Naming the caller costs nothing and removes
#: a failure mode that reads as someone else's fault.
USER_AGENT = "trading-api-railway-deploy/1.0 (+https://github.com/hanlinh227-ship-it/trading-api)"


#: GraphQL error text that means "this token is not accepted", as opposed to
#: "this request was wrong" or "the API is not there". Railway phrases the
#: refusal in the error body rather than the HTTP status in some cases, so the
#: status alone is not enough to tell the two apart.
_AUTH_REJECTION_RE = re.compile(
    # "Not Authorized" is Railway's own wording and does NOT contain
    # "unauthorized"; a test asserting the real string is what caught that.
    r"unauthori[sz]|not\s+authori[sz]ed|unauthenticat|not\s+authenticated|"
    r"forbidden|invalid\s+token|access\s+denied|missing\s+credentials",
    re.I,
)


class Failure(RuntimeError):
    """Something that must stop the deploy, with a message an operator can act on.

    `auth_rejected` records WHY this stopped, which the message alone cannot:
    True means the API answered and refused this token, False means the API
    never got to judge the token at all. Conflating the two is how an operator
    ends up rotating a perfectly good token because the endpoint was wrong.
    """

    def __init__(self, message: str, *, auth_rejected: bool = False) -> None:
        super().__init__(message)
        self.auth_rejected = auth_rejected


def _post(query: str, variables: dict, token: str, scheme: str) -> dict:
    headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
    if scheme == "bearer":
        headers["Authorization"] = "Bearer %s" % token
    else:
        headers["Project-Access-Token"] = token
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # 401/403 is the API refusing this token. Any other status is the API
        # refusing the REQUEST, or not being this API at all - a 404 from a
        # stale endpoint must never read as "your token is bad".
        raise Failure(
            "Railway API returned HTTP %s" % exc.code,
            auth_rejected=exc.code in (401, 403),
        ) from None
    except urllib.error.URLError as exc:
        raise Failure(
            "Railway API unreachable: %s" % type(exc).__name__,
            auth_rejected=False,
        ) from None
    if body.get("errors"):
        # Messages come from Railway and can quote the request, so only the
        # message text is surfaced and never the variables, which hold the token
        # in no case but would hold ids in every case.
        messages = [str(e.get("message"))[:200] for e in body["errors"]]
        joined = "; ".join(messages)
        raise Failure(joined, auth_rejected=bool(_AUTH_REJECTION_RE.search(joined)))
    return body.get("data") or {}


def _unauthenticated_status() -> str:
    """What this endpoint says to a request carrying NO token.

    The control for the question a refusal cannot answer on its own: if an
    endpoint returns 403 to everyone, a 403 holding our token says nothing about
    the token. If it answers an anonymous request differently, then the token
    WAS read and judged. Returns a short description, never raises - this is
    diagnostics attached to a failure that has already happened, and must not
    replace it with a failure of its own.
    """
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps({"query": "query { __typename }"}).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return "HTTP %s (the endpoint answers anonymous requests)" % response.status
    except urllib.error.HTTPError as exc:
        return "HTTP %s" % exc.code
    except Exception as exc:  # noqa: BLE001 - any failure here is still evidence
        return "unreachable (%s)" % type(exc).__name__


def authenticate(token: str) -> str:
    """Which auth header this token wants. Account and project tokens differ."""
    probe = "query { __typename }"
    refusals = []
    for scheme in ("bearer", "project"):
        try:
            _post(probe, {}, token, scheme)
            print("RAILWAY_AUTH_SCHEME=%s" % scheme)
            return scheme
        except Failure as exc:
            if not exc.auth_rejected:
                # The API did not refuse the token - it could not be asked. The
                # other scheme would fail identically, and telling an operator
                # to check their token here sends them to rotate a credential
                # that was never the problem.
                raise Failure(
                    "the Railway API could not be reached or did not answer as "
                    "expected at %s, so the token was never judged: %s. This is "
                    "NOT an authentication failure - check the endpoint and "
                    "network before touching RAILWAY_TOKEN."
                    % (ENDPOINT, exc),
                    auth_rejected=False,
                ) from None
            refusals.append("%s: %s" % (scheme, exc))
    # Both schemes were refused. Whether that refusal is ABOUT the token is a
    # separate fact, and an anonymous request is what decides it: an endpoint
    # that refuses everyone identically has not judged our token at all.
    anonymous = _unauthenticated_status()
    raise Failure(
        "the token was refused by the Railway API under both Authorization: "
        "Bearer and Project-Access-Token (%s). The same endpoint answers an "
        "UNAUTHENTICATED request with %s - if that differs from the refusals "
        "above, the token was read and rejected, so check RAILWAY_TOKEN is a "
        "current Railway token with access to this project; if it is the same, "
        "the endpoint is refusing every caller and the token is not the thing "
        "to change." % ("; ".join(refusals), anonymous),
        auth_rejected=True,
    )


def deploy_mutations(token: str, scheme: str) -> dict[str, list[str]]:
    """Every mutation whose name looks like a deploy, with its argument names."""
    query = """
    query {
      __type(name: "Mutation") {
        fields { name args { name } }
      }
    }
    """
    data = _post(query, {}, token, scheme)
    fields = ((data.get("__type") or {}).get("fields")) or []
    out = {}
    for field in fields:
        name = str(field.get("name") or "")
        if "deploy" in name.lower() or "redeploy" in name.lower():
            out[name] = [str(a.get("name")) for a in (field.get("args") or [])]
    return out


def choose_mutation(available: dict[str, list[str]]) -> tuple[str, str]:
    """The first preferred mutation that exists and can name a commit."""
    for name in DEPLOY_MUTATION_PREFERENCE:
        args = available.get(name)
        if args is None:
            continue
        for candidate in COMMIT_ARG_NAMES:
            if candidate in args:
                return name, candidate
    raise Failure(
        "no preferred deploy mutation on this API accepts a commit argument. "
        "Preference list: %s. Commit arguments looked for: %s. Deploy-shaped "
        "mutations this API offers: %s"
        % (", ".join(DEPLOY_MUTATION_PREFERENCE), ", ".join(COMMIT_ARG_NAMES),
           json.dumps(available, sort_keys=True)))


def access_report(token: str, scheme: str, service_id: str,
                  environment_id: str) -> str:
    """What this token can actually SEE, asked only when a deploy is refused.

    "Not Authorized" on the deploy mutation has two very different causes: the
    token cannot reach this service at all (wrong project, wrong account), or it
    can see it but may not deploy it. Reading each id back separates them.

    Reports PRESENCE, never the identifiers. RAILWAY_SERVICE_ID and
    RAILWAY_ENVIRONMENT_ID are repository secrets, and a diagnostic that printed
    them to explain why they did not work would put them in a public log. Never
    raises: this explains a failure that already happened.
    """
    notes = []
    for label, field, ident in (
        ("RAILWAY_SERVICE_ID", "service", service_id),
        ("RAILWAY_ENVIRONMENT_ID", "environment", environment_id),
    ):
        query = "query Q($id: String!) { %s(id: $id) { id } }" % field
        try:
            data = _post(query, {"id": ident}, token, scheme)
            node = data.get(field) or {}
            notes.append("%s: %s" % (
                label,
                "visible to this token" if node.get("id") else "no such %s" % field))
        except Failure as exc:
            notes.append("%s: not readable by this token (%s)" % (label, exc))
    return "; ".join(notes)


def start_deploy(token: str, scheme: str, mutation: str, commit_arg: str,
                 service_id: str, environment_id: str, sha: str) -> str:
    query = (
        "mutation Deploy($serviceId: String!, $environmentId: String!, $commit: String!) {"
        "  %s(serviceId: $serviceId, environmentId: $environmentId, %s: $commit)"
        "}" % (mutation, commit_arg)
    )
    data = _post(query, {"serviceId": service_id,
                         "environmentId": environment_id,
                         "commit": sha}, token, scheme)
    result = data.get(mutation)
    print("RAILWAY_DEPLOY_REQUESTED=%s" % mutation)
    if isinstance(result, dict) and result.get("id"):
        return str(result["id"])
    return ""


def latest_deployment(token: str, scheme: str, service_id: str,
                      environment_id: str) -> dict:
    query = """
    query Deployments($serviceId: String!, $environmentId: String!) {
      deployments(first: 1, input: {serviceId: $serviceId, environmentId: $environmentId}) {
        edges { node { id status meta createdAt } }
      }
    }
    """
    data = _post(query, {"serviceId": service_id, "environmentId": environment_id},
                 token, scheme)
    edges = ((data.get("deployments") or {}).get("edges")) or []
    return (edges[0].get("node") or {}) if edges else {}


def deployed_sha(node: dict) -> str:
    """The commit a deployment carries, from whichever field holds it.

    `meta` is a free-form object and its shape is Railway's to change, so this
    looks for a 40-hex value under the keys it has used rather than insisting on
    one path. A deployment whose commit cannot be read is reported as unknown,
    never as matching.
    """
    meta = node.get("meta")
    if not isinstance(meta, dict):
        return ""
    for key in ("commitHash", "commitSha", "commit"):
        value = meta.get(key)
        if isinstance(value, str) and _SHA_RE.match(value.strip().lower()):
            return value.strip().lower()
    return ""


TERMINAL_OK = ("SUCCESS",)
TERMINAL_BAD = ("FAILED", "CRASHED", "REMOVED", "SKIPPED")


def wait_for_deployment(token: str, scheme: str, service_id: str,
                        environment_id: str, sha: str, timeout: int) -> dict:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        node = latest_deployment(token, scheme, service_id, environment_id)
        status = str(node.get("status") or "")
        if status != last:
            print("RAILWAY_DEPLOYMENT_STATUS=%s id=%s" % (status, node.get("id")))
            last = status
        if status in TERMINAL_OK:
            return node
        if status in TERMINAL_BAD:
            raise Failure("deployment %s ended %s" % (node.get("id"), status))
        time.sleep(10)
    raise Failure("deployment did not reach a terminal status within %ss" % timeout)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sha", required=True)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args(argv)

    sha = args.sha.strip().lower()
    if not _SHA_RE.match(sha):
        print("REFUSED: --sha must be a full 40-character commit", file=sys.stderr)
        return 1

    missing = [n for n in ("RAILWAY_TOKEN", "RAILWAY_SERVICE_ID",
                           "RAILWAY_ENVIRONMENT_ID") if not os.environ.get(n)]
    if missing:
        print("RAILWAY_DEPLOY=BLOCKED_MISSING_CREDENTIALS")
        print("REFUSED: add these repository secrets, then re-run: %s"
              % ", ".join(missing), file=sys.stderr)
        return 1

    token = os.environ["RAILWAY_TOKEN"]
    service_id = os.environ["RAILWAY_SERVICE_ID"]
    environment_id = os.environ["RAILWAY_ENVIRONMENT_ID"]

    try:
        scheme = authenticate(token)
        available = deploy_mutations(token, scheme)
        mutation, commit_arg = choose_mutation(available)
        print("RAILWAY_DEPLOY_MUTATION=%s commit_arg=%s" % (mutation, commit_arg))
        try:
            start_deploy(token, scheme, mutation, commit_arg, service_id,
                         environment_id, sha)
        except Failure as exc:
            if not exc.auth_rejected:
                raise
            # The token authenticated - it got this far - so a refusal HERE is
            # about reaching or deploying this particular service, not about the
            # credential being invalid. Say which, instead of sending someone to
            # rotate a token that just proved it works.
            raise Failure(
                "%s. The token authenticated (scheme %s) and could read the "
                "schema, so this refusal is about THIS service, not the token's "
                "validity. Access check - %s"
                % (exc, scheme,
                   access_report(token, scheme, service_id, environment_id)),
                auth_rejected=True,
            ) from None
        node = wait_for_deployment(token, scheme, service_id, environment_id,
                                   sha, args.timeout)
    except Failure as exc:
        # Ordering matters in a CI log: stdout is block-buffered when piped, so
        # without this the refusal appears ABOVE the steps that preceded it and
        # reads as though nothing had succeeded.
        sys.stdout.flush()
        print("RAILWAY_DEPLOY=FAIL")
        sys.stdout.flush()
        print("REFUSED: %s" % exc, file=sys.stderr)
        return 1

    observed = deployed_sha(node)
    print("RAILWAY_DEPLOYMENT_ID=%s" % node.get("id"))
    print("RAILWAY_DEPLOYED_SHA=%s" % (observed or "unknown"))
    print("RAILWAY_TARGET_SHA=%s" % sha)
    if observed != sha:
        print("RAILWAY_DEPLOY=FAIL")
        print("REFUSED: the successful deployment carries %s, not the validated "
              "commit %s. Not calling this deployed."
              % (observed or "no readable commit", sha), file=sys.stderr)
        return 1
    print("RAILWAY_DEPLOY=SUCCESS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
