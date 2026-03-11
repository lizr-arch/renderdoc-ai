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

#pragma once

#include <QFrame>
#include <QJsonObject>
#include "Code/Analyzer/AnalyzerExporter.h"
#include "Code/Analyzer/FrameAnalyzer.h"
#include "Code/Analyzer/IssueEngine.h"
#include "Code/Interface/QRDInterface.h"

namespace Ui
{
class AnalyzerReportViewer;
}

class AnalyzerIssueModel;
class AnalyzerIssueSortModel;
class AnalyzerEventModel;
class AnalyzerDrawDispatchModel;
class AnalyzerStateThrashModel;
class AnalyzerPipelineBandwidthModel;
class AnalyzerGpuCounterModel;
class AnalyzerResourceModel;
class AnalyzerShaderModel;
class AnalyzerShaderSortModel;
class AnalyzerSeverityBadgeDelegate;
class AnalyzerImpactBarDelegate;
class AnalyzerTimingBadgeWidget;
class QSortFilterProxyModel;
class QProcess;

class AnalyzerReportViewer : public QFrame, public IAnalyzerReportViewer, public ICaptureViewer
{
  Q_OBJECT

public:
  explicit AnalyzerReportViewer(ICaptureContext &ctx, QWidget *parent = 0);
  ~AnalyzerReportViewer();

  // IAnalyzerReportViewer
  QWidget *Widget() override { return this; }
  void RefreshReport() override;
  // ICaptureViewer
  void OnCaptureLoaded() override;
  void OnCaptureClosed() override;
  void OnSelectedEventChanged(uint32_t eventId) override {}
  void OnEventChanged(uint32_t eventId) override {}

private slots:
  void on_refreshButton_clicked();
  void on_exportButton_clicked();
  void on_jumpButton_clicked();
  void on_maliRunButton_clicked();
  void OnIssueSelectionChanged(const QModelIndex &current, const QModelIndex &previous);
  void OnIssueFilterChanged(const QString &text);
  void OnEventFilterChanged(const QString &text);
  void OnDrawDispatchFilterChanged(const QString &text);
  void OnStateThrashFilterChanged(const QString &text);
  void OnPipelineFilterChanged(const QString &text);
  void OnGpuCounterFilterChanged(const QString &text);
  void OnResourceFilterChanged(const QString &text);
  void OnShaderFilterChanged(const QString &text);

private:
  void ApplyLightTheme();
  void UpdateSummaryText();
  void UpdateOverviewCards();
  QString ComputeTimingConfidence() const;
  void UpdateTimingNotice();
  void PopulateIssueTable();
  void PopulateEventTable();
  void PopulateDrawDispatchTable();
  void PopulateStateThrashTable();
  void PopulatePipelineTable();
  void PopulateGpuCounterTable();
  void PopulateResourceTable();
  void PopulateShaderTable();
  void ConfigureTableLayout();
  void PopulateMaliGpuList();
  void ResetMaliState();
  void StartMaliAnalysis();
  void HandleMaliProcessFinished(int exitCode, bool crashed);
  bool ApplyMaliAnalysisResults(const QString &jsonPath, const QString &gpuName, QString &error,
                                QString *summary);
  rdcstr ComputeShaderHash(IReplayController *replay, ResourceId shaderId, ShaderStage stage,
                           uint32_t fallbackEID, rdcstr *entryNameOut = NULL,
                           uint32_t *byteSizeOut = NULL) const;
  bool JumpToTextureTarget(const AnalyzerIssue &issue, uint32_t fallbackEID);
  bool JumpToShaderTarget(const AnalyzerIssue &issue, uint32_t fallbackEID);
  ResourceId FindShaderForEvent(uint32_t eid, ShaderStage *stage = NULL) const;
  ShaderStage FindShaderStageForEvent(ResourceId shaderId, uint32_t eid) const;
  ShaderStage FindKnownShaderStage(ResourceId shaderId) const;
  bool IsKnownShader(ResourceId id) const;
  void SetBusyState(bool busy, const QString &statusText);
  void UpdateIssueDetails(const AnalyzerIssue &issue);
  void ClearIssueDetails();
  void BuildIssueEvidenceForm(const AnalyzerIssue &issue);
  double ComputeIssueWeight(const AnalyzerIssue &issue) const;
  double ScoreFromWeight(double weight) const;
  QJsonObject BuildCaptureContextExport() const;

  Ui::AnalyzerReportViewer *ui = NULL;
  ICaptureContext &m_Ctx;
  AnalyzerSnapshot m_Snapshot;
  FrameAnalyzer m_FrameAnalyzer;
  IssueEngine m_IssueEngine;
  AnalyzerExporter m_Exporter;
  AnalyzerIssueModel *m_IssueModel = NULL;
  AnalyzerIssueSortModel *m_IssueSortModel = NULL;
  AnalyzerIssueModel *m_TopIssueModel = NULL;
  AnalyzerIssueSortModel *m_TopIssueSortModel = NULL;
  AnalyzerSeverityBadgeDelegate *m_SeverityDelegate = NULL;
  AnalyzerImpactBarDelegate *m_ImpactDelegate = NULL;
  AnalyzerTimingBadgeWidget *m_TimingBadge = NULL;
  AnalyzerEventModel *m_EventModel = NULL;
  QSortFilterProxyModel *m_EventFilter = NULL;
  AnalyzerDrawDispatchModel *m_DrawDispatchModel = NULL;
  QSortFilterProxyModel *m_DrawDispatchFilter = NULL;
  AnalyzerStateThrashModel *m_StateThrashModel = NULL;
  QSortFilterProxyModel *m_StateThrashFilter = NULL;
  AnalyzerPipelineBandwidthModel *m_PipelineModel = NULL;
  QSortFilterProxyModel *m_PipelineFilter = NULL;
  AnalyzerGpuCounterModel *m_GpuCounterModel = NULL;
  QSortFilterProxyModel *m_GpuCounterFilter = NULL;
  AnalyzerResourceModel *m_ResourceModel = NULL;
  QSortFilterProxyModel *m_ResourceFilter = NULL;
  AnalyzerShaderModel *m_ShaderModel = NULL;
  AnalyzerShaderSortModel *m_ShaderFilter = NULL;
  QProcess *m_MaliProcess = NULL;
  QString m_MaliOutputPath;
  QString m_MaliGpu;
  bool m_BuildInFlight = false;
  uint32_t m_BuildSerial = 0;
};
