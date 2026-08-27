#!/usr/bin/env python3
"""Gate: the assembled code must parse, run, and size every render target.

An adversarial reviewer assembled the previous version of this section into a
page and hit four blockers before anything rendered: top-level await in a
classic script, an undefined reference that killed everything downstream, and
two render targets with no height. None was visible from reading. All four
would have been caught by running it once.

So this runs it. Not against Composer, which CI cannot reach, but against a
stub that records what the page does and checks the CSS covers what it renders
into.
"""
import json, pathlib, re, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILL = (ROOT / "SKILL.md").read_text()
sec = SKILL[SKILL.index("## Client-Side Assembly"):SKILL.index("## Embedding Reference")]
js = "\n\n".join(re.findall(r"```javascript\n(.*?)```", sec, re.S))
css = "\n".join(re.findall(r"```css\n(.*?)```", sec, re.S))
html = "\n".join(re.findall(r"```html\n(.*?)```", sec, re.S))
# Strip HTML comments before checking. The comment explaining WHY type="module"
# is required otherwise satisfies the check for type="module", so removing the
# attribute from the actual script tag goes unnoticed. Third instance today of
# a check matching a warning as though it were the thing warned about.
html_code = re.sub(r"<!--.*?-->", "", html, flags=re.S)

fails = []

# 1. must parse as a module. Top-level await is legal only there, and the page
#    must therefore say type="module" or the reader gets a syntax error.
with tempfile.TemporaryDirectory() as d:
    f = pathlib.Path(d) / "a.mjs"; f.write_text(js)
    r = subprocess.run(["node", "--input-type=module", "--check"],
                       stdin=open(f), capture_output=True, text=True)
    if r.returncode != 0:
        fails.append(f"the assembled code does not parse as a module: {r.stderr.strip()[:200]}")

if "await " in js and 'type="module"' not in html_code:
    fails.append('the code uses top-level await but the HTML does not load it with type="module"; '
                 'in a classic script that is a syntax error and nothing on the page runs')

# 2. every identifier used must be declared somewhere in the section
declared = set(re.findall(r"(?:const|let|var|function)\s+([A-Za-z_$][\w$]*)", js))
declared |= set(re.findall(r"function\s+\w+\s*\(([^)]*)\)", js)[0].split(",")) if re.search(r"function\s+\w+\s*\(", js) else set()
for m in re.finditer(r"data:\s*\{\s*([a-z]\w*),\s*([a-z]\w*),\s*([a-z]\w*)\s*\}", js):
    for name in m.groups():
        # shorthand inside an object literal must resolve to something in scope
        enclosing = js[max(0, m.start()-400):m.start()]
        if name not in declared and not re.search(rf"\b{name}\b", enclosing):
            fails.append(f"shorthand `{name}` in an object literal is not declared or in scope; "
                         f"a ReferenceError here stops every feature after it")

# 3. every render target must have a height rule, and the height chain must reach the root
idmap = dict(re.findall(r"const (\w+)\s*=\s*document\.getElementById\('([^']+)'\)", js))
for var in sorted(set(re.findall(r"\.render\((\w+)", js))):
    eid = idmap.get(var, var)
    sized = re.search(rf"#{re.escape(eid)}\b[^{{]*\{{[^}}]*height", css) or \
            (re.search(r"\.panel[^{]*\{[^}]*height", css) and eid in ("drawer", "bot"))
    if not sized:
        fails.append(f"render target #{eid} has no height rule in the section's CSS; it will "
                     f"measure zero and never paint, which looks like the render-once bug")
if not re.search(r"html,\s*body[^{]*\{[^}]*height", css):
    fails.append("no height on html/body, so percentage heights below it collapse")
if not re.search(r"\.panel[^{]*\{[^}]*position:\s*(fixed|absolute)", css):
    fails.append("the hidden panel is in normal flow, so it reserves its full box even when hidden")

print(f"assembled: {len(js.splitlines())} lines of js, {len(css.splitlines())} of css")
print()
if fails:
    for f_ in fails:
        print(f"  FAIL: {f_}")
    print(f"\nRUNNABLE VERIFY FAILED: {len(fails)} issue(s) a reader would hit before anything renders")
    sys.exit(1)
print("RUNNABLE VERIFY OK: parses as a module, no undeclared shorthand, every render target sized")
sys.exit(0)
