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
#include "Code/QRDUtils.h"
#include "AnalyzerModels.h"
#include "ui_AnalyzerReportViewer.h"

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
  ui->issueTable->horizontalHeader()->setStretchLastSection(true);

  m_EventModel = new AnalyzerEventModel(this);
  ui->eventTable->setModel(m_EventModel);
  ui->eventTable->setSelectionBehavior(QAbstractItemView::SelectRows);
  ui->eventTable->setSelectionMode(QAbstractItemView::SingleSelection);
  ui->eventTable->horizontalHeader()->setStretchLastSection(true);

  m_ResourceModel = new AnalyzerResourceModel(this);
  ui->resourceTable->setModel(m_ResourceModel);
  ui->resourceTable->setSortingEnabled(true);
  ui->resourceTable->setSelectionBehavior(QAbstractItemView::SelectRows);
  ui->resourceTable->setSelectionMode(QAbstractItemView::SingleSelection);
  ui->resourceTable->horizontalHeader()->setStretchLastSection(true);

  m_ShaderModel = new AnalyzerShaderModel(this);
  ui->shaderTable->setModel(m_ShaderModel);
  ui->shaderTable->setSortingEnabled(true);
  ui->shaderTable->setSelectionBehavior(QAbstractItemView::SelectRows);
  ui->shaderTable->setSelectionMode(QAbstractItemView::SingleSelection);
  ui->shaderTable->horizontalHeader()->setStretchLastSection(true);

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
}

void AnalyzerReportViewer::RefreshReport()
{
  if(!m_Ctx.IsCaptureLoaded())
  {
    OnCaptureClosed();
    return;
  }

  m_Snapshot = m_FrameAnalyzer.Build(m_Ctx);
  m_Snapshot.issues = m_IssueEngine.Evaluate(m_Snapshot);

  UpdateSummaryText();
  PopulateIssueTable();
  PopulateEventTable();
  PopulateResourceTable();
  PopulateShaderTable();
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
  ui->issueTable->resizeColumnsToContents();
  ui->issueTable->sortByColumn(AnalyzerIssueModel::ColSeverity, Qt::AscendingOrder);
}

void AnalyzerReportViewer::PopulateEventTable()
{
  m_EventModel->SetEvents(m_Snapshot.events);
  ui->eventTable->resizeColumnsToContents();
}

void AnalyzerReportViewer::PopulateResourceTable()
{
  m_ResourceModel->SetResources(m_Snapshot.resources);
  ui->resourceTable->resizeColumnsToContents();
  ui->resourceTable->sortByColumn(AnalyzerResourceModel::ColBytes, Qt::DescendingOrder);
}

void AnalyzerReportViewer::PopulateShaderTable()
{
  m_ShaderModel->SetShaders(m_Snapshot.shaders);
  ui->shaderTable->resizeColumnsToContents();
  ui->shaderTable->sortByColumn(AnalyzerShaderModel::ColUseCount, Qt::DescendingOrder);
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

  if(m_Snapshot.events.empty() && m_Snapshot.issues.empty())
    RefreshReport();

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
  uint32_t eid = sourceIndex.data(AnalyzerIssueModel::EventIdRole).toUInt();

  if(eid == 0)
  {
    QMessageBox::warning(this, tr("Jump To GUI"),
                         tr("Selected issue does not have a concrete event id."));
    return;
  }

  m_Ctx.SetEventID({}, eid, eid, true);
  m_Ctx.ShowEventBrowser();
}
