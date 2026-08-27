#!/usr/bin/env python3
"""Gate: every SDK symbol the skill teaches must exist in the shipped SDK.

The skill tells someone how to drive Composer's embed API. If it names a method
or an event that does not exist, the reader writes code that throws, and the
skill looks authoritative while being wrong. That has already happened in this
product's documentation three times this week: `trigger` is documented and does
not exist, `forTopic` is accepted and silently ignored, and `EMBED/PUBLISH` is
documented as an event name when it is an inner discriminator.

So this checks the claims against embed-26.2.1.js, pulled from a running
26.2.1 instance, rather than against another document.

Exit 0 only if every claimed symbol resolves. Exit 1 names each one that does not.
"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SDK = (ROOT / "_run" / "embed-26.2.1.js").read_text(encoding="utf-8", errors="replace")
SKILL = (ROOT / "SKILL.md").read_text(encoding="utf-8")

# Symbols the SDK genuinely provides, derived from the SDK itself rather than
# hand-listed, so a new SDK build changes the answer instead of the manifest.
sdk_events = set(re.findall(r"composer-[a-z-]+", SDK)) | set(re.findall(r'"(EMBED/[A-Z_]+)"', SDK))
sdk_methods = set(re.findall(r"\b(publish|subscribe|unsubscribe|createComponent|render|destroy|update|initializeToken|addEventListener|removeEventListener)\s*\(", SDK))
sdk_idents = set(re.findall(r"[A-Za-z_$][A-Za-z0-9_$]{2,}", SDK))

fails, checked = [], 0

# 1. every composer-* event the skill names must exist in the SDK
# Only treat a composer-* token as an event claim when it is used as one.
# `isw-da/composer-mcp` is a repository name, not an event, and flagging it
# was the gate matching a pattern rather than a claim.
_ev_claims = set(re.findall(r'["\'](composer-[a-z-]+)["\']', SKILL)) | \
             set(re.findall(r'addEventListener\(\s*["\'](composer-[a-z-]+)', SKILL))
for ev in sorted(_ev_claims):
    checked += 1
    if ev not in sdk_events:
        fails.append(f"event named in SKILL.md but absent from the SDK: {ev}")

# 2. every EMBED/* string must exist, and must be used the way the SDK uses it
for tok in sorted(set(re.findall(r"EMBED/[A-Z_]+", SKILL))):
    checked += 1
    if tok not in SDK:
        fails.append(f"EMBED token named in SKILL.md but absent from the SDK: {tok}")

# 3. EMBED/PUBLISH must never be presented as an event NAME. The SDK dispatches
#    EMBED/CUSTOM_EVENT and carries EMBED/PUBLISH as detail.type.
for m in re.finditer(r'CustomEvent\(\s*["\']([^"\']+)["\']', SKILL):
    checked += 1
    if m.group(1) != "EMBED/CUSTOM_EVENT":
        fails.append(f"CustomEvent named '{m.group(1)}'; the SDK only dispatches EMBED/CUSTOM_EVENT")

# 4. any method called on a component or manager must exist in the SDK
for m in sorted(set(re.findall(r"(?:component|manager|dashboardComponent|embedManager)\.([a-zA-Z_$][\w$]*)\s*\(", SKILL))):
    checked += 1
    if m not in sdk_methods:
        fails.append(f"method .{m}() called in SKILL.md but not present in the SDK")

# 5. Config keys split by whether the SDK could possibly know them.
#
#    SDK_INTERPRETED keys are read by embed.js itself, so absence from the
#    bundle is proof they are wrong.
#
#    PASS_THROUGH keys ride inside publish()'s third argument, which the SDK
#    forwards opaquely: `publish(e,t,i){ L("EMBED/PUBLISH",{topic:e,message:t,options:i}) }`.
#    The embedded application interprets them, not the loader, so grepping the
#    bundle CANNOT confirm or deny them. An earlier version of this gate flagged
#    all four as absent, which was the gate asking the wrong question rather
#    than the documentation being wrong. They must instead carry a caveat, so a
#    reader knows the claim rests on someone's notes and not on the shipped code.
SDK_INTERPRETED = ["interactivityProfileName", "interactivityOverrides",
                   "initialFilters", "menuEventsConfig"]
PASS_THROUGH = ["targetComponents", "publisherId", "applyFiltersStrategy", "PublicationOptions"]

for k in SDK_INTERPRETED:
    if re.search(rf"\b{k}\b", SKILL):
        checked += 1
        if k not in sdk_idents:
            fails.append(f"config key {k} is read by the SDK and is absent from it: {k}")

for k in PASS_THROUGH:
    if re.search(rf"\b{k}\b", SKILL):
        checked += 1
        # find the section it appears in and require an unverified marker nearby
        i = SKILL.find(k)
        ctx = SKILL[max(0, i - 600): i + 600]
        if not re.search(r"not verifiable|unverified|opaque|pass(ed)?[- ]through|cannot be confirmed",
                         ctx, re.I):
            fails.append(
                f"{k} rides inside publish() options and cannot be confirmed from the SDK, "
                f"so it must be marked as unverified where it is used")

# 6. keys the SDK does NOT know must never be presented as working
for bad in ["forTopic"]:
    checked += 1
    if re.search(rf"\b{bad}\b", SKILL) and bad not in sdk_idents:
        ctx = SKILL[max(0, SKILL.find(bad) - 200): SKILL.find(bad) + 200]
        if not re.search(r"not|never|ignored|silently|does not", ctx, re.I):
            fails.append(f"{bad} appears in SKILL.md without being marked as unsupported")

print(f"SDK: {len(sdk_events)} events, {len(sdk_methods)} methods")
print(f"checked {checked} claims in SKILL.md against it")
print()
if fails:
    for f in fails:
        print(f"  FAIL: {f}")
    print(f"\nSDK VERIFY FAILED: {len(fails)} claim(s) the shipped SDK does not support")
    sys.exit(1)
print("SDK VERIFY OK: every SDK symbol the skill teaches exists in the shipped SDK")
sys.exit(0)
