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

#include "PerformanceReportBuilder.h"
#include <algorithm>

static int SeverityRank(const rdcstr &severity)
{
  if(severity == "critical")
    return 0;
  if(severity == "warning")
    return 1;
  return 2;
}

PerfReportData PerformanceReportBuilder::Build(const AnalyzerSnapshot &snapshot,
                                               const rdcarray<AnalyzerIssue> &issues,
                                               const std::map<uint32_t, double> *eventTimings,
                                               const rdcstr &timingConfidence) const
{
  PerfReportData report;
  report.summary = snapshot.summary;
  report.timingConfidence = timingConfidence;

  // Build opportunities from issues
  for(const AnalyzerIssue &issue : issues)
  {
    PerfOpportunity opp;
    opp.id = issue.code;
    opp.title = PickTitle(issue);
    opp.severity = issue.severity;
    opp.category = issue.category;
    opp.why = issue.message;
    opp.recommendation = issue.recommendation;
    opp.viewHint = PickViewHint(issue);
    opp.impactScore = issue.impactScore;
    opp.eventIds = issue.eventIds;
    opp.resourceIds = issue.resourceIds;
    opp.evidence = issue.evidence;

    opp.confidence = timingConfidence;
    if(timingConfidence != "low" && !HasTimingForOpportunity(opp, eventTimings))
      opp.confidence = "medium";

    if(eventTimings != NULL)
    {
      double best = -1.0;
      for(uint32_t eid : opp.eventIds)
      {
        auto it = eventTimings->find(eid);
        if(it == eventTimings->end())
          continue;
        if(it->second > best)
          best = it->second;
      }

      if(best >= 0.0)
        opp.impactMs = best * 1000.0;
    }

    report.opportunities.push_back(opp);
  }

  // Sort by severity then impact score
  std::sort(report.opportunities.begin(), report.opportunities.end(),
            [](const PerfOpportunity &a, const PerfOpportunity &b) {
              int aRank = SeverityRank(a.severity);
              int bRank = SeverityRank(b.severity);

              if(aRank != bRank)
                return aRank < bRank;

              return a.impactScore > b.impactScore;
            });

  // Compute scores
  PerfScores scores;
  for(const AnalyzerIssue &issue : issues)
    ApplyPenalty(scores, issue);

  scores.fill = std::max(0.0f, scores.fill);
  scores.bandwidth = std::max(0.0f, scores.bandwidth);
  scores.geometry = std::max(0.0f, scores.geometry);
  scores.sync = std::max(0.0f, scores.sync);
  scores.overall = (scores.fill + scores.bandwidth + scores.geometry + scores.sync) / 4.0f;

  report.scores = scores;
  return report;
}

float PerformanceReportBuilder::ApplyPenalty(PerfScores &scores, const AnalyzerIssue &issue) const
{
  float severityWeight = 10.0f;
  if(issue.severity == "critical")
    severityWeight = 30.0f;
  else if(issue.severity == "warning")
    severityWeight = 20.0f;

  float penalty = (float)(issue.impactScore * severityWeight);

  if(issue.category == "texture" || issue.category == "bandwidth" || issue.category == "memory")
    scores.bandwidth -= penalty;
  else if(issue.category == "draw" || issue.category == "geometry" || issue.category == "compute")
    scores.geometry -= penalty;
  else if(issue.category == "copy" || issue.category == "sync" || issue.category == "barrier")
    scores.sync -= penalty;
  else if(issue.category == "overdraw" || issue.category == "fill")
    scores.fill -= penalty;
  else if(issue.category == "state" || issue.category == "pipeline")
    scores.geometry -= penalty * 0.5f;
  else
    scores.geometry -= penalty * 0.3f;

  return penalty;
}

rdcstr PerformanceReportBuilder::PickViewHint(const AnalyzerIssue &issue) const
{
  if(issue.category == "texture" || issue.category == "bandwidth" || issue.category == "memory")
    return "texture";
  if(issue.category == "shader")
    return "shader";
  if(issue.category == "state" || issue.category == "pipeline")
    return "pipeline";
  if(issue.category == "draw" || issue.category == "geometry")
    return "mesh";
  if(issue.category == "overdraw" || issue.category == "fill")
    return "pipeline";
  return "event";
}

rdcstr PerformanceReportBuilder::PickTitle(const AnalyzerIssue &issue) const
{
  if(!issue.code.empty())
    return issue.code;

  return issue.message;
}

bool PerformanceReportBuilder::HasTimingForOpportunity(
    const PerfOpportunity &opp, const std::map<uint32_t, double> *eventTimings) const
{
  if(eventTimings == NULL)
    return false;

  for(uint32_t eid : opp.eventIds)
  {
    auto it = eventTimings->find(eid);
    if(it != eventTimings->end() && it->second > 0.0)
      return true;
  }

  return false;
}
