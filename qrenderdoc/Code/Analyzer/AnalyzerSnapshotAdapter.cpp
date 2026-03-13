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

#include "AnalyzerSnapshotAdapter.h"
#include <QDateTime>
#include <QFileInfo>
#include <QHash>
#include <QJsonArray>
#include <QSet>
#include <QStringList>
#include <QVector>
#include <algorithm>
#include "Code/QRDUtils.h"

namespace
{
struct TimingCandidate
{
  uint32_t eid = 0;
  QString name;
  double gpuTimeMs = 0.0;
};

QStringList NormalizeStringList(const QStringList &values)
{
  QStringList normalized;
  QSet<QString> dedup;

  for(const QString &value : values)
  {
    const QString trimmed = value.trimmed();
    if(trimmed.isEmpty() || dedup.contains(trimmed))
      continue;

    dedup.insert(trimmed);
    normalized.push_back(trimmed);
  }

  return normalized;
}

QJsonArray ToJsonStringArray(const QStringList &values)
{
  QJsonArray array;
  for(const QString &value : NormalizeStringList(values))
    array.push_back(value);
  return array;
}

QJsonObject MakeAvailability(const QString &status, const QStringList &missingFields,
                             const QStringList &notes)
{
  QJsonObject availability;
  availability[lit("status")] = status;
  if(!missingFields.isEmpty())
    availability[lit("missing_fields")] = ToJsonStringArray(missingFields);
  if(!notes.isEmpty())
    availability[lit("notes")] = ToJsonStringArray(notes);
  return availability;
}

QStringList BuildGlobalMissingFieldPaths()
{
  return QStringList({lit("passes"), lit("pipelines"), lit("actions.marker_path"),
                      lit("actions.flags"), lit("actions.pipeline_ref"),
                      lit("resources.textures.producer_event_refs"), lit("shaders.source_asm"),
                      lit("shaders.source_high_level"), lit("shaders.resource_bindings")});
}

QStringList BuildPreflightConclusions()
{
  return QStringList({lit("Pass-level grouping is unavailable in current GUI export."),
                      lit("Pipeline summaries are deferred to a later snapshot.v1 phase."),
                      lit("Buffer usage tags remain coarse-grained in GUI snapshot export.")});
}

QStringList BuildGlobalAvailabilityNotes()
{
  return QStringList(
      {lit("GUI snapshot.v1 export keeps the existing viewer display model unchanged."),
       lit("Buffer usage tags are emitted with coarse GUI-derived classification.")});
}

QJsonObject BuildActionAvailability(bool hasTiming, bool hasPipelineRef)
{
  QStringList missingFields;
  missingFields << lit("marker_path") << lit("flags");
  if(!hasTiming)
    missingFields << lit("timing_ms");
  if(!hasPipelineRef)
    missingFields << lit("pipeline_ref");

  return MakeAvailability(
      lit("partial"), missingFields,
      QStringList({lit("Marker hierarchy and draw flags are not sampled in analyzer snapshot.")}));
}

QJsonObject BuildTextureAvailability()
{
  return MakeAvailability(
      lit("partial"), QStringList({lit("producer_event_refs")}),
      QStringList({lit("Producer-event detection is not available in current GUI export.")}));
}

QJsonObject BuildBufferAvailability()
{
  return MakeAvailability(
      lit("partial"), QStringList(),
      QStringList({lit("Binding-role classification is simplified for GUI snapshot export.")}));
}

QJsonObject BuildShaderAvailability()
{
  return MakeAvailability(
      lit("partial"),
      QStringList({lit("source_asm"), lit("source_high_level"), lit("resource_bindings")}),
      QStringList(
          {lit("Shader source and binding reflection are not sampled in analyzer snapshot.")}));
}

QJsonObject BuildSectionStatus(const QJsonObject &timings)
{
  QJsonObject sectionStatus;
  sectionStatus[lit("preflight")] = lit("partial");
  sectionStatus[lit("overview")] = lit("full");
  sectionStatus[lit("timings")] =
      timings.value(lit("availability")).toObject().value(lit("status")).toString(lit("unavailable"));
  sectionStatus[lit("actions")] = lit("partial");
  sectionStatus[lit("resources")] = lit("partial");
  sectionStatus[lit("shaders")] = lit("partial");
  sectionStatus[lit("findings")] = lit("full");
  sectionStatus[lit("recommendations")] = lit("full");
  sectionStatus[lit("evidence_index")] = lit("full");
  sectionStatus[lit("passes")] = lit("unavailable");
  sectionStatus[lit("pipelines")] = lit("unavailable");
  return sectionStatus;
}

QJsonObject BuildRootAvailability(const QJsonObject &sectionStatus)
{
  QJsonObject availability = MakeAvailability(lit("partial"), BuildGlobalMissingFieldPaths(),
                                              BuildGlobalAvailabilityNotes());
  availability[lit("sections")] = sectionStatus;
  return availability;
}

void AppendUniqueEvidence(QJsonArray &array, QSet<QString> &dedup, const QJsonObject &evidence)
{
  QString key =
      evidence.value(lit("kind")).toString() + lit(":") + evidence.value(lit("id")).toString();
  if(dedup.contains(key))
    return;

  dedup.insert(key);
  array.push_back(evidence);
}

QJsonObject MakeEvidenceRef(const QString &kind, const QString &id, const QString &label,
                            const QString &sourceRef, const QString &anchor)
{
  QJsonObject evidence;
  evidence[lit("kind")] = kind;
  evidence[lit("id")] = id;
  evidence[lit("label")] = label;
  evidence[lit("source_ref")] = sourceRef;
  evidence[lit("anchor")] = anchor;
  return evidence;
}

QString NormalizeSeverity(const rdcstr &severity)
{
  const QString value = ToQStr(severity).trimmed().toLower();
  if(value == lit("critical"))
    return lit("critical");
  if(value == lit("high") || value == lit("warning") || value == lit("warn"))
    return lit("high");
  if(value == lit("medium"))
    return lit("medium");
  if(value == lit("low"))
    return lit("low");
  return lit("info");
}

QString PriorityFromSeverity(const QString &severity)
{
  if(severity == lit("critical") || severity == lit("high"))
    return lit("high");
  if(severity == lit("medium"))
    return lit("medium");
  return lit("low");
}

QString ActionKindFromType(const rdcstr &type)
{
  const QString value = ToQStr(type).trimmed().toLower();
  if(value.contains(lit("draw")))
    return lit("draw");
  if(value.contains(lit("dispatch")))
    return lit("dispatch");
  if(value.contains(lit("clear")))
    return lit("clear");
  return lit("marker");
}

bool ResourceAppearsInEvent(const AnalyzerEventRow &event, ResourceId resourceId)
{
  if(event.ds == resourceId)
    return true;

  for(ResourceId rt : event.rts)
  {
    if(rt == resourceId)
      return true;
  }

  return false;
}

bool IsTextureResource(const AnalyzerResourceRow &resource)
{
  QString kind = ToQStr(resource.kind).toLower();
  if(kind.contains(lit("texture")) || kind.contains(lit("render")) || kind.contains(lit("depth")) ||
     kind.contains(lit("image")))
    return true;
  if(kind.contains(lit("buffer")))
    return false;

  return resource.width > 0 || resource.height > 0 || resource.depth > 0;
}

QJsonArray BuildIssueEvidence(const AnalyzerIssue &issue)
{
  QJsonArray evidence;
  QSet<QString> dedup;

  for(uint32_t eid : issue.eventIds)
  {
    const QString eidStr = QString::number(eid);
    AppendUniqueEvidence(
        evidence, dedup,
        MakeEvidenceRef(lit("event"), eidStr, QFormatStr("event %1").arg(eidStr),
                        QFormatStr("actions/%1").arg(eidStr), QFormatStr("event-%1").arg(eidStr)));
  }

  for(ResourceId resourceId : issue.resourceIds)
  {
    const QString id = ToQStr(resourceId);
    if(id.isEmpty())
      continue;

    AppendUniqueEvidence(
        evidence, dedup,
        MakeEvidenceRef(lit("resource"), id, QFormatStr("resource %1").arg(id),
                        QFormatStr("resources/%1").arg(id), QFormatStr("resource-%1").arg(id)));
  }

  return evidence;
}

QJsonArray BuildActionShaderRefs(const AnalyzerEventRow &event)
{
  QJsonArray refs;
  QSet<QString> dedup;

  if(event.vs != ResourceId())
  {
    const QString id = ToQStr(event.vs);
    AppendUniqueEvidence(
        refs, dedup,
        MakeEvidenceRef(lit("shader"), id, QFormatStr("VS %1").arg(id),
                        QFormatStr("shaders/%1").arg(id), QFormatStr("shader-%1").arg(id)));
  }

  if(event.ps != ResourceId())
  {
    const QString id = ToQStr(event.ps);
    AppendUniqueEvidence(
        refs, dedup,
        MakeEvidenceRef(lit("shader"), id, QFormatStr("PS %1").arg(id),
                        QFormatStr("shaders/%1").arg(id), QFormatStr("shader-%1").arg(id)));
  }

  if(event.cs != ResourceId())
  {
    const QString id = ToQStr(event.cs);
    AppendUniqueEvidence(
        refs, dedup,
        MakeEvidenceRef(lit("shader"), id, QFormatStr("CS %1").arg(id),
                        QFormatStr("shaders/%1").arg(id), QFormatStr("shader-%1").arg(id)));
  }

  return refs;
}

QJsonArray BuildActionResourceRefs(const AnalyzerEventRow &event)
{
  QJsonArray refs;
  QSet<QString> dedup;

  for(ResourceId rt : event.rts)
  {
    if(rt == ResourceId())
      continue;

    const QString id = ToQStr(rt);
    AppendUniqueEvidence(
        refs, dedup,
        MakeEvidenceRef(lit("resource"), id, QFormatStr("RT %1").arg(id),
                        QFormatStr("resources/%1").arg(id), QFormatStr("resource-%1").arg(id)));
  }

  if(event.ds != ResourceId())
  {
    const QString id = ToQStr(event.ds);
    AppendUniqueEvidence(
        refs, dedup,
        MakeEvidenceRef(lit("resource"), id, QFormatStr("DS %1").arg(id),
                        QFormatStr("resources/%1").arg(id), QFormatStr("resource-%1").arg(id)));
  }

  return refs;
}

QJsonObject BuildPreflight()
{
  QJsonObject preflight;
  preflight[lit("status")] = lit("warning");
  preflight[lit("missing_data")] = ToJsonStringArray(BuildGlobalMissingFieldPaths());
  preflight[lit("degraded_conclusions")] = ToJsonStringArray(BuildPreflightConclusions());
  preflight[lit("capture_recommendations")] =
      ToJsonStringArray(QStringList({lit("Capture full pipeline state for pass/pipeline analysis."),
                                     lit("Keep GPU counters enabled for timing confidence.")}));
  return preflight;
}

QJsonObject BuildTimings(const AnalyzerSnapshot &snapshot)
{
  QJsonObject timings;

  QVector<TimingCandidate> entries;
  entries.reserve((int)snapshot.gpuCounters.count());
  bool anyAvailable = false;
  int usableCount = 0;
  int zeroOrNegativeCount = 0;
  double totalGpuMs = 0.0;

  QHash<uint32_t, QString> eventNames;
  for(const AnalyzerEventRow &event : snapshot.events)
    eventNames.insert(event.eid, ToQStr(event.name));

  for(const AnalyzerGpuCounterRow &counter : snapshot.gpuCounters)
  {
    if(!counter.gpuTimeValid)
      continue;

    anyAvailable = true;

    if(counter.gpuTimeMs > 0.0)
    {
      usableCount++;
      totalGpuMs += counter.gpuTimeMs;
    }
    else
    {
      zeroOrNegativeCount++;
    }

    TimingCandidate entry;
    entry.eid = counter.eid;
    entry.gpuTimeMs = counter.gpuTimeMs;
    entry.name = eventNames.value(counter.eid, ToQStr(counter.name));
    if(entry.name.isEmpty())
      entry.name = QFormatStr("event %1").arg(counter.eid);
    entries.push_back(entry);
  }

  std::sort(entries.begin(), entries.end(), [](const TimingCandidate &a, const TimingCandidate &b) {
    return a.gpuTimeMs > b.gpuTimeMs;
  });

  QJsonArray topActions;
  const int limit = std::min(entries.count(), 10);
  for(int i = 0; i < limit; i++)
  {
    const TimingCandidate &entry = entries[i];
    if(entry.gpuTimeMs <= 0.0)
      continue;

    QJsonObject action;
    action[lit("event_id")] = (int)entry.eid;
    action[lit("name")] = entry.name;
    action[lit("timing_ms")] = entry.gpuTimeMs;

    const QString eid = QString::number(entry.eid);
    QJsonArray evidence;
    evidence.push_back(MakeEvidenceRef(lit("event"), eid, entry.name,
                                       QFormatStr("actions/%1").arg(eid),
                                       QFormatStr("event-%1").arg(eid)));
    action[lit("evidence")] = evidence;
    topActions.push_back(action);
  }

  timings[lit("available")] = anyAvailable;
  timings[lit("usable_count")] = usableCount;
  timings[lit("zero_or_negative_count")] = zeroOrNegativeCount;
  timings[lit("total_gpu_ms")] = totalGpuMs;
  timings[lit("top_actions")] = topActions;

  if(anyAvailable)
    timings[lit("availability")] = MakeAvailability(lit("full"), QStringList(), QStringList());
  else
    timings[lit("availability")] = MakeAvailability(
        lit("unavailable"), QStringList({lit("top_actions"), lit("total_gpu_ms")}),
        QStringList({lit("No valid GPU timing values were exported for this capture.")}));

  return timings;
}

QJsonObject BuildOverview(const AnalyzerSnapshot &snapshot)
{
  QJsonObject overview;

  QJsonObject summary;
  summary[lit("draw_call_count")] = (int)snapshot.summary.drawCount;
  summary[lit("dispatch_count")] = (int)snapshot.summary.dispatchCount;
  summary[lit("texture_count")] = (int)snapshot.summary.textureCount;
  summary[lit("buffer_count")] = (int)snapshot.summary.bufferCount;
  summary[lit("shader_count")] = (int)snapshot.shaders.count();
  summary[lit("pass_count")] = (int)snapshot.summary.passCount;
  overview[lit("summary")] = summary;

  QJsonArray highlights;
  bool hasTop = false;
  AnalyzerGpuCounterRow topCounter;
  topCounter.gpuTimeMs = -1.0;

  QHash<uint32_t, QString> eventNames;
  for(const AnalyzerEventRow &event : snapshot.events)
    eventNames.insert(event.eid, ToQStr(event.name));

  for(const AnalyzerGpuCounterRow &counter : snapshot.gpuCounters)
  {
    if(!counter.gpuTimeValid || counter.gpuTimeMs <= topCounter.gpuTimeMs)
      continue;
    hasTop = true;
    topCounter = counter;
  }

  if(hasTop && topCounter.gpuTimeMs > 0.0)
  {
    QJsonObject highlight;
    highlight[lit("title")] = lit("Top GPU hotspot");
    QString eventName = eventNames.value(topCounter.eid, ToQStr(topCounter.name));
    if(eventName.isEmpty())
      eventName = QFormatStr("event %1").arg(topCounter.eid);
    highlight[lit("value")] =
        QFormatStr("event %1 / %2 ms").arg(topCounter.eid).arg(Formatter::Format(topCounter.gpuTimeMs));
    QJsonArray evidence;
    QString eid = QString::number(topCounter.eid);
    evidence.push_back(MakeEvidenceRef(lit("event"), eid, eventName, QFormatStr("actions/%1").arg(eid),
                                       QFormatStr("event-%1").arg(eid)));
    highlight[lit("evidence")] = evidence;
    highlights.push_back(highlight);
  }

  overview[lit("highlights")] = highlights;
  return overview;
}

QJsonArray BuildActions(const AnalyzerSnapshot &snapshot)
{
  QJsonArray actions;

  QHash<uint32_t, int> drawDispatchByEid;
  QHash<uint32_t, int> gpuCounterByEid;

  for(int i = 0; i < snapshot.drawDispatch.count(); i++)
    drawDispatchByEid.insert(snapshot.drawDispatch[i].eid, i);
  for(int i = 0; i < snapshot.gpuCounters.count(); i++)
    gpuCounterByEid.insert(snapshot.gpuCounters[i].eid, i);

  for(const AnalyzerEventRow &event : snapshot.events)
  {
    const QString eid = QString::number(event.eid);

    QJsonObject action;
    action[lit("event_id")] = (int)event.eid;
    action[lit("name")] = ToQStr(event.name);
    action[lit("kind")] = ActionKindFromType(event.type);
    action[lit("marker_path")] = QJsonArray();
    action[lit("flags")] = QJsonArray();

    if(gpuCounterByEid.contains(event.eid))
    {
      const AnalyzerGpuCounterRow &counter = snapshot.gpuCounters[gpuCounterByEid[event.eid]];
      if(counter.gpuTimeValid)
        action[lit("timing_ms")] = counter.gpuTimeMs;
    }

    if(drawDispatchByEid.contains(event.eid))
    {
      const AnalyzerDrawDispatchRow &drawDispatch =
          snapshot.drawDispatch[drawDispatchByEid[event.eid]];
      QJsonObject drawDispatchObj;
      drawDispatchObj[lit("num_indices")] = (int)drawDispatch.numIndices;
      drawDispatchObj[lit("num_instances")] = (int)drawDispatch.numInstances;
      drawDispatchObj[lit("indirect")] = drawDispatch.indirect;

      QJsonArray dispatchDim;
      dispatchDim.push_back((int)drawDispatch.dispatchDim[0]);
      dispatchDim.push_back((int)drawDispatch.dispatchDim[1]);
      dispatchDim.push_back((int)drawDispatch.dispatchDim[2]);
      drawDispatchObj[lit("dispatch_dim")] = dispatchDim;

      QJsonArray dispatchThreads;
      dispatchThreads.push_back((int)drawDispatch.dispatchThreads[0]);
      dispatchThreads.push_back((int)drawDispatch.dispatchThreads[1]);
      dispatchThreads.push_back((int)drawDispatch.dispatchThreads[2]);
      drawDispatchObj[lit("dispatch_threads")] = dispatchThreads;

      action[lit("draw_dispatch")] = drawDispatchObj;
    }

    QJsonArray shaderRefs = BuildActionShaderRefs(event);
    if(!shaderRefs.isEmpty())
      action[lit("shader_refs")] = shaderRefs;

    QJsonArray resourceRefs = BuildActionResourceRefs(event);
    if(!resourceRefs.isEmpty())
      action[lit("resource_refs")] = resourceRefs;

    action[lit("availability")] = BuildActionAvailability(action.contains(lit("timing_ms")),
                                                          action.contains(lit("pipeline_ref")));

    QJsonArray evidence;
    evidence.push_back(MakeEvidenceRef(lit("event"), eid, ToQStr(event.name),
                                       QFormatStr("actions/%1").arg(eid),
                                       QFormatStr("event-%1").arg(eid)));
    action[lit("evidence")] = evidence;

    actions.push_back(action);
  }

  return actions;
}

QJsonArray BuildConsumerRefs(const AnalyzerSnapshot &snapshot, ResourceId resourceId)
{
  QJsonArray refs;
  QSet<QString> dedup;

  for(const AnalyzerEventRow &event : snapshot.events)
  {
    if(!ResourceAppearsInEvent(event, resourceId))
      continue;

    const QString eid = QString::number(event.eid);
    AppendUniqueEvidence(
        refs, dedup,
        MakeEvidenceRef(lit("event"), eid, ToQStr(event.name), QFormatStr("actions/%1").arg(eid),
                        QFormatStr("event-%1").arg(eid)));
  }

  return refs;
}

QJsonObject BuildResources(const AnalyzerSnapshot &snapshot)
{
  QJsonObject resources;
  QJsonArray textures;
  QJsonArray buffers;

  for(const AnalyzerResourceRow &resource : snapshot.resources)
  {
    const QString resourceId = ToQStr(resource.id);
    if(resourceId.isEmpty())
      continue;

    const bool isTexture = IsTextureResource(resource);
    const QJsonArray consumerRefs = BuildConsumerRefs(snapshot, resource.id);
    const QStringList usageTags = QStringList({ToQStr(resource.kind).toLower()});

    if(isTexture)
    {
      QJsonObject texture;
      texture[lit("resource_id")] = resourceId;
      texture[lit("name")] = ToQStr(resource.name);
      texture[lit("width")] = (int)resource.width;
      texture[lit("height")] = (int)resource.height;
      texture[lit("depth")] = (int)resource.depth;
      texture[lit("format")] = ToQStr(resource.format);
      texture[lit("sample_count")] = (int)resource.samples;
      texture[lit("usage_tags")] = ToJsonStringArray(usageTags);
      texture[lit("producer_event_refs")] = QJsonArray();
      texture[lit("consumer_event_refs")] = consumerRefs;
      texture[lit("availability")] = BuildTextureAvailability();
      textures.push_back(texture);
    }
    else
    {
      QJsonObject buffer;
      buffer[lit("resource_id")] = resourceId;
      buffer[lit("name")] = ToQStr(resource.name);
      buffer[lit("byte_size")] = (double)resource.bytes;
      buffer[lit("usage_tags")] = ToJsonStringArray(usageTags);
      buffer[lit("bound_event_refs")] = consumerRefs;
      buffer[lit("availability")] = BuildBufferAvailability();
      buffers.push_back(buffer);
    }
  }

  resources[lit("textures")] = textures;
  resources[lit("buffers")] = buffers;
  return resources;
}

QJsonArray BuildShaderEventRefs(const AnalyzerSnapshot &snapshot, const AnalyzerShaderRow &shader)
{
  QJsonArray refs;
  QSet<QString> dedup;

  for(const AnalyzerEventRow &event : snapshot.events)
  {
    if(event.vs != shader.id && event.ps != shader.id && event.cs != shader.id)
      continue;

    const QString eid = QString::number(event.eid);
    AppendUniqueEvidence(
        refs, dedup,
        MakeEvidenceRef(lit("event"), eid, ToQStr(event.name), QFormatStr("actions/%1").arg(eid),
                        QFormatStr("event-%1").arg(eid)));
  }

  if(shader.firstEID > 0)
  {
    const QString first = QString::number(shader.firstEID);
    AppendUniqueEvidence(
        refs, dedup,
        MakeEvidenceRef(lit("event"), first, QFormatStr("event %1").arg(first),
                        QFormatStr("actions/%1").arg(first), QFormatStr("event-%1").arg(first)));
  }

  if(shader.lastEID > 0)
  {
    const QString last = QString::number(shader.lastEID);
    AppendUniqueEvidence(
        refs, dedup,
        MakeEvidenceRef(lit("event"), last, QFormatStr("event %1").arg(last),
                        QFormatStr("actions/%1").arg(last), QFormatStr("event-%1").arg(last)));
  }

  return refs;
}

QJsonArray BuildShaders(const AnalyzerSnapshot &snapshot)
{
  QJsonArray shaders;

  for(const AnalyzerShaderRow &shader : snapshot.shaders)
  {
    const QString shaderId = ToQStr(shader.id);
    if(shaderId.isEmpty())
      continue;

    QJsonObject item;
    item[lit("shader_id")] = shaderId;
    item[lit("stage")] = ToQStr(shader.stage);
    if(!ToQStr(shader.name).isEmpty())
      item[lit("entry_point")] = ToQStr(shader.name);
    item[lit("used_by_event_refs")] = BuildShaderEventRefs(snapshot, shader);
    item[lit("availability")] = BuildShaderAvailability();

    shaders.push_back(item);
  }

  return shaders;
}

QJsonArray BuildFindings(const AnalyzerSnapshot &snapshot)
{
  QJsonArray findings;

  for(int i = 0; i < snapshot.issues.count(); i++)
  {
    const AnalyzerIssue &issue = snapshot.issues[i];
    const QString code = ToQStr(issue.code).trimmed();

    QJsonObject finding;
    finding[lit("id")] = code.isEmpty() ? QFormatStr("FINDING_%1").arg(i + 1) : code;
    finding[lit("severity")] = NormalizeSeverity(issue.severity);
    finding[lit("category")] = ToQStr(issue.category);
    finding[lit("title")] = code.isEmpty() ? lit("Analyzer finding") : code;
    finding[lit("message")] = ToQStr(issue.message);
    finding[lit("evidence")] = BuildIssueEvidence(issue);

    QJsonObject metrics;
    metrics[lit("impact_score")] = issue.impactScore;
    metrics[lit("confidence")] = ToQStr(issue.confidence);
    finding[lit("metrics")] = metrics;

    finding[lit("availability")] = MakeAvailability(lit("full"), QStringList(), QStringList());
    findings.push_back(finding);
  }

  return findings;
}

QStringList SplitVerificationSteps(const rdcstr &recommendation)
{
  QString text = ToQStr(recommendation);
  text.replace(lit("\r\n"), lit("\n"));
  text = text.trimmed();
  if(text.isEmpty())
    return QStringList();

  QStringList steps;
  const QStringList lines = text.split(lit("\n"), QString::SkipEmptyParts);
  for(const QString &line : lines)
  {
    const QStringList parts = line.split(lit(";"), QString::SkipEmptyParts);
    if(parts.isEmpty())
    {
      const QString trimmed = line.trimmed();
      if(!trimmed.isEmpty())
        steps << trimmed;
      continue;
    }

    for(const QString &part : parts)
    {
      const QString trimmed = part.trimmed();
      if(!trimmed.isEmpty())
        steps << trimmed;
    }
  }

  if(steps.isEmpty())
    steps << text;

  return steps;
}

QJsonArray BuildRecommendations(const AnalyzerSnapshot &snapshot)
{
  QJsonArray recommendations;

  for(int i = 0; i < snapshot.issues.count(); i++)
  {
    const AnalyzerIssue &issue = snapshot.issues[i];
    QString recommendationText = ToQStr(issue.recommendation).trimmed();
    if(recommendationText.isEmpty())
      continue;

    QString severity = NormalizeSeverity(issue.severity);
    QString code = ToQStr(issue.code).trimmed();
    if(code.isEmpty())
      code = QFormatStr("REC_%1").arg(i + 1);

    QJsonObject recommendation;
    recommendation[lit("id")] = QFormatStr("REC_%1").arg(code);
    recommendation[lit("title")] =
        QFormatStr("Address %1")
            .arg(ToQStr(issue.code).isEmpty() ? lit("analyzer finding") : ToQStr(issue.code));
    recommendation[lit("priority")] = PriorityFromSeverity(severity);
    recommendation[lit("rationale")] = recommendationText;
    recommendation[lit("evidence")] = BuildIssueEvidence(issue);
    recommendation[lit("verification_steps")] =
        ToJsonStringArray(SplitVerificationSteps(issue.recommendation));

    recommendations.push_back(recommendation);
  }

  return recommendations;
}

QJsonObject BuildEvidenceIndex(const AnalyzerSnapshot &snapshot)
{
  QJsonObject evidenceIndex;

  QJsonObject events;
  for(const AnalyzerEventRow &event : snapshot.events)
  {
    const QString eid = QString::number(event.eid);
    events[eid] = QFormatStr("events.html#event-%1").arg(eid);
  }

  QJsonObject resources;
  for(const AnalyzerResourceRow &resource : snapshot.resources)
  {
    const QString id = ToQStr(resource.id);
    if(id.isEmpty())
      continue;
    resources[id] = QFormatStr("textures.html#resource-%1").arg(id);
  }

  QJsonObject shaders;
  for(const AnalyzerShaderRow &shader : snapshot.shaders)
  {
    const QString id = ToQStr(shader.id);
    if(id.isEmpty())
      continue;
    shaders[id] = QFormatStr("shaders.html#shader-%1").arg(id);
  }

  evidenceIndex[lit("events")] = events;
  evidenceIndex[lit("resources")] = resources;
  evidenceIndex[lit("shaders")] = shaders;
  evidenceIndex[lit("passes")] = QJsonObject();
  return evidenceIndex;
}

QJsonObject BuildMeta(const AnalyzerSnapshot &snapshot, const QJsonObject &captureContext,
                      int fullCount, int partialCount, int unavailableCount)
{
  QJsonObject meta;

  QString capturePath = captureContext.value(lit("capture_path")).toString().trimmed();
  if(capturePath.isEmpty())
    capturePath = captureContext.value(lit("capture_file")).toString().trimmed();

  QString captureName = captureContext.value(lit("capture_name")).toString().trimmed();
  if(captureName.isEmpty() && !capturePath.isEmpty())
    captureName = QFileInfo(capturePath).fileName();

  QString reportSurface = captureContext.value(lit("report_surface")).toString().trimmed();
  if(reportSurface.isEmpty())
    reportSurface = lit("gui_html");

  QString graphicsAPI = ToQStr(snapshot.summary.api).trimmed();
  if(graphicsAPI.isEmpty())
    graphicsAPI = lit("Unknown");

  meta[lit("source")] = lit("gui");
  meta[lit("capture_name")] = captureName;
  meta[lit("capture_path")] = capturePath;
  meta[lit("graphics_api")] = graphicsAPI;
  meta[lit("frame_number")] = (int)snapshot.summary.frameNumber;
  meta[lit("generated_at")] = QDateTime::currentDateTime().toString(Qt::ISODate);

  QJsonObject generator;
  generator[lit("kind")] = lit("gui_export");
  generator[lit("version")] = lit("1.0");
  meta[lit("generator")] = generator;

  meta[lit("report_surface")] = reportSurface;

  QJsonObject summary;
  summary[lit("full")] = fullCount;
  summary[lit("partial")] = partialCount;
  summary[lit("unavailable")] = unavailableCount;
  meta[lit("availability_summary")] = summary;

  return meta;
}

void CountStatus(const QString &status, int &fullCount, int &partialCount, int &unavailableCount)
{
  if(status == lit("full"))
    fullCount++;
  else if(status == lit("partial"))
    partialCount++;
  else
    unavailableCount++;
}
}

QJsonObject AnalyzerSnapshotAdapter::ToSnapshotV1(const AnalyzerSnapshot &snapshot,
                                                  const QJsonObject &captureContext)
{
  QJsonObject root;
  root[lit("schema_version")] = lit("snapshot.v1");

  QJsonObject preflight = BuildPreflight();
  QJsonObject overview = BuildOverview(snapshot);
  QJsonObject timings = BuildTimings(snapshot);
  QJsonArray actions = BuildActions(snapshot);
  QJsonObject resources = BuildResources(snapshot);
  QJsonArray shaders = BuildShaders(snapshot);
  QJsonArray findings = BuildFindings(snapshot);
  QJsonArray recommendations = BuildRecommendations(snapshot);
  QJsonObject evidenceIndex = BuildEvidenceIndex(snapshot);

  QJsonObject sectionStatus = BuildSectionStatus(timings);

  int fullCount = 0;
  int partialCount = 0;
  int unavailableCount = 0;
  const QStringList keys = sectionStatus.keys();
  for(const QString &key : keys)
    CountStatus(sectionStatus.value(key).toString(), fullCount, partialCount, unavailableCount);

  root[lit("meta")] = BuildMeta(snapshot, captureContext, fullCount, partialCount, unavailableCount);
  root[lit("preflight")] = preflight;
  root[lit("overview")] = overview;
  root[lit("timings")] = timings;
  root[lit("actions")] = actions;
  root[lit("passes")] = QJsonArray();
  root[lit("resources")] = resources;
  root[lit("shaders")] = shaders;
  root[lit("pipelines")] = QJsonArray();
  root[lit("findings")] = findings;
  root[lit("recommendations")] = recommendations;
  root[lit("evidence_index")] = evidenceIndex;
  root[lit("availability")] = BuildRootAvailability(sectionStatus);

  return root;
}
