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

#include "AnalyzerReportWidgets.h"
#include <QPainter>
#include <QStyle>
#include "AnalyzerModels.h"
#include "Code/QRDUtils.h"

namespace
{
QColor ScoreColor(double score)
{
  if(score >= 85.0)
    return QColor(lit("#16A34A"));
  if(score >= 60.0)
    return QColor(lit("#D97706"));
  return QColor(lit("#DC2626"));
}

QColor SeverityFill(int rank)
{
  if(rank == 0)
    return QColor(lit("#FEE2E2"));
  if(rank == 1)
    return QColor(lit("#FEF3C7"));
  return QColor(lit("#DBEAFE"));
}

QColor SeverityText(int rank)
{
  if(rank == 0)
    return QColor(lit("#991B1B"));
  if(rank == 1)
    return QColor(lit("#92400E"));
  return QColor(lit("#1D4ED8"));
}
}

AnalyzerScoreRingWidget::AnalyzerScoreRingWidget(QWidget *parent) : QWidget(parent)
{
  setMinimumSize(140, 140);
}

void AnalyzerScoreRingWidget::SetScore(double value)
{
  m_Score = value;
  update();
}

void AnalyzerScoreRingWidget::SetLabel(const QString &label)
{
  m_Label = label;
  update();
}

QSize AnalyzerScoreRingWidget::sizeHint() const
{
  return QSize(160, 160);
}

void AnalyzerScoreRingWidget::paintEvent(QPaintEvent *)
{
  QPainter p(this);
  p.setRenderHint(QPainter::Antialiasing, true);

  QRectF bounds = QRectF(8.0, 8.0, width() - 16.0, height() - 16.0);
  double score = qMax(0.0, qMin(100.0, m_Score));

  QPen bgPen(QColor(lit("#E5E7EB")));
  bgPen.setWidth(12);
  p.setPen(bgPen);
  p.drawArc(bounds, 0, 360 * 16);

  QPen fgPen(ScoreColor(score));
  fgPen.setWidth(12);
  p.setPen(fgPen);
  p.drawArc(bounds, 90 * 16, (int)(-360.0 * score / 100.0 * 16.0));

  QFont scoreFont = font();
  scoreFont.setPointSize(24);
  scoreFont.setBold(true);
  p.setFont(scoreFont);
  p.setPen(QColor(lit("#111827")));
  p.drawText(bounds, Qt::AlignCenter, QString::number((int)score));

  if(!m_Label.isEmpty())
  {
    QFont labelFont = font();
    labelFont.setPointSize(10);
    p.setFont(labelFont);
    p.setPen(QColor(lit("#6B7280")));
    QRectF labelRect = bounds.adjusted(0.0, bounds.height() * 0.55, 0.0, 0.0);
    p.drawText(labelRect, Qt::AlignHCenter | Qt::AlignTop, m_Label);
  }
}

AnalyzerSeverityBadgeDelegate::AnalyzerSeverityBadgeDelegate(QObject *parent)
    : QStyledItemDelegate(parent)
{
}

void AnalyzerSeverityBadgeDelegate::paint(QPainter *painter,
                                          const QStyleOptionViewItem &option,
                                          const QModelIndex &index) const
{
  painter->save();
  painter->setRenderHint(QPainter::Antialiasing, true);

  QString label = index.data(Qt::DisplayRole).toString();
  int rank = index.data(AnalyzerIssueModel::SeverityRole).toInt();
  QRectF rect = option.rect.adjusted(6, 6, -6, -6);
  rect.setHeight(qMin(rect.height(), 20.0));

  painter->setPen(Qt::NoPen);
  painter->setBrush(SeverityFill(rank));
  painter->drawRoundedRect(rect, 10, 10);

  painter->setPen(SeverityText(rank));
  QFont font = option.font;
  font.setBold(true);
  font.setPointSize(9);
  painter->setFont(font);
  painter->drawText(rect, Qt::AlignCenter, label);

  painter->restore();
}

QSize AnalyzerSeverityBadgeDelegate::sizeHint(const QStyleOptionViewItem &option,
                                              const QModelIndex &index) const
{
  QSize base = QStyledItemDelegate::sizeHint(option, index);
  return QSize(base.width(), qMax(base.height(), 26));
}

AnalyzerImpactBarDelegate::AnalyzerImpactBarDelegate(QObject *parent)
    : QStyledItemDelegate(parent)
{
}

void AnalyzerImpactBarDelegate::paint(QPainter *painter, const QStyleOptionViewItem &option,
                                      const QModelIndex &index) const
{
  painter->save();
  painter->setRenderHint(QPainter::Antialiasing, true);

  double impact = index.data(Qt::UserRole + 2).toDouble();
  QRectF rect = option.rect.adjusted(6, 8, -6, -8);
  double norm = qMax(0.0, qMin(1.0, impact));

  painter->setPen(Qt::NoPen);
  painter->setBrush(QColor(lit("#E5E7EB")));
  painter->drawRoundedRect(rect, 4, 4);

  QRectF fillRect = rect;
  fillRect.setWidth(rect.width() * norm);
  painter->setBrush(QColor(lit("#2563EB")));
  painter->drawRoundedRect(fillRect, 4, 4);

  painter->setPen(QColor(lit("#111827")));
  painter->drawText(option.rect.adjusted(8, 0, -8, 0), Qt::AlignVCenter | Qt::AlignRight,
                    index.data(Qt::DisplayRole).toString());

  painter->restore();
}

AnalyzerTimingBadgeWidget::AnalyzerTimingBadgeWidget(QWidget *parent) : QWidget(parent)
{
  setMinimumHeight(20);
}

void AnalyzerTimingBadgeWidget::SetConfidence(const QString &confidence)
{
  m_Confidence = confidence;
  update();
}

QSize AnalyzerTimingBadgeWidget::sizeHint() const
{
  return QSize(90, 20);
}

void AnalyzerTimingBadgeWidget::paintEvent(QPaintEvent *)
{
  QPainter p(this);
  p.setRenderHint(QPainter::Antialiasing, true);

  QColor bg(lit("#E5E7EB"));
  QColor fg(lit("#374151"));
  QString text = m_Confidence.isEmpty() ? lit("Low") : m_Confidence;

  if(text.compare(lit("high"), Qt::CaseInsensitive) == 0)
  {
    bg = QColor(lit("#DCFCE7"));
    fg = QColor(lit("#166534"));
    text = lit("High");
  }
  else if(text.compare(lit("medium"), Qt::CaseInsensitive) == 0)
  {
    bg = QColor(lit("#FEF3C7"));
    fg = QColor(lit("#92400E"));
    text = lit("Medium");
  }
  else
  {
    bg = QColor(lit("#FEE2E2"));
    fg = QColor(lit("#991B1B"));
    text = lit("Low");
  }

  QRectF r = rect().adjusted(0.5, 0.5, -0.5, -0.5);
  p.setPen(Qt::NoPen);
  p.setBrush(bg);
  p.drawRoundedRect(r, 9, 9);

  p.setPen(fg);
  QFont f = font();
  f.setPointSize(9);
  f.setBold(true);
  p.setFont(f);
  p.drawText(r, Qt::AlignCenter, text);
}
