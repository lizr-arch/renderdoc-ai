/******************************************************************************
 * The MIT License (MIT)
 *
 * Copyright (c) 2026 Baldur Karlsson
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 ******************************************************************************/

#include "AnalyzerReportViewer.h"
#include <QAbstractItemView>
#include <QDir>
#include <QFileInfo>
#include <QHeaderView>
#include <QMessageBox>
#include <QPointer>
#include "Code/QRDUtils.h"
#include "AnalyzerModels.h"
#include "ui_AnalyzerReportViewer.h"

namespace
{
ShaderStage StageFromAnalyzerLabel(const rdcstr &stage)
{
  if(stage == "PS")
    return ShaderStage::Pixel;
  if(stage == "VS")
    return ShaderStage::Vertex;
  if(stage == "CS")
    return ShaderStage::Compute;
  return ShaderStage::Count;
}

rdcarray<ResourceId> BuildTextureJumpCandidates(const AnalyzerIssue &issue, uint32_t fallbackEID,
                                                const rdcarray<AnalyzerEventRow> &events)
{
  rdcarray<ResourceId> candidates;
  auto appendUniqueCandidate = [&candidates](ResourceId id) {
    if(id == ResourceId())
      return;

    for(ResourceId existing : candidates)
    {
      if(existing == id)
        return;
    }

    candidates.push_back(id);
  };

  for(ResourceId id : issue.resourceIds)
    appendUniqueCandidate(id);

  if(fallbackEID != 0)
  {
    for(const AnalyzerEventRow &event : events)
    {
      if(event.eid != fallbackEID)
        continue;

      for(ResourceId rt : event.rts)
        appendUniqueCandidate(rt);

      appendUniqueCandidate(event.ds);
      break;
    }
  }

  return candidates;
}

ShaderEntryPoint PickEntryPointForStage(const rdcarray<ShaderEntryPoint> &entries,
                                        ShaderStage preferredStage)
{
  if(entries.empty())
    return ShaderEntryPoint();

  if(preferredStage != ShaderStage::Count)
  {
    for(const ShaderEntryPoint &entry : entries)
    {
      if(entry.stage == preferredStage)
        return entry;
    }
  }

  return entries[0];
}

ResourceId PickPipelineForShaderStage(ShaderStage preferredStage, ShaderStage selectedStage,
                                      ResourceId graphicsPipelineId, ResourceId computePipelineId)
{
  if(selectedStage == ShaderStage::Compute)
    return computePipelineId;
  if(selectedStage != ShaderStage::Count)
    return graphicsPipelineId;

  if(preferredStage == ShaderStage::Compute)
    return computePipelineId;
  if(preferredStage != ShaderStage::Count)
    return graphicsPipelineId;

  return ResourceId();
}
}

AnalyzerReportViewer::AnalyzerReportViewer(ICaptureContext &ctx, QWidget *parent)
    : QFrame(parent), ui(new Ui::AnalyzerReportViewer), m_Ctx(ctx)
{
  ui->setupUi(this);

  setWindowTitle(tr("Analyzer Report"));

  m_IssueModel = new AnalyzerIssueModel(this);
  m_IssueSortModel = new AnalyzerIssueSortModel(this);
  m_IssueSortModel->setSourceModel(m_IssueModel);

  ui->issueTable->setModel(m_IssueSortModel);
  ui->issueTable->setSortingEnabled(true);
  ui->issueTable->setSelectionBehavior(QAbstractItemView::SelectRows);
  ui->issueTable->setSelectionMode(QAbstractItemView::SingleSelection);

  m_EventModel = new AnalyzerEventModel(this);
  ui->eventTable->setModel(m_EventModel);
  ui->eventTable->setSortingEnabled(true);
  ui->eventTable->setSelectionBehavior(QAbstractItemView::SelectRows);
  ui->eventTable->setSelectionMode(QAbstractItemView::SingleSelection);

  m_ResourceModel = new AnalyzerResourceModel(this);
  ui->resourceTable->setModel(m_ResourceModel);
  ui->resourceTable->setSortingEnabled(true);
  ui->resourceTable->setSelectionBehavior(QAbstractItemView::SelectRows);
  ui->resourceTable->setSelectionMode(QAbstractItemView::SingleSelection);

  m_ShaderModel = new AnalyzerShaderModel(this);
  ui->shaderTable->setModel(m_ShaderModel);
  ui->shaderTable->setSortingEnabled(true);
  ui->shaderTable->setSelectionBehavior(QAbstractItemView::SelectRows);
  ui->shaderTable->setSelectionMode(QAbstractItemView::SingleSelection);
  ConfigureTableLayout();

  m_Ctx.AddCaptureViewer(this);

  OnCaptureClosed();
}

AnalyzerReportViewer::~AnalyzerReportViewer()
{
  m_Ctx.BuiltinWindowClosed(this);

  m_Ctx.RemoveCaptureViewer(this);
  delete ui;
}

void AnalyzerReportViewer::OnCaptureLoaded()
{
  RefreshReport();
}

void AnalyzerReportViewer::OnCaptureClosed()
{
  m_BuildSerial++;
  m_BuildInFlight = false;
  m_Snapshot = AnalyzerSnapshot();

  ui->summaryLabel->setText(tr("No capture loaded"));
  ui->overviewText->setPlainText(tr("Open a capture to build a native analyzer report."));

  rdcarray<AnalyzerIssue> emptyIssues;
  rdcarray<AnalyzerEventRow> emptyEvents;
  rdcarray<AnalyzerResourceRow> emptyResources;
  rdcarray<AnalyzerShaderRow> emptyShaders;

  m_IssueModel->SetIssues(emptyIssues);
  m_EventModel->SetEvents(emptyEvents);
  m_ResourceModel->SetResources(emptyResources);
  m_ShaderModel->SetShaders(emptyShaders);
  SetBusyState(false, QString());
}

void AnalyzerReportViewer::RefreshReport()
{
  if(!m_Ctx.IsCaptureLoaded())
  {
    OnCaptureClosed();
    return;
  }

  if(m_BuildInFlight)
    return;

  m_BuildInFlight = true;
  const uint32_t serial = ++m_BuildSerial;
  SetBusyState(true, tr("Building native analyzer report..."));

  FrameAnalyzer analyzer = m_FrameAnalyzer;
  IssueEngine issueEngine = m_IssueEngine;
  ICaptureContext *ctx = &m_Ctx;
  QObject *invokeTarget = m_Ctx.GetMainWindow() ? m_Ctx.GetMainWindow()->Widget() : this;
  QPointer<AnalyzerReportViewer> self(this);

  m_Ctx.Replay().AsyncInvoke(
      [analyzer, issueEngine, ctx, invokeTarget, serial, self](IReplayController *r) mutable {
        AnalyzerSnapshot snapshot = analyzer.Build(*ctx, r);
        snapshot.issues = issueEngine.Evaluate(snapshot);

        GUIInvoke::call(invokeTarget, [self, serial, snapshot] {
          if(!self || serial != self->m_BuildSerial)
            return;

          self->m_BuildInFlight = false;
          self->m_Snapshot = snapshot;

          self->UpdateSummaryText();
          self->PopulateIssueTable();
          self->PopulateEventTable();
          self->PopulateResourceTable();
          self->PopulateShaderTable();
          self->SetBusyState(false, QString());
        });
      });
}

void AnalyzerReportViewer::UpdateSummaryText()
{
  const AnalyzerSummary &summary = m_Snapshot.summary;

  QString frameName = QFileInfo(m_Ctx.GetCaptureFilename()).fileName();

  double texMB = (double)summary.textureBytes / (1024.0 * 1024.0);
  double bufMB = (double)summary.bufferBytes / (1024.0 * 1024.0);

  ui->summaryLabel->setText(
      tr("Capture: %1 | API: %2 | Frame: %3 | Draws: %4 | Dispatches: %5 | Passes: %6")
          .arg(frameName)
          .arg(ToQStr(summary.api))
          .arg(summary.frameNumber)
          .arg(summary.drawCount)
          .arg(summary.dispatchCount)
          .arg(summary.passCount));

  QString overview = tr("Native analyzer snapshot (schema: %1)\n\n"
                        "Issues: %2\n"
                        "Events: %3\n"
                        "Resources: %4\n"
                        "Shaders: %5\n"
                        "Textures: %6 (%7 MB)\n"
                        "Buffers: %8 (%9 MB)\n\n"
                        "This report is now generated directly from native C++ extraction + rules.")
                         .arg(ToQStr(m_Snapshot.schemaVersion))
                         .arg(m_Snapshot.issues.count())
                         .arg(m_Snapshot.events.count())
                         .arg(m_Snapshot.resources.count())
                         .arg(m_Snapshot.shaders.count())
                         .arg(summary.textureCount)
                         .arg(texMB, 0, 'f', 2)
                         .arg(summary.bufferCount)
                         .arg(bufMB, 0, 'f', 2);
  ui->overviewText->setPlainText(overview);
}

void AnalyzerReportViewer::PopulateIssueTable()
{
  m_IssueModel->SetIssues(m_Snapshot.issues);
  ui->issueTable->sortByColumn(AnalyzerIssueModel::ColSeverity, Qt::AscendingOrder);
}

void AnalyzerReportViewer::PopulateEventTable()
{
  m_EventModel->SetEvents(m_Snapshot.events);
  ui->eventTable->sortByColumn(0, Qt::AscendingOrder);
}

void AnalyzerReportViewer::PopulateResourceTable()
{
  m_ResourceModel->SetResources(m_Snapshot.resources);
  ui->resourceTable->sortByColumn(AnalyzerResourceModel::ColBytes, Qt::DescendingOrder);
}

void AnalyzerReportViewer::PopulateShaderTable()
{
  m_ShaderModel->SetShaders(m_Snapshot.shaders);
  ui->shaderTable->sortByColumn(AnalyzerShaderModel::ColUseCount, Qt::DescendingOrder);
}

void AnalyzerReportViewer::ConfigureTableLayout()
{
  QHeaderView *issueHeader = ui->issueTable->horizontalHeader();
  issueHeader->setStretchLastSection(false);
  issueHeader->setSectionResizeMode(QHeaderView::ResizeToContents);
  issueHeader->setSectionResizeMode(AnalyzerIssueModel::ColMessage, QHeaderView::Stretch);

  QHeaderView *eventHeader = ui->eventTable->horizontalHeader();
  eventHeader->setStretchLastSection(false);
  eventHeader->setSectionResizeMode(QHeaderView::ResizeToContents);
  eventHeader->setSectionResizeMode(1, QHeaderView::Stretch);

  QHeaderView *resourceHeader = ui->resourceTable->horizontalHeader();
  resourceHeader->setStretchLastSection(false);
  resourceHeader->setSectionResizeMode(QHeaderView::ResizeToContents);
  resourceHeader->setSectionResizeMode(AnalyzerResourceModel::ColName, QHeaderView::Stretch);

  QHeaderView *shaderHeader = ui->shaderTable->horizontalHeader();
  shaderHeader->setStretchLastSection(false);
  shaderHeader->setSectionResizeMode(QHeaderView::ResizeToContents);
  shaderHeader->setSectionResizeMode(AnalyzerShaderModel::ColName, QHeaderView::Stretch);
}

void AnalyzerReportViewer::SetBusyState(bool busy, const QString &statusText)
{
  bool hasCapture = m_Ctx.IsCaptureLoaded();

  ui->refreshButton->setEnabled(hasCapture && !busy);
  ui->exportButton->setEnabled(hasCapture && !busy);
  ui->jumpButton->setEnabled(hasCapture && !busy);

  ui->progressBar->setVisible(busy);
  ui->statusLabel->setText(busy ? statusText : QString());
}

void AnalyzerReportViewer::on_refreshButton_clicked()
{
  RefreshReport();
}

void AnalyzerReportViewer::on_exportButton_clicked()
{
  if(!m_Ctx.IsCaptureLoaded())
  {
    QMessageBox::warning(this, tr("Analyzer Export"), tr("No capture loaded."));
    return;
  }

  if(m_BuildInFlight)
  {
    QMessageBox::information(this, tr("Analyzer Export"),
                             tr("Please wait until report refresh is complete."));
    return;
  }

  if(m_Snapshot.events.empty() && m_Snapshot.issues.empty() && m_Snapshot.resources.empty() &&
     m_Snapshot.shaders.empty())
  {
    RefreshReport();
    QMessageBox::information(this, tr("Analyzer Export"),
                             tr("Report is being built. Please export again after refresh."));
    return;
  }

  QString outDir = RDDialog::getExistingDirectory(this, tr("Select analyzer export directory"));
  if(outDir.isEmpty())
    return;

  QString error;
  if(!m_Exporter.WriteAll(m_Snapshot, outDir, &error))
  {
    QMessageBox::critical(this, tr("Analyzer Export"), error);
    return;
  }

  QMessageBox::information(this, tr("Analyzer Export"),
                           tr("Exported analysis.json and issues_export.{csv,md} to:\n%1")
                               .arg(QDir::toNativeSeparators(outDir)));
}

void AnalyzerReportViewer::on_jumpButton_clicked()
{
  QModelIndexList rows = ui->issueTable->selectionModel()->selectedRows();
  if(rows.isEmpty())
    return;

  QModelIndex sourceIndex = m_IssueSortModel->mapToSource(rows[0]);
  AnalyzerIssue issue = m_IssueModel->IssueAt(sourceIndex.row());
  uint32_t eid = sourceIndex.data(AnalyzerIssueModel::EventIdRole).toUInt();

  // Prefer direct texture/shader navigation, then fallback to event browser.
  if(JumpToTextureTarget(issue, eid))
    return;

  if(JumpToShaderTarget(issue, eid))
    return;

  if(eid != 0)
  {
    m_Ctx.SetEventID({}, eid, eid, true);
    m_Ctx.ShowEventBrowser();
    return;
  }

  QMessageBox::warning(this, tr("Jump To GUI"),
                       tr("Selected issue does not have a concrete event or resource target."));
}

bool AnalyzerReportViewer::JumpToTextureTarget(const AnalyzerIssue &issue, uint32_t fallbackEID)
{
  rdcarray<ResourceId> candidates = BuildTextureJumpCandidates(issue, fallbackEID, m_Snapshot.events);

  for(ResourceId id : candidates)
  {
    if(id == ResourceId())
      continue;

    if(m_Ctx.GetTexture(id) == NULL)
      continue;

    if(fallbackEID != 0)
      m_Ctx.SetEventID({}, fallbackEID, fallbackEID, true);

    m_Ctx.ShowTextureViewer();
    m_Ctx.GetTextureViewer()->ViewTexture(id, CompType::Typeless, true);
    return true;
  }

  return false;
}

bool AnalyzerReportViewer::JumpToShaderTarget(const AnalyzerIssue &issue, uint32_t fallbackEID)
{
  ResourceId shaderId;
  ShaderStage preferredStage = ShaderStage::Count;

  for(ResourceId id : issue.resourceIds)
  {
    if(IsKnownShader(id))
    {
      shaderId = id;
      preferredStage = FindShaderStageForEvent(id, fallbackEID);
      if(preferredStage == ShaderStage::Count)
        preferredStage = FindKnownShaderStage(id);
      break;
    }
  }

  if(shaderId == ResourceId() && fallbackEID != 0)
    shaderId = FindShaderForEvent(fallbackEID, &preferredStage);

  if(shaderId == ResourceId())
    return false;

  if(preferredStage == ShaderStage::Count)
    preferredStage = FindKnownShaderStage(shaderId);

  if(fallbackEID != 0)
    m_Ctx.SetEventID({}, fallbackEID, fallbackEID, true);

  ICaptureContext *ctx = &m_Ctx;
  m_Ctx.Replay().AsyncInvoke([this, ctx, shaderId, preferredStage, fallbackEID](IReplayController *r) {
    ResourceId graphicsPipelineId;
    ResourceId computePipelineId;

    if(fallbackEID != 0)
    {
      r->SetFrameEvent(fallbackEID, false);
      const PipeState &pipe = r->GetPipelineState();
      graphicsPipelineId = pipe.GetGraphicsPipelineObject();
      computePipelineId = pipe.GetComputePipelineObject();
    }

    rdcarray<ShaderEntryPoint> entries = r->GetShaderEntryPoints(shaderId);
    if(entries.empty())
    {
      GUIInvoke::call(this, [this] {
        QMessageBox::warning(this, tr("Jump To Shader"),
                             tr("No shader entry point was available for this issue target."));
      });
      return;
    }

    ShaderEntryPoint selected = PickEntryPointForStage(entries, preferredStage);
    ResourceId pipelineId = PickPipelineForShaderStage(preferredStage, selected.stage,
                                                       graphicsPipelineId, computePipelineId);

    const ShaderReflection *refl = r->GetShader(pipelineId, shaderId, selected);
    if(!refl && pipelineId != ResourceId())
      refl = r->GetShader(ResourceId(), shaderId, selected);

    if(!refl)
    {
      GUIInvoke::call(this, [this] {
        QMessageBox::warning(this, tr("Jump To Shader"),
                             tr("Failed to load shader reflection for this issue target."));
      });
      return;
    }

    GUIInvoke::call(this, [ctx, refl, pipelineId] {
      IShaderViewer *viewer = ctx->ViewShader(refl, pipelineId);
      ctx->AddDockWindow(viewer->Widget(), DockReference::MainToolArea, NULL);
    });
  });

  return true;
}

ResourceId AnalyzerReportViewer::FindShaderForEvent(uint32_t eid, ShaderStage *stage) const
{
  if(stage)
    *stage = ShaderStage::Count;

  for(const AnalyzerEventRow &event : m_Snapshot.events)
  {
    if(event.eid != eid)
      continue;

    if(event.ps != ResourceId())
    {
      if(stage)
        *stage = ShaderStage::Pixel;
      return event.ps;
    }
    if(event.vs != ResourceId())
    {
      if(stage)
        *stage = ShaderStage::Vertex;
      return event.vs;
    }
    if(event.cs != ResourceId())
    {
      if(stage)
        *stage = ShaderStage::Compute;
      return event.cs;
    }
    break;
  }

  return ResourceId();
}

ShaderStage AnalyzerReportViewer::FindShaderStageForEvent(ResourceId shaderId, uint32_t eid) const
{
  if(shaderId == ResourceId() || eid == 0)
    return ShaderStage::Count;

  for(const AnalyzerEventRow &event : m_Snapshot.events)
  {
    if(event.eid != eid)
      continue;

    if(event.ps == shaderId)
      return ShaderStage::Pixel;
    if(event.vs == shaderId)
      return ShaderStage::Vertex;
    if(event.cs == shaderId)
      return ShaderStage::Compute;
    break;
  }

  return ShaderStage::Count;
}

ShaderStage AnalyzerReportViewer::FindKnownShaderStage(ResourceId shaderId) const
{
  if(shaderId == ResourceId())
    return ShaderStage::Count;

  for(const AnalyzerShaderRow &shader : m_Snapshot.shaders)
  {
    if(shader.id != shaderId)
      continue;

    ShaderStage stage = StageFromAnalyzerLabel(shader.stage);
    if(stage != ShaderStage::Count)
      return stage;
  }

  return ShaderStage::Count;
}

bool AnalyzerReportViewer::IsKnownShader(ResourceId id) const
{
  if(id == ResourceId())
    return false;

  for(const AnalyzerShaderRow &shader : m_Snapshot.shaders)
  {
    if(shader.id == id)
      return true;
  }

  return false;
}

#if ENABLE_UNIT_TESTS

#include <cstring>
#include "3rdparty/catch/catch.hpp"

namespace
{
ResourceId MakeAnalyzerTestResourceId(uint64_t raw)
{
  ResourceId id;
  static_assert(sizeof(ResourceId) == sizeof(uint64_t),
                "ResourceId size changed, update test helper");
  memcpy(&id, &raw, sizeof(raw));
  return id;
}
}

TEST_CASE("Analyzer texture jump candidates merge and dedup", "[analyzer]")
{
  ResourceId texA = MakeAnalyzerTestResourceId(1);
  ResourceId texB = MakeAnalyzerTestResourceId(2);
  ResourceId texC = MakeAnalyzerTestResourceId(3);

  AnalyzerIssue issue;
  issue.resourceIds.push_back(texA);

  AnalyzerEventRow event;
  event.eid = 77;
  event.rts.push_back(texA);
  event.rts.push_back(texB);
  event.ds = texC;

  rdcarray<AnalyzerEventRow> events;
  events.push_back(event);

  rdcarray<ResourceId> candidates = BuildTextureJumpCandidates(issue, 77, events);

  REQUIRE(candidates.count() == 3);
  CHECK(candidates[0] == texA);
  CHECK(candidates[1] == texB);
  CHECK(candidates[2] == texC);
}

TEST_CASE("Analyzer shader entrypoint selection prefers requested stage", "[analyzer]")
{
  ShaderEntryPoint vertexEntry;
  vertexEntry.stage = ShaderStage::Vertex;
  ShaderEntryPoint pixelEntry;
  pixelEntry.stage = ShaderStage::Pixel;

  rdcarray<ShaderEntryPoint> entries;
  entries.push_back(vertexEntry);
  entries.push_back(pixelEntry);

  ShaderEntryPoint selected = PickEntryPointForStage(entries, ShaderStage::Pixel);
  CHECK(selected.stage == ShaderStage::Pixel);
}

TEST_CASE("Analyzer shader entrypoint selection falls back to first entry", "[analyzer]")
{
  ShaderEntryPoint vertexEntry;
  vertexEntry.stage = ShaderStage::Vertex;
  ShaderEntryPoint pixelEntry;
  pixelEntry.stage = ShaderStage::Pixel;

  rdcarray<ShaderEntryPoint> entries;
  entries.push_back(vertexEntry);
  entries.push_back(pixelEntry);

  ShaderEntryPoint selected = PickEntryPointForStage(entries, ShaderStage::Compute);
  CHECK(selected.stage == ShaderStage::Vertex);
}

#endif
