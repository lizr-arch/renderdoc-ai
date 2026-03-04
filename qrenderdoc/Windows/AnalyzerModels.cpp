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
#include <algorithm>
#include <cmath>
#include "Code/QRDUtils.h"

namespace
{
QString LocalizeSeverityLabel(const rdcstr &severity)
{
  if(severity == "critical")
    return QString::fromUtf16(u"\u4e25\u91cd");
  if(severity == "warning")
    return QString::fromUtf16(u"\u8b66\u544a");
  return QString::fromUtf16(u"\u63d0\u793a");
}
}

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
      case ColSeverity: return QString::fromUtf16(u"\u4e25\u91cd\u6027");
      case ColCode: return QString::fromUtf16(u"\u89c4\u5219\u7f16\u53f7");
      case ColMessage: return QString::fromUtf16(u"\u95ee\u9898");
      case ColEID: return QString::fromUtf16(u"\u4e8b\u4ef6ID");
      case ColImpact: return QString::fromUtf16(u"\u5f71\u54cd\u8bc4\u5206");
      default: break;
    }
  }

  if(orientation == Qt::Horizontal && role == Qt::ToolTipRole)
  {
    switch(section)
    {
      case ColImpact:
        return QString::fromUtf16(
            u"\u5f71\u54cd\u8bc4\u5206\u4e3a 0-1 \u7684\u4f30\u8ba1\u503c\uff0c"
            u"\u8d8a\u5927\u4ee3\u8868\u5f71\u54cd\u8d8a\u9ad8\u3002");
      case ColCode:
        return QString::fromUtf16(
            u"\u89c4\u5219\u7f16\u53f7\u7528\u4e8e\u5b9a\u4f4d\u89c4\u5219\u4e0e"
            u"\u5bfc\u51fa\u5bf9\u9f50\u3002");
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
      case ColSeverity: return LocalizeSeverityLabel(issue.severity);
      case ColCode: return ToQStr(issue.code);
      case ColMessage: return ToQStr(issue.message);
      case ColEID: return (int)firstEID;
      case ColImpact:
      {
        int percent = (int)std::round(issue.impactScore * 100.0);
        return QString::asprintf("%d%%", percent);
      }
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

void AnalyzerIssueSortModel::SetFilterText(const QString &text)
{
  m_FilterText = text.trimmed().toLower();
  invalidateFilter();
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

bool AnalyzerIssueSortModel::filterAcceptsRow(int sourceRow, const QModelIndex &sourceParent) const
{
  if(m_FilterText.isEmpty())
    return true;

  if(!sourceModel())
    return true;
  const AnalyzerIssueModel *model = static_cast<const AnalyzerIssueModel *>(sourceModel());

  AnalyzerIssue issue = model->IssueAt(sourceRow);

  auto containsText = [this](const rdcstr &value) {
    return ToQStr(value).toLower().contains(m_FilterText);
  };

  if(containsText(issue.code) || containsText(issue.message) || containsText(issue.category) ||
     containsText(issue.recommendation))
    return true;

  return false;
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

void AnalyzerEventModel::sort(int column, Qt::SortOrder order)
{
  if(m_Events.count() <= 1)
    return;

  bool ascending = order == Qt::AscendingOrder;

  auto compareText = [ascending](const rdcstr &a, const rdcstr &b) {
    return ascending ? a < b : a > b;
  };
  auto compareUInt = [ascending](uint32_t a, uint32_t b) { return ascending ? a < b : a > b; };

  beginResetModel();
  std::stable_sort(
      m_Events.begin(), m_Events.end(),
      [column, &compareText, &compareUInt](const AnalyzerEventRow &a, const AnalyzerEventRow &b) {
        switch(column)
        {
          case 0:
            if(a.eid != b.eid)
              return compareUInt(a.eid, b.eid);
            break;
          case 1:
            if(a.name != b.name)
              return compareText(a.name, b.name);
            break;
          case 2:
            if(a.type != b.type)
              return compareText(a.type, b.type);
            break;
          case 3:
            if(a.drawIndex != b.drawIndex)
              return compareUInt(a.drawIndex, b.drawIndex);
            break;
          case 4:
            if(a.passIndex != b.passIndex)
              return compareUInt(a.passIndex, b.passIndex);
            break;
          default: break;
        }

        return a.eid < b.eid;
      });
  endResetModel();
}

AnalyzerDrawDispatchModel::AnalyzerDrawDispatchModel(QObject *parent) : QAbstractTableModel(parent)
{
}

void AnalyzerDrawDispatchModel::SetRows(const rdcarray<AnalyzerDrawDispatchRow> &rows)
{
  beginResetModel();
  m_Rows = rows;
  endResetModel();
}

AnalyzerDrawDispatchRow AnalyzerDrawDispatchModel::RowAt(int row) const
{
  if(row < 0 || row >= m_Rows.count())
    return AnalyzerDrawDispatchRow();

  return m_Rows[row];
}

int AnalyzerDrawDispatchModel::rowCount(const QModelIndex &parent) const
{
  if(parent.isValid())
    return 0;

  return m_Rows.count();
}

int AnalyzerDrawDispatchModel::columnCount(const QModelIndex &parent) const
{
  if(parent.isValid())
    return 0;

  return ColCount;
}

QVariant AnalyzerDrawDispatchModel::headerData(int section, Qt::Orientation orientation,
                                               int role) const
{
  if(orientation == Qt::Horizontal && role == Qt::DisplayRole)
  {
    switch(section)
    {
      case ColEID: return QObject::tr("EID");
      case ColName: return QObject::tr("Name");
      case ColType: return QObject::tr("Type");
      case ColIndices: return QObject::tr("Indices");
      case ColInstances: return QObject::tr("Instances");
      case ColDispatchDim: return QObject::tr("Dispatch");
      case ColDispatchThreads: return QObject::tr("Threads");
      case ColIndirect: return QObject::tr("Indirect");
      default: break;
    }
  }

  return QVariant();
}

QVariant AnalyzerDrawDispatchModel::data(const QModelIndex &index, int role) const
{
  if(!index.isValid() || index.row() < 0 || index.row() >= m_Rows.count())
    return QVariant();

  const AnalyzerDrawDispatchRow &row = m_Rows[index.row()];

  if(role == Qt::DisplayRole)
  {
    switch(index.column())
    {
      case ColEID: return (int)row.eid;
      case ColName: return ToQStr(row.name);
      case ColType: return ToQStr(row.type);
      case ColIndices: return (int)row.numIndices;
      case ColInstances: return (int)row.numInstances;
      case ColDispatchDim:
      {
        if(row.type != "dispatch")
          return QObject::tr("-");
        return QFormatStr("%1x%2x%3")
            .arg(row.dispatchDim[0])
            .arg(row.dispatchDim[1])
            .arg(row.dispatchDim[2]);
      }
      case ColDispatchThreads:
      {
        if(row.type != "dispatch")
          return QObject::tr("-");
        return QFormatStr("%1x%2x%3")
            .arg(row.dispatchThreads[0])
            .arg(row.dispatchThreads[1])
            .arg(row.dispatchThreads[2]);
      }
      case ColIndirect: return row.indirect ? QObject::tr("Indirect") : QObject::tr("Direct");
      default: break;
    }
  }

  if(role == EventIdRole)
    return (int)row.eid;

  return QVariant();
}

void AnalyzerDrawDispatchModel::sort(int column, Qt::SortOrder order)
{
  if(m_Rows.count() <= 1)
    return;

  bool ascending = order == Qt::AscendingOrder;

  auto compareText = [ascending](const rdcstr &a, const rdcstr &b) {
    return ascending ? a < b : a > b;
  };
  auto compareUInt = [ascending](uint32_t a, uint32_t b) { return ascending ? a < b : a > b; };

  beginResetModel();
  std::stable_sort(
      m_Rows.begin(), m_Rows.end(),
      [column, &compareText, &compareUInt, ascending](const AnalyzerDrawDispatchRow &a,
                                                      const AnalyzerDrawDispatchRow &b) {
        switch(column)
        {
          case ColEID:
            if(a.eid != b.eid)
              return compareUInt(a.eid, b.eid);
            break;
          case ColName:
            if(a.name != b.name)
              return compareText(a.name, b.name);
            break;
          case ColType:
            if(a.type != b.type)
              return compareText(a.type, b.type);
            break;
          case ColIndices:
            if(a.numIndices != b.numIndices)
              return compareUInt(a.numIndices, b.numIndices);
            break;
          case ColInstances:
            if(a.numInstances != b.numInstances)
              return compareUInt(a.numInstances, b.numInstances);
            break;
          case ColDispatchDim:
            if(a.dispatchDim[0] != b.dispatchDim[0])
              return compareUInt(a.dispatchDim[0], b.dispatchDim[0]);
            if(a.dispatchDim[1] != b.dispatchDim[1])
              return compareUInt(a.dispatchDim[1], b.dispatchDim[1]);
            if(a.dispatchDim[2] != b.dispatchDim[2])
              return compareUInt(a.dispatchDim[2], b.dispatchDim[2]);
            break;
          case ColDispatchThreads:
            if(a.dispatchThreads[0] != b.dispatchThreads[0])
              return compareUInt(a.dispatchThreads[0], b.dispatchThreads[0]);
            if(a.dispatchThreads[1] != b.dispatchThreads[1])
              return compareUInt(a.dispatchThreads[1], b.dispatchThreads[1]);
            if(a.dispatchThreads[2] != b.dispatchThreads[2])
              return compareUInt(a.dispatchThreads[2], b.dispatchThreads[2]);
            break;
          case ColIndirect:
            if(a.indirect != b.indirect)
              return ascending ? a.indirect < b.indirect : b.indirect < a.indirect;
            break;
          default: break;
        }

        return a.eid < b.eid;
      });
  endResetModel();
}

AnalyzerStateThrashModel::AnalyzerStateThrashModel(QObject *parent) : QAbstractTableModel(parent)
{
}

void AnalyzerStateThrashModel::SetRows(const rdcarray<AnalyzerStateThrashRow> &rows)
{
  beginResetModel();
  m_Rows = rows;
  endResetModel();
}

AnalyzerStateThrashRow AnalyzerStateThrashModel::RowAt(int row) const
{
  if(row < 0 || row >= m_Rows.count())
    return AnalyzerStateThrashRow();

  return m_Rows[row];
}

int AnalyzerStateThrashModel::rowCount(const QModelIndex &parent) const
{
  if(parent.isValid())
    return 0;

  return m_Rows.count();
}

int AnalyzerStateThrashModel::columnCount(const QModelIndex &parent) const
{
  if(parent.isValid())
    return 0;

  return ColCount;
}

QVariant AnalyzerStateThrashModel::headerData(int section, Qt::Orientation orientation,
                                              int role) const
{
  if(orientation == Qt::Horizontal && role == Qt::DisplayRole)
  {
    switch(section)
    {
      case ColStage: return QObject::tr("Stage");
      case ColShaderChanges: return QObject::tr("Shader Binds");
      case ColRedundantShaders: return QObject::tr("Shader Redundant");
      case ColResourceBinds: return QObject::tr("Resource Binds");
      case ColSamplerBinds: return QObject::tr("Sampler Binds");
      case ColConstantBinds: return QObject::tr("Constant Binds");
      default: break;
    }
  }

  return QVariant();
}

QVariant AnalyzerStateThrashModel::data(const QModelIndex &index, int role) const
{
  if(!index.isValid() || index.row() < 0 || index.row() >= m_Rows.count())
    return QVariant();

  const AnalyzerStateThrashRow &row = m_Rows[index.row()];

  if(role == Qt::DisplayRole)
  {
    switch(index.column())
    {
      case ColStage: return ToQStr(row.stage);
      case ColShaderChanges:
        return row.available ? QVariant((int)row.shaderChanges) : QObject::tr("N/A");
      case ColRedundantShaders:
        return row.available ? QVariant((int)row.redundantShaderBinds) : QObject::tr("N/A");
      case ColResourceBinds:
        return row.available ? QVariant((int)row.resourceBinds) : QObject::tr("N/A");
      case ColSamplerBinds:
        return row.available ? QVariant((int)row.samplerBinds) : QObject::tr("N/A");
      case ColConstantBinds:
        return row.available ? QVariant((int)row.constantBinds) : QObject::tr("N/A");
      default: break;
    }
  }

  if(role == EventIdRole)
    return (int)row.fallbackEID;

  return QVariant();
}

void AnalyzerStateThrashModel::sort(int column, Qt::SortOrder order)
{
  if(m_Rows.count() <= 1)
    return;

  bool ascending = order == Qt::AscendingOrder;

  auto compareText = [ascending](const rdcstr &a, const rdcstr &b) {
    return ascending ? a < b : a > b;
  };
  auto compareUInt = [ascending](uint32_t a, uint32_t b) { return ascending ? a < b : a > b; };

  beginResetModel();
  std::stable_sort(
      m_Rows.begin(), m_Rows.end(),
      [column, &compareText, &compareUInt, ascending](const AnalyzerStateThrashRow &a,
                                                      const AnalyzerStateThrashRow &b) {
        if(a.available != b.available)
          return a.available && !b.available;

        switch(column)
        {
          case ColStage:
            if(a.stage != b.stage)
              return compareText(a.stage, b.stage);
            break;
          case ColShaderChanges:
            if(a.shaderChanges != b.shaderChanges)
              return compareUInt(a.shaderChanges, b.shaderChanges);
            break;
          case ColRedundantShaders:
            if(a.redundantShaderBinds != b.redundantShaderBinds)
              return compareUInt(a.redundantShaderBinds, b.redundantShaderBinds);
            break;
          case ColResourceBinds:
            if(a.resourceBinds != b.resourceBinds)
              return compareUInt(a.resourceBinds, b.resourceBinds);
            break;
          case ColSamplerBinds:
            if(a.samplerBinds != b.samplerBinds)
              return compareUInt(a.samplerBinds, b.samplerBinds);
            break;
          case ColConstantBinds:
            if(a.constantBinds != b.constantBinds)
              return compareUInt(a.constantBinds, b.constantBinds);
            break;
          default: break;
        }

        return a.stage < b.stage;
      });
  endResetModel();
}

AnalyzerPipelineBandwidthModel::AnalyzerPipelineBandwidthModel(QObject *parent)
    : QAbstractTableModel(parent)
{
}

void AnalyzerPipelineBandwidthModel::SetRows(const rdcarray<AnalyzerPipelineBandwidthRow> &rows)
{
  beginResetModel();
  m_Rows = rows;
  endResetModel();
}

AnalyzerPipelineBandwidthRow AnalyzerPipelineBandwidthModel::RowAt(int row) const
{
  if(row < 0 || row >= m_Rows.count())
    return AnalyzerPipelineBandwidthRow();

  return m_Rows[row];
}

int AnalyzerPipelineBandwidthModel::rowCount(const QModelIndex &parent) const
{
  if(parent.isValid())
    return 0;

  return m_Rows.count();
}

int AnalyzerPipelineBandwidthModel::columnCount(const QModelIndex &parent) const
{
  if(parent.isValid())
    return 0;

  return ColCount;
}

QVariant AnalyzerPipelineBandwidthModel::headerData(int section, Qt::Orientation orientation,
                                                    int role) const
{
  if(orientation == Qt::Horizontal && role == Qt::DisplayRole)
  {
    switch(section)
    {
      case ColEID: return QObject::tr("EID");
      case ColName: return QObject::tr("Name");
      case ColRTCount: return QObject::tr("RTs");
      case ColSamples: return QObject::tr("MSAA Samples (RT/DS)");
      case ColBlendEnabled: return QObject::tr("Blend");
      case ColDepthWrite: return QObject::tr("Depth Write");
      default: break;
    }
  }

  if(orientation == Qt::Horizontal && role == Qt::ToolTipRole)
  {
    if(section == ColSamples)
    {
      return QObject::tr("Max MSAA samples among RT/DS. From texture msSamp or pipeline MSAA.");
    }
  }

  return QVariant();
}

QVariant AnalyzerPipelineBandwidthModel::data(const QModelIndex &index, int role) const
{
  if(!index.isValid() || index.row() < 0 || index.row() >= m_Rows.count())
    return QVariant();

  const AnalyzerPipelineBandwidthRow &row = m_Rows[index.row()];

  if(role == Qt::DisplayRole)
  {
    switch(index.column())
    {
      case ColEID: return (int)row.eid;
      case ColName: return ToQStr(row.name);
      case ColRTCount: return (int)row.rtCount;
      case ColSamples: return (int)row.samples;
      case ColBlendEnabled: return row.blendEnabled ? QObject::tr("Enabled") : QObject::tr("Off");
      case ColDepthWrite: return row.depthWrite ? QObject::tr("On") : QObject::tr("Off");
      default: break;
    }
  }

  if(role == EventIdRole)
    return (int)row.eid;

  return QVariant();
}

void AnalyzerPipelineBandwidthModel::sort(int column, Qt::SortOrder order)
{
  if(m_Rows.count() <= 1)
    return;

  bool ascending = order == Qt::AscendingOrder;

  auto compareText = [ascending](const rdcstr &a, const rdcstr &b) {
    return ascending ? a < b : a > b;
  };
  auto compareUInt = [ascending](uint32_t a, uint32_t b) { return ascending ? a < b : a > b; };

  beginResetModel();
  std::stable_sort(m_Rows.begin(), m_Rows.end(),
                   [column, &compareText, &compareUInt, ascending](
                       const AnalyzerPipelineBandwidthRow &a,
                       const AnalyzerPipelineBandwidthRow &b) {
                     switch(column)
                     {
                       case ColEID:
                         if(a.eid != b.eid)
                           return compareUInt(a.eid, b.eid);
                         break;
                       case ColName:
                         if(a.name != b.name)
                           return compareText(a.name, b.name);
                         break;
                       case ColRTCount:
                         if(a.rtCount != b.rtCount)
                           return compareUInt(a.rtCount, b.rtCount);
                         break;
                       case ColSamples:
                         if(a.samples != b.samples)
                           return compareUInt(a.samples, b.samples);
                         break;
                       case ColBlendEnabled:
                         if(a.blendEnabled != b.blendEnabled)
                           return ascending ? a.blendEnabled < b.blendEnabled
                                            : b.blendEnabled < a.blendEnabled;
                         break;
                       case ColDepthWrite:
                         if(a.depthWrite != b.depthWrite)
                           return ascending ? a.depthWrite < b.depthWrite
                                            : b.depthWrite < a.depthWrite;
                         break;
                       default: break;
                     }

                     return a.eid < b.eid;
                   });
  endResetModel();
}

AnalyzerGpuCounterModel::AnalyzerGpuCounterModel(QObject *parent) : QAbstractTableModel(parent)
{
}

void AnalyzerGpuCounterModel::SetRows(const rdcarray<AnalyzerGpuCounterRow> &rows)
{
  beginResetModel();
  m_Rows = rows;
  endResetModel();
}

AnalyzerGpuCounterRow AnalyzerGpuCounterModel::RowAt(int row) const
{
  if(row < 0 || row >= m_Rows.count())
    return AnalyzerGpuCounterRow();

  return m_Rows[row];
}

int AnalyzerGpuCounterModel::rowCount(const QModelIndex &parent) const
{
  if(parent.isValid())
    return 0;

  return m_Rows.count();
}

int AnalyzerGpuCounterModel::columnCount(const QModelIndex &parent) const
{
  if(parent.isValid())
    return 0;

  return ColCount;
}

QVariant AnalyzerGpuCounterModel::headerData(int section, Qt::Orientation orientation, int role) const
{
  if(orientation == Qt::Horizontal && role == Qt::DisplayRole)
  {
    switch(section)
    {
      case ColEID: return QObject::tr("EID");
      case ColName: return QObject::tr("Name");
      case ColGpuTime: return QObject::tr("GPU Time (ms)");
      case ColVSInvocations: return QObject::tr("VS Invocations");
      case ColPSInvocations: return QObject::tr("PS Invocations");
      case ColCSInvocations: return QObject::tr("CS Invocations");
      case ColTextureSamples: return QObject::tr("Texture Samples");
      default: break;
    }
  }

  if(orientation == Qt::Horizontal && role == Qt::ToolTipRole)
  {
    switch(section)
    {
      case ColGpuTime:
        return QObject::tr("Event GPU duration in milliseconds, if available.");
      case ColTextureSamples:
        return QObject::tr("Texture-related counter if available; otherwise N/A.");
      default: break;
    }
  }

  return QVariant();
}

QVariant AnalyzerGpuCounterModel::data(const QModelIndex &index, int role) const
{
  if(!index.isValid() || index.row() < 0 || index.row() >= m_Rows.count())
    return QVariant();

  const AnalyzerGpuCounterRow &row = m_Rows[index.row()];

  if(role == Qt::DisplayRole)
  {
    switch(index.column())
    {
      case ColEID: return (int)row.eid;
      case ColName: return ToQStr(row.name);
      case ColGpuTime:
        return row.gpuTimeValid ? QString::number(row.gpuTimeMs, 'f', 3) : QObject::tr("N/A");
      case ColVSInvocations:
        return row.vsValid ? QString::number((qulonglong)row.vsInvocations)
                           : QObject::tr("N/A");
      case ColPSInvocations:
        return row.psValid ? QString::number((qulonglong)row.psInvocations)
                           : QObject::tr("N/A");
      case ColCSInvocations:
        return row.csValid ? QString::number((qulonglong)row.csInvocations)
                           : QObject::tr("N/A");
      case ColTextureSamples:
        return row.textureValid ? QString::number(row.textureSamples, 'f', 2)
                                : QObject::tr("N/A");
      default: break;
    }
  }

  if(role == Qt::ToolTipRole && index.column() == ColTextureSamples && row.textureValid)
  {
    if(!row.textureCounterName.empty())
      return QObject::tr("Counter: %1").arg(ToQStr(row.textureCounterName));
  }

  if(role == EventIdRole)
    return (int)row.eid;

  return QVariant();
}

void AnalyzerGpuCounterModel::sort(int column, Qt::SortOrder order)
{
  if(m_Rows.count() <= 1)
    return;

  bool ascending = order == Qt::AscendingOrder;

  auto compareText = [ascending](const rdcstr &a, const rdcstr &b) {
    return ascending ? a < b : a > b;
  };
  auto compareUInt64 = [ascending](uint64_t a, uint64_t b) { return ascending ? a < b : a > b; };
  auto compareDouble = [ascending](double a, double b) { return ascending ? a < b : a > b; };

  auto validFirst = [](bool aValid, bool bValid) {
    if(aValid != bValid)
      return aValid && !bValid;
    return false;
  };

  beginResetModel();
  std::stable_sort(
      m_Rows.begin(), m_Rows.end(),
      [column, &compareText, &compareUInt64, &compareDouble, ascending,
       &validFirst](const AnalyzerGpuCounterRow &a, const AnalyzerGpuCounterRow &b) {
        switch(column)
        {
          case ColEID:
            if(a.eid != b.eid)
              return compareUInt64(a.eid, b.eid);
            break;
          case ColName:
            if(a.name != b.name)
              return compareText(a.name, b.name);
            break;
          case ColGpuTime:
            if(validFirst(a.gpuTimeValid, b.gpuTimeValid))
              return true;
            if(validFirst(b.gpuTimeValid, a.gpuTimeValid))
              return false;
            if(a.gpuTimeValid && b.gpuTimeValid && a.gpuTimeMs != b.gpuTimeMs)
              return compareDouble(a.gpuTimeMs, b.gpuTimeMs);
            break;
          case ColVSInvocations:
            if(validFirst(a.vsValid, b.vsValid))
              return true;
            if(validFirst(b.vsValid, a.vsValid))
              return false;
            if(a.vsValid && b.vsValid && a.vsInvocations != b.vsInvocations)
              return compareUInt64(a.vsInvocations, b.vsInvocations);
            break;
          case ColPSInvocations:
            if(validFirst(a.psValid, b.psValid))
              return true;
            if(validFirst(b.psValid, a.psValid))
              return false;
            if(a.psValid && b.psValid && a.psInvocations != b.psInvocations)
              return compareUInt64(a.psInvocations, b.psInvocations);
            break;
          case ColCSInvocations:
            if(validFirst(a.csValid, b.csValid))
              return true;
            if(validFirst(b.csValid, a.csValid))
              return false;
            if(a.csValid && b.csValid && a.csInvocations != b.csInvocations)
              return compareUInt64(a.csInvocations, b.csInvocations);
            break;
          case ColTextureSamples:
            if(validFirst(a.textureValid, b.textureValid))
              return true;
            if(validFirst(b.textureValid, a.textureValid))
              return false;
            if(a.textureValid && b.textureValid && a.textureSamples != b.textureSamples)
              return compareDouble(a.textureSamples, b.textureSamples);
            break;
          default: break;
        }

        return ascending ? a.eid < b.eid : b.eid < a.eid;
      });
  endResetModel();
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
      case ColBytes:
      {
        double mb = (double)resource.bytes / (1024.0 * 1024.0);
        return QFormatStr("%1 MB").arg(mb, 0, 'f', 2);
      }
      case ColShape:
      {
        if(resource.kind == "texture")
        {
          QString shape = QFormatStr("%1x%2").arg(resource.width).arg(resource.height);
          if(resource.depth > 1)
            shape += QFormatStr("x%1").arg(resource.depth);
          if(resource.arraySize > 1)
            shape += QFormatStr(" | Layers:%1").arg(resource.arraySize);
          if(resource.mips > 1)
            shape += QFormatStr(" | Mips:%1").arg(resource.mips);
          if(resource.samples > 1)
            shape += QFormatStr(" | MSAA:%1x").arg(resource.samples);
          return shape;
        }

        return QObject::tr("Linear buffer");
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

void AnalyzerResourceModel::sort(int column, Qt::SortOrder order)
{
  if(m_Resources.count() <= 1)
    return;

  bool ascending = order == Qt::AscendingOrder;

  auto compareText = [ascending](const rdcstr &a, const rdcstr &b) {
    return ascending ? a < b : a > b;
  };
  auto compareUInt = [ascending](uint32_t a, uint32_t b) { return ascending ? a < b : a > b; };
  auto compareU64 = [ascending](uint64_t a, uint64_t b) { return ascending ? a < b : a > b; };

  beginResetModel();
  std::stable_sort(m_Resources.begin(), m_Resources.end(),
                   [column, ascending, &compareText, &compareUInt, &compareU64](
                       const AnalyzerResourceRow &a, const AnalyzerResourceRow &b) {
                     switch(column)
                     {
                       case ColKind:
                         if(a.kind != b.kind)
                           return compareText(a.kind, b.kind);
                         break;
                       case ColName:
                         if(a.name != b.name)
                           return compareText(a.name, b.name);
                         break;
                       case ColId:
                         if(a.id != b.id)
                           return ascending ? a.id < b.id : b.id < a.id;
                         break;
                       case ColBytes:
                         if(a.bytes != b.bytes)
                           return compareU64(a.bytes, b.bytes);
                         break;
                       case ColShape:
                         if(a.width != b.width)
                           return compareUInt(a.width, b.width);
                         if(a.height != b.height)
                           return compareUInt(a.height, b.height);
                         if(a.depth != b.depth)
                           return compareUInt(a.depth, b.depth);
                         if(a.arraySize != b.arraySize)
                           return compareUInt(a.arraySize, b.arraySize);
                         if(a.mips != b.mips)
                           return compareUInt(a.mips, b.mips);
                         if(a.samples != b.samples)
                           return compareUInt(a.samples, b.samples);
                         if(a.bytes != b.bytes)
                           return compareU64(a.bytes, b.bytes);
                         break;
                       case ColFormat:
                         if(a.format != b.format)
                           return compareText(a.format, b.format);
                         break;
                       default: break;
                     }

                     return a.id < b.id;
                   });
  endResetModel();
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
      case ColByteSize: return QObject::tr("Size");
      case ColUseCount: return QObject::tr("Use Count");
      case ColFirstEID: return QObject::tr("First EID");
      case ColLastEID: return QObject::tr("Last EID");
      case ColMaliTotalCycles: return QObject::tr("Mali Total");
      case ColMaliShortestPath: return QObject::tr("Mali Short");
      case ColMaliLongestPath: return QObject::tr("Mali Long");
      case ColMaliUniformRegs: return QObject::tr("Mali URegs");
      case ColMaliFmaCycles: return QObject::tr("Mali FMA");
      case ColMaliCvtCycles: return QObject::tr("Mali CVT");
      case ColMaliSfuCycles: return QObject::tr("Mali SFU");
      case ColMaliLoadStoreCycles: return QObject::tr("Mali LS");
      case ColMaliTextureCycles: return QObject::tr("Mali Tex");
      case ColMaliVaryingCycles: return QObject::tr("Mali Var");
      case ColMaliWorkRegs: return QObject::tr("Mali Regs");
      case ColMaliSpillCount: return QObject::tr("Mali Spill");
      case ColMaliCost: return QObject::tr("Mali Cost");
      case ColMaliBound: return QObject::tr("Mali Bound");
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
      case ColByteSize:
      {
        if(shader.byteSize == 0)
          return QObject::tr("N/A");
        double kb = (double)shader.byteSize / 1024.0;
        return QFormatStr("%1 KB").arg(kb, 0, 'f', 2);
      }
      case ColUseCount: return (int)shader.useCount;
      case ColFirstEID: return (int)shader.firstEID;
      case ColLastEID: return (int)shader.lastEID;
      case ColMaliTotalCycles:
        return shader.maliValid ? QString::number(shader.maliTotalCycles, 'f', 2)
                                : QObject::tr("N/A");
      case ColMaliShortestPath:
        return shader.maliValid ? QString::number(shader.maliShortestPath, 'f', 2)
                                : QObject::tr("N/A");
      case ColMaliLongestPath:
        return shader.maliValid ? QString::number(shader.maliLongestPath, 'f', 2)
                                : QObject::tr("N/A");
      case ColMaliUniformRegs:
        return shader.maliValid ? QString::number(shader.maliUniformRegs)
                                : QObject::tr("N/A");
      case ColMaliFmaCycles:
        return shader.maliValid ? QString::number(shader.maliFmaCycles, 'f', 2)
                                : QObject::tr("N/A");
      case ColMaliCvtCycles:
        return shader.maliValid ? QString::number(shader.maliCvtCycles, 'f', 2)
                                : QObject::tr("N/A");
      case ColMaliSfuCycles:
        return shader.maliValid ? QString::number(shader.maliSfuCycles, 'f', 2)
                                : QObject::tr("N/A");
      case ColMaliLoadStoreCycles:
        return shader.maliValid ? QString::number(shader.maliLoadStoreCycles, 'f', 2)
                                : QObject::tr("N/A");
      case ColMaliTextureCycles:
        return shader.maliValid ? QString::number(shader.maliTextureCycles, 'f', 2)
                                : QObject::tr("N/A");
      case ColMaliVaryingCycles:
        return shader.maliValid ? QString::number(shader.maliVaryingCycles, 'f', 2)
                                : QObject::tr("N/A");
      case ColMaliWorkRegs:
        return shader.maliValid ? QString::number(shader.maliWorkRegs)
                                : QObject::tr("N/A");
      case ColMaliSpillCount:
        return shader.maliValid ? QString::number(shader.maliSpillCount)
                                : QObject::tr("N/A");
      case ColMaliCost:
        return shader.maliValid ? QString::number(shader.maliCost, 'f', 2)
                                : QObject::tr("N/A");
      case ColMaliBound:
        return shader.maliValid ? ToQStr(shader.maliBound) : QObject::tr("N/A");
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

void AnalyzerShaderModel::sort(int column, Qt::SortOrder order)
{
  if(m_Shaders.count() <= 1)
    return;

  bool ascending = order == Qt::AscendingOrder;

  auto compareText = [ascending](const rdcstr &a, const rdcstr &b) {
    return ascending ? a < b : a > b;
  };
  auto compareUInt = [ascending](uint32_t a, uint32_t b) { return ascending ? a < b : a > b; };
  auto compareFloat = [ascending](float a, float b) { return ascending ? a < b : a > b; };

  beginResetModel();
  std::stable_sort(m_Shaders.begin(), m_Shaders.end(),
                   [column, ascending, &compareText, &compareUInt,
                    &compareFloat](const AnalyzerShaderRow &a,
                                                                   const AnalyzerShaderRow &b) {
                     switch(column)
                     {
                       case ColStage:
                         if(a.stage != b.stage)
                           return compareText(a.stage, b.stage);
                         break;
                       case ColName:
                         if(a.name != b.name)
                           return compareText(a.name, b.name);
                         break;
                        case ColId:
                          if(a.id != b.id)
                            return ascending ? a.id < b.id : b.id < a.id;
                          break;
                        case ColByteSize:
                          if(a.byteSize != b.byteSize)
                            return compareUInt(a.byteSize, b.byteSize);
                          break;
                        case ColUseCount:
                          if(a.useCount != b.useCount)
                            return compareUInt(a.useCount, b.useCount);
                          break;
                       case ColFirstEID:
                         if(a.firstEID != b.firstEID)
                           return compareUInt(a.firstEID, b.firstEID);
                         break;
                        case ColLastEID:
                          if(a.lastEID != b.lastEID)
                            return compareUInt(a.lastEID, b.lastEID);
                          break;
                       case ColMaliTotalCycles:
                          if(a.maliValid != b.maliValid)
                            return a.maliValid && !b.maliValid;
                          if(a.maliTotalCycles != b.maliTotalCycles)
                            return compareFloat(a.maliTotalCycles, b.maliTotalCycles);
                          break;
                        case ColMaliShortestPath:
                          if(a.maliValid != b.maliValid)
                            return a.maliValid && !b.maliValid;
                          if(a.maliShortestPath != b.maliShortestPath)
                            return compareFloat(a.maliShortestPath, b.maliShortestPath);
                          break;
                        case ColMaliLongestPath:
                          if(a.maliValid != b.maliValid)
                            return a.maliValid && !b.maliValid;
                          if(a.maliLongestPath != b.maliLongestPath)
                            return compareFloat(a.maliLongestPath, b.maliLongestPath);
                          break;
                        case ColMaliUniformRegs:
                          if(a.maliValid != b.maliValid)
                            return a.maliValid && !b.maliValid;
                          if(a.maliUniformRegs != b.maliUniformRegs)
                            return compareUInt(a.maliUniformRegs, b.maliUniformRegs);
                          break;
                        case ColMaliFmaCycles:
                          if(a.maliValid != b.maliValid)
                            return a.maliValid && !b.maliValid;
                          if(a.maliFmaCycles != b.maliFmaCycles)
                            return compareFloat(a.maliFmaCycles, b.maliFmaCycles);
                          break;
                        case ColMaliCvtCycles:
                          if(a.maliValid != b.maliValid)
                            return a.maliValid && !b.maliValid;
                          if(a.maliCvtCycles != b.maliCvtCycles)
                            return compareFloat(a.maliCvtCycles, b.maliCvtCycles);
                          break;
                        case ColMaliSfuCycles:
                          if(a.maliValid != b.maliValid)
                            return a.maliValid && !b.maliValid;
                          if(a.maliSfuCycles != b.maliSfuCycles)
                            return compareFloat(a.maliSfuCycles, b.maliSfuCycles);
                          break;
                        case ColMaliLoadStoreCycles:
                          if(a.maliValid != b.maliValid)
                            return a.maliValid && !b.maliValid;
                          if(a.maliLoadStoreCycles != b.maliLoadStoreCycles)
                            return compareFloat(a.maliLoadStoreCycles, b.maliLoadStoreCycles);
                          break;
                        case ColMaliTextureCycles:
                          if(a.maliValid != b.maliValid)
                            return a.maliValid && !b.maliValid;
                          if(a.maliTextureCycles != b.maliTextureCycles)
                            return compareFloat(a.maliTextureCycles, b.maliTextureCycles);
                          break;
                        case ColMaliVaryingCycles:
                          if(a.maliValid != b.maliValid)
                            return a.maliValid && !b.maliValid;
                          if(a.maliVaryingCycles != b.maliVaryingCycles)
                            return compareFloat(a.maliVaryingCycles, b.maliVaryingCycles);
                          break;
                        case ColMaliWorkRegs:
                          if(a.maliValid != b.maliValid)
                            return a.maliValid && !b.maliValid;
                          if(a.maliWorkRegs != b.maliWorkRegs)
                            return compareUInt(a.maliWorkRegs, b.maliWorkRegs);
                          break;
                        case ColMaliSpillCount:
                          if(a.maliValid != b.maliValid)
                            return a.maliValid && !b.maliValid;
                          if(a.maliSpillCount != b.maliSpillCount)
                            return compareUInt(a.maliSpillCount, b.maliSpillCount);
                          break;
                        case ColMaliCost:
                          if(a.maliValid != b.maliValid)
                            return a.maliValid && !b.maliValid;
                          if(a.maliCost != b.maliCost)
                            return compareFloat(a.maliCost, b.maliCost);
                          break;
                        case ColMaliBound:
                          if(a.maliValid != b.maliValid)
                            return a.maliValid && !b.maliValid;
                          if(a.maliBound != b.maliBound)
                            return compareText(a.maliBound, b.maliBound);
                          break;
                        default: break;
                      }

                      return a.id < b.id;
                    });
  endResetModel();
}

AnalyzerShaderSortModel::AnalyzerShaderSortModel(QObject *parent)
    : QSortFilterProxyModel(parent), m_SortColumn(-1),
      m_SortOrder(Qt::AscendingOrder)
{
}

void AnalyzerShaderSortModel::sort(int column, Qt::SortOrder order)
{
  m_SortColumn = column;
  m_SortOrder = order;

  QSortFilterProxyModel::sort(column, Qt::AscendingOrder);
  invalidate();
}

bool AnalyzerShaderSortModel::lessThan(const QModelIndex &sourceLeft,
                                       const QModelIndex &sourceRight) const
{
  if(!sourceModel())
    return QSortFilterProxyModel::lessThan(sourceLeft, sourceRight);

  const AnalyzerShaderModel *model = static_cast<const AnalyzerShaderModel *>(sourceModel());
  AnalyzerShaderRow left = model->ShaderAt(sourceLeft.row());
  AnalyzerShaderRow right = model->ShaderAt(sourceRight.row());

  int column = m_SortColumn >= 0 ? m_SortColumn : sourceLeft.column();
  bool ascending = m_SortOrder == Qt::AscendingOrder;

  auto compareText = [ascending](const rdcstr &a, const rdcstr &b) {
    return ascending ? a < b : a > b;
  };
  auto compareUInt = [ascending](uint32_t a, uint32_t b) { return ascending ? a < b : a > b; };
  auto compareFloat = [ascending](float a, float b) { return ascending ? a < b : a > b; };

  switch(column)
  {
    case AnalyzerShaderModel::ColStage:
      if(left.stage != right.stage)
        return compareText(left.stage, right.stage);
      break;
    case AnalyzerShaderModel::ColName:
      if(left.name != right.name)
        return compareText(left.name, right.name);
      break;
    case AnalyzerShaderModel::ColId:
      if(left.id != right.id)
        return ascending ? left.id < right.id : right.id < left.id;
      break;
    case AnalyzerShaderModel::ColByteSize:
      if(left.byteSize == 0 || right.byteSize == 0)
      {
        if(left.byteSize == 0 && right.byteSize == 0)
          break;
        return right.byteSize == 0;
      }
      if(left.byteSize != right.byteSize)
        return compareUInt(left.byteSize, right.byteSize);
      break;
    case AnalyzerShaderModel::ColUseCount:
      if(left.useCount != right.useCount)
        return compareUInt(left.useCount, right.useCount);
      break;
    case AnalyzerShaderModel::ColFirstEID:
      if(left.firstEID != right.firstEID)
        return compareUInt(left.firstEID, right.firstEID);
      break;
    case AnalyzerShaderModel::ColLastEID:
      if(left.lastEID != right.lastEID)
        return compareUInt(left.lastEID, right.lastEID);
      break;
    case AnalyzerShaderModel::ColMaliTotalCycles:
      if(left.maliValid != right.maliValid)
        return left.maliValid && !right.maliValid;
      if(left.maliTotalCycles != right.maliTotalCycles)
        return compareFloat(left.maliTotalCycles, right.maliTotalCycles);
      break;
    case AnalyzerShaderModel::ColMaliShortestPath:
      if(left.maliValid != right.maliValid)
        return left.maliValid && !right.maliValid;
      if(left.maliShortestPath != right.maliShortestPath)
        return compareFloat(left.maliShortestPath, right.maliShortestPath);
      break;
    case AnalyzerShaderModel::ColMaliLongestPath:
      if(left.maliValid != right.maliValid)
        return left.maliValid && !right.maliValid;
      if(left.maliLongestPath != right.maliLongestPath)
        return compareFloat(left.maliLongestPath, right.maliLongestPath);
      break;
    case AnalyzerShaderModel::ColMaliUniformRegs:
      if(left.maliValid != right.maliValid)
        return left.maliValid && !right.maliValid;
      if(left.maliUniformRegs != right.maliUniformRegs)
        return compareUInt(left.maliUniformRegs, right.maliUniformRegs);
      break;
    case AnalyzerShaderModel::ColMaliFmaCycles:
      if(left.maliValid != right.maliValid)
        return left.maliValid && !right.maliValid;
      if(left.maliFmaCycles != right.maliFmaCycles)
        return compareFloat(left.maliFmaCycles, right.maliFmaCycles);
      break;
    case AnalyzerShaderModel::ColMaliCvtCycles:
      if(left.maliValid != right.maliValid)
        return left.maliValid && !right.maliValid;
      if(left.maliCvtCycles != right.maliCvtCycles)
        return compareFloat(left.maliCvtCycles, right.maliCvtCycles);
      break;
    case AnalyzerShaderModel::ColMaliSfuCycles:
      if(left.maliValid != right.maliValid)
        return left.maliValid && !right.maliValid;
      if(left.maliSfuCycles != right.maliSfuCycles)
        return compareFloat(left.maliSfuCycles, right.maliSfuCycles);
      break;
    case AnalyzerShaderModel::ColMaliLoadStoreCycles:
      if(left.maliValid != right.maliValid)
        return left.maliValid && !right.maliValid;
      if(left.maliLoadStoreCycles != right.maliLoadStoreCycles)
        return compareFloat(left.maliLoadStoreCycles, right.maliLoadStoreCycles);
      break;
    case AnalyzerShaderModel::ColMaliTextureCycles:
      if(left.maliValid != right.maliValid)
        return left.maliValid && !right.maliValid;
      if(left.maliTextureCycles != right.maliTextureCycles)
        return compareFloat(left.maliTextureCycles, right.maliTextureCycles);
      break;
    case AnalyzerShaderModel::ColMaliVaryingCycles:
      if(left.maliValid != right.maliValid)
        return left.maliValid && !right.maliValid;
      if(left.maliVaryingCycles != right.maliVaryingCycles)
        return compareFloat(left.maliVaryingCycles, right.maliVaryingCycles);
      break;
    case AnalyzerShaderModel::ColMaliWorkRegs:
      if(left.maliValid != right.maliValid)
        return left.maliValid && !right.maliValid;
      if(left.maliWorkRegs != right.maliWorkRegs)
        return compareUInt(left.maliWorkRegs, right.maliWorkRegs);
      break;
    case AnalyzerShaderModel::ColMaliSpillCount:
      if(left.maliValid != right.maliValid)
        return left.maliValid && !right.maliValid;
      if(left.maliSpillCount != right.maliSpillCount)
        return compareUInt(left.maliSpillCount, right.maliSpillCount);
      break;
    case AnalyzerShaderModel::ColMaliCost:
      if(left.maliValid != right.maliValid)
        return left.maliValid && !right.maliValid;
      if(left.maliCost != right.maliCost)
        return compareFloat(left.maliCost, right.maliCost);
      break;
    case AnalyzerShaderModel::ColMaliBound:
      if(left.maliValid != right.maliValid)
        return left.maliValid && !right.maliValid;
      if(left.maliBound != right.maliBound)
        return compareText(left.maliBound, right.maliBound);
      break;
    default: break;
  }

  return left.id < right.id;
}

#if ENABLE_UNIT_TESTS

#include <cstring>
#include "3rdparty/catch/catch.hpp"

namespace
{
ResourceId MakeAnalyzerTestResourceId(uint64_t raw)
{
  ResourceId id;
  static_assert(sizeof(ResourceId) == sizeof(uint64_t),
                "ResourceId size changed, update test helper");
  memcpy(&id, &raw, sizeof(raw));
  return id;
}
}

TEST_CASE("Analyzer resource model sorts size numerically", "[analyzer]")
{
  AnalyzerResourceRow small;
  small.id = MakeAnalyzerTestResourceId(1);
  small.kind = "texture";
  small.bytes = 16;
  small.width = 16;
  small.height = 16;
  small.format = "R8";

  AnalyzerResourceRow medium;
  medium.id = MakeAnalyzerTestResourceId(2);
  medium.kind = "texture";
  medium.bytes = 1024;
  medium.width = 32;
  medium.height = 32;
  medium.format = "R8G8";

  AnalyzerResourceRow large;
  large.id = MakeAnalyzerTestResourceId(3);
  large.kind = "texture";
  large.bytes = 4096;
  large.width = 64;
  large.height = 64;
  large.format = "R8G8B8A8";

  rdcarray<AnalyzerResourceRow> resources;
  resources.push_back(medium);
  resources.push_back(large);
  resources.push_back(small);

  AnalyzerResourceModel model;
  model.SetResources(resources);

  model.sort(AnalyzerResourceModel::ColBytes, Qt::AscendingOrder);
  CHECK(model.ResourceAt(0).bytes == 16);
  CHECK(model.ResourceAt(1).bytes == 1024);
  CHECK(model.ResourceAt(2).bytes == 4096);

  model.sort(AnalyzerResourceModel::ColBytes, Qt::DescendingOrder);
  CHECK(model.ResourceAt(0).bytes == 4096);
  CHECK(model.ResourceAt(1).bytes == 1024);
  CHECK(model.ResourceAt(2).bytes == 16);
}

TEST_CASE("Analyzer draw dispatch model sorts indices numerically", "[analyzer]")
{
  AnalyzerDrawDispatchRow small;
  small.eid = 10;
  small.name = "Draw";
  small.type = "draw";
  small.numIndices = 4;

  AnalyzerDrawDispatchRow medium;
  medium.eid = 11;
  medium.name = "Draw";
  medium.type = "draw";
  medium.numIndices = 64;

  AnalyzerDrawDispatchRow large;
  large.eid = 12;
  large.name = "Draw";
  large.type = "draw";
  large.numIndices = 512;

  rdcarray<AnalyzerDrawDispatchRow> rows;
  rows.push_back(medium);
  rows.push_back(large);
  rows.push_back(small);

  AnalyzerDrawDispatchModel model;
  model.SetRows(rows);

  model.sort(AnalyzerDrawDispatchModel::ColIndices, Qt::AscendingOrder);
  CHECK(model.RowAt(0).numIndices == 4);
  CHECK(model.RowAt(1).numIndices == 64);
  CHECK(model.RowAt(2).numIndices == 512);

  model.sort(AnalyzerDrawDispatchModel::ColIndices, Qt::DescendingOrder);
  CHECK(model.RowAt(0).numIndices == 512);
  CHECK(model.RowAt(1).numIndices == 64);
  CHECK(model.RowAt(2).numIndices == 4);
}

TEST_CASE("Analyzer state thrash model sorts shader binds numerically", "[analyzer]")
{
  AnalyzerStateThrashRow low;
  low.stage = "VS";
  low.available = true;
  low.shaderChanges = 1;

  AnalyzerStateThrashRow mid;
  mid.stage = "PS";
  mid.available = true;
  mid.shaderChanges = 6;

  AnalyzerStateThrashRow high;
  high.stage = "CS";
  high.available = true;
  high.shaderChanges = 20;

  rdcarray<AnalyzerStateThrashRow> rows;
  rows.push_back(mid);
  rows.push_back(high);
  rows.push_back(low);

  AnalyzerStateThrashModel model;
  model.SetRows(rows);

  model.sort(AnalyzerStateThrashModel::ColShaderChanges, Qt::DescendingOrder);
  CHECK(model.RowAt(0).shaderChanges == 20);
  CHECK(model.RowAt(1).shaderChanges == 6);
  CHECK(model.RowAt(2).shaderChanges == 1);

  model.sort(AnalyzerStateThrashModel::ColShaderChanges, Qt::AscendingOrder);
  CHECK(model.RowAt(0).shaderChanges == 1);
  CHECK(model.RowAt(1).shaderChanges == 6);
  CHECK(model.RowAt(2).shaderChanges == 20);
}

TEST_CASE("Analyzer pipeline bandwidth model sorts targets numerically", "[analyzer]")
{
  AnalyzerPipelineBandwidthRow low;
  low.eid = 100;
  low.name = "Draw";
  low.rtCount = 1;
  low.samples = 1;

  AnalyzerPipelineBandwidthRow mid;
  mid.eid = 101;
  mid.name = "Draw";
  mid.rtCount = 2;
  mid.samples = 4;

  AnalyzerPipelineBandwidthRow high;
  high.eid = 102;
  high.name = "Draw";
  high.rtCount = 6;
  high.samples = 8;

  rdcarray<AnalyzerPipelineBandwidthRow> rows;
  rows.push_back(mid);
  rows.push_back(high);
  rows.push_back(low);

  AnalyzerPipelineBandwidthModel model;
  model.SetRows(rows);

  model.sort(AnalyzerPipelineBandwidthModel::ColRTCount, Qt::AscendingOrder);
  CHECK(model.RowAt(0).rtCount == 1);
  CHECK(model.RowAt(1).rtCount == 2);
  CHECK(model.RowAt(2).rtCount == 6);

  model.sort(AnalyzerPipelineBandwidthModel::ColRTCount, Qt::DescendingOrder);
  CHECK(model.RowAt(0).rtCount == 6);
  CHECK(model.RowAt(1).rtCount == 2);
  CHECK(model.RowAt(2).rtCount == 1);

  model.sort(AnalyzerPipelineBandwidthModel::ColSamples, Qt::DescendingOrder);
  CHECK(model.RowAt(0).samples == 8);
  CHECK(model.RowAt(1).samples == 4);
  CHECK(model.RowAt(2).samples == 1);
}

TEST_CASE("Analyzer gpu counter model sorts gpu time and texture samples", "[analyzer]")
{
  AnalyzerGpuCounterRow low;
  low.eid = 200;
  low.name = "Draw";
  low.gpuTimeMs = 0.5;
  low.gpuTimeValid = true;
  low.textureSamples = 12.0;
  low.textureValid = true;

  AnalyzerGpuCounterRow mid;
  mid.eid = 201;
  mid.name = "Draw";
  mid.gpuTimeMs = 2.0;
  mid.gpuTimeValid = true;
  mid.textureSamples = 4.0;
  mid.textureValid = true;

  AnalyzerGpuCounterRow high;
  high.eid = 202;
  high.name = "Draw";
  high.gpuTimeMs = 5.0;
  high.gpuTimeValid = true;
  high.textureSamples = 32.0;
  high.textureValid = true;

  rdcarray<AnalyzerGpuCounterRow> rows;
  rows.push_back(mid);
  rows.push_back(high);
  rows.push_back(low);

  AnalyzerGpuCounterModel model;
  model.SetRows(rows);

  model.sort(AnalyzerGpuCounterModel::ColGpuTime, Qt::AscendingOrder);
  CHECK(model.RowAt(0).gpuTimeMs == Approx(0.5));
  CHECK(model.RowAt(2).gpuTimeMs == Approx(5.0));

  model.sort(AnalyzerGpuCounterModel::ColTextureSamples, Qt::DescendingOrder);
  CHECK(model.RowAt(0).textureSamples == Approx(32.0));
  CHECK(model.RowAt(2).textureSamples == Approx(4.0));
}

TEST_CASE("Analyzer shader model sorts use count numerically", "[analyzer]")
{
  AnalyzerShaderRow low;
  low.id = MakeAnalyzerTestResourceId(11);
  low.stage = "PS";
  low.useCount = 1;
  low.firstEID = 100;
  low.lastEID = 100;

  AnalyzerShaderRow mid;
  mid.id = MakeAnalyzerTestResourceId(12);
  mid.stage = "PS";
  mid.useCount = 3;
  mid.firstEID = 101;
  mid.lastEID = 105;

  AnalyzerShaderRow high;
  high.id = MakeAnalyzerTestResourceId(13);
  high.stage = "PS";
  high.useCount = 20;
  high.firstEID = 90;
  high.lastEID = 140;

  rdcarray<AnalyzerShaderRow> shaders;
  shaders.push_back(mid);
  shaders.push_back(low);
  shaders.push_back(high);

  AnalyzerShaderModel model;
  model.SetShaders(shaders);

  model.sort(AnalyzerShaderModel::ColUseCount, Qt::DescendingOrder);
  CHECK(model.ShaderAt(0).useCount == 20);
  CHECK(model.ShaderAt(1).useCount == 3);
  CHECK(model.ShaderAt(2).useCount == 1);

  model.sort(AnalyzerShaderModel::ColUseCount, Qt::AscendingOrder);
  CHECK(model.ShaderAt(0).useCount == 1);
  CHECK(model.ShaderAt(1).useCount == 3);
  CHECK(model.ShaderAt(2).useCount == 20);
}

TEST_CASE("Analyzer shader model sorts mali cost numerically", "[analyzer]")
{
  AnalyzerShaderRow low;
  low.id = MakeAnalyzerTestResourceId(21);
  low.stage = "PS";
  low.maliValid = true;
  low.maliCost = 1.0f;

  AnalyzerShaderRow mid;
  mid.id = MakeAnalyzerTestResourceId(22);
  mid.stage = "PS";
  mid.maliValid = true;
  mid.maliCost = 3.5f;

  AnalyzerShaderRow high;
  high.id = MakeAnalyzerTestResourceId(23);
  high.stage = "PS";
  high.maliValid = true;
  high.maliCost = 9.0f;

  AnalyzerShaderRow invalid;
  invalid.id = MakeAnalyzerTestResourceId(24);
  invalid.stage = "PS";
  invalid.maliValid = false;
  invalid.maliCost = 100.0f;

  rdcarray<AnalyzerShaderRow> shaders;
  shaders.push_back(mid);
  shaders.push_back(invalid);
  shaders.push_back(low);
  shaders.push_back(high);

  AnalyzerShaderModel model;
  model.SetShaders(shaders);

  model.sort(AnalyzerShaderModel::ColMaliCost, Qt::DescendingOrder);
  CHECK(model.ShaderAt(0).maliCost == 9.0f);
  CHECK(model.ShaderAt(1).maliCost == 3.5f);
  CHECK(model.ShaderAt(2).maliCost == 1.0f);
  CHECK(model.ShaderAt(3).maliValid == false);

  model.sort(AnalyzerShaderModel::ColMaliCost, Qt::AscendingOrder);
  CHECK(model.ShaderAt(0).maliCost == 1.0f);
  CHECK(model.ShaderAt(1).maliCost == 3.5f);
  CHECK(model.ShaderAt(2).maliCost == 9.0f);
  CHECK(model.ShaderAt(3).maliValid == false);
}

TEST_CASE("Analyzer shader model sorts mali longest path numerically", "[analyzer]")
{
  AnalyzerShaderRow low;
  low.id = MakeAnalyzerTestResourceId(21);
  low.stage = "PS";
  low.maliValid = true;
  low.maliLongestPath = 5.0f;

  AnalyzerShaderRow mid;
  mid.id = MakeAnalyzerTestResourceId(22);
  mid.stage = "PS";
  mid.maliValid = true;
  mid.maliLongestPath = 12.5f;

  AnalyzerShaderRow high;
  high.id = MakeAnalyzerTestResourceId(23);
  high.stage = "PS";
  high.maliValid = true;
  high.maliLongestPath = 30.0f;

  AnalyzerShaderRow invalid;
  invalid.id = MakeAnalyzerTestResourceId(24);
  invalid.stage = "PS";
  invalid.maliValid = false;
  invalid.maliLongestPath = 100.0f;

  rdcarray<AnalyzerShaderRow> shaders;
  shaders.push_back(mid);
  shaders.push_back(high);
  shaders.push_back(low);
  shaders.push_back(invalid);

  AnalyzerShaderModel model;
  model.SetShaders(shaders);

  model.sort(AnalyzerShaderModel::ColMaliLongestPath, Qt::DescendingOrder);
  CHECK(model.ShaderAt(0).maliLongestPath == 30.0f);
  CHECK(model.ShaderAt(1).maliLongestPath == 12.5f);
  CHECK(model.ShaderAt(2).maliLongestPath == 5.0f);
  CHECK(model.ShaderAt(3).maliValid == false);

  model.sort(AnalyzerShaderModel::ColMaliLongestPath, Qt::AscendingOrder);
  CHECK(model.ShaderAt(0).maliLongestPath == 5.0f);
  CHECK(model.ShaderAt(1).maliLongestPath == 12.5f);
  CHECK(model.ShaderAt(2).maliLongestPath == 30.0f);
  CHECK(model.ShaderAt(3).maliValid == false);
}

#endif
