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
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDebug>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QHeaderView>
#include <QHash>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMessageBox>
#include <QPointer>
#include <QProcess>
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
  PopulateMaliGpuList();
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
  issueHeader->setSectionResizeMode(QHeaderView::Interactive);
  issueHeader->resizeSections(QHeaderView::ResizeToContents);

  QHeaderView *eventHeader = ui->eventTable->horizontalHeader();
  eventHeader->setStretchLastSection(false);
  eventHeader->setSectionResizeMode(QHeaderView::Interactive);
  eventHeader->resizeSections(QHeaderView::ResizeToContents);

  QHeaderView *resourceHeader = ui->resourceTable->horizontalHeader();
  resourceHeader->setStretchLastSection(false);
  resourceHeader->setSectionResizeMode(QHeaderView::Interactive);
  resourceHeader->resizeSections(QHeaderView::ResizeToContents);

  QHeaderView *shaderHeader = ui->shaderTable->horizontalHeader();
  shaderHeader->setStretchLastSection(false);
  shaderHeader->setSectionResizeMode(QHeaderView::Interactive);
  shaderHeader->resizeSections(QHeaderView::ResizeToContents);
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
  metrics.reserve(shaderArray.size());
  for(const QJsonValue &value : shaderArray)
  {
    QJsonObject obj = value.toObject();
    QString hash = obj.value(lit("hash")).toString().trimmed();
    QString stage = obj.value(lit("stage")).toString().trimmed().toUpper();
    if(hash.isEmpty() || stage.isEmpty())
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
    metrics.insert(hash + lit("|") + stage, m);
  }

  if(metrics.isEmpty())
  {
    error = tr("Mali analysis JSON did not contain usable shader metrics.");
    return false;
  }

  int totalShaders = 0;
  int foundShaders = 0;
  int validShaders = 0;
  int invalidShaders = 0;
  int noDataShaders = 0;
  int noSpirvShaders = 0;
  int unsupportedStageShaders = 0;

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

      rdcstr hash = ComputeShaderHash(r, shader.id, stage, shader.firstEID);
      if(hash.empty())
      {
        shader.maliError = "No SPIR-V";
        noSpirvShaders++;
        continue;
      }

      shader.maliHash = hash;
      QString key = ToQStr(hash) + lit("|") + ToQStr(shader.stage).toUpper();
      auto it = metrics.find(key);
      if(it == metrics.end())
      {
        shader.maliError = "No Mali data";
        noDataShaders++;
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

  if(summary)
  {
    *summary = tr("found %1/%2 (valid %3, invalid %4, no data %5, no SPIR-V %6, unsupported %7)")
                   .arg(foundShaders)
                   .arg(totalShaders)
                   .arg(validShaders)
                   .arg(invalidShaders)
                   .arg(noDataShaders)
                   .arg(noSpirvShaders)
                   .arg(unsupportedStageShaders);
    qInfo().noquote() << "Mali analysis summary:" << *summary << "json:" << jsonPath;
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
      QMessageBox::information(this, tr("Jump To Event"),
                               tr("Select an event row to jump to the Event Browser."));
      return;
    }

    uint32_t eid = rows[0].data().toUInt();
    if(eid == 0)
    {
      QMessageBox::warning(this, tr("Jump To Event"),
                           tr("Selected event does not have a valid EID."));
      return;
    }

    m_Ctx.SetEventID({}, eid, eid, true);
    m_Ctx.ShowEventBrowser();
    return;
  }

  if(currentTab != ui->issuesTab)
  {
    QMessageBox::information(this, tr("Jump To GUI"),
                             tr("Jump is currently supported for Issues and Events only."));
    return;
  }

  QModelIndexList rows = ui->issueTable->selectionModel()->selectedRows();
  if(rows.isEmpty())
  {
    QMessageBox::information(this, tr("Jump To GUI"),
                             tr("Select an issue row to jump to its target."));
    return;
  }

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

rdcstr AnalyzerReportViewer::ComputeShaderHash(IReplayController *replay, ResourceId shaderId,
                                               ShaderStage stage, uint32_t fallbackEID) const
{
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
  ResourceId pipelineId =
      PickPipelineForShaderStage(stage, selected.stage, graphicsPipelineId, computePipelineId);
  const ShaderReflection *refl = replay->GetShader(pipelineId, shaderId, selected);
  if(!refl && pipelineId != ResourceId())
    refl = replay->GetShader(ResourceId(), shaderId, selected);

  if(!refl)
    return rdcstr();

  if(refl->encoding != ShaderEncoding::SPIRV || refl->rawBytes.count() == 0)
    return rdcstr();

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
