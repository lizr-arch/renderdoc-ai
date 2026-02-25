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

#include "AnalyzerModels.h"
#include "Code/QRDUtils.h"

AnalyzerIssueModel::AnalyzerIssueModel(QObject *parent) : QAbstractTableModel(parent)
{
}

void AnalyzerIssueModel::SetIssues(const rdcarray<AnalyzerIssue> &issues)
{
  beginResetModel();
  m_Issues = issues;
  endResetModel();
}

AnalyzerIssue AnalyzerIssueModel::IssueAt(int row) const
{
  if(row < 0 || row >= m_Issues.count())
    return AnalyzerIssue();

  return m_Issues[row];
}

int AnalyzerIssueModel::rowCount(const QModelIndex &parent) const
{
  if(parent.isValid())
    return 0;

  return m_Issues.count();
}

int AnalyzerIssueModel::columnCount(const QModelIndex &parent) const
{
  if(parent.isValid())
    return 0;

  return ColCount;
}

QVariant AnalyzerIssueModel::headerData(int section, Qt::Orientation orientation, int role) const
{
  if(orientation == Qt::Horizontal && role == Qt::DisplayRole)
  {
    switch(section)
    {
      case ColSeverity: return QObject::tr("Severity");
      case ColCode: return QObject::tr("Code");
      case ColMessage: return QObject::tr("Message");
      case ColEID: return QObject::tr("EID");
      case ColImpact: return QObject::tr("Impact");
      default: break;
    }
  }

  return QVariant();
}

QVariant AnalyzerIssueModel::data(const QModelIndex &index, int role) const
{
  if(!index.isValid() || index.row() < 0 || index.row() >= m_Issues.count())
    return QVariant();

  const AnalyzerIssue &issue = m_Issues[index.row()];
  uint32_t firstEID = issue.eventIds.empty() ? 0 : issue.eventIds[0];

  if(role == Qt::DisplayRole)
  {
    switch(index.column())
    {
      case ColSeverity: return ToQStr(issue.severity);
      case ColCode: return ToQStr(issue.code);
      case ColMessage: return ToQStr(issue.message);
      case ColEID: return (int)firstEID;
      case ColImpact: return Formatter::Format(issue.impactScore);
      default: break;
    }
  }

  if(role == EventIdRole)
    return (int)firstEID;

  if(role == ImpactRole)
    return issue.impactScore;

  if(role == SeverityRole)
    return SeverityRank(issue.severity);

  return QVariant();
}

int AnalyzerIssueModel::SeverityRank(const rdcstr &severity) const
{
  if(severity == "critical")
    return 0;
  if(severity == "warning")
    return 1;
  return 2;
}

AnalyzerIssueSortModel::AnalyzerIssueSortModel(QObject *parent) : QSortFilterProxyModel(parent)
{
}

bool AnalyzerIssueSortModel::lessThan(const QModelIndex &sourceLeft,
                                      const QModelIndex &sourceRight) const
{
  if(sourceLeft.column() == AnalyzerIssueModel::ColSeverity)
  {
    int leftRank = sourceLeft.data(AnalyzerIssueModel::SeverityRole).toInt();
    int rightRank = sourceRight.data(AnalyzerIssueModel::SeverityRole).toInt();

    if(leftRank != rightRank)
      return leftRank < rightRank;
  }

  if(sourceLeft.column() == AnalyzerIssueModel::ColImpact)
  {
    double left = sourceLeft.data(AnalyzerIssueModel::ImpactRole).toDouble();
    double right = sourceRight.data(AnalyzerIssueModel::ImpactRole).toDouble();

    if(left != right)
      return left > right;
  }

  return QSortFilterProxyModel::lessThan(sourceLeft, sourceRight);
}

AnalyzerEventModel::AnalyzerEventModel(QObject *parent) : QAbstractTableModel(parent)
{
}

void AnalyzerEventModel::SetEvents(const rdcarray<AnalyzerEventRow> &events)
{
  beginResetModel();
  m_Events = events;
  endResetModel();
}

int AnalyzerEventModel::rowCount(const QModelIndex &parent) const
{
  if(parent.isValid())
    return 0;

  return m_Events.count();
}

int AnalyzerEventModel::columnCount(const QModelIndex &parent) const
{
  if(parent.isValid())
    return 0;

  return 5;
}

QVariant AnalyzerEventModel::headerData(int section, Qt::Orientation orientation, int role) const
{
  if(orientation == Qt::Horizontal && role == Qt::DisplayRole)
  {
    switch(section)
    {
      case 0: return QObject::tr("EID");
      case 1: return QObject::tr("Name");
      case 2: return QObject::tr("Type");
      case 3: return QObject::tr("Action");
      case 4: return QObject::tr("Pass");
      default: break;
    }
  }

  return QVariant();
}

QVariant AnalyzerEventModel::data(const QModelIndex &index, int role) const
{
  if(!index.isValid() || index.row() < 0 || index.row() >= m_Events.count())
    return QVariant();

  const AnalyzerEventRow &event = m_Events[index.row()];

  if(role == Qt::DisplayRole)
  {
    switch(index.column())
    {
      case 0: return (int)event.eid;
      case 1: return ToQStr(event.name);
      case 2: return ToQStr(event.type);
      case 3: return (int)event.drawIndex;
      case 4: return (int)event.passIndex;
      default: break;
    }
  }

  return QVariant();
}
