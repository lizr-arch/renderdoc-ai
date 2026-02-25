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
class AnalyzerResourceModel;
class AnalyzerShaderModel;

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

private:
  void UpdateSummaryText();
  void PopulateIssueTable();
  void PopulateEventTable();
  void PopulateResourceTable();
  void PopulateShaderTable();
  bool JumpToTextureTarget(const AnalyzerIssue &issue, uint32_t fallbackEID);
  bool JumpToShaderTarget(const AnalyzerIssue &issue, uint32_t fallbackEID);
  ResourceId FindShaderForEvent(uint32_t eid) const;
  bool IsKnownShader(ResourceId id) const;
  void SetBusyState(bool busy, const QString &statusText);

  Ui::AnalyzerReportViewer *ui = NULL;
  ICaptureContext &m_Ctx;
  AnalyzerSnapshot m_Snapshot;
  FrameAnalyzer m_FrameAnalyzer;
  IssueEngine m_IssueEngine;
  AnalyzerExporter m_Exporter;
  AnalyzerIssueModel *m_IssueModel = NULL;
  AnalyzerIssueSortModel *m_IssueSortModel = NULL;
  AnalyzerEventModel *m_EventModel = NULL;
  AnalyzerResourceModel *m_ResourceModel = NULL;
  AnalyzerShaderModel *m_ShaderModel = NULL;
  bool m_BuildInFlight = false;
  uint32_t m_BuildSerial = 0;
};
