Scope / Assumptions
- Implement Events tab jump-to-Event Browser when clicking Jump.
- Keep Issues tab jump behavior, but only when Issues tab is active.
- Texture/Shader jump design is out of scope for this change (explicitly defer).
- Display Resource Size in MB (decimal, 2 dp) instead of hex bytes.
- Column headers: default auto-fit + allow manual resize for all tables.
- MCP tools unavailable in this session; evidence is from local rg/reads.

File List (targets with evidence line refs)
- `qrenderdoc/Windows/AnalyzerReportViewer.cpp:301` ConfigureTableLayout (header resize mode)
- `qrenderdoc/Windows/AnalyzerReportViewer.cpp:381` on_jumpButton_clicked (tab-specific jump)
- `qrenderdoc/Windows/AnalyzerModels.cpp:320` AnalyzerResourceModel::data (Size display)
- `qrenderdoc/Windows/AnalyzerReportViewer.ui:107` QTabWidget + tab names (issuesTab/eventsTab)

Pseudo-code / Proposed edits
1) Header resize behavior
```
void AnalyzerReportViewer::ConfigureTableLayout()
{
  auto configureHeader = [](QHeaderView *header) {
    header->setStretchLastSection(false);
    header->setSectionResizeMode(QHeaderView::Interactive);
    header->resizeSections(QHeaderView::ResizeToContents); // default auto-fit
  };

  configureHeader(ui->issueTable->horizontalHeader());
  configureHeader(ui->eventTable->horizontalHeader());
  configureHeader(ui->resourceTable->horizontalHeader());
  configureHeader(ui->shaderTable->horizontalHeader());
}
```

2) Resource Size display (MB)
```
case ColBytes:
{
  double mb = (double)resource.bytes / (1024.0 * 1024.0);
  return QFormatStr("%1 MB").arg(mb, 0, 'f', 2);
}
```

3) Jump button: tab-specific behavior
```
void AnalyzerReportViewer::on_jumpButton_clicked()
{
  QWidget *current = ui->tabWidget->currentWidget();

  if(current == ui->eventsTab)
  {
    QModelIndexList rows = ui->eventTable->selectionModel()->selectedRows();
    if(rows.isEmpty()) { info("Select an event row."); return; }
    uint32_t eid = rows[0].data().toUInt();
    if(eid == 0) { warning("Selected event has no valid EID."); return; }
    m_Ctx.SetEventID({}, eid, eid, true);
    m_Ctx.ShowEventBrowser();
    return;
  }

  if(current == ui->issuesTab)
  {
    // existing issue jump (textures/shaders/event fallback)
    if(!issue row selected) { info("Select an issue row."); return; }
    ... existing logic ...
    return;
  }

  info("Jump is not available for this tab yet.");
}
```

Impact Analysis
- UI only; no capture data extraction changes.
- Size formatting now in MB: affects display only, sorting remains on raw bytes.
- Jump behavior becomes tab-specific (prevents confusing cross-tab jump).

Risks / Blockers
- If users expect Jump to work from other tabs, they will now see an explicit message.
- Auto-fit + interactive headers could slightly change initial column widths.

Build / Test / Lint Quick Guide (do not run in /plan)
- Build (Windows MSBuild):
  `"/mnt/e/Program Files/Microsoft Visual Studio/2022/Community/MSBuild/Current/Bin/MSBuild.exe" renderdoc.sln /p:Configuration=Development /p:Platform=x64 /m`
  Expected: "Build succeeded."
- Unit tests:
  `D:\Code\git\renderdoc\x64\Development\qrenderdoc.exe --unittest`
  Expected: tests complete with 0 failures.

Task Checklist (2–5 min steps)
- [x] Update ConfigureTableLayout to Interactive + resizeSections for all tables.
- [x] Change Resource Size display to MB with 2 decimals.
- [x] Make Jump button tab-specific; implement Events → Event Browser jump.
- [x] Add info/warn prompts when no row selected / unsupported tab.
- [x] Update `/plans/2026-02-25-174102-Agent01-NativeQt-PerfectReport.md` in /do.
- [ ] Verify manually: Events Jump, Size display, header resizing.

Verification / Acceptance (Definition of Done)
- Events tab: select a row, click Jump → Event Browser opens to that EID.
- Resources tab: Size column shows “X.XX MB” (no hex), sorting still works.
- All tables: headers auto-fit initially; user can drag to resize columns.

Next Steps
- Manual GUI verification on a real capture.

/do Execution Log (2026-02-26 12:30)
- Updated table headers to default auto-fit + interactive resize.
- Resource Size column now shows MB (2 decimals).
- Jump button is tab-aware: Events -> Event Browser; Issues keeps existing target logic.
- Verification:
  - MSBuild Development|x64: PASS after closing qrenderdoc (initial LNK1168 due to locked renderdoc.dll).
  - `qrenderdoc.exe --unittest`: PASS (exit 0). qrenderdoc left running; terminated to avoid DLL lock.
