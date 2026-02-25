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
#include <QFileInfo>
#include <QHeaderView>
#include <QTableWidgetItem>
#include "Code/QRDUtils.h"
#include "ui_AnalyzerReportViewer.h"

AnalyzerReportViewer::AnalyzerReportViewer(ICaptureContext &ctx, QWidget *parent)
    : QFrame(parent), ui(new Ui::AnalyzerReportViewer), m_Ctx(ctx)
{
  ui->setupUi(this);

  setWindowTitle(tr("Analyzer Report"));

  ui->issueTable->setColumnCount(5);
  ui->issueTable->setHorizontalHeaderLabels(
      {tr("Severity"), tr("Code"), tr("Message"), tr("EID"), tr("Impact")});
  ui->issueTable->horizontalHeader()->setStretchLastSection(true);
  ui->issueTable->setSelectionBehavior(QAbstractItemView::SelectRows);
  ui->issueTable->setSelectionMode(QAbstractItemView::SingleSelection);

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
  ui->summaryLabel->setText(tr("No capture loaded"));
  ui->overviewText->setPlainText(tr("Open a capture to build a native analyzer report."));
  ui->issueTable->setRowCount(0);
}

void AnalyzerReportViewer::RefreshReport()
{
  if(!m_Ctx.IsCaptureLoaded())
  {
    OnCaptureClosed();
    return;
  }

  UpdateSummaryText();
  PopulateIssueTable();
}

void AnalyzerReportViewer::UpdateSummaryText()
{
  const FrameDescription &frame = m_Ctx.FrameInfo();

  uint32_t drawCount = frame.stats.draws.calls;
  uint32_t dispatchCount = frame.stats.dispatches.calls;

  QString frameName = QFileInfo(m_Ctx.GetCaptureFilename()).fileName();

  ui->summaryLabel->setText(
      tr("Capture: %1 | Frame: %2 | Draws: %3 | Dispatches: %4 | Textures: %5 | Buffers: %6")
          .arg(frameName)
          .arg(frame.frameNumber)
          .arg(drawCount)
          .arg(dispatchCount)
          .arg(m_Ctx.GetTextures().count())
          .arg(m_Ctx.GetBuffers().count()));

  QString overview = tr("Native analyzer report shell (Qt/C++)\n\n"
                        "This viewer is now integrated as a built-in qrenderdoc window.\n"
                        "Next steps in this branch will progressively replace placeholders "
                        "with full analyzer models and rule engine output.");

  ui->overviewText->setPlainText(overview);
}

void AnalyzerReportViewer::PopulateIssueTable()
{
  ui->issueTable->setRowCount(0);

  const FrameDescription &frame = m_Ctx.FrameInfo();

  int nextRow = 0;

  auto addIssue = [this, &nextRow](const QString &severity, const QString &code,
                                   const QString &message, uint32_t eid, float impact) {
    ui->issueTable->insertRow(nextRow);
    ui->issueTable->setItem(nextRow, 0, new QTableWidgetItem(severity));
    ui->issueTable->setItem(nextRow, 1, new QTableWidgetItem(code));
    ui->issueTable->setItem(nextRow, 2, new QTableWidgetItem(message));
    ui->issueTable->setItem(nextRow, 3, new QTableWidgetItem(QString::number(eid)));
    ui->issueTable->setItem(nextRow, 4, new QTableWidgetItem(Formatter::Format(impact)));
    nextRow++;
  };

  uint32_t drawCount = frame.stats.draws.calls;
  if(drawCount > 5000)
  {
    addIssue(tr("warning"), tr("PERF_DC_001"),
             tr("High draw-call count may cause CPU submission overhead."), m_Ctx.CurEvent(), 0.80f);
  }

  uint32_t dispatchCount = frame.stats.dispatches.calls;
  if(dispatchCount > 1000)
  {
    addIssue(tr("info"), tr("PERF_CS_001"),
             tr("High dispatch count detected; verify workload batching efficiency."),
             m_Ctx.CurEvent(), 0.45f);
  }

  if(m_Ctx.GetTextures().count() > 4096)
  {
    addIssue(tr("warning"), tr("TEX_COUNT_001"),
             tr("Texture count is high; validate residency pressure and descriptor churn."),
             m_Ctx.CurEvent(), 0.65f);
  }

  if(nextRow == 0)
  {
    addIssue(tr("info"), tr("ANALYZER_BASELINE"),
             tr("No high-priority baseline issues detected by shell heuristics."),
             m_Ctx.CurEvent(), 0.10f);
  }

  ui->issueTable->resizeColumnsToContents();
}

void AnalyzerReportViewer::on_refreshButton_clicked()
{
  RefreshReport();
}

void AnalyzerReportViewer::on_jumpButton_clicked()
{
  QModelIndexList rows = ui->issueTable->selectionModel()->selectedRows();
  if(rows.isEmpty())
    return;

  int row = rows[0].row();

  QTableWidgetItem *eidItem = ui->issueTable->item(row, 3);
  if(!eidItem)
    return;

  bool ok = false;
  uint32_t eid = eidItem->text().toUInt(&ok);

  if(!ok || eid == 0)
    return;

  m_Ctx.SetEventID({}, eid, eid, true);
  m_Ctx.ShowEventBrowser();
}
