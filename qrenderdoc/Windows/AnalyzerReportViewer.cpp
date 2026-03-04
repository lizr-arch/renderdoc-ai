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
#include <cmath>
#include <QColor>
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDebug>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QHeaderView>
#include <QHash>
#include <QHBoxLayout>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMessageBox>
#include <QPalette>
#include <QPointer>
#include <QProcess>
#include <QSortFilterProxyModel>
#include "Code/QRDUtils.h"
#include "AnalyzerModels.h"
#include "AnalyzerReportWidgets.h"
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

QString LocalizeSeverityLabel(const rdcstr &severity)
{
  if(severity == "critical")
    return QString::fromUtf16(u"\u4e25\u91cd");
  if(severity == "warning")
    return QString::fromUtf16(u"\u8b66\u544a");
  return QString::fromUtf16(u"\u63d0\u793a");
}

QString LocalizeConfidenceLabel(const rdcstr &confidence)
{
  if(confidence == "high")
    return QString::fromUtf16(u"\u9ad8");
  if(confidence == "medium")
    return QString::fromUtf16(u"\u4e2d");
  if(confidence == "low")
    return QString::fromUtf16(u"\u4f4e");
  return ToQStr(confidence);
}

QString LocalizeCategoryLabel(const rdcstr &category)
{
  if(category == "geometry")
    return QString::fromUtf16(u"\u51e0\u4f55");
  if(category == "compute")
    return QString::fromUtf16(u"\u8ba1\u7b97");
  if(category == "bandwidth")
    return QString::fromUtf16(u"\u5e26\u5bbd");
  if(category == "state")
    return QString::fromUtf16(u"\u72b6\u6001");
  if(category == "sync")
    return QString::fromUtf16(u"\u540c\u6b65");
  if(category == "fill")
    return QString::fromUtf16(u"\u6e05\u5c4f/\u586b\u5145");
  if(category == "shader")
    return QString::fromUtf16(u"\u7740\u8272\u5668");
  if(category == "baseline")
    return QString::fromUtf16(u"\u57fa\u7ebf");
  return ToQStr(category);
}

QString ImpactLevelLabel(double impact)
{
  if(impact >= 0.8)
    return QString::fromUtf16(u"\u9ad8");
  if(impact >= 0.5)
    return QString::fromUtf16(u"\u4e2d");
  return QString::fromUtf16(u"\u4f4e");
}

QString LocalizeEvidenceMetric(const rdcstr &metric)
{
  if(metric == "baseline")
    return QString::fromUtf16(u"\u57fa\u7ebf");
  if(metric == "draw_count")
    return QString::fromUtf16(u"Draw \u8c03\u7528\u6570");
  if(metric == "dispatch_count")
    return QString::fromUtf16(u"Dispatch \u8c03\u7528\u6570");
  if(metric == "texture_bytes")
    return QString::fromUtf16(u"\u7eb9\u7406\u5360\u7528");
  if(metric == "buffer_bytes")
    return QString::fromUtf16(u"\u7f13\u51b2\u533a\u5360\u7528");
  if(metric == "pass_count")
    return QString::fromUtf16(u"Pass \u6570\u91cf");
  if(metric == "copy_events")
    return QString::fromUtf16(u"Copy \u4e8b\u4ef6\u6570");
  if(metric == "clear_events")
    return QString::fromUtf16(u"Clear \u4e8b\u4ef6\u6570");
  if(metric == "largest_rt_dim")
    return QString::fromUtf16(u"\u6700\u5927 RT \u5c3a\u5bf8");
  if(metric == "largest_rt_bytes")
    return QString::fromUtf16(u"\u6700\u5927 RT \u5927\u5c0f");
  if(metric == "uncompressed_large_textures")
    return QString::fromUtf16(u"\u5927\u7eb9\u7406\u672a\u538b\u7f29\u6570");
  if(metric == "shader_count")
    return QString::fromUtf16(u"Shader \u6570\u91cf");
  if(metric == "texture_count")
    return QString::fromUtf16(u"\u7eb9\u7406\u6570\u91cf");
  return ToQStr(metric);
}

QString LocalizeEvidenceUnit(const rdcstr &unit)
{
  if(unit == "calls")
    return QString::fromUtf16(u"\u6b21");
  if(unit == "bytes")
    return QString::fromUtf16(u"\u5b57\u8282");
  if(unit == "passes")
    return QString::fromUtf16(u"\u4e2a");
  if(unit == "events")
    return QString::fromUtf16(u"\u6b21");
  if(unit == "textures")
    return QString::fromUtf16(u"\u4e2a");
  if(unit == "shaders")
    return QString::fromUtf16(u"\u4e2a");
  if(unit == "px")
    return QString::fromUtf16(u"\u50cf\u7d20");
  return ToQStr(unit);
}

uint32_t PickIssueEventId(const AnalyzerIssue &issue)
{
  for(uint32_t eid : issue.eventIds)
  {
    if(eid != 0)
      return eid;
  }
  return 0;
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

struct MaliShaderMetrics
{
  bool valid = false;
  double totalCycles = 0.0;
  double shortestPath = 0.0;
  double longestPath = 0.0;
  double fmaCycles = 0.0;
  double cvtCycles = 0.0;
  double sfuCycles = 0.0;
  double loadStoreCycles = 0.0;
  double textureCycles = 0.0;
  double varyingCycles = 0.0;
  uint32_t workRegs = 0;
  uint32_t uniformRegs = 0;
  uint32_t spillCount = 0;
  double cost = 0.0;
  rdcstr bound;
  QString error;
};

double ComputeMaliCost(double cycles, uint32_t workRegs, uint32_t spillCount)
{
  double registerPenalty = 0.0;
  if(workRegs > 32)
    registerPenalty = (double)(workRegs - 32) * 0.5;
  double spillPenalty = (double)spillCount * 10.0;
  return cycles + registerPenalty + spillPenalty;
}

rdcstr ComputeMaliBound(const MaliShaderMetrics &m)
{
  double arith = m.fmaCycles + m.cvtCycles + m.sfuCycles;
  double ls = m.loadStoreCycles;
  double tex = m.textureCycles;
  double vary = m.varyingCycles;

  double maxVal = arith;
  const char *bound = "A";
  if(ls > maxVal)
  {
    maxVal = ls;
    bound = "LS";
  }
  if(tex > maxVal)
  {
    maxVal = tex;
    bound = "T";
  }
  if(vary > maxVal)
  {
    maxVal = vary;
    bound = "V";
  }
  return bound;
}
}

AnalyzerReportViewer::AnalyzerReportViewer(ICaptureContext &ctx, QWidget *parent)
    : QFrame(parent), ui(new Ui::AnalyzerReportViewer), m_Ctx(ctx)
{
  ui->setupUi(this);

  setWindowTitle(tr("Analyzer Report"));

  setObjectName(lit("analyzerReportRoot"));
  ApplyLightTheme();

  ui->titleLabel->setProperty("arH1", true);
  ui->infoLabel->setProperty("arCaption", true);
  ui->topIssuesTitle->setProperty("arH2", true);
  ui->issueDetailTitle->setProperty("arH2", true);
  ui->issueDetailMeta->setProperty("arCaption", true);

  ui->scoreFrame->setProperty("arCard", true);
  ui->topIssuesFrame->setProperty("arCard", true);
  ui->statsFrame->setProperty("arCard", true);
  ui->issueListFrame->setProperty("arCard", true);
  ui->issueDetailFrame->setProperty("arCard", true);
  ui->subscoreCard1->setProperty("arCard", true);
  ui->subscoreCard2->setProperty("arCard", true);
  ui->subscoreCard3->setProperty("arCard", true);
  ui->subscoreCard4->setProperty("arCard", true);
  ui->statCard1->setProperty("arCard", true);
  ui->statCard2->setProperty("arCard", true);
  ui->statCard3->setProperty("arCard", true);
  ui->statCard4->setProperty("arCard", true);

  m_IssueModel = new AnalyzerIssueModel(this);
  m_IssueSortModel = new AnalyzerIssueSortModel(this);
  m_IssueSortModel->setSourceModel(m_IssueModel);

  ui->issueTable->setModel(m_IssueSortModel);
  ui->issueTable->setSortingEnabled(true);
  ui->issueTable->setSelectionBehavior(QAbstractItemView::SelectRows);
  ui->issueTable->setSelectionMode(QAbstractItemView::SingleSelection);

  m_SeverityDelegate = new AnalyzerSeverityBadgeDelegate(this);
  m_ImpactDelegate = new AnalyzerImpactBarDelegate(this);
  ui->issueTable->setItemDelegateForColumn(AnalyzerIssueModel::ColSeverity, m_SeverityDelegate);
  ui->issueTable->setItemDelegateForColumn(AnalyzerIssueModel::ColImpact, m_ImpactDelegate);

  m_EventModel = new AnalyzerEventModel(this);
  m_EventFilter = new QSortFilterProxyModel(this);
  m_EventFilter->setSourceModel(m_EventModel);
  m_EventFilter->setFilterCaseSensitivity(Qt::CaseInsensitive);
  m_EventFilter->setFilterKeyColumn(-1);
  ui->eventTable->setModel(m_EventFilter);
  ui->eventTable->setSortingEnabled(true);
  ui->eventTable->setSelectionBehavior(QAbstractItemView::SelectRows);
  ui->eventTable->setSelectionMode(QAbstractItemView::SingleSelection);

  m_DrawDispatchModel = new AnalyzerDrawDispatchModel(this);
  m_DrawDispatchFilter = new QSortFilterProxyModel(this);
  m_DrawDispatchFilter->setSourceModel(m_DrawDispatchModel);
  m_DrawDispatchFilter->setFilterCaseSensitivity(Qt::CaseInsensitive);
  m_DrawDispatchFilter->setFilterKeyColumn(-1);
  ui->drawDispatchTable->setModel(m_DrawDispatchFilter);
  ui->drawDispatchTable->setSortingEnabled(true);
  ui->drawDispatchTable->setSelectionBehavior(QAbstractItemView::SelectRows);
  ui->drawDispatchTable->setSelectionMode(QAbstractItemView::SingleSelection);

  m_StateThrashModel = new AnalyzerStateThrashModel(this);
  m_StateThrashFilter = new QSortFilterProxyModel(this);
  m_StateThrashFilter->setSourceModel(m_StateThrashModel);
  m_StateThrashFilter->setFilterCaseSensitivity(Qt::CaseInsensitive);
  m_StateThrashFilter->setFilterKeyColumn(-1);
  ui->stateThrashTable->setModel(m_StateThrashFilter);
  ui->stateThrashTable->setSortingEnabled(true);
  ui->stateThrashTable->setSelectionBehavior(QAbstractItemView::SelectRows);
  ui->stateThrashTable->setSelectionMode(QAbstractItemView::SingleSelection);

  m_PipelineModel = new AnalyzerPipelineBandwidthModel(this);
  m_PipelineFilter = new QSortFilterProxyModel(this);
  m_PipelineFilter->setSourceModel(m_PipelineModel);
  m_PipelineFilter->setFilterCaseSensitivity(Qt::CaseInsensitive);
  m_PipelineFilter->setFilterKeyColumn(-1);
  ui->pipelineTable->setModel(m_PipelineFilter);
  ui->pipelineTable->setSortingEnabled(true);
  ui->pipelineTable->setSelectionBehavior(QAbstractItemView::SelectRows);
  ui->pipelineTable->setSelectionMode(QAbstractItemView::SingleSelection);

  m_ResourceModel = new AnalyzerResourceModel(this);
  m_ResourceFilter = new QSortFilterProxyModel(this);
  m_ResourceFilter->setSourceModel(m_ResourceModel);
  m_ResourceFilter->setFilterCaseSensitivity(Qt::CaseInsensitive);
  m_ResourceFilter->setFilterKeyColumn(-1);
  ui->resourceTable->setModel(m_ResourceFilter);
  ui->resourceTable->setSortingEnabled(true);
  ui->resourceTable->setSelectionBehavior(QAbstractItemView::SelectRows);
  ui->resourceTable->setSelectionMode(QAbstractItemView::SingleSelection);

  m_ShaderModel = new AnalyzerShaderModel(this);
  m_ShaderFilter = new AnalyzerShaderSortModel(this);
  m_ShaderFilter->setSourceModel(m_ShaderModel);
  m_ShaderFilter->setFilterCaseSensitivity(Qt::CaseInsensitive);
  m_ShaderFilter->setFilterKeyColumn(-1);
  ui->shaderTable->setModel(m_ShaderFilter);
  ui->shaderTable->setSortingEnabled(true);
  ui->shaderTable->setSelectionBehavior(QAbstractItemView::SelectRows);
  ui->shaderTable->setSelectionMode(QAbstractItemView::SingleSelection);

  ui->issueFilterEdit->setPlaceholderText(tr("Search issues..."));
  ui->eventFilterEdit->setPlaceholderText(tr("Search events..."));
  ui->drawDispatchFilterEdit->setPlaceholderText(tr("Filter draw/dispatch..."));
  ui->stateThrashFilterEdit->setPlaceholderText(tr("Filter state stats..."));
  ui->pipelineFilterEdit->setPlaceholderText(tr("Filter pipeline..."));
  ui->resourceFilterEdit->setPlaceholderText(tr("Search resources..."));
  ui->shaderFilterEdit->setPlaceholderText(tr("Search shaders..."));

  m_TopIssueModel = new AnalyzerIssueModel(this);
  m_TopIssueSortModel = new AnalyzerIssueSortModel(this);
  m_TopIssueSortModel->setSourceModel(m_TopIssueModel);
  ui->topIssuesTable->setModel(m_TopIssueSortModel);
  ui->topIssuesTable->setSelectionBehavior(QAbstractItemView::SelectRows);
  ui->topIssuesTable->setSelectionMode(QAbstractItemView::SingleSelection);
  ui->topIssuesTable->setSortingEnabled(true);
  ui->topIssuesTable->verticalHeader()->setDefaultSectionSize(44);
  ui->topIssuesTable->horizontalHeader()->setSectionResizeMode(QHeaderView::Stretch);
  ui->topIssuesTable->horizontalHeader()->setStretchLastSection(false);
  ui->topIssuesTable->horizontalHeader()->setSectionResizeMode(AnalyzerIssueModel::ColSeverity,
                                                               QHeaderView::ResizeToContents);
  ui->topIssuesTable->horizontalHeader()->setSectionResizeMode(AnalyzerIssueModel::ColImpact,
                                                               QHeaderView::ResizeToContents);
  ui->topIssuesTable->setItemDelegateForColumn(AnalyzerIssueModel::ColSeverity, m_SeverityDelegate);
  ui->topIssuesTable->setItemDelegateForColumn(AnalyzerIssueModel::ColImpact, m_ImpactDelegate);

  ui->overviewScroll->setFrameShape(QFrame::NoFrame);

  ui->overallTitle->setProperty("arCaption", true);
  ui->overallValue->setProperty("arH1", true);

  PopulateMaliGpuList();
  ConfigureTableLayout();

  m_Ctx.AddCaptureViewer(this);

  connect(ui->issueTable->selectionModel(), &QItemSelectionModel::currentRowChanged, this,
          &AnalyzerReportViewer::OnIssueSelectionChanged);
  connect(ui->issueFilterEdit, &QLineEdit::textChanged, this,
          &AnalyzerReportViewer::OnIssueFilterChanged);
  connect(ui->eventFilterEdit, &QLineEdit::textChanged, this,
          &AnalyzerReportViewer::OnEventFilterChanged);
  connect(ui->drawDispatchFilterEdit, &QLineEdit::textChanged, this,
          &AnalyzerReportViewer::OnDrawDispatchFilterChanged);
  connect(ui->stateThrashFilterEdit, &QLineEdit::textChanged, this,
          &AnalyzerReportViewer::OnStateThrashFilterChanged);
  connect(ui->pipelineFilterEdit, &QLineEdit::textChanged, this,
          &AnalyzerReportViewer::OnPipelineFilterChanged);
  connect(ui->resourceFilterEdit, &QLineEdit::textChanged, this,
          &AnalyzerReportViewer::OnResourceFilterChanged);
  connect(ui->shaderFilterEdit, &QLineEdit::textChanged, this,
          &AnalyzerReportViewer::OnShaderFilterChanged);

  OnCaptureClosed();
}

AnalyzerReportViewer::~AnalyzerReportViewer()
{
  m_Ctx.BuiltinWindowClosed(this);

  m_Ctx.RemoveCaptureViewer(this);
  delete ui;
}

void AnalyzerReportViewer::ApplyLightTheme()
{
  QPalette pal = palette();
  pal.setColor(QPalette::Window, QColor(lit("#F6F7FB")));
  pal.setColor(QPalette::Base, QColor(lit("#FFFFFF")));
  pal.setColor(QPalette::Text, QColor(lit("#111827")));
  pal.setColor(QPalette::Button, QColor(lit("#FFFFFF")));
  pal.setColor(QPalette::ButtonText, QColor(lit("#111827")));
  setPalette(pal);
  setAutoFillBackground(true);

  QFile qss(lit(":/AnalyzerReportLight.qss"));
  if(qss.open(QIODevice::ReadOnly))
    setStyleSheet(QString::fromUtf8(qss.readAll()));
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

  ui->infoLabel->setText(tr("No capture loaded"));
  ui->issueFilterEdit->clear();
  ui->eventFilterEdit->clear();
  ui->drawDispatchFilterEdit->clear();
  ui->stateThrashFilterEdit->clear();
  ui->pipelineFilterEdit->clear();
  ui->resourceFilterEdit->clear();
  ui->shaderFilterEdit->clear();

  rdcarray<AnalyzerIssue> emptyIssues;
  rdcarray<AnalyzerEventRow> emptyEvents;
  rdcarray<AnalyzerDrawDispatchRow> emptyDrawDispatch;
  rdcarray<AnalyzerStateThrashRow> emptyStateThrash;
  rdcarray<AnalyzerPipelineBandwidthRow> emptyPipeline;
  rdcarray<AnalyzerResourceRow> emptyResources;
  rdcarray<AnalyzerShaderRow> emptyShaders;

  m_IssueModel->SetIssues(emptyIssues);
  m_TopIssueModel->SetIssues(emptyIssues);
  m_EventModel->SetEvents(emptyEvents);
  m_DrawDispatchModel->SetRows(emptyDrawDispatch);
  m_StateThrashModel->SetRows(emptyStateThrash);
  m_PipelineModel->SetRows(emptyPipeline);
  m_ResourceModel->SetResources(emptyResources);
  m_ShaderModel->SetShaders(emptyShaders);
  UpdateOverviewCards();
  ClearIssueDetails();
  ResetMaliState();
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
          self->ResetMaliState();

          self->UpdateSummaryText();
          self->PopulateIssueTable();
          self->PopulateEventTable();
          self->PopulateDrawDispatchTable();
          self->PopulateStateThrashTable();
          self->PopulatePipelineTable();
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

  ui->infoLabel->setText(tr("Capture: %1 | API: %2 | Frame: %3")
                             .arg(frameName)
                             .arg(ToQStr(summary.api))
                             .arg(summary.frameNumber));

  UpdateOverviewCards();
}

double AnalyzerReportViewer::ComputeIssueWeight(const AnalyzerIssue &issue) const
{
  double impact = issue.impactScore > 0.0 ? issue.impactScore : 1.0;
  double sev = 1.0;
  if(issue.severity == "critical")
    sev = 3.0;
  else if(issue.severity == "warning")
    sev = 2.0;

  double conf = 0.6;
  if(issue.confidence == "high")
    conf = 1.0;
  else if(issue.confidence == "medium")
    conf = 0.7;
  else if(issue.confidence == "low")
    conf = 0.4;

  return sev * impact * conf;
}

double AnalyzerReportViewer::ScoreFromWeight(double weight) const
{
  double score = 100.0 - std::log1p(weight) * 12.0;
  if(score < 0.0)
    score = 0.0;
  if(score > 100.0)
    score = 100.0;
  return score;
}

void AnalyzerReportViewer::UpdateOverviewCards()
{
  const AnalyzerSummary &summary = m_Snapshot.summary;
  double texMB = (double)summary.textureBytes / (1024.0 * 1024.0);

  ui->statValue1->setText(QString::number(summary.drawCount));
  ui->statValue2->setText(QString::number(summary.dispatchCount));
  ui->statValue3->setText(QString::number(summary.passCount));
  ui->statValue4->setText(QString::asprintf("%.2f", texMB));

  double drawWeight = 0.0;
  double shaderWeight = 0.0;
  double resourceWeight = 0.0;
  double stateWeight = 0.0;

  rdcarray<rdcpair<double, AnalyzerIssue>> ranked;
  rdcarray<rdcpair<double, AnalyzerIssue>> drawIssues;
  rdcarray<rdcpair<double, AnalyzerIssue>> shaderIssues;
  rdcarray<rdcpair<double, AnalyzerIssue>> resourceIssues;
  rdcarray<rdcpair<double, AnalyzerIssue>> stateIssues;
  ranked.reserve(m_Snapshot.issues.count());
  drawIssues.reserve(m_Snapshot.issues.count());
  shaderIssues.reserve(m_Snapshot.issues.count());
  resourceIssues.reserve(m_Snapshot.issues.count());
  stateIssues.reserve(m_Snapshot.issues.count());

  for(const AnalyzerIssue &issue : m_Snapshot.issues)
  {
    double weight = ComputeIssueWeight(issue);
    ranked.push_back(rdcpair<double, AnalyzerIssue>(weight, issue));

    QString category = ToQStr(issue.category).toLower();
    if(category.contains(lit("shader")))
    {
      shaderWeight += weight;
      shaderIssues.push_back(rdcpair<double, AnalyzerIssue>(weight, issue));
    }
    else if(category.contains(lit("texture")) || category.contains(lit("resource")) ||
            category.contains(lit("buffer")))
    {
      resourceWeight += weight;
      resourceIssues.push_back(rdcpair<double, AnalyzerIssue>(weight, issue));
    }
    else if(category.contains(lit("state")) || category.contains(lit("pipeline")) ||
            category.contains(lit("sync")))
    {
      stateWeight += weight;
      stateIssues.push_back(rdcpair<double, AnalyzerIssue>(weight, issue));
    }
    else
    {
      drawWeight += weight;
      drawIssues.push_back(rdcpair<double, AnalyzerIssue>(weight, issue));
    }
  }

  double overallWeight = drawWeight + shaderWeight + resourceWeight + stateWeight;
  double overallScore = ScoreFromWeight(overallWeight);
  ui->overallValue->setText(QString::number((int)overallScore));

  double drawScore = ScoreFromWeight(drawWeight);
  double shaderScore = ScoreFromWeight(shaderWeight);
  double resourceScore = ScoreFromWeight(resourceWeight);
  double stateScore = ScoreFromWeight(stateWeight);

  ui->subscoreValue1->setText(QString::number((int)drawScore));
  ui->subscoreValue2->setText(QString::number((int)shaderScore));
  ui->subscoreValue3->setText(QString::number((int)resourceScore));
  ui->subscoreValue4->setText(QString::number((int)stateScore));

  auto formatEvidenceSummary = [](const AnalyzerIssue &issue) {
    if(issue.evidence.empty())
      return QString();
    const AnalyzerEvidence &e = issue.evidence[0];
    QString metric = LocalizeEvidenceMetric(e.metric);
    QString valueText = QString::number(e.value, 'f', 2);
    QString unitText = LocalizeEvidenceUnit(e.unit);
    if(!unitText.isEmpty())
      valueText = QFormatStr("%1 %2").arg(valueText).arg(unitText);
    QString thresholdText;
    if(e.hasThreshold)
    {
      QString thresholdValue = QString::number(e.threshold, 'f', 2);
      QString thresholdUnit = unitText;
      if(!thresholdUnit.isEmpty())
        thresholdValue = QFormatStr("%1 %2").arg(thresholdValue).arg(thresholdUnit);
      thresholdText = QFormatStr(" %1 %2").arg(ToQStr(e.comparison)).arg(thresholdValue);
    }
    return QFormatStr("%1: %2%3").arg(metric).arg(valueText).arg(thresholdText);
  };

  auto pickSummary = [&](rdcarray<rdcpair<double, AnalyzerIssue>> &issues) {
    if(issues.empty())
      return QString::fromUtf16(u"\u6682\u65e0\u8bc1\u636e");
    std::stable_sort(issues.begin(), issues.end(),
                     [](const rdcpair<double, AnalyzerIssue> &a,
                        const rdcpair<double, AnalyzerIssue> &b) { return a.first > b.first; });
    QString first = formatEvidenceSummary(issues[0].second);
    if(issues.size() < 2)
      return first;
    QString second = formatEvidenceSummary(issues[1].second);
    if(second.isEmpty())
      return first;
    return QFormatStr("%1 | %2").arg(first).arg(second);
  };

  ui->subscoreDetail1->setText(pickSummary(drawIssues));
  ui->subscoreDetail2->setText(pickSummary(shaderIssues));
  ui->subscoreDetail3->setText(pickSummary(resourceIssues));
  ui->subscoreDetail4->setText(pickSummary(stateIssues));

  std::stable_sort(ranked.begin(), ranked.end(),
                   [](const rdcpair<double, AnalyzerIssue> &a,
                      const rdcpair<double, AnalyzerIssue> &b) { return a.first > b.first; });

  rdcarray<AnalyzerIssue> topIssues;
  for(size_t i = 0; i < ranked.size() && i < 8; ++i)
    topIssues.push_back(ranked[i].second);
  m_TopIssueModel->SetIssues(topIssues);
  ui->topIssuesTable->sortByColumn(AnalyzerIssueModel::ColImpact, Qt::DescendingOrder);
}

void AnalyzerReportViewer::ClearIssueDetails()
{
  ui->issueDetailTitle->setText(QString::fromUtf16(u"\u8bf7\u9009\u62e9\u4e00\u4e2a\u95ee\u9898"));
  ui->issueDetailMeta->setText(QString());
  ui->issueRecommendationLabel->setText(QString());

  while(QLayoutItem *item = ui->issueEvidenceForm->takeAt(0))
  {
    delete item->widget();
    delete item;
  }
}

void AnalyzerReportViewer::BuildIssueEvidenceForm(const AnalyzerIssue &issue)
{
  while(QLayoutItem *item = ui->issueEvidenceForm->takeAt(0))
  {
    delete item->widget();
    delete item;
  }

  if(issue.evidence.empty())
  {
    QLabel *label = new QLabel(QString::fromUtf16(u"\u6682\u65e0\u8bc1\u636e\u3002"));
    label->setProperty("arCaption", true);
    ui->issueEvidenceForm->addRow(QString::fromUtf16(u"\u8bc1\u636e"), label);
    return;
  }

  for(const AnalyzerEvidence &evidence : issue.evidence)
  {
    QString metricLabel = LocalizeEvidenceMetric(evidence.metric);
    QString unitLabel = LocalizeEvidenceUnit(evidence.unit);
    QString valueText = QString::number(evidence.value, 'f', 2);
    if(!unitLabel.isEmpty())
      valueText = QFormatStr("%1 %2").arg(valueText).arg(unitLabel);
    if(evidence.hasThreshold)
    {
      QString thresholdText = QString::number(evidence.threshold, 'f', 2);
      if(!unitLabel.isEmpty())
        thresholdText = QFormatStr("%1 %2").arg(thresholdText).arg(unitLabel);
      valueText =
          QFormatStr("%1\n%2 %3").arg(valueText).arg(ToQStr(evidence.comparison)).arg(thresholdText);
    }

    QLabel *metric = new QLabel(metricLabel);
    QLabel *value = new QLabel(valueText);
    value->setProperty("arCaption", true);
    value->setWordWrap(true);

    QString tooltipText;
    if(!evidence.detail.empty())
      tooltipText = ToQStr(evidence.detail);
    if(!evidence.source.empty())
    {
      if(!tooltipText.isEmpty())
        tooltipText += QLatin1Char('\n');
      tooltipText += QFormatStr("%1: %2")
                         .arg(QString::fromUtf16(u"\u6765\u6e90"))
                         .arg(ToQStr(evidence.source));
    }
    if(!tooltipText.isEmpty())
      value->setToolTip(tooltipText);

    ui->issueEvidenceForm->addRow(metric, value);
  }
}

void AnalyzerReportViewer::UpdateIssueDetails(const AnalyzerIssue &issue)
{
  ui->issueDetailTitle->setText(ToQStr(issue.message));

  int impactPercent = (int)std::round(issue.impactScore * 100.0);
  QString meta =
      QString::fromUtf16(
          u"\u4e25\u91cd\u6027: %1  |  \u5f71\u54cd\u8bc4\u5206: %2%% (%3)  |  "
          u"\u53ef\u4fe1\u5ea6: %4  |  \u7c7b\u522b: %5  |  \u89c4\u5219\u7f16\u53f7: %6")
                     .arg(LocalizeSeverityLabel(issue.severity))
                     .arg(impactPercent)
                     .arg(ImpactLevelLabel(issue.impactScore))
                     .arg(LocalizeConfidenceLabel(issue.confidence))
                     .arg(LocalizeCategoryLabel(issue.category))
                     .arg(ToQStr(issue.code));
  ui->issueDetailMeta->setText(meta);
  ui->issueDetailMeta->setToolTip(
      QString::fromUtf16(
          u"\u89c4\u5219\u7f16\u53f7\u7528\u4e8e\u5b9a\u4f4d\u89c4\u5219\u4e0e\u5bfc\u51fa\u5bf9\u9f50\u3002"
          u"\u5f71\u54cd\u8bc4\u5206\u4e3a 0-1 \u7684\u4f30\u8ba1\u503c\uff0c\u8d8a\u5927\u4ee3\u8868"
          u"\u5f71\u54cd\u8d8a\u9ad8\u3002"));

  if(issue.recommendation.empty())
    ui->issueRecommendationLabel->setText(QString::fromUtf16(u"\u5efa\u8bae: -"));
  else
    ui->issueRecommendationLabel->setText(
        QString::fromUtf16(u"\u5efa\u8bae: %1").arg(ToQStr(issue.recommendation)));

  BuildIssueEvidenceForm(issue);
}

void AnalyzerReportViewer::PopulateIssueTable()
{
  m_IssueModel->SetIssues(m_Snapshot.issues);
  ui->issueTable->sortByColumn(AnalyzerIssueModel::ColSeverity, Qt::AscendingOrder);

  if(m_Snapshot.issues.empty())
  {
    ClearIssueDetails();
  }
  else
  {
    ui->issueTable->selectRow(0);
  }
}

void AnalyzerReportViewer::PopulateEventTable()
{
  m_EventModel->SetEvents(m_Snapshot.events);
  ui->eventTable->sortByColumn(0, Qt::AscendingOrder);
}

void AnalyzerReportViewer::PopulateDrawDispatchTable()
{
  m_DrawDispatchModel->SetRows(m_Snapshot.drawDispatch);
  ui->drawDispatchTable->sortByColumn(AnalyzerDrawDispatchModel::ColIndices, Qt::DescendingOrder);
}

void AnalyzerReportViewer::PopulateStateThrashTable()
{
  m_StateThrashModel->SetRows(m_Snapshot.stateThrash);
  ui->stateThrashTable->sortByColumn(AnalyzerStateThrashModel::ColShaderChanges,
                                     Qt::DescendingOrder);
}

void AnalyzerReportViewer::PopulatePipelineTable()
{
  m_PipelineModel->SetRows(m_Snapshot.pipelineBandwidth);
  ui->pipelineTable->sortByColumn(AnalyzerPipelineBandwidthModel::ColRTCount,
                                  Qt::DescendingOrder);
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
  issueHeader->setSectionResizeMode(QHeaderView::Interactive);
  issueHeader->resizeSections(QHeaderView::ResizeToContents);
  issueHeader->setSectionResizeMode(AnalyzerIssueModel::ColMessage, QHeaderView::Stretch);
  issueHeader->setSectionResizeMode(AnalyzerIssueModel::ColSeverity, QHeaderView::ResizeToContents);
  issueHeader->setSectionResizeMode(AnalyzerIssueModel::ColImpact, QHeaderView::ResizeToContents);
  ui->issueTable->setColumnHidden(AnalyzerIssueModel::ColCode, true);
  ui->issueTable->setColumnHidden(AnalyzerIssueModel::ColEID, true);

  QHeaderView *eventHeader = ui->eventTable->horizontalHeader();
  eventHeader->setStretchLastSection(false);
  eventHeader->setSectionResizeMode(QHeaderView::Interactive);
  eventHeader->resizeSections(QHeaderView::ResizeToContents);

  QHeaderView *drawDispatchHeader = ui->drawDispatchTable->horizontalHeader();
  drawDispatchHeader->setStretchLastSection(false);
  drawDispatchHeader->setSectionResizeMode(QHeaderView::Interactive);
  drawDispatchHeader->resizeSections(QHeaderView::ResizeToContents);

  QHeaderView *stateThrashHeader = ui->stateThrashTable->horizontalHeader();
  stateThrashHeader->setStretchLastSection(false);
  stateThrashHeader->setSectionResizeMode(QHeaderView::Interactive);
  stateThrashHeader->resizeSections(QHeaderView::ResizeToContents);

  QHeaderView *pipelineHeader = ui->pipelineTable->horizontalHeader();
  pipelineHeader->setStretchLastSection(false);
  pipelineHeader->setSectionResizeMode(QHeaderView::Interactive);
  pipelineHeader->resizeSections(QHeaderView::ResizeToContents);

  QHeaderView *resourceHeader = ui->resourceTable->horizontalHeader();
  resourceHeader->setStretchLastSection(false);
  resourceHeader->setSectionResizeMode(QHeaderView::Interactive);
  resourceHeader->resizeSections(QHeaderView::ResizeToContents);

  QHeaderView *shaderHeader = ui->shaderTable->horizontalHeader();
  shaderHeader->setStretchLastSection(false);
  shaderHeader->setSectionResizeMode(QHeaderView::Interactive);
  shaderHeader->resizeSections(QHeaderView::ResizeToContents);

  QHeaderView *topHeader = ui->topIssuesTable->horizontalHeader();
  topHeader->setStretchLastSection(false);
  topHeader->setSectionResizeMode(QHeaderView::Interactive);
  topHeader->setSectionResizeMode(AnalyzerIssueModel::ColMessage, QHeaderView::Stretch);
  topHeader->setSectionResizeMode(AnalyzerIssueModel::ColSeverity, QHeaderView::ResizeToContents);
  topHeader->setSectionResizeMode(AnalyzerIssueModel::ColImpact, QHeaderView::ResizeToContents);
  ui->topIssuesTable->setColumnHidden(AnalyzerIssueModel::ColCode, true);
  ui->topIssuesTable->setColumnHidden(AnalyzerIssueModel::ColEID, true);
}

void AnalyzerReportViewer::PopulateMaliGpuList()
{
  ui->maliGpuCombo->clear();
  ui->maliGpuCombo->setEditable(true);

  const char *gpuList[] = {"Mali-G1",    "Immortalis-G925", "Immortalis-G720",
                           "Mali-G725", "Mali-G720",        "Mali-G625",
                           "Mali-G620", "Immortalis-G715",  "Mali-G715",
                           "Mali-G710", "Mali-G615",        "Mali-G610",
                           "Mali-G510", "Mali-G310",        "Mali-G78AE",
                           "Mali-G78",  "Mali-G77",         "Mali-G68",
                           "Mali-G57",  "Mali-G76",         "Mali-G72",
                           "Mali-G71",  "Mali-G52",         "Mali-G51",
                           "Mali-G31",  "Mali-T880",        "Mali-T860",
                           "Mali-T830", "Mali-T820",        "Mali-T760",
                           "Mali-T720"};
  for(const char *gpu : gpuList)
    ui->maliGpuCombo->addItem(QString::fromLatin1(gpu));

  ui->maliGpuCombo->setCurrentText(lit("Mali-G78"));
}

void AnalyzerReportViewer::ResetMaliState()
{
  if(m_MaliProcess && m_MaliProcess->state() != QProcess::NotRunning)
  {
    m_MaliProcess->kill();
    m_MaliProcess->waitForFinished(2000);
  }

  m_MaliOutputPath.clear();
  m_MaliGpu.clear();
  ui->maliStatusLabel->setText(tr("Not run"));

  for(AnalyzerShaderRow &shader : m_Snapshot.shaders)
  {
    shader.maliHash.clear();
    shader.maliGpu.clear();
    shader.maliValid = false;
    shader.maliTotalCycles = 0.0f;
    shader.maliShortestPath = 0.0f;
    shader.maliLongestPath = 0.0f;
    shader.maliFmaCycles = 0.0f;
    shader.maliCvtCycles = 0.0f;
    shader.maliSfuCycles = 0.0f;
    shader.maliLoadStoreCycles = 0.0f;
    shader.maliTextureCycles = 0.0f;
    shader.maliVaryingCycles = 0.0f;
    shader.maliWorkRegs = 0;
    shader.maliUniformRegs = 0;
    shader.maliSpillCount = 0;
    shader.maliCost = 0.0f;
    shader.maliBound.clear();
    shader.maliError.clear();
  }
}

void AnalyzerReportViewer::SetBusyState(bool busy, const QString &statusText)
{
  bool hasCapture = m_Ctx.IsCaptureLoaded();

  ui->refreshButton->setEnabled(hasCapture && !busy);
  ui->exportButton->setEnabled(hasCapture && !busy);
  ui->jumpButton->setEnabled(hasCapture && !busy);
  ui->maliRunButton->setEnabled(hasCapture && !busy);
  ui->maliGpuCombo->setEnabled(hasCapture && !busy);

  ui->progressBar->setVisible(busy);
  ui->statusLabel->setText(busy ? statusText : QString());
}

void AnalyzerReportViewer::OnIssueSelectionChanged(const QModelIndex &current,
                                                   const QModelIndex &previous)
{
  Q_UNUSED(previous);

  if(!current.isValid())
  {
    ClearIssueDetails();
    return;
  }

  QModelIndex sourceIndex = m_IssueSortModel->mapToSource(current);
  AnalyzerIssue issue = m_IssueModel->IssueAt(sourceIndex.row());
  UpdateIssueDetails(issue);
}

void AnalyzerReportViewer::OnIssueFilterChanged(const QString &text)
{
  m_IssueSortModel->SetFilterText(text);
}

void AnalyzerReportViewer::OnEventFilterChanged(const QString &text)
{
  m_EventFilter->setFilterFixedString(text);
}

void AnalyzerReportViewer::OnDrawDispatchFilterChanged(const QString &text)
{
  m_DrawDispatchFilter->setFilterFixedString(text);
}

void AnalyzerReportViewer::OnStateThrashFilterChanged(const QString &text)
{
  m_StateThrashFilter->setFilterFixedString(text);
}

void AnalyzerReportViewer::OnPipelineFilterChanged(const QString &text)
{
  m_PipelineFilter->setFilterFixedString(text);
}

void AnalyzerReportViewer::OnResourceFilterChanged(const QString &text)
{
  m_ResourceFilter->setFilterFixedString(text);
}

void AnalyzerReportViewer::OnShaderFilterChanged(const QString &text)
{
  m_ShaderFilter->setFilterFixedString(text);
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

void AnalyzerReportViewer::on_maliRunButton_clicked()
{
  if(!m_Ctx.IsCaptureLoaded())
  {
    QMessageBox::warning(this, tr("Mali Analysis"), tr("No capture loaded."));
    return;
  }

  if(m_BuildInFlight)
  {
    QMessageBox::information(this, tr("Mali Analysis"),
                             tr("Please wait until report refresh is complete."));
    return;
  }

  StartMaliAnalysis();
}

void AnalyzerReportViewer::StartMaliAnalysis()
{
  if(m_MaliProcess && m_MaliProcess->state() != QProcess::NotRunning)
  {
    QMessageBox::information(this, tr("Mali Analysis"),
                             tr("Mali analysis is already running."));
    return;
  }

  const QString capturePath = m_Ctx.GetCaptureFilename();
  if(capturePath.isEmpty())
  {
    QMessageBox::warning(this, tr("Mali Analysis"), tr("No capture filename available."));
    return;
  }

  QString gpuName = ui->maliGpuCombo->currentText().trimmed();
  if(gpuName.isEmpty())
  {
    QMessageBox::warning(this, tr("Mali Analysis"), tr("Select a Mali GPU target first."));
    return;
  }

  QString rootPath = QDir(QCoreApplication::applicationDirPath()).absoluteFilePath(lit("../.."));
  QString scriptPath = QDir(rootPath).absoluteFilePath(lit("scripts/rdc_analyzer/analyze_rdc.py"));
  if(!QFileInfo::exists(scriptPath))
  {
    QMessageBox::warning(this, tr("Mali Analysis"),
                         tr("Mali analyzer script not found:\n%1").arg(scriptPath));
    return;
  }

  m_MaliGpu = gpuName;
  m_MaliOutputPath =
      QDir::tempPath() + QDir::separator() +
      QString(lit("renderdoc_mali_%1.json")).arg(QCoreApplication::applicationPid());

  if(m_MaliProcess)
  {
    m_MaliProcess->deleteLater();
    m_MaliProcess = NULL;
  }

  m_MaliProcess = new QProcess(this);
  m_MaliProcess->setWorkingDirectory(rootPath);
  QStringList args;
  args << lit("-3") << scriptPath << capturePath << lit("--core") << gpuName << lit("--json")
       << m_MaliOutputPath;

  QObject::connect(m_MaliProcess, QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
                   this, [this](int exitCode, QProcess::ExitStatus status) {
                     HandleMaliProcessFinished(exitCode, status != QProcess::NormalExit);
                   });
  QObject::connect(m_MaliProcess, &QProcess::errorOccurred, this,
                   [this](QProcess::ProcessError) {
                     ui->maliRunButton->setEnabled(m_Ctx.IsCaptureLoaded() && !m_BuildInFlight);
                     ui->maliGpuCombo->setEnabled(m_Ctx.IsCaptureLoaded() && !m_BuildInFlight);
                     ui->maliStatusLabel->setText(tr("Mali analysis failed"));
                     QMessageBox::warning(this, tr("Mali Analysis"),
                                          tr("Failed to start Mali analysis.\n\n%1")
                                              .arg(m_MaliProcess->errorString()));
                     if(m_MaliProcess)
                     {
                       m_MaliProcess->deleteLater();
                       m_MaliProcess = NULL;
                     }
                   });

  ui->maliStatusLabel->setText(tr("Running Mali analysis..."));
  ui->maliRunButton->setEnabled(false);
  ui->maliGpuCombo->setEnabled(false);

  m_MaliProcess->start(lit("py"), args);
}

void AnalyzerReportViewer::HandleMaliProcessFinished(int exitCode, bool crashed)
{
  QString stdErr;
  if(m_MaliProcess)
    stdErr = QString::fromUtf8(m_MaliProcess->readAllStandardError());

  ui->maliRunButton->setEnabled(m_Ctx.IsCaptureLoaded() && !m_BuildInFlight);
  ui->maliGpuCombo->setEnabled(m_Ctx.IsCaptureLoaded() && !m_BuildInFlight);

  if(crashed || exitCode != 0)
  {
    ui->maliStatusLabel->setText(tr("Mali analysis failed"));
    QMessageBox::warning(this, tr("Mali Analysis"),
                         tr("Mali analysis failed.\n\n%1").arg(stdErr));
    if(m_MaliProcess)
    {
      m_MaliProcess->deleteLater();
      m_MaliProcess = NULL;
    }
    return;
  }

  QString error;
  QString summary;
  if(!ApplyMaliAnalysisResults(m_MaliOutputPath, m_MaliGpu, error, &summary))
  {
    ui->maliStatusLabel->setText(tr("Mali analysis failed"));
    QMessageBox::warning(this, tr("Mali Analysis"), error);
    if(m_MaliProcess)
    {
      m_MaliProcess->deleteLater();
      m_MaliProcess = NULL;
    }
    return;
  }

  if(summary.isEmpty())
    ui->maliStatusLabel->setText(tr("Mali analysis ready (%1)").arg(m_MaliGpu));
  else
    ui->maliStatusLabel->setText(tr("Mali analysis ready (%1) - %2").arg(m_MaliGpu, summary));
  if(m_MaliProcess)
  {
    m_MaliProcess->deleteLater();
    m_MaliProcess = NULL;
  }
}

bool AnalyzerReportViewer::ApplyMaliAnalysisResults(const QString &jsonPath, const QString &gpuName,
                                                    QString &error, QString *summary)
{
  QFile file(jsonPath);
  if(!file.open(QIODevice::ReadOnly | QIODevice::Text))
  {
    error = tr("Failed to read Mali analysis JSON:\n%1").arg(jsonPath);
    return false;
  }

  QJsonParseError parseError;
  QJsonDocument doc = QJsonDocument::fromJson(file.readAll(), &parseError);
  if(parseError.error != QJsonParseError::NoError)
  {
    error = tr("Failed to parse Mali analysis JSON (%1)").arg(parseError.errorString());
    return false;
  }

  if(!doc.isArray() || doc.array().isEmpty())
  {
    error = tr("Mali analysis JSON does not contain results.");
    return false;
  }

  QJsonObject root = doc.array()[0].toObject();
  QJsonArray shaderArray = root.value(lit("shaders")).toArray();
  if(shaderArray.isEmpty())
  {
    error = tr("Mali analysis JSON has no shader metrics.");
    return false;
  }

  QHash<QString, MaliShaderMetrics> metrics;
  QHash<QString, MaliShaderMetrics> entryMetrics;
  metrics.reserve(shaderArray.size());
  entryMetrics.reserve(shaderArray.size());
  int entryCollisions = 0;
  for(const QJsonValue &value : shaderArray)
  {
    QJsonObject obj = value.toObject();
    QString hash = obj.value(lit("hash")).toString().trimmed();
    QString resourceId = obj.value(lit("resource_id")).toString().trimmed();
    QString stage = obj.value(lit("stage")).toString().trimmed().toUpper();
    QString entryName = obj.value(lit("entry_name")).toString().trimmed();
    int codeSize = obj.value(lit("size")).toInt(0);
    if(stage.isEmpty() || (hash.isEmpty() && resourceId.isEmpty()))
      continue;

    MaliShaderMetrics m;
    m.valid = obj.value(lit("valid")).toBool(false);
    m.totalCycles = obj.value(lit("total_cycles")).toDouble(0.0);
    m.shortestPath = obj.value(lit("shortest_path")).toDouble(0.0);
    m.longestPath = obj.value(lit("longest_path")).toDouble(
        obj.value(lit("total_cycles")).toDouble(0.0));
    m.fmaCycles = obj.value(lit("fma_cycles")).toDouble(0.0);
    m.cvtCycles = obj.value(lit("cvt_cycles")).toDouble(0.0);
    m.sfuCycles = obj.value(lit("sfu_cycles")).toDouble(0.0);
    m.loadStoreCycles = obj.value(lit("load_store_cycles")).toDouble(0.0);
    m.textureCycles = obj.value(lit("texture_cycles")).toDouble(0.0);
    m.varyingCycles = obj.value(lit("varying_cycles")).toDouble(0.0);
    m.workRegs = (uint32_t)obj.value(lit("work_registers")).toInt(0);
    m.uniformRegs = (uint32_t)obj.value(lit("uniform_registers")).toInt(0);
    m.spillCount = (uint32_t)obj.value(lit("spill_count")).toInt(0);
    m.error = obj.value(lit("error")).toString();
    if(m.valid)
    {
      m.cost = ComputeMaliCost(m.longestPath, m.workRegs, m.spillCount);
      m.bound = ComputeMaliBound(m);
    }
    if(!hash.isEmpty())
      metrics.insert(hash + lit("|") + stage, m);
    if(!resourceId.isEmpty())
      metrics.insert(resourceId + lit("|") + stage, m);
    if(!entryName.isEmpty() && codeSize > 0)
    {
      QString entryKey = stage + lit("|") + entryName + lit("|") + QString::number(codeSize);
      if(entryMetrics.contains(entryKey))
        entryCollisions++;
      else
        entryMetrics.insert(entryKey, m);
    }
  }

  if(metrics.isEmpty())
  {
    error = tr("Mali analysis JSON did not contain usable shader metrics.");
    return false;
  }

  int totalShaders = 0;
  int foundShaders = 0;
  int foundByHash = 0;
  int foundByResource = 0;
  int foundByEntry = 0;
  int validShaders = 0;
  int invalidShaders = 0;
  int noDataShaders = 0;
  int noSpirvShaders = 0;
  int unsupportedStageShaders = 0;
  QStringList missSamples;
  const int missSampleLimit = 5;

  rdcarray<AnalyzerShaderRow> updated = m_Snapshot.shaders;
  m_Ctx.Replay().BlockInvoke([&](IReplayController *r) {
    totalShaders = updated.count();
    for(AnalyzerShaderRow &shader : updated)
    {
      shader.maliHash.clear();
      shader.maliGpu = rdcstr(gpuName);
      shader.maliValid = false;
      shader.maliTotalCycles = 0.0f;
      shader.maliShortestPath = 0.0f;
      shader.maliLongestPath = 0.0f;
      shader.maliFmaCycles = 0.0f;
      shader.maliCvtCycles = 0.0f;
      shader.maliSfuCycles = 0.0f;
      shader.maliLoadStoreCycles = 0.0f;
      shader.maliTextureCycles = 0.0f;
      shader.maliVaryingCycles = 0.0f;
      shader.maliWorkRegs = 0;
      shader.maliUniformRegs = 0;
      shader.maliSpillCount = 0;
      shader.maliCost = 0.0f;
      shader.maliBound.clear();
      shader.maliError.clear();

      ShaderStage stage = StageFromAnalyzerLabel(shader.stage);
      if(stage == ShaderStage::Count)
      {
        shader.maliError = "Unsupported stage";
        unsupportedStageShaders++;
        continue;
      }

      rdcstr entryName;
      uint32_t byteSize = 0;
      rdcstr hash = ComputeShaderHash(r, shader.id, stage, shader.firstEID, &entryName, &byteSize);
      if(!hash.empty())
        shader.maliHash = hash;

      const QString stageKey = ToQStr(shader.stage).toUpper();
      QString hashKey;
      if(!hash.empty())
        hashKey = ToQStr(hash) + lit("|") + stageKey;
      QString resourceKey = ToQStr(shader.id) + lit("|") + stageKey;
      QString entryKey;
      if(byteSize > 0 && !entryName.empty())
        entryKey = stageKey + lit("|") + ToQStr(entryName) + lit("|") + QString::number(byteSize);

      auto it = hashKey.isEmpty() ? metrics.end() : metrics.find(hashKey);
      if(it == metrics.end())
      {
        it = metrics.find(resourceKey);
        if(it != metrics.end())
          foundByResource++;
      }
      else
      {
        foundByHash++;
      }

      if(it == metrics.end() && !entryKey.isEmpty())
      {
        auto entryIt = entryMetrics.find(entryKey);
        if(entryIt != entryMetrics.end())
        {
          it = entryIt;
          foundByEntry++;
        }
      }

      if(it == metrics.end())
      {
        if(missSamples.count() < missSampleLimit)
        {
          QString sample = lit("stage=%1 hash=%2 entry=%3 bytes=%4 entryName=%5")
                               .arg(stageKey,
                                    hashKey.isEmpty() ? lit("<none>") : hashKey,
                                    entryKey.isEmpty() ? lit("<none>") : entryKey,
                                    QString::number(byteSize),
                                    ToQStr(entryName));
          missSamples << sample;
        }
        if(hash.empty())
        {
          shader.maliError = "No SPIR-V";
          noSpirvShaders++;
        }
        else
        {
          shader.maliError = "No Mali data";
          noDataShaders++;
        }
        continue;
      }

      const MaliShaderMetrics &m = it.value();
      foundShaders++;
      shader.maliValid = m.valid;
      shader.maliTotalCycles = (float)m.totalCycles;
      shader.maliShortestPath = (float)m.shortestPath;
      shader.maliLongestPath = (float)m.longestPath;
      shader.maliFmaCycles = (float)m.fmaCycles;
      shader.maliCvtCycles = (float)m.cvtCycles;
      shader.maliSfuCycles = (float)m.sfuCycles;
      shader.maliLoadStoreCycles = (float)m.loadStoreCycles;
      shader.maliTextureCycles = (float)m.textureCycles;
      shader.maliVaryingCycles = (float)m.varyingCycles;
      shader.maliWorkRegs = m.workRegs;
      shader.maliUniformRegs = m.uniformRegs;
      shader.maliSpillCount = m.spillCount;
      shader.maliCost = (float)m.cost;
      shader.maliBound = m.bound;
      shader.maliError = rdcstr(m.error);
      if(m.valid)
        validShaders++;
      else
        invalidShaders++;
    }
  });

  m_Snapshot.shaders = updated;
  PopulateShaderTable();
  ui->shaderTable->sortByColumn(AnalyzerShaderModel::ColMaliCost, Qt::DescendingOrder);
  // Ensure proxy model refreshes after mali update.
  m_ShaderFilter->invalidate();
  ui->shaderTable->viewport()->update();

  if(!m_Snapshot.shaders.empty())
  {
    const AnalyzerShaderRow &sample = m_Snapshot.shaders[0];
    qInfo().noquote() << "Mali UI sample row:"
                      << "name=" << ToQStr(sample.name)
                      << "stage=" << ToQStr(sample.stage)
                      << "valid=" << sample.maliValid
                      << "total=" << sample.maliTotalCycles
                      << "cost=" << sample.maliCost;
  }

  if(summary)
  {
    *summary = tr("found %1/%2 (hash %3, id %4, entry %5, valid %6, invalid %7, no data %8, no SPIR-V %9, unsupported %10)")
                   .arg(foundShaders)
                   .arg(totalShaders)
                   .arg(foundByHash)
                   .arg(foundByResource)
                   .arg(foundByEntry)
                   .arg(validShaders)
                   .arg(invalidShaders)
                   .arg(noDataShaders)
                   .arg(noSpirvShaders)
                   .arg(unsupportedStageShaders);
    qInfo().noquote() << "Mali analysis summary:" << *summary << "json:" << jsonPath
                      << "entryCollisions:" << entryCollisions;
    if(!missSamples.isEmpty())
      qInfo().noquote() << "Mali match misses (sample):" << missSamples.join(lit(" | "));
  }

  return true;
}

void AnalyzerReportViewer::on_jumpButton_clicked()
{
  QWidget *currentTab = ui->tabWidget->currentWidget();

  if(currentTab == ui->eventsTab)
  {
    QModelIndexList rows = ui->eventTable->selectionModel()->selectedRows();
    if(rows.isEmpty())
    {
      QMessageBox::information(
          this, QString::fromUtf16(u"\u8df3\u8f6c\u5230\u4e8b\u4ef6"),
          QString::fromUtf16(
              u"\u8bf7\u5148\u9009\u62e9\u4e00\u884c\u4e8b\u4ef6\uff0c\u518d\u8df3\u8f6c\u5230 "
              u"Event Browser\u3002"));
      return;
    }

    uint32_t eid = rows[0].data().toUInt();
    if(eid == 0)
    {
      QMessageBox::warning(
          this, QString::fromUtf16(u"\u8df3\u8f6c\u5230\u4e8b\u4ef6"),
          QString::fromUtf16(u"\u6240\u9009\u4e8b\u4ef6\u6ca1\u6709\u6709\u6548\u7684 EID\u3002"));
      return;
    }

    m_Ctx.SetEventID({}, eid, eid, true);
    m_Ctx.ShowEventBrowser();
    return;
  }

  if(currentTab == ui->performanceTab)
  {
    QModelIndexList rows = ui->drawDispatchTable->selectionModel()->selectedRows();
    if(rows.isEmpty())
    {
      QMessageBox::information(
          this, QString::fromUtf16(u"\u8df3\u8f6c\u5230\u4e8b\u4ef6"),
          QString::fromUtf16(
              u"\u8bf7\u5148\u9009\u62e9\u4e00\u884c draw/dispatch\uff0c\u518d\u8df3\u8f6c\u5230 "
              u"Event Browser\u3002"));
      return;
    }

    uint32_t eid = rows[0].data().toUInt();
    if(eid == 0)
    {
      QMessageBox::warning(
          this, QString::fromUtf16(u"\u8df3\u8f6c\u5230\u4e8b\u4ef6"),
          QString::fromUtf16(u"\u6240\u9009\u4e8b\u4ef6\u6ca1\u6709\u6709\u6548\u7684 EID\u3002"));
      return;
    }

    m_Ctx.SetEventID({}, eid, eid, true);
    m_Ctx.ShowEventBrowser();
    return;
  }

  if(currentTab == ui->stateThrashTab)
  {
    QModelIndexList rows = ui->stateThrashTable->selectionModel()->selectedRows();
    if(rows.isEmpty())
    {
      QMessageBox::information(
          this, QString::fromUtf16(u"\u8df3\u8f6c\u5230\u4e8b\u4ef6"),
          QString::fromUtf16(
              u"\u8bf7\u5148\u9009\u62e9\u4e00\u884c\u72b6\u6001\u7edf\u8ba1\uff0c\u518d\u8df3\u8f6c\u5230 "
              u"Event Browser\u3002"));
      return;
    }

    uint32_t eid = rows[0].data(AnalyzerStateThrashModel::EventIdRole).toUInt();
    if(eid == 0)
    {
      QMessageBox::warning(
          this, QString::fromUtf16(u"\u8df3\u8f6c\u5230\u4e8b\u4ef6"),
          QString::fromUtf16(u"\u5f53\u524d\u6355\u83b7\u4e0d\u63d0\u4f9b\u6709\u6548\u7684\u4e8b\u4ef6\u4f9d\u636e\u3002"));
      return;
    }

    m_Ctx.SetEventID({}, eid, eid, true);
    m_Ctx.ShowEventBrowser();
    return;
  }

  if(currentTab == ui->pipelineTab)
  {
    QModelIndexList rows = ui->pipelineTable->selectionModel()->selectedRows();
    if(rows.isEmpty())
    {
      QMessageBox::information(
          this, QString::fromUtf16(u"\u8df3\u8f6c\u5230\u4e8b\u4ef6"),
          QString::fromUtf16(
              u"\u8bf7\u5148\u9009\u62e9\u4e00\u884c Pipeline \u6570\u636e\uff0c\u518d\u8df3\u8f6c\u5230 "
              u"Event Browser \u4e0e Pipeline State\u3002"));
      return;
    }

    uint32_t eid = rows[0].data(AnalyzerPipelineBandwidthModel::EventIdRole).toUInt();
    if(eid == 0)
    {
      QMessageBox::warning(
          this, QString::fromUtf16(u"\u8df3\u8f6c\u5230\u4e8b\u4ef6"),
          QString::fromUtf16(u"\u6240\u9009\u4e8b\u4ef6\u6ca1\u6709\u6709\u6548\u7684 EID\u3002"));
      return;
    }

    m_Ctx.SetEventID({}, eid, eid, true);
    m_Ctx.ShowEventBrowser();
    m_Ctx.ShowPipelineViewer();
    return;
  }

  if(currentTab != ui->issuesTab)
  {
    QMessageBox::information(
        this, QString::fromUtf16(u"\u8df3\u8f6c\u5230\u754c\u9762"),
        QString::fromUtf16(
            u"\u5f53\u524d\u4ec5\u652f\u6301\u5bf9 Issues \u548c Events \u8fdb\u884c\u8df3\u8f6c\u3002"));
    return;
  }

  QModelIndexList rows = ui->issueTable->selectionModel()->selectedRows();
  if(rows.isEmpty())
  {
    QMessageBox::information(
        this, QString::fromUtf16(u"\u8df3\u8f6c\u5230\u754c\u9762"),
        QString::fromUtf16(
            u"\u8bf7\u5148\u9009\u62e9\u4e00\u6761\u95ee\u9898\uff0c\u518d\u8df3\u8f6c\u5230\u5176"
            u"\u76ee\u6807\u3002"));
    return;
  }

  QModelIndex sourceIndex = m_IssueSortModel->mapToSource(rows[0]);
  AnalyzerIssue issue = m_IssueModel->IssueAt(sourceIndex.row());
  uint32_t eid = PickIssueEventId(issue);

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

  QMessageBox::warning(
      this, QString::fromUtf16(u"\u8df3\u8f6c\u5230\u754c\u9762"),
      QString::fromUtf16(
          u"\u8be5\u95ee\u9898\u6ca1\u6709\u53ef\u8df3\u8f6c\u7684\u4e8b\u4ef6\u6216\u8d44\u6e90"
          u"\u76ee\u6807\u3002"));
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

rdcstr AnalyzerReportViewer::ComputeShaderHash(IReplayController *replay, ResourceId shaderId,
                                               ShaderStage stage, uint32_t fallbackEID,
                                               rdcstr *entryNameOut, uint32_t *byteSizeOut) const
{
  if(entryNameOut)
    entryNameOut->clear();
  if(byteSizeOut)
    *byteSizeOut = 0;

  if(!replay || shaderId == ResourceId())
    return rdcstr();

  ResourceId graphicsPipelineId;
  ResourceId computePipelineId;
  if(fallbackEID != 0)
  {
    replay->SetFrameEvent(fallbackEID, false);
    const PipeState &pipe = replay->GetPipelineState();
    graphicsPipelineId = pipe.GetGraphicsPipelineObject();
    computePipelineId = pipe.GetComputePipelineObject();
  }

  rdcarray<ShaderEntryPoint> entries = replay->GetShaderEntryPoints(shaderId);
  if(entries.empty())
    return rdcstr();

  ShaderEntryPoint selected = PickEntryPointForStage(entries, stage);
  if(entryNameOut)
    *entryNameOut = selected.name;
  ResourceId pipelineId =
      PickPipelineForShaderStage(stage, selected.stage, graphicsPipelineId, computePipelineId);
  // Prefer the module reflection to keep hashes stable vs pipeline specialization.
  const ShaderReflection *refl = replay->GetShader(ResourceId(), shaderId, selected);
  if(!refl && pipelineId != ResourceId())
    refl = replay->GetShader(pipelineId, shaderId, selected);

  if(!refl)
    return rdcstr();

  if(refl->encoding != ShaderEncoding::SPIRV || refl->rawBytes.count() == 0)
    return rdcstr();

  if(byteSizeOut)
    *byteSizeOut = (uint32_t)refl->rawBytes.count();

  QByteArray bytes((const char *)refl->rawBytes.data(), refl->rawBytes.count());
  QByteArray digest = QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex();
  return rdcstr(QString::fromLatin1(digest.left(16)));
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
