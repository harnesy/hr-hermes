"""Tells whether Hermes Agent would leave a text out when it is a profile's SOUL.md.

Hermes scans a SOUL.md that a profile distribution installed each time it builds the prompt, and on any hit leaves
the whole file out: the profile then runs without its persona. The patterns below are the ones of its scanner for
context files (Hermes Agent v0.23.1, tools/threat_patterns.py, the entries of scope "all" and "context", in its order;
github.com/NousResearch/hermes-agent, © 2025 Nous Research, MIT licence: its text is the LICENSE file in this folder).

They are here so that a rendered employee can be checked before it is installed. This is a compatibility check and
nothing more: it protects nobody from anything, and the scanner in Hermes itself stays the judge.
"""

from __future__ import annotations

import re
import unicodedata

MAX_SCAN_CHARS = 65_536  # Hermes reads no further

_FILLER = r"(?:\w+\s+){0,8}"
_SECRET_VAR = r"\$\{?\w*(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)S?\b"

PATTERNS: list[tuple[str, re.Pattern]] = [(id, re.compile(pattern, re.IGNORECASE)) for pattern, id in [
    (rf'ignore\s+{_FILLER}(previous|all|above|prior)\s+{_FILLER}instructions', "prompt_injection"),
    (r'system\s+prompt\s+override', "sys_prompt_override"),
    (rf'disregard\s+{_FILLER}(your|all|any)\s+{_FILLER}(instructions|rules|guidelines)', "disregard_rules"),
    (rf'act\s+as\s+(if|though)\s+{_FILLER}you\s+{_FILLER}(have\s+no|don\'t\s+have)\s+{_FILLER}(restrictions|limits|rules)', "bypass_restrictions"),
    (r'<!--[^>]{0,512}(?:ignore|override|system|secret|hidden)[^>]{0,512}-->', "html_comment_injection"),
    (r'<\s*div\s+style\s*=\s*["\'][^>]{0,2048}display\s*:\s*none', "hidden_div"),
    (r"translate\s+[^\n]{0,512}\s+into\s+\w+(?:[\s-]+\w+){0,2}\s+and\s+(execute|run|eval)\b", "translate_execute"),
    (rf'do\s+not\s+{_FILLER}tell\s+{_FILLER}the\s+user', "deception_hide"),
    (rf'you\s+are\s+{_FILLER}now\s+(?:a|an|the)\s+', "role_hijack"),
    (rf'pretend\s+{_FILLER}(you\s+are|to\s+be)\s+', "role_pretend"),
    (rf'output\s+{_FILLER}(system|initial)\s+prompt', "leak_system_prompt"),
    (rf'(respond|answer|reply)\s+without\s+{_FILLER}(restrictions|limitations|filters|safety)', "remove_filters"),
    (rf'you\s+have\s+been\s+{_FILLER}(updated|upgraded|patched)\s+to', "fake_update"),
    (r'\bname\s+yourself\s+\w+', "identity_override"),
    (r'register\s+(as\s+)?a?\s*node', "c2_node_registration"),
    (r'(heartbeat|beacon|check[\s\-]?in)\s+(to|with)\s+', "c2_heartbeat"),
    (r'pull\s+(down\s+)?(?:new\s+)?task(?:ing|s)?\b', "c2_task_pull"),
    (r'connect\s+to\s+the\s+network\b', "c2_network_connect"),
    (r'you\s+must\s+(?:\w+\s+){0,3}(register|connect|report|beacon)\b', "forced_action"),
    (r'only\s+use\s+one[\s\-]?liners?\b', "anti_forensic_oneliner"),
    (rf'never\s+{_FILLER}(?:create|write)\s+{_FILLER}(?:script|file)\s+{_FILLER}disk', "anti_forensic_disk"),
    (r'unset\s+\w*(?:CLAUDE|CODEX|HERMES|AGENT|OPENAI|ANTHROPIC)\w*', "env_var_unset_agent"),
    (r'\b(?:cobalt\s*strike|sliver|havoc|mythic|metasploit|brainworm)\b', "known_c2_framework"),
    (r'\bc2\s+(?:server|channel|infrastructure|beacon)\b', "c2_explicit"),
    (r'\bcommand\s+and\s+control\b', "c2_explicit_long"),
    (rf'curl\s+[^\n]{{0,2048}}{_SECRET_VAR}', "exfil_curl"),
    (rf'wget\s+[^\n]{{0,2048}}{_SECRET_VAR}', "exfil_wget"),
    (r'cat\s+[^\n]{0,2048}(\.env|credentials|\.netrc|\.pgpass|\.npmrc|\.pypirc)', "read_secrets"),
]]

# Characters a reader does not see; one of them anywhere is a hit. An emoji made of joined signs has one.
INVISIBLE = frozenset("​‌‍⁠⁢⁣⁤﻿‪‫‬‭‮⁦⁧⁨⁩")


def scan(text: str) -> list[str]:
    """The ids of what the text trips, the way Hermes reads a SOUL.md: invisible characters first, then the patterns
    in the scanner's order. None means the text would load."""
    text = text.strip().removeprefix("﻿")[:MAX_SCAN_CHARS]  # a leading byte order mark is dropped before the scan
    hits = [f"invisible_unicode_U+{ord(ch):04X}" for ch in sorted(set(text) & INVISIBLE)]
    folded = unicodedata.normalize("NFKC", text)  # full-width and other compatibility letters read as plain ones
    return hits + [id for id, pattern in PATTERNS if pattern.search(folded)]
