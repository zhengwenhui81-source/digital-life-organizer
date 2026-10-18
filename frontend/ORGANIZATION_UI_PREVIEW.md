# Organization UI preview (Developer B)

This is an isolated **local UI view model**, not a public API or a `classify_files`
ToolResult consumer. Open Agent Workspace → 轻量智能分类整理 → choose a local
scenario → 加载演示预览. It never reads the Workspace, classifies user files,
plans actual backend operations, or approves/executes filesystem changes.
Material-mode API transport and Mock data are unchanged.

`organization-demo.js` supplies synthetic Windows paths, explicit categories,
evidence descriptions and optional empty folders. No category names or counts
are embedded in the renderer. Scenarios: mixed, empty, single, all uncertain,
same-name collision, incomplete. The visible demo label is independent of the
Agent Mock/Real selector. Unknown files have no destination and never appear in
the copy list/tree. Excluded files stay outside the plan too.

Local display-only shape (must be adapted after the team freezes a contract):

```js
{
  localPreview: true,
  pathStyle: 'windows', // or 'posix'; presentation only, no path authorization
  outputRoot: 'E:\\UI演示输出（未创建）',
  folders: [['optional empty folder']], // relative display segments
  categories: [{name: 'any category', files: [{
    filename: 'any.txt', source: 'C:\\fictional\\any.txt',
    target: ['nested', 'any.txt'], // explicit suggested target, never inferred
    evidenceKind: 'file_type', // filename | text also supported
    reason: '.txt extension only; purpose unknown'
  }]}],
  pending: [{filename: 'unknown.pdf', source: 'C:\\fictional\\unknown.pdf', reason: 'insufficient evidence'}],
  excluded: []
}
```

The module groups supplied categories, joins display paths, builds a collapsible
tree from target segments, and lists their parent folders and copies. Root is a
label / proposed destination, not an existing directory check. Empty folders are
preserved. Repeated Windows targets are compared case-insensitively for a visible
**possible collision** warning; file/folder target collisions are also shown.
It neither resolves collisions nor verifies actual disk contents, source scope,
permissions or path identity. Backend validation remains mandatory.
All data is escaped before HTML rendering; native `<details>` supports keyboard
expansion. Long paths wrap. Display segments support up to 32 levels; malformed
or deeper data gets an explicit incomplete-data state with no partial plan.

Run:

```powershell
node --test frontend/tests/*.test.cjs
node --check frontend/organization-preview.js
node --check frontend/organization-demo.js
git diff --check
```

Serve the existing application with the normal project startup command. Browser
regression: check 1280×720 and 1366×768; load each scenario, toggle folders, verify
disabled real buttons and no classification/mutation request, return to materials,
then run Mock happy path and verify Real Mode transport/error behavior. Preview
files should never appear in the material form or an outgoing API payload.

Next integration requires frozen D classification/evidence/uncertainty output
and A operation planning + `pending_operations`/`preview_id` approval/verification.
No current demo shape is a proposal to freeze a second public contract.
