#!/usr/bin/env python3
"""Canonical integrity guard + bounded V6 research accelerator entrypoint.

Importing forex_research_guard installs the canonical guarded lab.run implementation
and evidence quarantine logic. The accelerator changes only 3AI research memory and
DEV tournament efficiency; strict V7 acceptance remains untouched.
"""
import forex_research_guard as guard
import forex_research_loop_v6_accelerator as accelerator

if __name__=='__main__':
    guard.quarantine_invalid_pending()
    raise SystemExit(accelerator.main())
