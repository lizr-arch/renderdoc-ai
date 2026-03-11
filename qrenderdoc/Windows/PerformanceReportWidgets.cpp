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

#include "PerformanceReportWidgets.h"
#include <QPainter>
#include <QtMath>
#include "Code/QRDUtils.h"

static QColor ScoreColor(float score)
{
  if(score >= 80.0f)
    return QColor("#16A34A");
  if(score >= 60.0f)
    return QColor("#F59E0B");
  return QColor("#DC2626");
}

ScoreRingWidget::ScoreRingWidget(QWidget *parent) : QWidget(parent)
{
  setMinimumSize(120, 120);
}

void ScoreRingWidget::SetScore(float score)
{
  m_Score = qBound(0.0f, score, 100.0f);
  update();
}

void ScoreRingWidget::SetLabel(const QString &label)
{
  m_Label = label;
  update();
}

QSize ScoreRingWidget::sizeHint() const
{
  return QSize(140, 140);
}

void ScoreRingWidget::paintEvent(QPaintEvent *)
{
  QPainter p(this);
  p.setRenderHint(QPainter::Antialiasing, true);

  const int side = qMin(width(), height());
  const QRectF rect((width() - side) * 0.5f + 6.0f, (height() - side) * 0.5f + 6.0f,
                    side - 12.0f, side - 12.0f);

  QPen basePen(QColor("#E5E7EB"), 10);
  p.setPen(basePen);
  p.drawArc(rect, 0, 16 * 360);

  QPen scorePen(ScoreColor(m_Score), 10);
  scorePen.setCapStyle(Qt::RoundCap);
  p.setPen(scorePen);
  const int span = (int)(16 * 360.0f * (m_Score / 100.0f));
  p.drawArc(rect, 90 * 16, -span);

  p.setPen(QColor("#111827"));
  QFont scoreFont = font();
  scoreFont.setPointSize(22);
  scoreFont.setBold(true);
  p.setFont(scoreFont);
  p.drawText(rect, Qt::AlignCenter, QString::number((int)m_Score));

  if(!m_Label.isEmpty())
  {
    QFont labelFont = font();
    labelFont.setPointSize(10);
    labelFont.setBold(false);
    p.setFont(labelFont);
    p.setPen(QColor("#6B7280"));
    QRectF labelRect = rect;
    labelRect.setTop(rect.center().y() + 18);
    p.drawText(labelRect, Qt::AlignHCenter | Qt::AlignTop, m_Label);
  }
}

MiniBarWidget::MiniBarWidget(QWidget *parent) : QWidget(parent)
{
  m_Color = QColor("#2563EB");
  setMinimumHeight(8);
}

void MiniBarWidget::SetValue(float value)
{
  m_Value = qBound(0.0f, value, 100.0f);
  update();
}

void MiniBarWidget::SetBarColor(const QColor &color)
{
  m_Color = color;
  update();
}

QSize MiniBarWidget::sizeHint() const
{
  return QSize(120, 8);
}

void MiniBarWidget::paintEvent(QPaintEvent *)
{
  QPainter p(this);
  p.setRenderHint(QPainter::Antialiasing, true);

  QRectF barRect = rect().adjusted(0, 2, 0, -2);
  p.setPen(Qt::NoPen);
  p.setBrush(QColor("#E5E7EB"));
  p.drawRoundedRect(barRect, 3, 3);

  if(m_Value <= 0.0f)
    return;

  QRectF fill = barRect;
  fill.setWidth(barRect.width() * (m_Value / 100.0f));
  p.setBrush(m_Color);
  p.drawRoundedRect(fill, 3, 3);
}

TimingBadgeWidget::TimingBadgeWidget(QWidget *parent) : QWidget(parent)
{
  setMinimumHeight(20);
}

void TimingBadgeWidget::SetConfidence(const QString &confidence)
{
  m_Confidence = confidence;
  update();
}

QSize TimingBadgeWidget::sizeHint() const
{
  return QSize(90, 20);
}

void TimingBadgeWidget::paintEvent(QPaintEvent *)
{
  QPainter p(this);
  p.setRenderHint(QPainter::Antialiasing, true);

  QColor bg("#E5E7EB");
  QColor fg("#374151");
  QString text = m_Confidence.isEmpty() ? lit("Low") : m_Confidence;

  if(text.compare(lit("high"), Qt::CaseInsensitive) == 0)
  {
    bg = QColor("#DCFCE7");
    fg = QColor("#166534");
    text = lit("High");
  }
  else if(text.compare(lit("medium"), Qt::CaseInsensitive) == 0)
  {
    bg = QColor("#FEF3C7");
    fg = QColor("#92400E");
    text = lit("Medium");
  }
  else
  {
    bg = QColor("#FEE2E2");
    fg = QColor("#991B1B");
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
