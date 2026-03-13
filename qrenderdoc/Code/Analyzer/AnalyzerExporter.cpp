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

#include "AnalyzerExporter.h"
#include <QDir>
#include <QFile>
#include <QJsonDocument>
#include <QTextStream>
#include "Code/QRDUtils.h"
#include "AnalyzerContract.h"
#include "AnalyzerSnapshotAdapter.h"

bool AnalyzerExporter::WriteAll(const AnalyzerSnapshot &snapshot, const QString &directory,
                                const QJsonObject &captureContext, QString *error) const
{
  QDir dir(directory);
  if(!dir.exists() && !dir.mkpath(lit(".")))
  {
    if(error)
      *error = QObject::tr("Failed to create export directory: %1").arg(directory);
    return false;
  }

  const QString jsonPath = dir.absoluteFilePath(lit("analysis.json"));
  const QString csvPath = dir.absoluteFilePath(lit("issues_export.csv"));
  const QString mdPath = dir.absoluteFilePath(lit("issues_export.md"));
  const QString captureContextPath = dir.absoluteFilePath(lit("capture_context.json"));
  const QString snapshotV1Path = dir.absoluteFilePath(lit("snapshot.v1.json"));

  // Keep the native analyzer JSON as a compatibility sidecar only. snapshot.v1 is built directly
  // from the in-memory AnalyzerSnapshot plus capture context and must not round-trip through it.
  if(!WriteAnalysisJSON(snapshot, jsonPath, error))
    return false;

  if(!WriteIssuesCSV(snapshot, csvPath, error))
    return false;

  if(!WriteIssuesMarkdown(snapshot, mdPath, error))
    return false;

  if(!WriteCaptureContextJSON(captureContext, captureContextPath, error))
    return false;

  if(!WriteSnapshotV1JSON(snapshot, captureContext, snapshotV1Path, error))
    return false;

  return true;
}

bool AnalyzerExporter::WriteAnalysisJSON(const AnalyzerSnapshot &snapshot, const QString &path,
                                         QString *error) const
{
  // This file is intentionally preserved for legacy consumers and debugging. It is not a source of
  // truth for snapshot.v1 generation.
  return WriteBytes(path, AnalyzerContract::ToJsonBytes(snapshot), error);
}

bool AnalyzerExporter::WriteIssuesCSV(const AnalyzerSnapshot &snapshot, const QString &path,
                                      QString *error) const
{
  QByteArray data;
  QTextStream stream(&data, QIODevice::WriteOnly);

  stream << "severity,code,category,message,eid,impact,confidence,recommendation\n";

  for(const AnalyzerIssue &issue : snapshot.issues)
  {
    uint32_t eid = issue.eventIds.empty() ? 0 : issue.eventIds[0];

    QString line = QFormatStr("\"%1\",\"%2\",\"%3\",\"%4\",%5,%6,\"%7\",\"%8\"\n")
                       .arg(ToQStr(issue.severity).replace(lit("\""), lit("\"\"")))
                       .arg(ToQStr(issue.code).replace(lit("\""), lit("\"\"")))
                       .arg(ToQStr(issue.category).replace(lit("\""), lit("\"\"")))
                       .arg(ToQStr(issue.message).replace(lit("\""), lit("\"\"")))
                       .arg(eid)
                       .arg(issue.impactScore)
                       .arg(ToQStr(issue.confidence).replace(lit("\""), lit("\"\"")))
                       .arg(ToQStr(issue.recommendation).replace(lit("\""), lit("\"\"")));

    stream << line;
  }

  stream.flush();

  return WriteBytes(path, data, error);
}

bool AnalyzerExporter::WriteIssuesMarkdown(const AnalyzerSnapshot &snapshot, const QString &path,
                                           QString *error) const
{
  QByteArray data;
  QTextStream stream(&data, QIODevice::WriteOnly);

  stream << "# Analyzer Issues\n\n";
  stream << "| Severity | Code | Category | Message | EID | Impact |\n";
  stream << "| --- | --- | --- | --- | ---: | ---: |\n";

  for(const AnalyzerIssue &issue : snapshot.issues)
  {
    uint32_t eid = issue.eventIds.empty() ? 0 : issue.eventIds[0];

    stream << "| " << ToQStr(issue.severity) << " | " << ToQStr(issue.code) << " | "
           << ToQStr(issue.category) << " | " << ToQStr(issue.message) << " | " << eid << " | "
           << Formatter::Format(issue.impactScore) << " |\n";
  }

  stream.flush();

  return WriteBytes(path, data, error);
}

bool AnalyzerExporter::WriteCaptureContextJSON(const QJsonObject &captureContext,
                                               const QString &path, QString *error) const
{
  QJsonObject root = captureContext;
  if(!root.contains(lit("schema_version")))
    root[lit("schema_version")] = lit("capture_context.v1");

  return WriteBytes(path, QJsonDocument(root).toJson(QJsonDocument::Indented), error);
}

bool AnalyzerExporter::WriteSnapshotV1JSON(const AnalyzerSnapshot &snapshot,
                                           const QJsonObject &captureContext, const QString &path,
                                           QString *error) const
{
  // snapshot.v1 is emitted from the live analyzer snapshot contract, not by reading back legacy
  // exporter output.
  QJsonObject root = AnalyzerSnapshotAdapter::ToSnapshotV1(snapshot, captureContext);
  return WriteBytes(path, QJsonDocument(root).toJson(QJsonDocument::Indented), error);
}

bool AnalyzerExporter::WriteBytes(const QString &path, const QByteArray &bytes, QString *error) const
{
  QFile file(path);
  if(!file.open(QIODevice::WriteOnly | QIODevice::Truncate))
  {
    if(error)
      *error = QObject::tr("Failed to open file for writing: %1").arg(path);
    return false;
  }

  qint64 written = file.write(bytes);
  file.close();

  if(written != bytes.size())
  {
    if(error)
      *error = QObject::tr("Failed to write full file: %1").arg(path);
    return false;
  }

  return true;
}
