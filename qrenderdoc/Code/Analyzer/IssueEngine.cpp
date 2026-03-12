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
#include <cctype>

namespace
{
rdcstr Utf8Literal(const char16_t *text)
{
  return rdcstr(QString::fromUtf16(text));
}

AnalyzerEvidence MakeEvidence(const char *metric, double value, const char *unit,
                              const char16_t *detail, bool hasThreshold, double threshold,
                              const char *comparison, const char *source, const char *scope)
{
  AnalyzerEvidence evidence;
  evidence.metric = metric;
  evidence.value = value;
  evidence.unit = unit;
  evidence.detail = Utf8Literal(detail);
  evidence.hasThreshold = hasThreshold;
  evidence.threshold = threshold;
  evidence.comparison = comparison ? comparison : "";
  evidence.source = source ? source : "";
  evidence.scope = scope ? scope : "";
  return evidence;
}
}

rdcarray<AnalyzerIssue> IssueEngine::Evaluate(const AnalyzerSnapshot &snapshot) const
{
  rdcarray<AnalyzerIssue> issues;

  const uint32_t drawCount = snapshot.summary.drawCount;
  const uint32_t dispatchCount = snapshot.summary.dispatchCount;
  const uint32_t passCount = snapshot.summary.passCount;
  const uint64_t textureBytes = snapshot.summary.textureBytes;
  const uint64_t bufferBytes = snapshot.summary.bufferBytes;

  uint32_t copyCount = 0;
  uint32_t clearCount = 0;
  for(const AnalyzerEventRow &event : snapshot.events)
  {
    if(event.type == "copy")
      copyCount++;
    else if(event.type == "clear")
      clearCount++;
  }

  uint32_t shaderCount = (uint32_t)snapshot.shaders.count();
  uint32_t textureCount = snapshot.summary.textureCount;

  ResourceId largestTextureId = ResourceId();
  uint32_t largestTextureDim = 0;
  uint64_t largestTextureBytes = 0;
  uint32_t uncompressedLargeCount = 0;

  auto isCompressedFormat = [](const rdcstr &format) {
    rdcstr fmt = format;
    for(char &c : fmt)
      c = (char)tolower(c);
    return fmt.contains("bc") || fmt.contains("astc") || fmt.contains("etc") || fmt.contains("dxt");
  };

  for(const AnalyzerResourceRow &resource : snapshot.resources)
  {
    if(resource.kind != "texture")
      continue;

    uint32_t maxDim = std::max(resource.width, resource.height);
    if(maxDim > largestTextureDim)
    {
      largestTextureDim = maxDim;
      largestTextureId = resource.id;
      largestTextureBytes = resource.bytes;
    }

    if(maxDim >= 2048 && !isCompressedFormat(resource.format))
      uncompressedLargeCount++;
  }

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

  auto largestTexture = [&snapshot]() -> ResourceId {
    for(const AnalyzerResourceRow &resource : snapshot.resources)
    {
      if(resource.kind == "texture")
        return resource.id;
    }
    return ResourceId();
  };

  auto busiestShader = [&snapshot]() -> ResourceId {
    if(snapshot.shaders.empty())
      return ResourceId();
    return snapshot.shaders[0].id;
  };

  if(drawCount > 4000)
  {
    AnalyzerIssue issue;
    issue.code = "PERF_DC_001";
    issue.severity = (drawCount > 8000) ? "critical" : "warning";
    issue.category = "geometry";
    issue.message = Utf8Literal(
        u"Draw \u8c03\u7528\u8fc7\u591a\uff0c\u53ef\u80fd\u5e26\u6765\u8f83\u9ad8\u7684 CPU "
        u"\u63d0\u4ea4\u5f00\u9500\u3002");
    issue.impactScore = (drawCount > 8000) ? 0.95 : 0.80;
    issue.confidence = "high";
    issue.recommendation = Utf8Literal(
        u"\u5408\u6279/\u5b9e\u4f8b\u5316\uff0c\u51cf\u5c11\u4e0d\u5fc5\u8981\u7684\u72b6\u6001"
        u"\u5207\u6362\u3002");
    issue.eventIds.push_back(firstEvent());
    if(lastEvent() != firstEvent())
      issue.eventIds.push_back(lastEvent());

    ResourceId shader = busiestShader();
    if(shader != ResourceId())
      issue.resourceIds.push_back(shader);

    issue.evidence.push_back(MakeEvidence(
        "draw_count", (double)drawCount, "calls",
        u"\u672c\u5e27 draw \u8c03\u7528\u6570\u91cf\u7edf\u8ba1\u3002", true, 4000.0, ">",
        "frame.stats.draws.calls", "frame"));

    issues.push_back(issue);
  }

  if(dispatchCount > 1500)
  {
    AnalyzerIssue issue;
    issue.code = "PERF_DP_001";
    issue.severity = (dispatchCount > 3000) ? "warning" : "info";
    issue.category = "compute";
    issue.message = Utf8Literal(
        u"Dispatch \u8c03\u7528\u8fc7\u591a\u53ef\u80fd\u589e\u52a0\u8c03\u5ea6\u5f00\u9500\u3002");
    issue.impactScore = (dispatchCount > 3000) ? 0.70 : 0.45;
    issue.confidence = "medium";
    issue.recommendation = Utf8Literal(
        u"\u964d\u4f4e dispatch \u9891\u7387\u6216\u5408\u5e76\u53ef\u517c\u5bb9\u7684\u8ba1\u7b97 "
        u"pass\u3002");
    issue.eventIds.push_back(firstEvent());

    issue.evidence.push_back(MakeEvidence(
        "dispatch_count", (double)dispatchCount, "calls",
        u"\u672c\u5e27 dispatch \u8c03\u7528\u6570\u91cf\u7edf\u8ba1\u3002", true, 1500.0, ">",
        "frame.stats.dispatches.calls", "frame"));

    issues.push_back(issue);
  }

  if(textureBytes > (uint64_t)(1024ULL * 1024ULL * 1024ULL))
  {
    AnalyzerIssue issue;
    issue.code = "TEX_SIZE_001";
    issue.severity = "warning";
    issue.category = "bandwidth";
    issue.message = Utf8Literal(u"\u7eb9\u7406\u5185\u5b58\u5360\u7528\u8d85\u8fc7 1GB\u3002");
    issue.impactScore = 0.70;
    issue.confidence = "medium";
    issue.recommendation = Utf8Literal(
        u"\u68c0\u67e5\u8d85\u5927\u7eb9\u7406\uff0c\u786e\u8ba4\u9ad8\u5206\u8fa8\u7387\u8d44\u6e90"
        u"\u662f\u5426\u5fc5\u8981\u3002");
    issue.eventIds.push_back(lastEvent());

    ResourceId texture = largestTexture();
    if(texture != ResourceId())
      issue.resourceIds.push_back(texture);

    issue.evidence.push_back(MakeEvidence(
        "texture_bytes", (double)textureBytes, "bytes",
        u"\u672c\u5e27\u8d44\u6e90\u5217\u8868\u4e2d\u7684\u7eb9\u7406\u603b\u5360\u7528\u3002", true,
        (double)(1024ULL * 1024ULL * 1024ULL), ">", "textures[].byteSize sum", "frame"));

    issues.push_back(issue);
  }

  if(bufferBytes > (uint64_t)(512ULL * 1024ULL * 1024ULL))
  {
    AnalyzerIssue issue;
    issue.code = "BUF_SIZE_001";
    issue.severity = "info";
    issue.category = "bandwidth";
    issue.message = Utf8Literal(u"\u7f13\u51b2\u533a\u5185\u5b58\u5360\u7528\u8f83\u5927\u3002");
    issue.impactScore = 0.55;
    issue.confidence = "medium";
    issue.recommendation = Utf8Literal(
        u"\u68c0\u67e5\u5927\u7f13\u51b2\u533a\uff0c\u8003\u8651\u6d41\u5f0f\u6216\u538b\u7f29\u3002");
    issue.eventIds.push_back(lastEvent());

    issue.evidence.push_back(MakeEvidence(
        "buffer_bytes", (double)bufferBytes, "bytes",
        u"\u672c\u5e27\u8d44\u6e90\u5217\u8868\u4e2d\u7684\u7f13\u51b2\u533a\u603b\u5360\u7528\u3002",
        true, (double)(512ULL * 1024ULL * 1024ULL), ">", "buffers[].length sum", "frame"));

    issues.push_back(issue);
  }

  if(passCount > 200)
  {
    AnalyzerIssue issue;
    issue.code = "STATE_SWITCH_001";
    issue.severity = "info";
    issue.category = "state";
    issue.message = Utf8Literal(
        u"Render Pass \u6570\u91cf\u8f83\u591a\uff0c\u53ef\u80fd\u5b58\u5728\u72b6\u6001\u6296\u52a8"
        u"\u3002");
    issue.impactScore = 0.50;
    issue.confidence = "medium";
    issue.recommendation = Utf8Literal(
        u"\u68c0\u67e5 pass \u8fb9\u754c\uff0c\u5408\u5e76\u53ef\u517c\u5bb9\u7684 pass\u3002");
    issue.eventIds.push_back(lastEvent());

    issue.evidence.push_back(MakeEvidence(
        "pass_count", (double)passCount, "passes",
        u"\u4ece ActionFlags::BeginPass \u6807\u8bb0\u7edf\u8ba1\u3002", true, 200.0, ">",
        "events[BeginPass] count", "frame"));

    issues.push_back(issue);
  }

  if(copyCount > 400)
  {
    AnalyzerIssue issue;
    issue.code = "COPY_001";
    issue.severity = "warning";
    issue.category = "sync";
    issue.message = Utf8Literal(
        u"Copy/Resolve \u8fc7\u591a\u53ef\u80fd\u5f15\u5165\u540c\u6b65\u5f00\u9500\u3002");
    issue.impactScore = 0.65;
    issue.confidence = "medium";
    issue.recommendation = Utf8Literal(
        u"\u51cf\u5c11\u4e34\u65f6\u62f7\u8d1d\u6216\u5408\u5e76\u8d44\u6e90\u8f6c\u6362\u3002");
    issue.eventIds.push_back(firstEvent());

    issue.evidence.push_back(MakeEvidence(
        "copy_events", (double)copyCount, "events",
        u"ActionType::copy \u4e8b\u4ef6\u6570\u91cf\u7edf\u8ba1\u3002", true, 400.0, ">",
        "events[type=copy] count", "frame"));

    issues.push_back(issue);
  }

  if(clearCount > 200)
  {
    AnalyzerIssue issue;
    issue.code = "CLEAR_001";
    issue.severity = "info";
    issue.category = "fill";
    issue.message = Utf8Literal(
        u"Clear \u64cd\u4f5c\u8fc7\u591a\uff0c\u53ef\u80fd\u5b58\u5728\u5197\u4f59\u7684 pass "
        u"\u521d\u59cb\u5316\u3002");
    issue.impactScore = 0.40;
    issue.confidence = "medium";
    issue.recommendation = Utf8Literal(
        u"\u68c0\u67e5\u6e05\u9664\u64cd\u4f5c\uff0c\u907f\u514d\u4e0d\u5fc5\u8981\u7684\u5168\u5c4f"
        u"\u6e05\u9664\u3002");
    issue.eventIds.push_back(firstEvent());

    issue.evidence.push_back(MakeEvidence(
        "clear_events", (double)clearCount, "events",
        u"ActionType::clear \u4e8b\u4ef6\u6570\u91cf\u7edf\u8ba1\u3002", true, 200.0, ">",
        "events[type=clear] count", "frame"));

    issues.push_back(issue);
  }

  if(largestTextureDim > 4096 || largestTextureBytes > (uint64_t)(64ULL * 1024ULL * 1024ULL))
  {
    AnalyzerIssue issue;
    issue.code = "RT_SIZE_001";
    issue.severity = "warning";
    issue.category = "bandwidth";
    issue.message = Utf8Literal(
        u"\u8d85\u5927 Render Target \u53ef\u80fd\u5e26\u6765\u5e26\u5bbd\u538b\u529b\u3002");
    issue.impactScore = 0.60;
    issue.confidence = "medium";
    issue.recommendation = Utf8Literal(
        u"\u8003\u8651\u964d\u4f4e RT \u5206\u8fa8\u7387\u6216\u4f7f\u7528\u66f4\u4f4e\u7cbe\u5ea6"
        u"\u683c\u5f0f\u3002");
    if(lastEvent() != 0)
      issue.eventIds.push_back(lastEvent());

    if(largestTextureId != ResourceId())
      issue.resourceIds.push_back(largestTextureId);

    issue.evidence.push_back(MakeEvidence(
        "largest_rt_dim", (double)largestTextureDim, "px",
        u"\u8d44\u6e90\u5217\u8868\u4e2d\u7684\u6700\u5927\u7eb9\u7406\u5c3a\u5bf8\u3002", true,
        4096.0, ">", "textures[].max(width,height)", "frame"));
    issue.evidence.push_back(MakeEvidence(
        "largest_rt_bytes", (double)largestTextureBytes, "bytes",
        u"\u8d44\u6e90\u5217\u8868\u4e2d\u7684\u6700\u5927\u7eb9\u7406\u5927\u5c0f\u3002", true,
        (double)(64ULL * 1024ULL * 1024ULL), ">", "textures[].byteSize max", "frame"));

    issues.push_back(issue);
  }

  if(uncompressedLargeCount > 20)
  {
    AnalyzerIssue issue;
    issue.code = "TEX_FMT_001";
    issue.severity = "warning";
    issue.category = "bandwidth";
    issue.message = Utf8Literal(u"\u5927\u91cf\u5927\u7eb9\u7406\u672a\u538b\u7f29\u3002");
    issue.impactScore = 0.60;
    issue.confidence = "low";
    issue.recommendation = Utf8Literal(
        u"\u5c3d\u91cf\u4f7f\u7528 BC/ASTC/ETC \u538b\u7f29\u683c\u5f0f\u3002");
    issue.eventIds.push_back(lastEvent());

    issue.evidence.push_back(MakeEvidence(
        "uncompressed_large_textures", (double)uncompressedLargeCount, "textures",
        u">= 2048 \u4e14\u975e\u538b\u7f29\u683c\u5f0f\u7684\u7eb9\u7406\u6570\u91cf\u7edf\u8ba1\u3002",
        true, 20.0, ">", "textures[>=2048 & !compressed] count", "frame"));

    issues.push_back(issue);
  }

  if(shaderCount > 800)
  {
    AnalyzerIssue issue;
    issue.code = "SHADER_001";
    issue.severity = "info";
    issue.category = "shader";
    issue.message = Utf8Literal(
        u"Shader \u6570\u91cf\u8fc7\u591a\u53ef\u80fd\u5bfc\u81f4\u7ba1\u7ebf\u5207\u6362\u9891\u7e41"
        u"\u3002");
    issue.impactScore = 0.45;
    issue.confidence = "medium";
    issue.recommendation =
        Utf8Literal(u"\u51cf\u5c11\u53d8\u4f53\u6216\u5408\u5e76\u6392\u5217\u3002");
    issue.eventIds.push_back(lastEvent());

    ResourceId shader = busiestShader();
    if(shader != ResourceId())
      issue.resourceIds.push_back(shader);

    issue.evidence.push_back(MakeEvidence(
        "shader_count", (double)shaderCount, "shaders",
        u"\u672c\u5e27\u89c2\u5bdf\u5230\u7684\u552f\u4e00 shader \u6570\u91cf\u3002", true, 800.0,
        ">", "unique shaders count", "frame"));

    issues.push_back(issue);
  }

  if(textureCount > 1500)
  {
    AnalyzerIssue issue;
    issue.code = "TEX_COUNT_001";
    issue.severity = "info";
    issue.category = "bandwidth";
    issue.message = Utf8Literal(
        u"\u7eb9\u7406\u6570\u91cf\u8fc7\u591a\u53ef\u80fd\u5f71\u54cd\u9a7b\u7559\u4e0e\u7f13\u5b58"
        u"\u6548\u7387\u3002");
    issue.impactScore = 0.40;
    issue.confidence = "low";
    issue.recommendation = Utf8Literal(
        u"\u68c0\u67e5\u6d41\u5f0f\u7b56\u7565\uff0c\u79fb\u9664\u672a\u4f7f\u7528\u7eb9\u7406\u3002");
    issue.eventIds.push_back(lastEvent());

    issue.evidence.push_back(MakeEvidence(
        "texture_count", (double)textureCount, "textures",
        u"\u672c\u5e27\u8d44\u6e90\u5217\u8868\u4e2d\u7684\u7eb9\u7406\u6570\u91cf\u3002", true,
        1500.0, ">", "textures count", "frame"));

    issues.push_back(issue);
  }

  if(issues.empty())
  {
    AnalyzerIssue issue;
    issue.code = "ANALYZER_BASELINE";
    issue.severity = "info";
    issue.category = "baseline";
    issue.message =
        Utf8Literal(u"\u5f53\u524d\u89c4\u5219\u672a\u53d1\u73b0\u9ad8\u4f18\u5148\u7ea7\u95ee\u9898\u3002");
    issue.impactScore = 0.10;
    issue.confidence = "low";
    issue.recommendation = Utf8Literal(
        u"\u53ef\u6839\u636e\u5de5\u4f5c\u8d1f\u8f7d\u8865\u5145\u89c4\u5219\u4ee5\u83b7\u5f97\u66f4"
        u"\u6df1\u5165\u7684\u8bca\u65ad\u3002");
    issue.eventIds.push_back(lastEvent());
    issue.evidence.push_back(MakeEvidence(
        "baseline", 0.0, "", u"\u672a\u89c2\u5bdf\u5230\u660e\u786e\u8d85\u9608\u95ee\u9898\u3002",
        false, 0.0, "", "rule engine", "frame"));
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
