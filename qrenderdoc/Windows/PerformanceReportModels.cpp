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

#include "PerformanceReportModels.h"
#include <algorithm>
#include <QMouseEvent>
#include <QPainter>
#include "Code/QRDUtils.h"

static int SeverityRank(const rdcstr &severity)
{
  if(severity == "critical")
    return 0;
  if(severity == "warning")
    return 1;
  return 2;
}

static QColor SeverityColor(const QString &severity)
{
  QString value = severity.toLower();
  if(value == lit("critical"))
    return QColor("#DC2626");
  if(value == lit("warning"))
    return QColor("#F59E0B");
  return QColor("#2563EB");
}

PerfOpportunityModel::PerfOpportunityModel(QObject *parent) : QAbstractTableModel(parent)
{
}

void PerfOpportunityModel::SetOpportunities(const rdcarray<PerfOpportunity> &opps)
{
  beginResetModel();
  m_Opportunities = opps;
  endResetModel();
}

PerfOpportunity PerfOpportunityModel::OpportunityAt(int row) const
{
  if(row < 0 || row >= m_Opportunities.count())
    return PerfOpportunity();
  return m_Opportunities[row];
}

int PerfOpportunityModel::rowCount(const QModelIndex &parent) const
{
  if(parent.isValid())
    return 0;
  return m_Opportunities.count();
}

int PerfOpportunityModel::columnCount(const QModelIndex &parent) const
{
  if(parent.isValid())
    return 0;
  return ColCount;
}

QVariant PerfOpportunityModel::headerData(int section, Qt::Orientation orientation, int role) const
{
  if(orientation == Qt::Horizontal && role == Qt::DisplayRole)
  {
    switch(section)
    {
      case ColSeverity: return tr("Severity");
      case ColTitle: return tr("Opportunity");
      case ColImpact: return tr("Impact");
      case ColJump: return QString();
      default: break;
    }
  }
  return QVariant();
}

QVariant PerfOpportunityModel::data(const QModelIndex &index, int role) const
{
  if(!index.isValid() || index.row() < 0 || index.row() >= m_Opportunities.count())
    return QVariant();

  const PerfOpportunity &opp = m_Opportunities[index.row()];

  if(role == Qt::DisplayRole)
  {
    if(index.column() == ColSeverity)
      return ToQStr(opp.severity);
    if(index.column() == ColTitle)
    {
      QString title = ToQStr(opp.title);
      QString why = ToQStr(opp.why);
      if(!why.isEmpty())
        return title + lit("\n") + why;
      return title;
    }
    if(index.column() == ColImpact)
    {
      if(opp.impactMs >= 0.0)
        return QString::asprintf("%.2f ms", opp.impactMs);

      if(opp.impactScore >= 0.8)
        return tr("High impact");
      if(opp.impactScore >= 0.5)
        return tr("Medium impact");
      return tr("Low impact");
    }
    if(index.column() == ColJump)
      return tr("Jump");
  }

  if(role == Qt::ToolTipRole)
  {
    QString tip = ToQStr(opp.recommendation);
    if(tip.isEmpty())
      tip = ToQStr(opp.why);
    if(!ToQStr(opp.confidence).isEmpty())
      tip += lit("\nTiming confidence: ") + ToQStr(opp.confidence);
    return tip;
  }

  if(role == ImpactRole)
    return opp.impactMs >= 0.0 ? opp.impactMs : (opp.impactScore * 100.0);

  if(role == SeverityRole)
    return SeverityRank(opp.severity);

  if(role == OpportunityRole)
    return index.row();

  return QVariant();
}

PerfOpportunitySortModel::PerfOpportunitySortModel(QObject *parent) : QSortFilterProxyModel(parent)
{
}

bool PerfOpportunitySortModel::lessThan(const QModelIndex &left, const QModelIndex &right) const
{
  if(left.column() == PerfOpportunityModel::ColSeverity)
  {
    int leftRank = left.data(PerfOpportunityModel::SeverityRole).toInt();
    int rightRank = right.data(PerfOpportunityModel::SeverityRole).toInt();
    if(leftRank != rightRank)
      return leftRank < rightRank;
  }

  if(left.column() == PerfOpportunityModel::ColImpact)
  {
    double leftImpact = left.data(PerfOpportunityModel::ImpactRole).toDouble();
    double rightImpact = right.data(PerfOpportunityModel::ImpactRole).toDouble();
    if(leftImpact != rightImpact)
      return leftImpact > rightImpact;
  }

  return QSortFilterProxyModel::lessThan(left, right);
}

PerfEventModel::PerfEventModel(QObject *parent) : QAbstractTableModel(parent)
{
}

void PerfEventModel::SetEvents(const QVector<PerfEventRow> &events)
{
  beginResetModel();
  m_Events = events;
  endResetModel();
}

int PerfEventModel::rowCount(const QModelIndex &parent) const
{
  if(parent.isValid())
    return 0;
  return m_Events.count();
}

int PerfEventModel::columnCount(const QModelIndex &parent) const
{
  if(parent.isValid())
    return 0;
  return ColCount;
}

QVariant PerfEventModel::headerData(int section, Qt::Orientation orientation, int role) const
{
  if(orientation == Qt::Horizontal && role == Qt::DisplayRole)
  {
    switch(section)
    {
      case ColEID: return tr("EID");
      case ColDuration: return tr("Duration");
      case ColPass: return tr("Pass");
      case ColRTSize: return tr("RT Size");
      case ColNotes: return tr("Notes");
      default: break;
    }
  }
  return QVariant();
}

QVariant PerfEventModel::data(const QModelIndex &index, int role) const
{
  if(!index.isValid() || index.row() < 0 || index.row() >= m_Events.count())
    return QVariant();

  const PerfEventRow &row = m_Events[index.row()];

  if(role == Qt::DisplayRole)
  {
    switch(index.column())
    {
      case ColEID: return (int)row.eid;
      case ColDuration:
        return row.durationMs > 0.0 ? QString::asprintf("%.3f ms", row.durationMs) : tr("-");
      case ColPass: return row.pass;
      case ColRTSize: return row.rtSize;
      case ColNotes: return row.notes;
      default: break;
    }
  }

  if(role == Qt::ForegroundRole && index.column() == ColDuration && row.durationMs > 0.0 &&
     !row.timingValid)
    return QColor("#9CA3AF");

  if(role == Qt::ToolTipRole && index.column() == ColDuration && row.durationMs > 0.0 &&
     !row.timingValid)
    return tr("Timing unavailable or low confidence");

  if(role == DurationRole)
    return row.durationMs;

  return QVariant();
}

void PerfEventModel::sort(int column, Qt::SortOrder order)
{
  if(column != ColDuration)
  {
    QAbstractTableModel::sort(column, order);
    return;
  }

  beginResetModel();
  std::sort(m_Events.begin(), m_Events.end(), [order](const PerfEventRow &a, const PerfEventRow &b) {
    if(order == Qt::AscendingOrder)
      return a.durationMs < b.durationMs;
    return a.durationMs > b.durationMs;
  });
  endResetModel();
}

PerfEventFilterModel::PerfEventFilterModel(QObject *parent) : QSortFilterProxyModel(parent)
{
  setFilterCaseSensitivity(Qt::CaseInsensitive);
}

void PerfEventFilterModel::SetFilterText(const QString &text)
{
  m_FilterText = text;
  invalidateFilter();
}

bool PerfEventFilterModel::filterAcceptsRow(int sourceRow, const QModelIndex &sourceParent) const
{
  if(m_FilterText.isEmpty())
    return true;

  for(int col = 0; col < PerfEventModel::ColCount; ++col)
  {
    QModelIndex idx = sourceModel()->index(sourceRow, col, sourceParent);
    QString value = idx.data(Qt::DisplayRole).toString();
    if(value.contains(m_FilterText, Qt::CaseInsensitive))
      return true;
  }

  return false;
}

bool PerfEventFilterModel::lessThan(const QModelIndex &left, const QModelIndex &right) const
{
  if(left.column() == PerfEventModel::ColDuration)
  {
    double leftDuration = left.data(PerfEventModel::DurationRole).toDouble();
    double rightDuration = right.data(PerfEventModel::DurationRole).toDouble();
    return leftDuration < rightDuration;
  }

  if(left.column() == PerfEventModel::ColEID)
    return left.data(Qt::DisplayRole).toUInt() < right.data(Qt::DisplayRole).toUInt();

  return QSortFilterProxyModel::lessThan(left, right);
}

PerfSeverityBadgeDelegate::PerfSeverityBadgeDelegate(QObject *parent)
    : QStyledItemDelegate(parent)
{
}

void PerfSeverityBadgeDelegate::paint(QPainter *painter, const QStyleOptionViewItem &option,
                                      const QModelIndex &index) const
{
  const QString text = index.data(Qt::DisplayRole).toString();
  QColor color = SeverityColor(text);

  painter->save();
  painter->setRenderHint(QPainter::Antialiasing, true);

  QRectF rect = option.rect.adjusted(6, 6, -6, -6);
  QColor bg = color;
  bg.setAlpha(35);

  painter->setBrush(bg);
  painter->setPen(Qt::NoPen);
  painter->drawRoundedRect(rect, rect.height() / 2.0, rect.height() / 2.0);

  painter->setPen(color.darker(150));
  QFont f = option.font;
  f.setBold(true);
  f.setPointSize(9);
  painter->setFont(f);
  painter->drawText(rect, Qt::AlignCenter, text.toUpper());

  painter->restore();
}

QSize PerfSeverityBadgeDelegate::sizeHint(const QStyleOptionViewItem &option,
                                          const QModelIndex &index) const
{
  Q_UNUSED(index);
  return QSize(option.rect.width(), 32);
}

PerfJumpDelegate::PerfJumpDelegate(QObject *parent) : QStyledItemDelegate(parent)
{
}

void PerfJumpDelegate::paint(QPainter *painter, const QStyleOptionViewItem &option,
                             const QModelIndex &index) const
{
  Q_UNUSED(index);
  painter->save();
  painter->setRenderHint(QPainter::Antialiasing, true);

  QRectF rect = option.rect.adjusted(6, 8, -6, -8);
  QColor bg("#2563EB");
  if(option.state & QStyle::State_MouseOver)
    bg = QColor("#1D4ED8");

  painter->setBrush(bg);
  painter->setPen(Qt::NoPen);
  painter->drawRoundedRect(rect, 6, 6);

  painter->setPen(Qt::white);
  QFont f = option.font;
  f.setBold(true);
  f.setPointSize(9);
  painter->setFont(f);
  painter->drawText(rect, Qt::AlignCenter, tr("Jump"));

  painter->restore();
}

bool PerfJumpDelegate::editorEvent(QEvent *event, QAbstractItemModel *model,
                                   const QStyleOptionViewItem &option,
                                   const QModelIndex &index)
{
  Q_UNUSED(model);
  if(event->type() == QEvent::MouseButtonRelease)
  {
    QMouseEvent *mouse = static_cast<QMouseEvent *>(event);
    QRect clickRect = option.rect.adjusted(6, 8, -6, -8);
    if(clickRect.contains(mouse->pos()))
    {
      emit JumpRequested(index);
      return true;
    }
  }

  return QStyledItemDelegate::editorEvent(event, model, option, index);
}
