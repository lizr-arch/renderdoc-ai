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

AnalyzerResourceModel::AnalyzerResourceModel(QObject *parent) : QAbstractTableModel(parent)
{
}

void AnalyzerResourceModel::SetResources(const rdcarray<AnalyzerResourceRow> &resources)
{
  beginResetModel();
  m_Resources = resources;
  endResetModel();
}

AnalyzerResourceRow AnalyzerResourceModel::ResourceAt(int row) const
{
  if(row < 0 || row >= m_Resources.count())
    return AnalyzerResourceRow();

  return m_Resources[row];
}

int AnalyzerResourceModel::rowCount(const QModelIndex &parent) const
{
  if(parent.isValid())
    return 0;

  return m_Resources.count();
}

int AnalyzerResourceModel::columnCount(const QModelIndex &parent) const
{
  if(parent.isValid())
    return 0;

  return ColCount;
}

QVariant AnalyzerResourceModel::headerData(int section, Qt::Orientation orientation, int role) const
{
  if(orientation == Qt::Horizontal && role == Qt::DisplayRole)
  {
    switch(section)
    {
      case ColKind: return QObject::tr("Kind");
      case ColName: return QObject::tr("Name");
      case ColId: return QObject::tr("Resource");
      case ColBytes: return QObject::tr("Size");
      case ColShape: return QObject::tr("Shape");
      case ColFormat: return QObject::tr("Format");
      default: break;
    }
  }

  return QVariant();
}

QVariant AnalyzerResourceModel::data(const QModelIndex &index, int role) const
{
  if(!index.isValid() || index.row() < 0 || index.row() >= m_Resources.count())
    return QVariant();

  const AnalyzerResourceRow &resource = m_Resources[index.row()];

  if(role == Qt::DisplayRole)
  {
    switch(index.column())
    {
      case ColKind: return ToQStr(resource.kind);
      case ColName: return ToQStr(resource.name);
      case ColId: return ToQStr(resource.id);
      case ColBytes: return Formatter::HumanFormat(resource.bytes, Formatter::OffsetSize);
      case ColShape:
      {
        if(resource.kind == "texture")
        {
          QString shape =
              QFormatStr("%1x%2x%3").arg(resource.width).arg(resource.height).arg(resource.depth);
          if(resource.arraySize > 1)
            shape += QFormatStr(" a%1").arg(resource.arraySize);
          if(resource.mips > 1)
            shape += QFormatStr(" m%1").arg(resource.mips);
          if(resource.samples > 1)
            shape += QFormatStr(" %1xMSAA").arg(resource.samples);
          return shape;
        }

        return QFormatStr("%1 bytes").arg(Formatter::Format(resource.bytes));
      }
      case ColFormat: return ToQStr(resource.format);
      default: break;
    }
  }

  if(role == ResourceIdRole)
    return ToQStr(resource.id);

  if(role == ResourceKindRole)
    return ToQStr(resource.kind);

  if(role == BytesRole)
    return qulonglong(resource.bytes);

  return QVariant();
}

AnalyzerShaderModel::AnalyzerShaderModel(QObject *parent) : QAbstractTableModel(parent)
{
}

void AnalyzerShaderModel::SetShaders(const rdcarray<AnalyzerShaderRow> &shaders)
{
  beginResetModel();
  m_Shaders = shaders;
  endResetModel();
}

AnalyzerShaderRow AnalyzerShaderModel::ShaderAt(int row) const
{
  if(row < 0 || row >= m_Shaders.count())
    return AnalyzerShaderRow();

  return m_Shaders[row];
}

int AnalyzerShaderModel::rowCount(const QModelIndex &parent) const
{
  if(parent.isValid())
    return 0;

  return m_Shaders.count();
}

int AnalyzerShaderModel::columnCount(const QModelIndex &parent) const
{
  if(parent.isValid())
    return 0;

  return ColCount;
}

QVariant AnalyzerShaderModel::headerData(int section, Qt::Orientation orientation, int role) const
{
  if(orientation == Qt::Horizontal && role == Qt::DisplayRole)
  {
    switch(section)
    {
      case ColStage: return QObject::tr("Stage");
      case ColName: return QObject::tr("Name");
      case ColId: return QObject::tr("Shader");
      case ColUseCount: return QObject::tr("Use Count");
      case ColFirstEID: return QObject::tr("First EID");
      case ColLastEID: return QObject::tr("Last EID");
      default: break;
    }
  }

  return QVariant();
}

QVariant AnalyzerShaderModel::data(const QModelIndex &index, int role) const
{
  if(!index.isValid() || index.row() < 0 || index.row() >= m_Shaders.count())
    return QVariant();

  const AnalyzerShaderRow &shader = m_Shaders[index.row()];

  if(role == Qt::DisplayRole)
  {
    switch(index.column())
    {
      case ColStage: return ToQStr(shader.stage);
      case ColName: return ToQStr(shader.name);
      case ColId: return ToQStr(shader.id);
      case ColUseCount: return (int)shader.useCount;
      case ColFirstEID: return (int)shader.firstEID;
      case ColLastEID: return (int)shader.lastEID;
      default: break;
    }
  }

  if(role == ShaderIdRole)
    return ToQStr(shader.id);

  if(role == FirstEventRole)
    return (int)shader.firstEID;

  if(role == UseCountRole)
    return (int)shader.useCount;

  return QVariant();
}
