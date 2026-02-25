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
#include "Code/Analyzer/AnalyzerTypes.h"

class AnalyzerIssueModel : public QAbstractTableModel
{
public:
  enum Columns
  {
    ColSeverity = 0,
    ColCode,
    ColMessage,
    ColEID,
    ColImpact,
    ColCount,
  };

  enum Roles
  {
    EventIdRole = Qt::UserRole + 1,
    ImpactRole,
    SeverityRole,
  };

  explicit AnalyzerIssueModel(QObject *parent = NULL);

  void SetIssues(const rdcarray<AnalyzerIssue> &issues);
  AnalyzerIssue IssueAt(int row) const;

  int rowCount(const QModelIndex &parent = QModelIndex()) const override;
  int columnCount(const QModelIndex &parent = QModelIndex()) const override;
  QVariant headerData(int section, Qt::Orientation orientation, int role) const override;
  QVariant data(const QModelIndex &index, int role = Qt::DisplayRole) const override;

private:
  int SeverityRank(const rdcstr &severity) const;

  rdcarray<AnalyzerIssue> m_Issues;
};

class AnalyzerIssueSortModel : public QSortFilterProxyModel
{
public:
  explicit AnalyzerIssueSortModel(QObject *parent = NULL);

protected:
  bool lessThan(const QModelIndex &sourceLeft, const QModelIndex &sourceRight) const override;
};

class AnalyzerEventModel : public QAbstractTableModel
{
public:
  explicit AnalyzerEventModel(QObject *parent = NULL);

  void SetEvents(const rdcarray<AnalyzerEventRow> &events);

  int rowCount(const QModelIndex &parent = QModelIndex()) const override;
  int columnCount(const QModelIndex &parent = QModelIndex()) const override;
  QVariant headerData(int section, Qt::Orientation orientation, int role) const override;
  QVariant data(const QModelIndex &index, int role = Qt::DisplayRole) const override;
  void sort(int column, Qt::SortOrder order = Qt::AscendingOrder) override;

private:
  rdcarray<AnalyzerEventRow> m_Events;
};

class AnalyzerResourceModel : public QAbstractTableModel
{
public:
  enum Columns
  {
    ColKind = 0,
    ColName,
    ColId,
    ColBytes,
    ColShape,
    ColFormat,
    ColCount,
  };

  enum Roles
  {
    ResourceIdRole = Qt::UserRole + 1,
    ResourceKindRole,
    BytesRole,
  };

  explicit AnalyzerResourceModel(QObject *parent = NULL);

  void SetResources(const rdcarray<AnalyzerResourceRow> &resources);
  AnalyzerResourceRow ResourceAt(int row) const;

  int rowCount(const QModelIndex &parent = QModelIndex()) const override;
  int columnCount(const QModelIndex &parent = QModelIndex()) const override;
  QVariant headerData(int section, Qt::Orientation orientation, int role) const override;
  QVariant data(const QModelIndex &index, int role = Qt::DisplayRole) const override;
  void sort(int column, Qt::SortOrder order = Qt::AscendingOrder) override;

private:
  rdcarray<AnalyzerResourceRow> m_Resources;
};

class AnalyzerShaderModel : public QAbstractTableModel
{
public:
  enum Columns
  {
    ColStage = 0,
    ColName,
    ColId,
    ColUseCount,
    ColFirstEID,
    ColLastEID,
    ColCount,
  };

  enum Roles
  {
    ShaderIdRole = Qt::UserRole + 1,
    FirstEventRole,
    UseCountRole,
  };

  explicit AnalyzerShaderModel(QObject *parent = NULL);

  void SetShaders(const rdcarray<AnalyzerShaderRow> &shaders);
  AnalyzerShaderRow ShaderAt(int row) const;

  int rowCount(const QModelIndex &parent = QModelIndex()) const override;
  int columnCount(const QModelIndex &parent = QModelIndex()) const override;
  QVariant headerData(int section, Qt::Orientation orientation, int role) const override;
  QVariant data(const QModelIndex &index, int role = Qt::DisplayRole) const override;
  void sort(int column, Qt::SortOrder order = Qt::AscendingOrder) override;

private:
  rdcarray<AnalyzerShaderRow> m_Shaders;
};
