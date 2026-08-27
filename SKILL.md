---
name: symphony-dashboard-builder
description: Build Logi Symphony (Composer) dashboard configuration files via conversational interview, then output importable JSON. Trigger whenever the user mentions Logi Symphony dashboards, Composer dashboards, dashboard JSON config, dashboard import, dashboard export, building dashboards in Composer, creating visuals or widgets for Composer, Logi Composer configuration, Symphony dashboard layout, embedded analytics dashboards, VDD dashboards, Composer API dashboard creation, or asks to create/scope/configure a Composer dashboard. Also trigger on indirect cues like "I want a dashboard that shows…", "build me a dashboard for…", "create a KPI dashboard in Composer", "scope a dashboard", or any reference to dashboardLayout, widgets, forced filters, or visual configuration in Composer. Even if the user doesn't say "Composer" explicitly but mentions Symphony, VDD, or Logi alongside dashboard intent, use this skill.
---

# Symphony Dashboard Builder

Generate importable Logi Symphony (Composer) dashboard configurations through a structured interview, then output JSON files the user can import via the Composer API or UI.

## Why This Skill Exists

Logi Composer's dashboard configuration is powerful but complex. The JSON structures for dashboards, visuals, and sources are deeply nested and reference internal IDs. Hand-writing them is error-prone. This skill bridges the gap: it interviews the user about what they want, then generates technically correct configuration files they can import directly.

## Critical Technical Foundation

Before generating anything, internalize these non-negotiable rules:

### The Vendor Media Type

Every Composer API call requires a custom content type. Using `application/json` returns `415 Unsupported Media Type`.

```
Content-Type: application/vnd.composer.v3+json
Accept: application/vnd.composer.v3+json
```

### API Response Wrapping

Composer list endpoints wrap results in `{content: [...]}`. Parsers must handle both flat arrays and wrapped responses:

```javascript
const raw = await response.json();
const items = Array.isArray(raw) ? raw : (raw.content || raw.items || raw.data || []);
```

### API Base Path

The API lives at `{instanceUrl}/discovery/api/...` — not `/composer/api/...`.

### API Version

This skill targets the **Composer v25 API**. Earlier versions may have different endpoint paths or missing features (e.g., dashboard import/export was added in later versions). If the user's instance is on an older version, the export-modify-import workflow may not be available — fall back to individual `POST /api/dashboards` calls.

### Authentication Patterns

- **Basic Auth** (client_id:secret as base64) → only for creating Trusted Access tokens
- **Bearer Token** → for all data/admin API calls
- **Pull tokens**: server-side user lookup (`POST /api/trusted-access/pull/tokens`)
- **Push tokens**: caller provides user details (`POST /api/trusted-access/push/tokens`)

### Admin Users Bypass RLS

Admin and supervisor users bypass forced filters entirely. When testing or demoing row-level security, always use non-admin viewer accounts. This is the single most common gotcha in Symphony implementations.

---

## CRITICAL: The Initial-Visual Workflow (Required for Programmatic Dashboard Creation)

**This is the only reliable method for creating dashboards via API.** Do NOT hand-craft visual JSON — the Composer frontend depends on internal default state that only the `initial-visual` API endpoint provides. Hand-crafted visuals will be accepted by the API but crash the frontend with `TypeError: Cannot read properties of undefined (reading 'values')`.

### The Correct Workflow

```
1. Discover source + visual types
2. GET /api/sources/{sourceId}/visual-types/{visualTypeId}/initial-visual  ← THE KEY ENDPOINT
3. Modify the template (field names, visual name, level)
4. POST /api/visuals  (create each visual)
5. POST /api/dashboards  (create dashboard referencing visual IDs)
```

### Step-by-Step

#### Step 1: Discover visual type IDs

```javascript
// Get available visual types for a source
var resp = await fetch(BASE + '/api/sources/' + SOURCE_ID + '/visual-types', {
  headers: { 'Accept': CT }, credentials: 'same-origin'
});
var types = await resp.json();
// Each type has: { visualTypeId: "...", name: "...", type: "HISTOGRAM" }
// IMPORTANT: the ID field is called `visualTypeId`, NOT `id`
```

**Common type strings** (actual values vary by instance):
- `HISTOGRAM` — bar/histogram charts
- `LINE_CHART` — line/trend charts
- `KPI` — single-value KPI cards
- `RAW_DATA_TABLE` — data tables
- `PIE` — pie/donut charts
- `FLOATING_BUBBLES` — bubble charts
- `HEAT_MAP`, `WATERFALL`, `SUN_BURST`, etc.

#### Step 2: Fetch initial-visual templates

```javascript
// This returns a PROPERLY INITIALIZED visual template with all required defaults
var template = await fetch(
  BASE + '/api/sources/' + SOURCE_ID + '/visual-types/' + visualTypeId + '/initial-visual',
  { headers: { 'Accept': CT }, credentials: 'same-origin' }
).then(r => r.json());
```

**Why this is critical:** Each visual type has different variable structures. For example:
- `HISTOGRAM` uses `Group By` with `binsType`/`binsCount` — NOT `X Axis`/`Y Axis`
- `KPI` uses `Metric` (singular array) and `Comparison Metric` — NOT `Metrics` (plural)
- `LINE_CHART` uses `Y Axis` and `Trend Attribute`

The `initial-visual` endpoint returns the correct structure with all required defaults, color configs, conditional formatting templates, and internal state. Do NOT guess at these structures.

#### Step 3: Modify the template

Only change what's needed — field names, visual name, and level:

```javascript
// Example: Modify a LINE_CHART template
template.visualName = 'Session Cost Over Time';
template.level = 'IN_DASHBOARD';  // MUST change from 'TOP' to 'IN_DASHBOARD'
template.source.variables['Y Axis'] = [{ name: 'session_cost', func: 'sum', colorConfig: { autoShowColorLegend: true } }];
template.source.variables['Trend Attribute'].name = 'session_date';
template.source.variables['Trend Attribute'].sort.name = 'session_date';
delete template.id;  // Remove any ID so Composer generates a new one

// Example: Modify a KPI template
template.visualName = 'Total Budget';
template.level = 'IN_DASHBOARD';
template.source.variables['Metric'] = [{ name: 'budget', func: 'sum' }];
template.source.variables['Comparison Metric'] = [{ name: 'budget', func: 'sum' }];
// Update conditional formatting metric references too
template.source.variables['Conditional Formatting'].forEach(function(cf) {
  if (cf.condition && cf.condition.metric) {
    cf.condition.metric.name = 'budget';
    cf.condition.metric.func = 'sum';
  }
});

// Example: Modify a HISTOGRAM template
template.visualName = 'Budget Distribution';
template.level = 'IN_DASHBOARD';
template.source.variables['Group By'].name = 'budget';
```

#### Step 4: Create visuals via API

```javascript
var result = await fetch(BASE + '/api/visuals', {
  method: 'POST',
  headers: { 'Content-Type': CT, 'Accept': CT },
  credentials: 'same-origin',
  body: JSON.stringify(template)
}).then(r => r.json());
// result.id is the visual ID to use in the dashboard
```

#### Step 5: Create dashboard referencing visual IDs

```javascript
var dashboard = {
  name: 'My Dashboard',
  description: 'Description',
  layout: 'unset',
  dashboardLayout: {
    layout: [
      { widgetId: w1, path: [0, 0], params: [50, 100] },
      { widgetId: w2, path: [1, 0], params: [50, 50] },
      { widgetId: w3, path: [1, 1], params: [50, 50] }
    ],
    locked: [],
    isResponsive: true,
    isFreeForm: false
  },
  showDescription: false,
  isReportDashboard: false,
  // NOTE: Do NOT include unifiedBarCfgs here — causes HV000028 Hibernate validation error
  fieldLinks: [],
  rowFilters: [],
  mutedLinks: [],
  widgets: [
    {
      id: w1, name: 'Widget Name', description: '',
      header: { visibility: 'VISIBLE' },
      layout: { col: 1, row: 1, rowSpan: 6, colSpan: 16 },
      visualId: kpiVisualId,
      content: { contentType: 'VISUAL', visualId: kpiVisualId },
      pickers: { hiddenPickers: [], visibility: 'VISIBLE' }
    }
    // ... more widgets
  ],
  tags: []
};
```

### Key Constraints Discovered Through Testing

1. **Visuals CANNOT be shared across dashboards.** Each dashboard must own its own visual objects. Attempting to reference a visual already used by another dashboard returns: `"visuals already used in other dashboards"`.

2. **Widget IDs must be unique 32-char hex strings.** Generate with `crypto.getRandomValues`:
   ```javascript
   var wid = function() {
     return Array.from(crypto.getRandomValues(new Uint8Array(16)))
       .map(function(b) { return b.toString(16).padStart(2, '0'); }).join('');
   };
   ```

3. **Widget `id` field is REQUIRED.** Omitting it returns `"must not be blank"` validation error.

4. **Every widget needs both `visualId` AND `content.visualId`.** Missing either causes a 404 with `"Visuals were not found [null]"`.

5. **Visual `level` must be `'IN_DASHBOARD'`** when creating visuals for dashboard use. The initial-visual endpoint returns `'TOP'` — you must change this.

---

## The Interview Workflow

When a user asks to build a dashboard, follow these phases. Do NOT skip the discovery phase — generating config without knowing the instance state produces broken files.

### Phase 1: Discovery (Required)

Start with the three most important questions. Do NOT dump all questions at once — ask these first, then follow up based on answers.

**Ask these 3 first:**

1. **Do you have an existing working dashboard you could export?** This is an alternative reliable path. If yes → go to the Export-Modify-Import workflow (see later section).

2. **What is your Composer instance URL?** (e.g., `https://yourcompany.logi-symphony.com`) — and do you have admin/supervisor access?

3. **Do you already know your source IDs and field names, or do you need help discovering them?** If they don't know, provide the discovery script (Phase 1b).

**Then follow up based on answers:**

If they have an export → skip to Phase 3 (modify the export).

If building from scratch, ask:
- Which source(s) should the dashboard use? What are the key field names?
- What story should the dashboard tell? (KPIs, trends, comparisons, detail)
- Who is the audience? (executives → KPI cards; analysts → filters and drill-down)
- How many widgets? (suggest 4-8 for a balanced layout)
- Any data security needs? (forced filters, column-level security, multi-tenancy)

### Phase 1b: Discovery Script

If the user doesn't know their instance state, provide this script to run in their browser console while logged into Composer:

```javascript
// === Symphony Instance Discovery ===
// Run this in your browser console while logged into Composer
// It outputs everything Claude needs to generate your dashboard config

(async () => {
  const BASE = window.location.origin + '/discovery';
  const CT = 'application/vnd.composer.v3+json';

  // Get CSRF token for same-origin requests
  const csrf = document.querySelector('meta[name="_csrf"]')?.content;
  const headers = { 'Accept': CT };
  if (csrf) headers['X-CSRF-TOKEN'] = csrf;

  const get = async (path) => {
    const r = await fetch(BASE + path, { headers, credentials: 'same-origin' });
    if (!r.ok) return { _error: r.status };
    const d = await r.json();
    return Array.isArray(d) ? d : (d.content || d);
  };

  const result = {};

  // Current user
  result.user = await get('/api/user');

  // All sources
  const sources = await get('/api/sources');
  result.sources = (sources || []).map(s => ({
    id: s.id, name: s.name, connectionId: s.connectionId
  }));

  // Fields for each source (first 10 sources)
  result.sourceFields = {};
  for (const s of (sources || []).slice(0, 10)) {
    const fields = await get('/api/sources/' + s.id + '/fields');
    result.sourceFields[s.name] = (fields || []).map(f => ({
      name: f.name,
      type: f.type || f.dataType,
      visible: f.visible !== false
    }));
  }

  // Existing dashboards
  const dashboards = await get('/api/dashboards');
  result.dashboards = (dashboards || []).map(d => ({
    id: d.id,
    name: d.name,
    widgetCount: d.dashboardLayout?.layout?.length || 0
  }));

  // Accounts (tenants)
  result.accounts = await get('/api/accounts');

  // Connections
  const conns = await get('/api/connections');
  result.connections = (conns || []).map(c => ({
    id: c.id, name: c.name, type: c.connectionType
  }));

  // Existing forced filters (for each source)
  result.forcedFilters = {};
  for (const s of (sources || []).slice(0, 10)) {
    const ff = await get('/api/sources/' + s.id + '/security/filters');
    if (ff && !ff._error) result.forcedFilters[s.name] = ff;
  }

  // Visual types for each source (needed for initial-visual workflow)
  result.visualTypes = {};
  for (const s of (sources || []).slice(0, 10)) {
    const vt = await get('/api/sources/' + s.id + '/visual-types');
    result.visualTypes[s.name] = (vt || []).map(v => ({
      visualTypeId: v.visualTypeId, name: v.name, type: v.type
    }));
  }

  console.log('=== PASTE EVERYTHING BELOW TO CLAUDE ===');
  console.log(JSON.stringify(result, null, 2));
  console.log('=== END ===');
})();
```

### Phase 2: Dashboard Design

Once you have the instance context, design the dashboard:

1. **Propose a layout** — describe the widget grid (e.g., "KPI top, bar chart left, line chart right")
2. **Map fields to visuals** — specify which source fields go into which chart axes, metrics, and dimensions
3. **Confirm with the user** before generating the script

### Phase 3: Generate the All-in-One Script

Generate a single browser console script that:
1. Fetches initial-visual templates from the API
2. Modifies them with the user's field mappings
3. Creates visuals via POST /api/visuals
4. Creates the dashboard referencing those visual IDs
5. Prints the dashboard URL and cleanup instructions

**IMPORTANT**: Always output scripts as downloadable `.js` files — never in markdown code blocks. Markdown formatting (backticks, smart quotes) corrupts scripts when users paste them into the console.

### Phase 4: Verification

After the user runs the script, have them open the dashboard URL. If it works, provide cleanup/rollback instructions. If it fails, debug based on the error.

---

## Dashboard JSON Structure Reference

A Composer dashboard object has this structure:

```json
{
  "name": "My Dashboard",
  "description": "Dashboard description",
  "layout": "unset",
  "dashboardLayout": {
    "layout": [
      {
        "widgetId": "32-char-hex-id",
        "path": [0, 0],
        "params": [50, 100]
      }
    ],
    "locked": [],
    "isResponsive": true,
    "isFreeForm": false
  },
  "showDescription": false,
  "isReportDashboard": false,
  "fieldLinks": [],
  "rowFilters": [],
  "mutedLinks": [],
  "widgets": [],
  "tags": []
}
```

**WARNING**: Do NOT include `unifiedBarCfgs` in the dashboard creation payload. It causes a Hibernate validation error (`HV000028: Unexpected exception during isValid call`). Add time controls via the Composer UI after creation.

### Layout System

Each widget in `dashboardLayout.layout` has:
- **widgetId**: 32-character hex string (must match a widget `id` in the `widgets` array)
- **path**: Array of 2 integers `[row, column]` defining position in the grid
- **params**: Array of 2 numbers `[height%, width%]` controlling size

**IMPORTANT**: `path` and `params` are 2-element arrays, NOT 4-element. This was confirmed by examining working dashboard exports from Composer v25.

Common layout patterns:

**Full width top + 2-column bottom:**
```json
[
  {"widgetId": "w1", "path": [0, 0], "params": [50, 100]},
  {"widgetId": "w2", "path": [1, 0], "params": [50, 50]},
  {"widgetId": "w3", "path": [1, 1], "params": [50, 50]}
]
```

**3 columns top row + full width bottom:**
```json
[
  {"widgetId": "w1", "path": [0, 0], "params": [50, 30]},
  {"widgetId": "w2", "path": [0, 1], "params": [50, 32]},
  {"widgetId": "w3", "path": [0, 2], "params": [50, 38]},
  {"widgetId": "w4", "path": [1, 0], "params": [50, 50]},
  {"widgetId": "w5", "path": [1, 1], "params": [50, 50]}
]
```

### Widget Object Structure

Each widget in the `widgets` array MUST have:

```json
{
  "id": "32-char-hex-matching-widgetId-in-layout",
  "name": "Widget Title",
  "description": "",
  "header": { "visibility": "VISIBLE" },
  "layout": { "col": 1, "row": 1, "rowSpan": 6, "colSpan": 16 },
  "visualId": "id-from-POST-api-visuals",
  "content": { "contentType": "VISUAL", "visualId": "id-from-POST-api-visuals" },
  "pickers": { "hiddenPickers": [], "visibility": "VISIBLE" }
}
```

**All fields are required.** Missing `id` → validation error. Missing `visualId` or `content.visualId` → 404 "Visuals were not found [null]".

### Generating Widget IDs

Widget IDs are 32-character lowercase hex strings. Generate with crypto:

```javascript
function widgetId() {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)))
    .map(function(b) { return b.toString(16).padStart(2, '0'); }).join('');
}
```

---

## Visual Configuration — DO NOT HAND-CRAFT

**NEVER hand-write visual JSON.** Always use the `initial-visual` endpoint to get a template, then modify only the field names.

Each visual type has a completely different `source.variables` structure. Examples from real Composer v25 instances:

### HISTOGRAM variables
```json
{
  "Bins Color": "_inherit",
  "Cumulative Line Color": "_inherit",
  "Formatting": [],
  "Group By": {
    "binsType": "auto",
    "binsCount": 10,
    "binsWidth": 100,
    "values": "absolute",
    "cumulative": false,
    "name": "field_name_here"
  }
}
```

### LINE_CHART variables
```json
{
  "Formatting": [],
  "Y Axis": [
    { "name": "field_name", "func": "sum", "colorConfig": { "autoShowColorLegend": true } }
  ],
  "Trend Attribute": {
    "name": "time_field",
    "limit": 1000,
    "sort": { "name": "time_field", "dir": "asc" }
  }
}
```

### KPI variables
```json
{
  "Metric": [{ "name": "field_name", "func": "sum" }],
  "Comparison Metric": [{ "name": "field_name", "func": "sum" }],
  "Formatting": [],
  "Conditional Formatting": [
    {
      "type": "palette",
      "condition": { "type": "metric", "metric": { "name": "field_name", "func": "sum" } },
      "applyTo": { "type": "namedTargets", "targets": ["metric"] },
      "format": { "type": "palette", "palette": "_inherit", "mode": "gradient", "colorNum": 3, "thresholds": "auto" }
    }
  ]
}
```

These examples are illustrative only — always fetch from `initial-visual` for the exact structure your instance expects.

---

## Data Security Configuration

### Forced Filters (Row-Level Security)

Create via `POST /api/sources/{sourceId}/security/filters`:

```json
{
  "field": "hospital",
  "operator": "eq",
  "value": "${User.hospital}",
  "sids": [{"type": "group", "name": "hospital-users"}]
}
```

The `${User.attribute_name}` syntax interpolates user attributes at query time. This is how per-user data filtering works without creating separate dashboards.

**Key RLS details:**
- Operators: `eq`, `ne`, `in`, `gt`, `lt`, `gte`, `lte`, `contains`, `startsWith`
- `sids` can target users, groups, or accounts
- User attributes are set via `PUT /api/users/{id}` with `attributes` field
- In push token calls, attributes use array format: `"attributes": {"hospital": ["City General"]}`
- In user PUT calls, attributes use comma-separated strings: `"hospital": "City General"`
- Admin/supervisor users bypass ALL forced filters — test with viewer accounts only

### Column-Level Security

Create via `POST /api/sources/{sourceId}/security/fields`:

```json
{
  "fieldName": "salary",
  "sids": [{"type": "group", "name": "hr-team"}],
  "permission": "read"
}
```

Fields without explicit grants are hidden from users not in the specified SIDs.

---

## Multi-Tenancy Configuration

Composer's account system provides native multi-tenancy. Each account (tenant) isolates:
- Dashboard access
- Source permissions
- User memberships
- Forced filter scope

### Tenant Setup Workflow

1. Create account: `POST /api/accounts` with `{"name": "Tenant Name"}`
2. Assign users: `PUT /api/accounts/{id}/users` with array of user IDs
3. Share sources: `PUT /api/sources/{sourceId}/acls/bulk` to grant tenant access
4. Share dashboards: `PUT /api/dashboards/{dashId}/acls/bulk`
5. Configure RLS: `POST /api/sources/{sourceId}/security/filters` to scope data per tenant

### Push Token Tenant Switching

```javascript
// Embed as user in specific tenant
const token = await fetch(baseUrl + '/api/trusted-access/push/tokens', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/vnd.composer.v3+json',
    'Accept': 'application/vnd.composer.v3+json',
    'Authorization': 'Basic ' + btoa(clientId + ':' + secret)
  },
  body: JSON.stringify({
    username: 'viewer-user',
    account: 'Tenant Name',
    roles: ['viewer'],
    attributes: { region: ['EMEA'] }
  })
});
```

---

## Client-Side Assembly

Everything above builds the dashboard on the server. This part builds the application around
it. It is one working page rather than a set of snippets, because an earlier version of this
section was snippets and a reviewer who assembled them hit four separate blockers before
anything rendered.

Every symbol below is checked against the embed SDK served by a running Composer 26.2.1
(`/discovery/embed/embed.js`) by `_run/verify-against-sdk.py`, which also parses this code as
a module and fails on an undefined reference.

### The three rules everything else follows from

1. **Render once.** Calling `render()` again re-appends the loader, appends a second
   `<style>` block, and re-initialises the same component instance. (It does not abort
   in-flight requests: there is no such code, and an earlier draft of this section said there
   was.) If you genuinely need to re-render, use `manager.refreshComponent(id)`, which
   destroys first. Otherwise boot once, render once, show and hide with CSS.
2. **Every render target needs a real box before you render into it.** Not `auto`, not
   `display: none`. A zero-height container measures zero and never paints, and looks exactly
   like rule 1 being broken.
3. **Never detach or reparent a rendered container.** The manager runs a debounced
   `MutationObserver` over `document.body` and silently destroys any component whose element
   `document.querySelector` can no longer find. Opacity survives this; moving the node does
   not, and the destruction is permanent and unlogged.
4. **A hidden panel must leave the layout.** Rule 2 forbids `display: none`, so use
   `position: fixed` plus opacity. Otherwise your hidden drawer occupies its full width
   forever and shoves everything below it off screen.

### The page

```html
<!doctype html>
<html>
<head>
  <link rel="stylesheet" href="app.css">
  <!-- The SDK loader. It has no `type`, and that is correct: it is not your code. -->
  <script src="https://your-instance/discovery/embed/embed.js"
          data-name="composer-embed-manager"></script>
</head>
<body>
  <div id="filters"></div>
  <div id="dash"></div>

  <!-- hidden but laid out, and out of flow: see rule 3 -->
  <aside id="drawer" class="panel is-hidden"><div id="drawer-body"></div></aside>
  <aside id="bot"    class="panel is-hidden"></aside>

  <!-- type="module" is required. Without it, top-level await is a syntax error
       and nothing on this page runs at all. -->
  <script type="module" src="app.js"></script>
</body>
</html>
```

```css
/* Rule 2: every render target needs height, and percentage height needs an
   unbroken chain to the root. Omitting these two lines is the single most
   common way an embed silently never paints. */
html, body { height: 100%; margin: 0; }
#dash      { width: 100%; height: calc(100% - 48px); }
#filters   { height: 48px; }

/* Rule 3: out of flow, so hiding it does not reserve space. */
.panel     { position: fixed; top: 0; right: 0; width: 480px; height: 100%;
             transition: opacity .15s; }
#drawer-body { width: 100%; height: 100%; }   /* the panel is sized; its body is not */
.is-hidden { opacity: 0; pointer-events: none; }
```

```javascript
// app.js  (loaded with type="module")

// Your endpoint, not Composer's. Minting a Trusted Access token needs a client
// id and secret, so it cannot happen in the browser.
const getToken = async () => (await fetch('/api/composer-token')).json();  // {access_token, expires_in}

// The URL in Composer shows accountId_dashId with an underscore. The embed
// manager wants a plus. Wrong separator gives a dashboard that never resolves.
const ACCOUNT = '65659d06b5ca0667ef2bb2d1';
const DASH    = '69fce58b0b70396702ebcab0';
const DRAWER  = '69fdf0ea0b70396702ebde32';

const dashEl = document.getElementById('dash');
const drawerEl = document.getElementById('drawer');
const drawerBody = document.getElementById('drawer-body');
const botEl = document.getElementById('bot');

const manager = await window.initComposerEmbedManager({ getToken });

// --- primary dashboard -------------------------------------------------
const dashboard = await manager.createComponent('dashboard', {
  dashboardId: `${ACCOUNT}+${DASH}`,
  interactivityProfileName: 'interactive',
  // NOT an array. The SDK reads this only when it has `sourceId` AND one of
  // `timeFilter` / `filters`; anything else is silently discarded, exactly the
  // way forTopic is. It becomes querystring `inheritSourceId` on the route.
  initialFilters: {
    sourceId: '69fce5780b70396702ebca7a',
    filters: [{ path: 'region', operation: 'IN', value: ['EMEA'] }]
  }
});
// render() is NOT async: the SDK's own code does
// `(await t.createComponent(...)).render(...)`, awaiting the create and not
// the render. Awaiting it returns undefined immediately and tells you nothing
// about painting. Use composer-dashboard-loaded if you need a signal.
dashboard.render(dashEl, { width: '100%', height: '100%' });

// --- drawer: created and rendered ONCE, at boot, into its hidden panel ---
const drawer = await manager.createComponent('dashboard', {
  dashboardId: `${ACCOUNT}+${DRAWER}`,
  interactivityProfileName: 'readonly',
  header: { visible: false },
  // A secondary embed with its own time bar gives the user two competing
  // time controls. TIMEBAR_PANEL and TIMEBAR_FIELD are both SDK-recognised.
  interactivityOverrides: { visualSettings: { TIMEBAR_PANEL: false } }
});
drawer.render(drawerBody, { width: '100%', height: '100%' });

// --- chatbot -----------------------------------------------------------
const bot = await manager.createComponent('chat-bot', { theme: '__platform__' });
bot.render(botEl, { width: '100%', height: '100%' });

// --- filtering ---------------------------------------------------------
// initialFilters sets the boot state and is read by the SDK. publish() changes
// a LIVE component and is what a filter bar uses. publish lives on the MANAGER;
// there is no `trigger` method on anything.
const applyFilters = (filters) =>
  manager.publish('region-filter', filters);      // array or single object

document.getElementById('filters').addEventListener('change', (e) => {
  const v = e.target.value;
  // Clearing: publish an empty array rather than omitting the call.
  applyFilters(v ? [{ path: 'region', operation: 'IN', value: [v] }] : []);
});

// The dashboard must be authored with a cross-visual link on this topic, or the
// publish lands nowhere and nothing errors. See "Cross-Source Links" above.

// Sync the bar back when the dashboard filters itself internally.
const unsubscribe = manager.subscribe('region-filter', (msg) => reflectInBar(msg));

// --- drill-through -----------------------------------------------------
// Listen on the COMPONENT. Every component class ships
// `addEventListener(e,t){this.htmlElement.addEventListener(e,t)}`, proxying onto
// its own element. Do not use the container you passed to render(): the SDK
// appends htmlElement as a CHILD of it, so a container listener only fires if
// the event bubbles, which embed.js does not establish.
dashboard.addEventListener('composer-visual-series-clicked', (e) => {
  // The detail shape is set by the embedded application, not the loader, so it
  // is NOT verifiable from the SDK bundle. Log it once on your own instance
  // before relying on a field name.
  console.log('series-clicked detail', e.detail);
  openDrawer(e.detail);
});

function openDrawer(detail) {
  const id = detail?.filters?.[0]?.value?.[0];   // confirm against your own log first
  if (id == null) return;                        // never publish a null filter
  manager.publish('drawer-context', [{ path: 'account_id', operation: 'IN', value: [id] }]);
  drawerEl.classList.remove('is-hidden');
}

// --- chatbot handoff ---------------------------------------------------
bot.addEventListener('composer-chat-visual-received', (e) => {
  // visParams does not appear in the SDK bundle: it comes from the embedded
  // app. Not verifiable from the loader; confirm the name on your instance.
  const visParams = e.detail?.visParams;
  if (visParams) openInDashboard(visParams);
});

// --- tokens: there is nothing to do here -----------------------------
// The SDK re-mints on its own. It calls getToken, reads expires_in, and
// schedules itself again 60s before expiry, recursively, forever. A wall
// display does not outlive its first token.
//
// So do NOT write a refresh handler. Two specific traps if you try:
//   * composer-init-failed is dispatched inside initComposerEmbedManager,
//     BEFORE the manager is constructed, so `manager` is still in the temporal
//     dead zone and your handler throws. It also cannot signal mid-session
//     expiry: the probe that raises it runs exactly once, at boot.
//   * initializeToken() is `initializeToken(){this.updateToken()}`, not async
//     and with no return, so awaiting it resolves immediately.
//
// The one thing you MUST get right is expires_in. The SDK computes
// `expires_in * 1000 - 60000`; omit it and that is NaN, setTimeout coerces NaN
// to 0, and you get a tight loop hammering your own token endpoint.

function reflectInBar(_msg) { /* your filter bar UI */ }
function openInDashboard(_visParams) { /* open the visual, or save then embed it */ }
```

### The modal, and how it differs

A modal is the same component in a centred overlay: created once, rendered once, shown with
the same class toggle. Use the drawer when the user needs the parent visible for comparison,
and the modal when they need to stop and focus. The only real difference is the CSS box and
that a modal usually takes a backdrop.

### Traps this section exists to record

- **`forTopic`** inside `initialFilters` is not a key the SDK knows. JavaScript accepts it
  and it does nothing at all, silently.
- **`composer-unauthorized`** is declared once in the bundle and dispatched nowhere. A
  listener on it waits forever. Use `composer-init-failed`, on `document`.
- **There are no export events.** `EXPORT` exists only as an interactivity flag, so there is
  no start, completion or progress to hook. An earlier draft of this section documented
  `composer-export-started` and `composer-export-completed`; both were invented, and the SDK
  check caught them.
- **Sixteen chatbot events, not fifteen.** Fifteen use the `composer-chat-` prefix and one,
  `composer-bot-suggestions-failed`, uses `composer-bot-`. A listener loop built by
  concatenating onto the common stem drops suggestion failures.
- **`interactivityProfileName`** accepts `interactive`, `readonly`, `embedded`, `linked` and
  `lite`.
- **`symphony`, `__platform__` and `visParams` all appear zero times in the SDK bundle.**
  In `embed.js`, `theme` is a plain string interpolated into an element id and a scoped CSS
  selector; it has no blocks. Everything claimed about theme structure or about the shape of
  a chatbot event payload comes from the embedded application, **not verifiable from the SDK
  bundle**, and is on the same footing as `targetComponents` and `publisherId`. Log the event
  on your own instance before depending on a field name.

### Driving it without a manager reference

If your filter UI cannot reach the manager, dispatch what the SDK dispatches. The event
**name** is `EMBED/CUSTOM_EVENT`; `EMBED/PUBLISH` is the `type` inside it and is never an
event name:

```javascript
function publishWithoutManager(topic, message, options = {}) {
  document.dispatchEvent(new CustomEvent("EMBED/CUSTOM_EVENT", {
    detail: { type: "EMBED/PUBLISH", data: { topic, message, options } },
    bubbles: true
  }));
}
```

`options` is forwarded opaquely by the loader, so keys inside it such as `targetComponents`
and `publisherId` are interpreted by the embedded application. Their behaviour is **not
verifiable from the SDK bundle**; treat them as unconfirmed until you have watched them work.

### What this does not cover

Write-back. Composer writes back through upload-backed sources and the OData surface rather
than the embed SDK, so it is an API concern. See `WRITEBACK_ODATA.md` in `isw-da/composer-mcp`.

## Embedding Reference

Logi Symphony supports true iframeless embedding via the Embed Manager JavaScript API.

### Setup

```html
<script src="https://your-instance.com/discovery/embed/embed.js"
        data-name="composer-embed-manager"></script>
```

### Embed a Dashboard

```javascript
const getToken = async () => {
  // Return {access_token, expires_in} from your auth endpoint
};
const manager = await window.initComposerEmbedManager({ getToken });
const component = await manager.createComponent('dashboard', {
  dashboardId: 'your-dashboard-id',
  interactivityProfileName: 'interactive',
  theme: '__platform__',
  header: { showActions: false, showTitle: false, visible: false }
});
component.render(document.getElementById('container'), {
  width: '100%',
  height: '100%'
});   // render() is not async; see Client-Side Assembly above
```

### Key Embedding Points
- Content renders directly into your DOM — no iframes
- Container element must have explicit dimensions (not `auto`)
- Cross-origin requires CORS configuration on the Symphony server
- Same-origin requires CSRF token on mutating requests (`X-CSRF-TOKEN` from `<meta name="_csrf">`)
- White-labeling and CSS theming are fully supported

---

## Export-Then-Modify Workflow (Alternative for Complex Dashboards)

An alternative approach is the "export → modify → import" pattern. Note: the bulk export endpoints (`GET /api/dashboards/export`, `GET /api/visuals/export`) may return 500 on some instances. If so, fall back to individual GET requests.

1. **Build a template dashboard manually** in the Composer UI with the right layout and chart types
2. **Export it**: `GET /api/dashboards/{id}` for the dashboard, `GET /api/visuals/{id}` for each visual
3. **Modify the exported JSON** — change source references, field mappings, titles
4. **Create new visuals** via `POST /api/visuals` (visuals CANNOT be shared across dashboards)
5. **Create new dashboard** via `POST /api/dashboards` referencing the new visual IDs

### Where Source References Live in the JSON

When modifying an export to point at a different source, update sourceId in ALL locations:

```
dashboard
├── dashboardLayout.layout[].widgetId     → links widget to visual
├── unifiedBarCfgs[].sourceId             → time control source binding
│
visuals (separate from dashboard object)
├── visual.source.sourceId                → the primary data source
├── visual.source.sourceName              → human-readable source name
```

### Critical: Visuals Are Separate From Dashboards

A dashboard's `dashboardLayout` only defines the grid positions of widgets. The actual chart configurations (which fields, which chart type, which aggregations) live in **visual objects** that are linked by `visualId` in the widget. Each visual can only belong to ONE dashboard.

---

## Common Pitfalls

1. **Hand-crafting visual JSON** → Frontend crashes with `TypeError: Cannot read properties of undefined (reading 'values')`. ALWAYS use `initial-visual` templates.
2. **Using `application/json`** → 415 error. Always use `application/vnd.composer.v3+json`.
3. **Reading `id` instead of `visualTypeId` from visual-types endpoint** → Visual type objects use `visualTypeId` as their ID field, not `id`. Using the wrong field sends `undefined` as the type reference.
4. **Using 4-element path/params arrays** → Composer v25 uses 2-element arrays: `path: [row, col]`, `params: [height%, width%]`.
5. **Omitting widget `id` field** → Validation error: "must not be blank".
6. **Omitting `content.visualId` on widgets** → 404: "Visuals were not found [null]".
7. **Sharing visuals across dashboards** → Error: "visuals already used in other dashboards".
8. **Forgetting `level: 'IN_DASHBOARD'`** → Initial-visual returns `level: 'TOP'`. Must change to `'IN_DASHBOARD'` for dashboard-embedded visuals.
9. **Testing RLS with admin users** → Admins bypass forced filters silently. Use viewer accounts.
10. **Forgetting `isResponsive: true, isFreeForm: false`** → Dashboard layout may not render correctly.
11. **CSRF on same-origin** → POST/PUT/DELETE from the same origin require `X-CSRF-TOKEN` header, or you get a misleading "session expired" 403.
12. **Outputting scripts in markdown code blocks** → Smart quotes and backtick formatting corrupt JavaScript. Always output as downloadable `.js` files.
13. **Bulk export returning 500** → The `GET /api/dashboards/export` and `GET /api/visuals/export` endpoints may fail on some instances. Use individual GET endpoints instead.
14. **Including `unifiedBarCfgs` in dashboard creation** → Causes `HV000028: Unexpected exception during isValid call` (Hibernate validation error) on `POST /api/dashboards`. The `unifiedBarCfgs` time control configuration is NOT safe to include during initial dashboard creation. **Always omit `unifiedBarCfgs` from the dashboard POST payload.** The time filter can be added manually via the Composer UI after the dashboard is created, or configured via a subsequent PUT call once the dashboard exists.
15. **Using HISTOGRAM type for attribute/category fields** → HISTOGRAM expects a numeric field for binning (e.g., `session_cost`). Using an ATTRIBUTE field like `department` produces "Can't calculate statistics for fields: department; only numeric and time fields supported". For category-based bar charts (e.g., cost grouped by department), use a `BAR_CHART` or `VERTICAL_BAR` visual type instead, or look for a type with `X Axis` / `Y Axis` variables rather than `Group By` with `binsType`.

---

## Output Format

When generating dashboard configurations, always provide:

1. **A `.js` file** — a single all-in-one browser console script that fetches templates, creates visuals, creates the dashboard, and prints the URL
2. **Cleanup instructions** — DELETE commands for rollback
3. **Verification** — the script should print the dashboard URL on success

**CRITICAL**: Always output scripts as downloadable files via `create_file` + `present_files`. Never output long scripts in markdown code blocks — they get corrupted when users paste them.

Structure the output clearly:

```
📁 Generated Files:
├── build-dashboard.js     — All-in-one browser console script
└── (dashboard URL printed by the script on success)
```
