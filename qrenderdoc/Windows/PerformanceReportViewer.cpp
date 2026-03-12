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

#include "PerformanceReportViewer.h"
#include <QAbstractItemView>
#include <QFile>
#include <QFileInfo>
#include <QHeaderView>
#include <QMessageBox>
#include <QPainter>
#include <QScrollArea>
#include <QSplitter>
#include <QTextStream>
#include "Code/QRDUtils.h"
#include "data_types.h"
#include "replay_enums.h"
#include "ui_PerformanceReportViewer.h"

namespace
{
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

PerformanceReportViewer::PerformanceReportViewer(ICaptureContext &ctx, QWidget *parent)
    : QFrame(parent), ui(new Ui::PerformanceReportViewer), m_Ctx(ctx)
{
  ui->setupUi(this);
  setWindowTitle(tr("Performance Report"));

  setObjectName(lit("perfReportRoot"));
  ApplyLightTheme();

  ui->titleLabel->setProperty("perfH1", true);
  ui->infoLabel->setProperty("perfCaption", true);
  ui->oppsTitle->setProperty("perfH2", true);
  ui->evidenceTitle->setProperty("perfH2", true);
  ui->exportHtmlButton->setProperty("perfPrimary", true);

  m_OpportunityModel = new PerfOpportunityModel(this);
  m_OpportunitySort = new PerfOpportunitySortModel(this);
  m_OpportunitySort->setSourceModel(m_OpportunityModel);

  ui->oppsTable->setModel(m_OpportunitySort);
  ui->oppsTable->setSelectionBehavior(QAbstractItemView::SelectRows);
  ui->oppsTable->setSelectionMode(QAbstractItemView::SingleSelection);
  ui->oppsTable->setSortingEnabled(true);
  ui->oppsTable->setWordWrap(true);
  ui->oppsTable->verticalHeader()->setDefaultSectionSize(52);
  ui->oppsTable->horizontalHeader()->setSectionResizeMode(QHeaderView::Stretch);
  ui->oppsTable->horizontalHeader()->setStretchLastSection(false);
  ui->oppsTable->horizontalHeader()->setSectionResizeMode(PerfOpportunityModel::ColSeverity,
                                                          QHeaderView::ResizeToContents);
  ui->oppsTable->horizontalHeader()->setSectionResizeMode(PerfOpportunityModel::ColImpact,
                                                          QHeaderView::ResizeToContents);
  ui->oppsTable->horizontalHeader()->setSectionResizeMode(PerfOpportunityModel::ColJump,
                                                          QHeaderView::ResizeToContents);
  ui->oppsTable->sortByColumn(PerfOpportunityModel::ColImpact, Qt::DescendingOrder);

  m_SeverityDelegate = new PerfSeverityBadgeDelegate(this);
  m_JumpDelegate = new PerfJumpDelegate(this);
  ui->oppsTable->setItemDelegateForColumn(PerfOpportunityModel::ColSeverity, m_SeverityDelegate);
  ui->oppsTable->setItemDelegateForColumn(PerfOpportunityModel::ColJump, m_JumpDelegate);
  connect(m_JumpDelegate, &PerfJumpDelegate::JumpRequested, this,
          &PerformanceReportViewer::OnOpportunityJumpRequested);

  ui->overviewScroll->setFrameShape(QFrame::NoFrame);

  m_EventModel = new PerfEventModel(this);
  m_EventFilter = new PerfEventFilterModel(this);
  m_EventFilter->setSourceModel(m_EventModel);
  ui->eventTable->setModel(m_EventFilter);
  ui->eventTable->setSortingEnabled(true);
  ui->eventTable->setSelectionBehavior(QAbstractItemView::SelectRows);
  ui->eventTable->setSelectionMode(QAbstractItemView::SingleSelection);
  ui->eventTable->horizontalHeader()->setSectionResizeMode(QHeaderView::Stretch);
  ui->eventTable->horizontalHeader()->setSectionResizeMode(PerfEventModel::ColEID,
                                                           QHeaderView::ResizeToContents);
  ui->eventTable->horizontalHeader()->setSectionResizeMode(PerfEventModel::ColDuration,
                                                           QHeaderView::ResizeToContents);
  ui->eventTable->sortByColumn(PerfEventModel::ColDuration, Qt::DescendingOrder);

  connect(ui->oppsTable->selectionModel(), &QItemSelectionModel::currentRowChanged, this,
          &PerformanceReportViewer::OnOpportunitySelectionChanged);
  connect(ui->jumpOpportunityButton, &QPushButton::clicked, this,
          &PerformanceReportViewer::OnJumpFromEvidence);
  connect(ui->exportHtmlButton, &QPushButton::clicked, this,
          &PerformanceReportViewer::OnExportHtml);
  connect(ui->refreshButton, &QPushButton::clicked, this,
          &PerformanceReportViewer::OnRefreshClicked);
  connect(ui->eventSearch, &QLineEdit::textChanged, this,
          &PerformanceReportViewer::OnSearchTextChanged);

  m_ScoreRing = new ScoreRingWidget(ui->scoreRingHost);
  m_ScoreRing->SetLabel(tr("Overall"));
  QVBoxLayout *ringLayout = new QVBoxLayout(ui->scoreRingHost);
  ringLayout->setContentsMargins(0, 0, 0, 0);
  ringLayout->addWidget(m_ScoreRing, 0, Qt::AlignLeft | Qt::AlignVCenter);

  m_TimingBadge = new TimingBadgeWidget(ui->timingBadgeHost);
  QVBoxLayout *timingLayout = new QVBoxLayout(ui->timingBadgeHost);
  timingLayout->setContentsMargins(0, 0, 0, 0);
  timingLayout->addWidget(m_TimingBadge);

  auto makeCard = [](QFrame *frame, const QString &title) {
    ScoreCard card;
    card.frame = frame;
    card.frame->setProperty("perfCard", true);
    QVBoxLayout *layout = new QVBoxLayout(card.frame);
    layout->setContentsMargins(12, 10, 12, 10);
    card.title = new QLabel(title, card.frame);
    card.title->setProperty("perfCaption", true);
    card.value = new QLabel(lit("0"), card.frame);
    card.value->setProperty("perfH2", true);
    card.value->setAlignment(Qt::AlignRight | Qt::AlignVCenter);
    card.bar = new MiniBarWidget(card.frame);
    layout->addWidget(card.title);
    layout->addWidget(card.value);
    layout->addWidget(card.bar);
    return card;
  };

  m_SubscoreCards.push_back(makeCard(ui->subscoreCard1, tr("Fill / Overdraw")));
  m_SubscoreCards.push_back(makeCard(ui->subscoreCard2, tr("Bandwidth")));
  m_SubscoreCards.push_back(makeCard(ui->subscoreCard3, tr("Geometry")));
  m_SubscoreCards.push_back(makeCard(ui->subscoreCard4, tr("Sync / Copy")));

  m_SummaryCards.push_back(makeCard(ui->statCard1, tr("Draws")));
  m_SummaryCards.push_back(makeCard(ui->statCard2, tr("Passes")));
  m_SummaryCards.push_back(makeCard(ui->statCard3, tr("Textures")));
  m_SummaryCards.push_back(makeCard(ui->statCard4, tr("VRAM")));

  ui->scoreFrame->setProperty("perfCard", true);
  ui->oppsFrame->setProperty("perfCard", true);
  ui->summaryFrame->setProperty("perfCard", true);
  ui->previewFrame->setProperty("perfCard", true);
  ui->evidenceLeft->setProperty("perfCard", true);
  ui->evidenceRight->setProperty("perfCard", true);

  m_Ctx.AddCaptureViewer(this);
  OnCaptureClosed();
}

PerformanceReportViewer::~PerformanceReportViewer()
{
  m_Ctx.BuiltinWindowClosed(this);
  m_Ctx.RemoveCaptureViewer(this);
  delete ui;
}

void PerformanceReportViewer::ApplyLightTheme()
{
  QPalette pal = palette();
  pal.setColor(QPalette::Window, QColor("#F6F7FB"));
  pal.setColor(QPalette::Base, QColor("#FFFFFF"));
  pal.setColor(QPalette::Text, QColor("#111827"));
  pal.setColor(QPalette::Button, QColor("#FFFFFF"));
  pal.setColor(QPalette::ButtonText, QColor("#111827"));
  setPalette(pal);
  setAutoFillBackground(true);

  QFile qss(lit(":/PerfReportLight.qss"));
  if(qss.open(QIODevice::ReadOnly))
    setStyleSheet(QString::fromUtf8(qss.readAll()));
}

void PerformanceReportViewer::OnCaptureLoaded()
{
  RefreshReport();
}

void PerformanceReportViewer::OnCaptureClosed()
{
  ui->infoLabel->setText(tr("No capture loaded"));
  ui->exportHtmlButton->setEnabled(false);
  ui->refreshButton->setEnabled(false);
  m_OpportunityModel->SetOpportunities(rdcarray<PerfOpportunity>());
  m_EventModel->SetEvents(QVector<PerfEventRow>());
  m_Report = PerfReportData();
  m_Snapshot = AnalyzerSnapshot();
  m_EventDurations.clear();
  UpdateOverview();
  UpdateEvidence();
}

void PerformanceReportViewer::OnSelectedEventChanged(uint32_t)
{
}

void PerformanceReportViewer::OnEventChanged(uint32_t)
{
}

void PerformanceReportViewer::RefreshReport()
{
  BuildReportAsync();
}

void PerformanceReportViewer::BuildReportAsync()
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
  ui->infoLabel->setText(tr("Building performance report..."));
  ui->refreshButton->setEnabled(false);
  ui->exportHtmlButton->setEnabled(false);

  FrameAnalyzer analyzer = m_FrameAnalyzer;
  IssueEngine issueEngine = m_IssueEngine;
  PerformanceReportBuilder builder = m_ReportBuilder;
  ICaptureContext *ctx = &m_Ctx;
  QObject *invokeTarget = m_Ctx.GetMainWindow() ? m_Ctx.GetMainWindow()->Widget() : this;
  QPointer<PerformanceReportViewer> self(this);

  m_Ctx.Replay().AsyncInvoke([analyzer, issueEngine, builder, ctx, invokeTarget, serial, self](
                                 IReplayController *r) mutable {
    AnalyzerSnapshot snapshot = analyzer.Build(*ctx, r);
    snapshot.issues = issueEngine.Evaluate(snapshot);

    rdcstr timingConfidence = "low";
    std::map<uint32_t, double> durations;
    if(self)
      durations = self->FetchEventDurations(r, timingConfidence);

    PerfReportData report = builder.Build(snapshot, snapshot.issues,
                                          durations.empty() ? NULL : &durations, timingConfidence);

    GUIInvoke::call(invokeTarget, [self, serial, snapshot, report, durations] {
      if(!self || serial != self->m_BuildSerial)
        return;

      self->m_BuildInFlight = false;
      self->m_Snapshot = snapshot;
      self->m_Report = report;
      self->m_EventDurations = durations;
      self->UpdateOverview();
      self->UpdateEvidence();
      self->ui->refreshButton->setEnabled(true);
      self->ui->exportHtmlButton->setEnabled(true);
    });
  });
}

void PerformanceReportViewer::UpdateOverview()
{
  if(!m_Ctx.IsCaptureLoaded())
  {
    ui->infoLabel->setText(tr("No capture loaded"));
    m_ScoreRing->SetScore(0.0f);
    UpdateTimingBadge(lit("low"));
    for(ScoreCard &card : m_SubscoreCards)
      card.value->setText(lit("0"));
    for(ScoreCard &card : m_SummaryCards)
      card.value->setText(lit("0"));
    return;
  }

  QString frameName = QFileInfo(m_Ctx.GetCaptureFilename()).fileName();
  const AnalyzerSummary &summary = m_Report.summary;

  ui->infoLabel->setText(tr("Capture: %1 | API: %2 | Frame: %3")
                             .arg(frameName)
                             .arg(ToQStr(summary.api))
                             .arg(summary.frameNumber));

  UpdateScoreCards();
  UpdateSummaryCards();
  UpdateOpportunityTable();

  m_ScoreRing->SetScore(m_Report.scores.overall);
  UpdateTimingBadge(QString::fromUtf8(m_Report.timingConfidence.c_str()));
}

void PerformanceReportViewer::UpdateScoreCards()
{
  if(m_SubscoreCards.count() < 4)
    return;

  const float values[4] = {
      m_Report.scores.fill,
      m_Report.scores.bandwidth,
      m_Report.scores.geometry,
      m_Report.scores.sync,
  };

  for(int i = 0; i < 4; ++i)
  {
    m_SubscoreCards[i].value->setText(QString::number((int)values[i]));
    m_SubscoreCards[i].bar->SetValue(values[i]);
    m_SubscoreCards[i].bar->SetBarColor(QColor("#2563EB"));
  }
}

void PerformanceReportViewer::UpdateSummaryCards()
{
  if(m_SummaryCards.count() < 4)
    return;

  const AnalyzerSummary &summary = m_Report.summary;
  double texMB = (double)summary.textureBytes / (1024.0 * 1024.0);

  m_SummaryCards[0].value->setText(QString::number(summary.drawCount));
  m_SummaryCards[1].value->setText(QString::number(summary.passCount));
  m_SummaryCards[2].value->setText(QString::number(summary.textureCount));
  m_SummaryCards[3].value->setText(QString::number((int)texMB) + tr(" MB"));
}

void PerformanceReportViewer::UpdateOpportunityTable()
{
  rdcarray<PerfOpportunity> top;
  const int maxRows = 10;
  for(int i = 0; i < m_Report.opportunities.count() && i < maxRows; ++i)
    top.push_back(m_Report.opportunities[i]);

  m_OpportunityModel->SetOpportunities(top);

  if(m_OpportunityModel->rowCount() > 0)
  {
    QModelIndex first = m_OpportunitySort->index(0, 0);
    ui->oppsTable->selectionModel()->select(first, QItemSelectionModel::Select | QItemSelectionModel::Rows);
    ui->oppsTable->selectionModel()->setCurrentIndex(first, QItemSelectionModel::Select | QItemSelectionModel::Rows);
  }
}

void PerformanceReportViewer::UpdateEvidence()
{
  QModelIndex current = ui->oppsTable->selectionModel()
                             ? ui->oppsTable->selectionModel()->currentIndex()
                             : QModelIndex();
  if(!current.isValid())
  {
    ui->evidenceTitle->setText(tr("No selection"));
    m_EventModel->SetEvents(QVector<PerfEventRow>());
    return;
  }

  QModelIndex source = m_OpportunitySort->mapToSource(current);
  PerfOpportunity opp = m_OpportunityModel->OpportunityAt(source.row());
  ui->evidenceTitle->setText(ToQStr(opp.title));

  BuildEvidenceForm(opp);

  QVector<PerfEventRow> events;
  bool timingLow = QString::fromUtf8(m_Report.timingConfidence.c_str())
                       .compare(lit("low"), Qt::CaseInsensitive) == 0;
  std::map<ResourceId, QSize> rtSizes;
  for(const AnalyzerResourceRow &res : m_Snapshot.resources)
  {
    if(res.kind != "texture")
      continue;
    rtSizes[res.id] = QSize((int)res.width, (int)res.height);
  }

  for(uint32_t eid : opp.eventIds)
  {
    PerfEventRow row;
    row.eid = eid;
    for(const AnalyzerEventRow &event : m_Snapshot.events)
    {
      if(event.eid != eid)
        continue;

      row.name = ToQStr(event.name);
      row.pass = QString::number(event.passIndex);
      row.notes = ToQStr(event.type);
      if(!event.rts.empty())
      {
        ResourceId rt = event.rts[0];
        auto sizeIt = rtSizes.find(rt);
        if(sizeIt != rtSizes.end())
        {
          QSize size = sizeIt->second;
          row.rtSize = QString::number(size.width()) + lit("x") + QString::number(size.height());
        }
      }
      break;
    }

    auto it = m_EventDurations.find(eid);
    if(it != m_EventDurations.end() && it->second > 0.0)
    {
      row.durationMs = it->second * 1000.0;
      row.timingValid = !timingLow;
    }

    events.push_back(row);
  }

  m_EvidenceEvents = events;
  m_EventModel->SetEvents(events);
  ui->eventTable->sortByColumn(PerfEventModel::ColDuration, Qt::DescendingOrder);
}

void PerformanceReportViewer::BuildEvidenceForm(const PerfOpportunity &opp)
{
  QLayoutItem *item;
  while((item = ui->evidenceForm->takeAt(0)) != nullptr)
  {
    if(item->widget())
      item->widget()->deleteLater();
    if(item->layout())
      delete item->layout();
    delete item;
  }

  auto addRow = [this](const QString &name, const QString &value) {
    QLabel *label = new QLabel(name, ui->evidenceLeft);
    label->setProperty("perfCaption", true);
    QLabel *val = new QLabel(value, ui->evidenceLeft);
    val->setWordWrap(true);
    ui->evidenceForm->addRow(label, val);
  };

  addRow(tr("Rule"), ToQStr(opp.id));
  addRow(tr("Severity"), ToQStr(opp.severity));
  addRow(tr("Impact"), opp.impactMs >= 0.0 ? QString::asprintf("%.2f ms", opp.impactMs)
                                           : tr("Estimated"));
  addRow(tr("Confidence"), ToQStr(opp.confidence));

  for(const AnalyzerEvidence &ev : opp.evidence)
  {
    QString value = QString::number(ev.value, 'f', 2);
    if(!ev.unit.empty())
      value += lit(" ") + ToQStr(ev.unit);
    if(!ev.detail.empty())
      value += lit(" - ") + ToQStr(ev.detail);
    addRow(ToQStr(ev.metric), value);
  }
}

void PerformanceReportViewer::UpdateTimingBadge(const QString &confidence)
{
  m_TimingBadge->SetConfidence(confidence);
  if(confidence.compare(lit("low"), Qt::CaseInsensitive) == 0)
    m_TimingBadge->setToolTip(tr("Timing unavailable or unstable; durations are degraded."));
  else
    m_TimingBadge->setToolTip(QString());
}

void PerformanceReportViewer::OnOpportunitySelectionChanged(const QModelIndex &current,
                                                            const QModelIndex &previous)
{
  Q_UNUSED(previous);
  if(!current.isValid())
    return;

  UpdateEvidence();
}

void PerformanceReportViewer::OnOpportunityJumpRequested(const QModelIndex &index)
{
  QModelIndex source = m_OpportunitySort->mapToSource(index);
  PerfOpportunity opp = m_OpportunityModel->OpportunityAt(source.row());
  JumpToOpportunity(opp);
}

void PerformanceReportViewer::OnJumpFromEvidence()
{
  QModelIndex current = ui->oppsTable->selectionModel()
                             ? ui->oppsTable->selectionModel()->currentIndex()
                             : QModelIndex();
  if(!current.isValid())
    return;

  QModelIndex source = m_OpportunitySort->mapToSource(current);
  PerfOpportunity opp = m_OpportunityModel->OpportunityAt(source.row());
  JumpToOpportunity(opp);
}

void PerformanceReportViewer::SelectEvidenceRow(uint32_t eid)
{
  if(eid == 0 || !m_EventFilter || !ui->eventTable->selectionModel())
    return;

  for(int row = 0; row < m_EventFilter->rowCount(); ++row)
  {
    QModelIndex idx = m_EventFilter->index(row, PerfEventModel::ColEID);
    if(idx.data(Qt::DisplayRole).toUInt() == eid)
    {
      ui->eventTable->selectionModel()->select(
          idx, QItemSelectionModel::ClearAndSelect | QItemSelectionModel::Rows);
      ui->eventTable->selectionModel()->setCurrentIndex(
          idx, QItemSelectionModel::ClearAndSelect | QItemSelectionModel::Rows);
      ui->eventTable->scrollTo(idx, QAbstractItemView::PositionAtCenter);
      break;
    }
  }
}

void PerformanceReportViewer::JumpToOpportunity(const PerfOpportunity &opp)
{
  uint32_t eid = opp.eventIds.empty() ? 0 : opp.eventIds[0];
  if(eid != 0)
    m_Ctx.SetEventID({}, eid, eid, true);

  SelectEvidenceRow(eid);

  if(opp.viewHint == "texture")
  {
    if(JumpToTextureTarget(opp, eid))
      return;
  }
  else if(opp.viewHint == "shader")
  {
    if(JumpToShaderTarget(opp, eid))
      return;
  }
  else if(opp.viewHint == "pipeline")
  {
    m_Ctx.ShowPipelineViewer();
  }
  else if(opp.viewHint == "mesh")
  {
    m_Ctx.ShowMeshPreview();
  }

  m_Ctx.ShowEventBrowser();
}

rdcarray<ResourceId> PerformanceReportViewer::BuildTextureJumpCandidates(const PerfOpportunity &opp,
                                                                         uint32_t fallbackEID)
{
  rdcarray<ResourceId> candidates;
  auto appendUnique = [&candidates](ResourceId id) {
    if(id == ResourceId())
      return;
    for(ResourceId existing : candidates)
    {
      if(existing == id)
        return;
    }
    candidates.push_back(id);
  };

  for(ResourceId id : opp.resourceIds)
    appendUnique(id);

  if(fallbackEID != 0)
  {
    for(const AnalyzerEventRow &event : m_Snapshot.events)
    {
      if(event.eid != fallbackEID)
        continue;

      for(ResourceId rt : event.rts)
        appendUnique(rt);
      appendUnique(event.ds);
      break;
    }
  }

  return candidates;
}

bool PerformanceReportViewer::JumpToTextureTarget(const PerfOpportunity &opp, uint32_t fallbackEID)
{
  rdcarray<ResourceId> candidates = BuildTextureJumpCandidates(opp, fallbackEID);

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

ResourceId PerformanceReportViewer::FindShaderForEvent(uint32_t eid, ShaderStage *stage) const
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

bool PerformanceReportViewer::JumpToShaderTarget(const PerfOpportunity &opp, uint32_t fallbackEID)
{
  ResourceId shaderId;
  ShaderStage preferredStage = ShaderStage::Count;

  for(ResourceId id : opp.resourceIds)
  {
    for(const AnalyzerShaderRow &shader : m_Snapshot.shaders)
    {
      if(shader.id == id)
      {
        shaderId = id;
        break;
      }
    }
  }

  if(shaderId == ResourceId() && fallbackEID != 0)
    shaderId = FindShaderForEvent(fallbackEID, &preferredStage);

  if(shaderId == ResourceId())
    return false;

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
                             tr("No shader entry point available for this target."));
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
                             tr("Failed to load shader reflection for this target."));
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

double PerformanceReportViewer::ExtractCounterValue(const CounterDescription &desc,
                                                    const CounterResult &res) const
{
  if(desc.resultType == CompType::UInt)
  {
    return desc.resultByteWidth == 4 ? (double)res.value.u32 : (double)res.value.u64;
  }
  return desc.resultByteWidth == 4 ? (double)res.value.f : (double)res.value.d;
}

std::map<uint32_t, double> PerformanceReportViewer::FetchEventDurations(IReplayController *r,
                                                                        rdcstr &confidence) const
{
  std::map<uint32_t, double> durations;
  rdcarray<GPUCounter> available = r->EnumerateCounters();
  bool hasDuration = false;
  for(GPUCounter c : available)
  {
    if(c == GPUCounter::EventGPUDuration)
    {
      hasDuration = true;
      break;
    }
  }

  if(!hasDuration)
  {
    confidence = "low";
    return durations;
  }

  rdcarray<GPUCounter> counters;
  counters.push_back(GPUCounter::EventGPUDuration);
  CounterDescription desc = r->DescribeCounter(GPUCounter::EventGPUDuration);
  rdcarray<CounterResult> results = r->FetchCounters(counters);

  if(results.empty())
  {
    confidence = "low";
    return durations;
  }

  uint32_t nonZero = 0;
  for(const CounterResult &res : results)
  {
    double value = ExtractCounterValue(desc, res);
    if(value > 0.0)
      nonZero++;
    durations[res.eventId] = value;
  }

  double coverage = (results.empty() ? 0.0 : (double)nonZero / (double)results.size());
  if(coverage < 0.2)
    confidence = "low";
  else if(coverage < 0.6)
    confidence = "medium";
  else
    confidence = "high";

  return durations;
}

void PerformanceReportViewer::OnExportHtml()
{
  if(!m_Ctx.IsCaptureLoaded())
  {
    QMessageBox::warning(this, tr("Export HTML"), tr("No capture loaded."));
    return;
  }

  QString path = RDDialog::getSaveFileName(this, tr("Export Performance Report"),
                                           tr("performance_report.html"),
                                           tr("HTML files (*.html)"));
  if(path.isEmpty())
    return;

  QString css = lit("body{font-family:Segoe UI,Arial,sans-serif;background:#F6F7FB;color:#111827;}"
                    ".card{background:#fff;border:1px solid #E5E7EB;border-radius:8px;padding:16px;margin:12px 0;}"
                    ".badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:600;}"
                    ".badge.warn{background:#FEF3C7;color:#92400E;}"
                    ".badge.crit{background:#FEE2E2;color:#991B1B;}"
                    ".badge.info{background:#DBEAFE;color:#1D4ED8;}"
                    "table{width:100%;border-collapse:collapse;}th,td{padding:6px;border-bottom:1px solid #E5E7EB;}");

  QString html;
  QTextStream stream(&html);
  stream << "<html><head><meta charset=\"utf-8\"><style>" << css
         << "</style></head><body>";
  stream << "<h1>Performance Report</h1>";
  stream << "<div class=\"card\"><b>Overall Score:</b> " << m_Report.scores.overall << "</div>";

  stream << "<div class=\"card\"><h2>Top Opportunities</h2><table>";
  stream << "<tr><th>Severity</th><th>Opportunity</th><th>Impact</th></tr>";
  int count = 0;
  for(const PerfOpportunity &opp : m_Report.opportunities)
  {
    if(count++ >= 10)
      break;
    QString sev = ToQStr(opp.severity);
    QString badgeClass =
        sev == lit("critical") ? lit("crit") : (sev == lit("warning") ? lit("warn") : lit("info"));
    stream << "<tr><td><span class=\"badge " << badgeClass << "\">" << sev
           << "</span></td><td>" << ToQStr(opp.why) << "</td><td>";
    if(opp.impactMs >= 0.0)
      stream << QString::asprintf("%.2f ms", opp.impactMs);
    else
      stream << "Est.";
    stream << "</td></tr>";
  }
  stream << "</table></div>";

  stream << "<div class=\"card\"><h2>Evidence</h2><table>";
  stream << "<tr><th>EID</th><th>Duration</th><th>Pass</th><th>RT Size</th><th>Notes</th></tr>";
  for(const PerfEventRow &row : m_EvidenceEvents)
  {
    stream << "<tr><td>" << row.eid << "</td><td>";
    if(row.timingValid)
      stream << QString::asprintf("%.3f ms", row.durationMs);
    else
      stream << "-";
    stream << "</td><td>" << row.pass << "</td><td>" << row.rtSize << "</td><td>" << row.notes
           << "</td></tr>";
  }
  stream << "</table></div>";
  stream << "</body></html>";

  QFile out(path);
  if(!out.open(QIODevice::WriteOnly | QIODevice::Truncate))
  {
    QMessageBox::critical(this, tr("Export HTML"), tr("Failed to write HTML report."));
    return;
  }

  out.write(html.toUtf8());
  out.close();

  QMessageBox::information(this, tr("Export HTML"), tr("Performance report exported."));
}

void PerformanceReportViewer::OnSearchTextChanged(const QString &text)
{
  if(m_EventFilter)
    m_EventFilter->SetFilterText(text);
}

void PerformanceReportViewer::OnRefreshClicked()
{
  RefreshReport();
}
