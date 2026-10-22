# Course Material Workflow — first frontend slice

## Scope

This page is a local, browser-only interaction prototype for the course-material workflow. The repository does not contain the authoritative names/inventory of the 22 materials, so the page does not fabricate them or require exactly 22 uploads.

The page supports:
- selecting multiple files or a directory, and dropping files into the page;
- showing browser-provided filename, relative path, size and last-modified time;
- manually assigning a category, marking report candidates, and explicitly selecting a report version;
- a directory-tree preview derived only from the categories selected by the user;
- exporting a JSON manifest containing metadata and explicit user choices.

## Important boundary

This is **not** a real document-analysis or filesystem-execution workflow. File contents are not uploaded or parsed; category assignment is manual; report candidates and the selected version are user-selected. File modification time is a clue, not proof that a version is newest. The directory is only a preview and no files are copied, moved, overwritten or deleted. The list is held in browser memory for the current page session and is cleared on refresh.

The expected count of 22 is a reference indicator, not an upload limit. The actual inventory needs to be supplied before the UI can show named required-material slots or validate completeness.

## Start and inspect

From the repository root in the project's supported Python environment, start the existing app using the command documented in the local Agent run guide. Open the app root, then choose **课程材料工作台** in the top bar. The direct static route is /static/course-workflow.html.

For frontend-only state tests, run:

    node --check frontend/course-workflow.js
    node --test frontend/tests/course-workflow.test.cjs
    git diff --check

## Browser acceptance checklist

1. At desktop width (1366×768), verify the new page and the link from the main workspace.
2. Import several real, non-sensitive sample files; confirm the displayed count and metadata, and that no network upload is triggered.
3. Import a folder and confirm relative paths are visible. Re-selecting the same file should not duplicate the entry.
4. Search/filter the inventory; change a file's category and verify the directory preview changes immediately.
5. Mark two files as report candidates; explicitly select one. Verify there is no automatic version selection and the selected candidate is cleared if removed or unmarked.
6. Export the JSON manifest and inspect that it contains metadata/user selections but no document text.
7. Remove a file, clear the list, and verify the metrics, progress steps, candidate list and directory preview update together.
8. Check a narrow mobile viewport; confirm the inventory and side panels stack and controls remain usable.
9. Refresh the page; the session list should clear and the page should not claim prior work was saved.
10. Confirm no real analysis, approval or file mutation is advertised as complete.

## Next integration gate

Only after the UI is reviewed should the team connect a frozen backend contract for document parsing, semantic classification/evidence, version comparison and final report. Do not treat browser metadata or this local preview as authoritative analysis output.
