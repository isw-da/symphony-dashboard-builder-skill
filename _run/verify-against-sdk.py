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
# Ownership matters: `destroy` exists on both the manager and a component and
# means very different things. Record every method DEFINITION with its shape
# rather than every call site, so a name that only ever appears as a call does
# not count as provided.
# In minified class bodies a method definition follows the previous method's
# closing brace, so `}` must be in the preceding set or every one is missed.
sdk_methods = set(re.findall(r"(?:^|[{};,])\s*(?:async\s+)?([a-zA-Z_$][\w$]*)\s*\([^)]{0,80}\)\s*\{", SDK))
sdk_async = set(re.findall(r"\basync\s+([a-zA-Z_$][\w$]*)\s*\(", SDK))
# Some methods are assigned rather than declared, so the async keyword is not
# adjacent. The SDK awaiting its own call is the authority: it does
# `(await t.createComponent(i.type,i)).render(...)`, awaiting the create and
# NOT the render.
sdk_async |= set(re.findall(r"await\s+[a-zA-Z_$][\w$]*\.([a-zA-Z_$][\w$]*)\s*\(", SDK))
sdk_methods |= sdk_async
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
    # EVERY occurrence needs the caveat. Checking only the first passes the whole
    # file once one correctly-worded mention exists. This is the second place that
    # bug appeared; the first was the declared-only event check.
    for _m in re.finditer(rf"\b{k}\b", SKILL):
        checked += 1
        ctx = SKILL[max(0, _m.start() - 600): _m.start() + 600]
        if not re.search(r"not verifiable|unverified|opaque|pass(ed)?[- ]through|cannot be confirmed",
                         ctx, re.I):
            fails.append(
                f"{k} at offset {_m.start()} rides inside publish() options and cannot be "
                f"confirmed from the SDK, so it must be marked as unverified where it is used")
            break

# 6. keys the SDK does NOT know must never be presented as working
for bad in ["forTopic"]:
    checked += 1
    if re.search(rf"\b{bad}\b", SKILL) and bad not in sdk_idents:
        ctx = SKILL[max(0, SKILL.find(bad) - 200): SKILL.find(bad) + 200]
        if not re.search(r"not|never|ignored|silently|does not", ctx, re.I):
            fails.append(f"{bad} appears in SKILL.md without being marked as unsupported")

# 7. Existence is not enough: a real symbol used on the wrong object fails
#    silently, which is worse than a typo. Two rules the bundle establishes.
#
#    (a) Components DO proxy addEventListener onto their own element: every
#        component class ships
#        `addEventListener(e,t){this.htmlElement.addEventListener(e,t)}`.
#        An earlier version of this gate asserted the opposite and hard-failed
#        the correct pattern, because it was written from a reading of the
#        bundle rather than from the bundle. So assert the proxy EXISTS, and
#        flag the container-listener pattern instead: renderComponent does
#        `i.appendChild(e.htmlElement)`, making htmlElement a CHILD of the
#        container, so a container listener depends on bubbling that embed.js
#        never establishes.
checked += 1
if "addEventListener(e,t){this.htmlElement.addEventListener(e,t)}" not in SDK:
    fails.append("the component addEventListener proxy is gone from this SDK build; "
                 "re-check which target the skill should teach")
for m in re.finditer(r"\b(dashEl|botEl|drawerBody|drawerEl)\.addEventListener\(\s*[\"'](composer-[a-z-]+)", SKILL):
    checked += 1
    fails.append(
        f"{m.group(1)}.addEventListener() listens on the container; the SDK appends "
        f"htmlElement as a child of it, so this depends on bubbling the bundle does not "
        f"establish. Listen on the component.")

#    (b) An event NAME that exists in the bundle but is never dispatched is a
#        listener that waits forever. Check that each claimed event is actually
#        emitted, not merely declared in an enum. composer-unauthorized is the
#        live example: declared once, dispatched nowhere.
_dispatched = set()
for m in re.finditer(r"[\"'](composer-[a-z-]+)[\"']", SDK):
    ev = m.group(1)
    # an event assigned into an enum and never referenced again is declared, not emitted
    if len(re.findall(re.escape(ev), SDK)) > 1 or re.search(rf"dispatchEvent\([^)]*{re.escape(ev)}", SDK):
        _dispatched.add(ev)
_declared_only = {"composer-unauthorized"}
for ev in sorted(_ev_claims):
    if ev in _declared_only:
        # EVERY occurrence must be caveated, not just the first. Checking only
        # SKILL.find(ev) passes the whole file the moment one properly-worded
        # mention exists, which is how a later uncaveated use slips through.
        for m in re.finditer(re.escape(ev), SKILL):
            checked += 1
            ctx = SKILL[max(0, m.start() - 500): m.start() + 500]
            if not re.search(r"never dispatch|never fire|declared|waits forever|trap", ctx, re.I):
                fails.append(
                    f"{ev} at offset {m.start()} is never dispatched by the SDK; using it "
                    f"without saying so gives a listener that waits forever")
                break

# 8. `await x.m()` where m is not async returns undefined immediately and
#    guarantees nothing. initializeToken and render are both like this.
for m in re.finditer(r"await\s+[a-zA-Z_$][\w$]*\.([a-zA-Z_$][\w$]*)\s*\(", SKILL):
    name = m.group(1)
    if name in sdk_methods and name not in sdk_async:
        checked += 1
        i = m.start()
        ctx = SKILL[max(0, i - 400): i + 400]
        if not re.search(r"not async|returns undefined|resolves immediately|guarantees nothing", ctx, re.I):
            fails.append(f"await on .{name}(), which the SDK does not declare async: it returns "
                         f"undefined and the await guarantees nothing")

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
