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


class Failure(RuntimeError):
    """Something that must stop the deploy, with a message an operator can act on."""


def _post(query: str, variables: dict, token: str, scheme: str) -> dict:
    headers = {"Content-Type": "application/json"}
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
        raise Failure("Railway API returned HTTP %s" % exc.code) from None
    except urllib.error.URLError as exc:
        raise Failure("Railway API unreachable: %s" % type(exc).__name__) from None
    if body.get("errors"):
        # Messages come from Railway and can quote the request, so only the
        # message text is surfaced and never the variables, which hold the token
        # in no case but would hold ids in every case.
        raise Failure("; ".join(str(e.get("message"))[:200] for e in body["errors"]))
    return body.get("data") or {}


def authenticate(token: str) -> str:
    """Which auth header this token wants. Account and project tokens differ."""
    probe = "query { __typename }"
    for scheme in ("bearer", "project"):
        try:
            _post(probe, {}, token, scheme)
            print("RAILWAY_AUTH_SCHEME=%s" % scheme)
            return scheme
        except Failure:
            continue
    raise Failure(
        "the token was rejected under both Authorization: Bearer and "
        "Project-Access-Token. Check RAILWAY_TOKEN is a current Railway token "
        "with access to this project.")


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
        start_deploy(token, scheme, mutation, commit_arg, service_id,
                     environment_id, sha)
        node = wait_for_deployment(token, scheme, service_id, environment_id,
                                   sha, args.timeout)
    except Failure as exc:
        print("RAILWAY_DEPLOY=FAIL")
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
