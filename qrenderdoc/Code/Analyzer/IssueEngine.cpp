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

#include "IssueEngine.h"
#include <algorithm>

rdcarray<AnalyzerIssue> IssueEngine::Evaluate(const AnalyzerSnapshot &snapshot) const
{
  rdcarray<AnalyzerIssue> issues;

  auto firstEvent = [&snapshot]() -> uint32_t {
    if(snapshot.events.empty())
      return 0;
    return snapshot.events[0].eid;
  };

  auto lastEvent = [&snapshot]() -> uint32_t {
    if(snapshot.events.empty())
      return 0;
    return snapshot.events.back().eid;
  };

  if(snapshot.summary.drawCount > 5000)
  {
    AnalyzerIssue issue;
    issue.code = "PERF_DC_001";
    issue.severity = "warning";
    issue.category = "draw";
    issue.message = "High draw-call count may increase CPU submission overhead.";
    issue.impactScore = 0.85;
    issue.confidence = "high";
    issue.recommendation =
        "Batch draw calls and reduce redundant state transitions where possible.";
    issue.eventIds.push_back(firstEvent());
    if(lastEvent() != firstEvent())
      issue.eventIds.push_back(lastEvent());

    AnalyzerEvidence evidence;
    evidence.metric = "draw_count";
    evidence.value = (double)snapshot.summary.drawCount;
    evidence.unit = "calls";
    evidence.detail = "Frame-level draw call count.";
    issue.evidence.push_back(evidence);

    issues.push_back(issue);
  }

  if(snapshot.summary.textureBytes > (uint64_t)(1024ULL * 1024ULL * 1024ULL))
  {
    AnalyzerIssue issue;
    issue.code = "TEX_SIZE_001";
    issue.severity = "warning";
    issue.category = "texture";
    issue.message = "Texture memory usage exceeds 1GB in this frame snapshot.";
    issue.impactScore = 0.70;
    issue.confidence = "medium";
    issue.recommendation =
        "Review oversized textures and ensure high-resolution assets are justified.";
    issue.eventIds.push_back(lastEvent());

    AnalyzerEvidence evidence;
    evidence.metric = "texture_bytes";
    evidence.value = (double)snapshot.summary.textureBytes;
    evidence.unit = "bytes";
    evidence.detail = "Total texture memory footprint in frame resource list.";
    issue.evidence.push_back(evidence);

    issues.push_back(issue);
  }

  if(snapshot.summary.passCount > 200)
  {
    AnalyzerIssue issue;
    issue.code = "STATE_SWITCH_001";
    issue.severity = "info";
    issue.category = "state";
    issue.message = "High render pass count can indicate state churn.";
    issue.impactScore = 0.50;
    issue.confidence = "medium";
    issue.recommendation =
        "Inspect pass boundaries and merge compatible passes when practical.";
    issue.eventIds.push_back(lastEvent());

    AnalyzerEvidence evidence;
    evidence.metric = "pass_count";
    evidence.value = (double)snapshot.summary.passCount;
    evidence.unit = "passes";
    evidence.detail = "Counted from ActionFlags::BeginPass markers.";
    issue.evidence.push_back(evidence);

    issues.push_back(issue);
  }

  if(issues.empty())
  {
    AnalyzerIssue issue;
    issue.code = "ANALYZER_BASELINE";
    issue.severity = "info";
    issue.category = "baseline";
    issue.message = "No high-priority baseline issues detected by current native rules.";
    issue.impactScore = 0.10;
    issue.confidence = "low";
    issue.recommendation = "Extend rule set with workload-specific checks for deeper diagnostics.";
    issue.eventIds.push_back(lastEvent());
    issues.push_back(issue);
  }

  std::sort(issues.begin(), issues.end(), [this](const AnalyzerIssue &a, const AnalyzerIssue &b) {
    int aRank = SeverityRank(a.severity);
    int bRank = SeverityRank(b.severity);

    if(aRank != bRank)
      return aRank < bRank;

    return a.impactScore > b.impactScore;
  });

  return issues;
}

int IssueEngine::SeverityRank(const rdcstr &severity) const
{
  if(severity == "critical")
    return 0;
  if(severity == "warning")
    return 1;
  return 2;
}
