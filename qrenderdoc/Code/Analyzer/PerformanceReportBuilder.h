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

#include <map>
#include "AnalyzerTypes.h"

struct PerfOpportunity
{
  rdcstr id;
  rdcstr title;
  rdcstr severity;
  rdcstr category;
  rdcstr why;
  rdcstr recommendation;
  rdcstr viewHint;     // event | texture | pipeline | mesh | shader
  rdcstr confidence;   // high | medium | low
  double impactScore = 0.0;  // 0..1 (from AnalyzerIssue)
  double impactMs = -1.0;    // <0 if not available
  rdcarray<uint32_t> eventIds;
  rdcarray<ResourceId> resourceIds;
  rdcarray<AnalyzerEvidence> evidence;
};

struct PerfScores
{
  float overall = 100.0f;
  float fill = 100.0f;
  float bandwidth = 100.0f;
  float geometry = 100.0f;
  float sync = 100.0f;
};

struct PerfReportData
{
  AnalyzerSummary summary;
  PerfScores scores;
  rdcarray<PerfOpportunity> opportunities;
  rdcstr timingConfidence;  // high | medium | low
};

class PerformanceReportBuilder
{
public:
  PerfReportData Build(const AnalyzerSnapshot &snapshot, const rdcarray<AnalyzerIssue> &issues,
                       const std::map<uint32_t, double> *eventTimings,
                       const rdcstr &timingConfidence) const;

private:
  float ApplyPenalty(PerfScores &scores, const AnalyzerIssue &issue) const;
  rdcstr PickViewHint(const AnalyzerIssue &issue) const;
  rdcstr PickTitle(const AnalyzerIssue &issue) const;
  bool HasTimingForOpportunity(const PerfOpportunity &opp,
                               const std::map<uint32_t, double> *eventTimings) const;
};
