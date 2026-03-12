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

#include <QAbstractTableModel>
#include <QSortFilterProxyModel>
#include <QStyledItemDelegate>
#include "Code/Analyzer/PerformanceReportBuilder.h"

class PerfOpportunityModel : public QAbstractTableModel
{
  Q_OBJECT
public:
  enum Columns
  {
    ColSeverity = 0,
    ColTitle,
    ColImpact,
    ColJump,
    ColCount,
  };

  enum Roles
  {
    ImpactRole = Qt::UserRole + 1,
    SeverityRole,
    OpportunityRole,
  };

  explicit PerfOpportunityModel(QObject *parent = nullptr);

  void SetOpportunities(const rdcarray<PerfOpportunity> &opps);
  PerfOpportunity OpportunityAt(int row) const;

  int rowCount(const QModelIndex &parent = QModelIndex()) const override;
  int columnCount(const QModelIndex &parent = QModelIndex()) const override;
  QVariant headerData(int section, Qt::Orientation orientation, int role) const override;
  QVariant data(const QModelIndex &index, int role = Qt::DisplayRole) const override;

private:
  rdcarray<PerfOpportunity> m_Opportunities;
};

class PerfOpportunitySortModel : public QSortFilterProxyModel
{
  Q_OBJECT
public:
  explicit PerfOpportunitySortModel(QObject *parent = nullptr);

protected:
  bool lessThan(const QModelIndex &left, const QModelIndex &right) const override;
};

struct PerfEventRow
{
  uint32_t eid = 0;
  QString name;
  QString pass;
  QString rtSize;
  QString notes;
  double durationMs = 0.0;
  bool timingValid = false;
};

class PerfEventModel : public QAbstractTableModel
{
  Q_OBJECT
public:
  enum Columns
  {
    ColEID = 0,
    ColDuration,
    ColPass,
    ColRTSize,
    ColNotes,
    ColCount,
  };

  enum Roles
  {
    DurationRole = Qt::UserRole + 1,
  };

  explicit PerfEventModel(QObject *parent = nullptr);

  void SetEvents(const QVector<PerfEventRow> &events);

  int rowCount(const QModelIndex &parent = QModelIndex()) const override;
  int columnCount(const QModelIndex &parent = QModelIndex()) const override;
  QVariant headerData(int section, Qt::Orientation orientation, int role) const override;
  QVariant data(const QModelIndex &index, int role = Qt::DisplayRole) const override;
  void sort(int column, Qt::SortOrder order = Qt::AscendingOrder) override;

private:
  QVector<PerfEventRow> m_Events;
};

class PerfEventFilterModel : public QSortFilterProxyModel
{
  Q_OBJECT
public:
  explicit PerfEventFilterModel(QObject *parent = nullptr);

  void SetFilterText(const QString &text);

protected:
  bool filterAcceptsRow(int sourceRow, const QModelIndex &sourceParent) const override;
  bool lessThan(const QModelIndex &left, const QModelIndex &right) const override;

private:
  QString m_FilterText;
};

class PerfSeverityBadgeDelegate : public QStyledItemDelegate
{
  Q_OBJECT
public:
  explicit PerfSeverityBadgeDelegate(QObject *parent = nullptr);

  void paint(QPainter *painter, const QStyleOptionViewItem &option,
             const QModelIndex &index) const override;
  QSize sizeHint(const QStyleOptionViewItem &option, const QModelIndex &index) const override;
};

class PerfJumpDelegate : public QStyledItemDelegate
{
  Q_OBJECT
public:
  explicit PerfJumpDelegate(QObject *parent = nullptr);

  void paint(QPainter *painter, const QStyleOptionViewItem &option,
             const QModelIndex &index) const override;
  bool editorEvent(QEvent *event, QAbstractItemModel *model, const QStyleOptionViewItem &option,
                   const QModelIndex &index) override;

signals:
  void JumpRequested(const QModelIndex &index) const;
};
