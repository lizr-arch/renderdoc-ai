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
