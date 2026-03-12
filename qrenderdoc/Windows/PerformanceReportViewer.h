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

#include <map>
#include <QFrame>
#include <QLabel>
#include <QPointer>
#include <QVector>
#include "Code/Analyzer/FrameAnalyzer.h"
#include "Code/Analyzer/IssueEngine.h"
#include "Code/Analyzer/PerformanceReportBuilder.h"
#include "Code/Interface/QRDInterface.h"
#include "Windows/PerformanceReportModels.h"
#include "Windows/PerformanceReportWidgets.h"

namespace Ui
{
class PerformanceReportViewer;
}

class PerformanceReportViewer : public QFrame, public IPerformanceReportViewer, public ICaptureViewer
{
  Q_OBJECT

public:
  explicit PerformanceReportViewer(ICaptureContext &ctx, QWidget *parent = nullptr);
  ~PerformanceReportViewer() override;

  // IPerformanceReportViewer
  QWidget *Widget() override { return this; }
  void RefreshReport() override;

  // ICaptureViewer
  void OnCaptureLoaded() override;
  void OnCaptureClosed() override;
  void OnSelectedEventChanged(uint32_t eventId) override;
  void OnEventChanged(uint32_t eventId) override;

private slots:
  void OnOpportunitySelectionChanged(const QModelIndex &current, const QModelIndex &previous);
  void OnOpportunityJumpRequested(const QModelIndex &index);
  void OnJumpFromEvidence();
  void OnExportHtml();
  void OnSearchTextChanged(const QString &text);
  void OnRefreshClicked();

private:
  void ApplyLightTheme();
  void BuildReportAsync();
  void UpdateOverview();
  void UpdateEvidence();
  void UpdateTimingBadge(const QString &confidence);
  void UpdateSummaryCards();
  void UpdateScoreCards();
  void UpdateOpportunityTable();
  void UpdateEventTable();
  void BuildEvidenceForm(const PerfOpportunity &opp);
  void SelectEvidenceRow(uint32_t eid);
  void JumpToOpportunity(const PerfOpportunity &opp);
  rdcarray<ResourceId> BuildTextureJumpCandidates(const PerfOpportunity &opp, uint32_t fallbackEID);
  ResourceId FindShaderForEvent(uint32_t eid, ShaderStage *stage) const;
  bool JumpToTextureTarget(const PerfOpportunity &opp, uint32_t fallbackEID);
  bool JumpToShaderTarget(const PerfOpportunity &opp, uint32_t fallbackEID);

  std::map<uint32_t, double> FetchEventDurations(IReplayController *r, rdcstr &confidence) const;
  double ExtractCounterValue(const CounterDescription &desc, const CounterResult &res) const;

  Ui::PerformanceReportViewer *ui = nullptr;
  ICaptureContext &m_Ctx;

  FrameAnalyzer m_FrameAnalyzer;
  IssueEngine m_IssueEngine;
  PerformanceReportBuilder m_ReportBuilder;

  PerfOpportunityModel *m_OpportunityModel = nullptr;
  PerfOpportunitySortModel *m_OpportunitySort = nullptr;
  PerfEventModel *m_EventModel = nullptr;
  PerfEventFilterModel *m_EventFilter = nullptr;

  PerfSeverityBadgeDelegate *m_SeverityDelegate = nullptr;
  PerfJumpDelegate *m_JumpDelegate = nullptr;

  ScoreRingWidget *m_ScoreRing = nullptr;
  TimingBadgeWidget *m_TimingBadge = nullptr;

  struct ScoreCard
  {
    QFrame *frame = nullptr;
    QLabel *title = nullptr;
    QLabel *value = nullptr;
    MiniBarWidget *bar = nullptr;
  };

  QVector<ScoreCard> m_SubscoreCards;
  QVector<ScoreCard> m_SummaryCards;

  PerfReportData m_Report;
  QVector<PerfEventRow> m_EvidenceEvents;
  AnalyzerSnapshot m_Snapshot;
  std::map<uint32_t, double> m_EventDurations;

  bool m_BuildInFlight = false;
  uint32_t m_BuildSerial = 0;
};
