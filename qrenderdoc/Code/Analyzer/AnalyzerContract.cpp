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

#include "AnalyzerContract.h"
#include <QJsonArray>
#include <QJsonDocument>
#include "Code/QRDUtils.h"

namespace
{
QJsonObject EvidenceToQJson(const AnalyzerEvidence &evidence)
{
  QJsonObject obj;
  obj[lit("metric")] = ToQStr(evidence.metric);
  obj[lit("value")] = evidence.value;
  obj[lit("unit")] = ToQStr(evidence.unit);
  obj[lit("detail")] = ToQStr(evidence.detail);
  return obj;
}

QJsonObject IssueToQJson(const AnalyzerIssue &issue)
{
  QJsonObject obj;

  obj[lit("code")] = ToQStr(issue.code);
  obj[lit("severity")] = ToQStr(issue.severity);
  obj[lit("category")] = ToQStr(issue.category);
  obj[lit("message")] = ToQStr(issue.message);
  obj[lit("impact_score")] = issue.impactScore;
  obj[lit("confidence")] = ToQStr(issue.confidence);
  obj[lit("recommendation")] = ToQStr(issue.recommendation);

  QJsonArray eventIds;
  for(uint32_t eid : issue.eventIds)
    eventIds.push_back((int)eid);
  obj[lit("event_ids")] = eventIds;

  QJsonArray resourceIds;
  for(ResourceId id : issue.resourceIds)
    resourceIds.push_back(ToQStr(id));
  obj[lit("resource_ids")] = resourceIds;

  QJsonArray evidenceArray;
  for(const AnalyzerEvidence &evidence : issue.evidence)
    evidenceArray.push_back(EvidenceToQJson(evidence));
  obj[lit("evidence")] = evidenceArray;

  return obj;
}

QJsonObject EventToQJson(const AnalyzerEventRow &event)
{
  QJsonObject obj;

  obj[lit("eid")] = (int)event.eid;
  obj[lit("name")] = ToQStr(event.name);
  obj[lit("type")] = ToQStr(event.type);
  obj[lit("draw_index")] = (int)event.drawIndex;
  obj[lit("pass_index")] = (int)event.passIndex;
  obj[lit("vs")] = ToQStr(event.vs);
  obj[lit("ps")] = ToQStr(event.ps);
  obj[lit("cs")] = ToQStr(event.cs);
  obj[lit("ds")] = ToQStr(event.ds);

  QJsonArray rts;
  for(ResourceId rt : event.rts)
    rts.push_back(ToQStr(rt));
  obj[lit("rts")] = rts;

  return obj;
}

QJsonObject ResourceToQJson(const AnalyzerResourceRow &resource)
{
  QJsonObject obj;
  obj[lit("id")] = ToQStr(resource.id);
  obj[lit("name")] = ToQStr(resource.name);
  obj[lit("kind")] = ToQStr(resource.kind);
  obj[lit("bytes")] = (double)resource.bytes;
  obj[lit("width")] = (int)resource.width;
  obj[lit("height")] = (int)resource.height;
  obj[lit("depth")] = (int)resource.depth;
  obj[lit("mips")] = (int)resource.mips;
  obj[lit("array_size")] = (int)resource.arraySize;
  obj[lit("samples")] = (int)resource.samples;
  obj[lit("format")] = ToQStr(resource.format);
  return obj;
}

QJsonObject ShaderToQJson(const AnalyzerShaderRow &shader)
{
  QJsonObject obj;
  obj[lit("id")] = ToQStr(shader.id);
  obj[lit("name")] = ToQStr(shader.name);
  obj[lit("stage")] = ToQStr(shader.stage);
  obj[lit("use_count")] = (int)shader.useCount;
  obj[lit("first_eid")] = (int)shader.firstEID;
  obj[lit("last_eid")] = (int)shader.lastEID;
  return obj;
}
}

QJsonObject AnalyzerContract::ToQJson(const AnalyzerSnapshot &snapshot)
{
  QJsonObject root;

  root[lit("schema_version")] = ToQStr(snapshot.schemaVersion);

  QJsonObject summary;
  summary[lit("api")] = ToQStr(snapshot.summary.api);
  summary[lit("frame_number")] = (int)snapshot.summary.frameNumber;
  summary[lit("draw_count")] = (int)snapshot.summary.drawCount;
  summary[lit("dispatch_count")] = (int)snapshot.summary.dispatchCount;
  summary[lit("texture_count")] = (int)snapshot.summary.textureCount;
  summary[lit("buffer_count")] = (int)snapshot.summary.bufferCount;
  summary[lit("pass_count")] = (int)snapshot.summary.passCount;
  summary[lit("texture_bytes")] = (double)snapshot.summary.textureBytes;
  summary[lit("buffer_bytes")] = (double)snapshot.summary.bufferBytes;
  root[lit("summary")] = summary;

  QJsonArray events;
  for(const AnalyzerEventRow &event : snapshot.events)
    events.push_back(EventToQJson(event));
  root[lit("events")] = events;

  QJsonArray resources;
  for(const AnalyzerResourceRow &resource : snapshot.resources)
    resources.push_back(ResourceToQJson(resource));
  root[lit("resources")] = resources;

  QJsonArray shaders;
  for(const AnalyzerShaderRow &shader : snapshot.shaders)
    shaders.push_back(ShaderToQJson(shader));
  root[lit("shaders")] = shaders;

  QJsonArray issues;
  for(const AnalyzerIssue &issue : snapshot.issues)
    issues.push_back(IssueToQJson(issue));
  root[lit("issues")] = issues;

  return root;
}

QByteArray AnalyzerContract::ToJsonBytes(const AnalyzerSnapshot &snapshot)
{
  return QJsonDocument(ToQJson(snapshot)).toJson(QJsonDocument::Indented);
}
