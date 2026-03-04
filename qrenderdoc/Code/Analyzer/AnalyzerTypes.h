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

#include "data_types.h"

struct AnalyzerEvidence
{
  rdcstr metric;
  double value = 0.0;
  rdcstr unit;
  rdcstr detail;
  bool hasThreshold = false;
  double threshold = 0.0;
  rdcstr comparison;
  rdcstr source;
  rdcstr scope;
};

struct AnalyzerIssue
{
  rdcstr code;
  rdcstr severity;
  rdcstr category;
  rdcstr message;
  rdcarray<uint32_t> eventIds;
  rdcarray<ResourceId> resourceIds;
  double impactScore = 0.0;
  rdcstr confidence;
  rdcarray<AnalyzerEvidence> evidence;
  rdcstr recommendation;
};

struct AnalyzerEventRow
{
  uint32_t eid = 0;
  rdcstr name;
  rdcstr type;
  uint32_t drawIndex = 0;
  uint32_t passIndex = 0;
  ResourceId vs;
  ResourceId ps;
  ResourceId cs;
  rdcarray<ResourceId> rts;
  ResourceId ds;
};

struct AnalyzerDrawDispatchRow
{
  uint32_t eid = 0;
  rdcstr name;
  rdcstr type;
  uint32_t numIndices = 0;
  uint32_t numInstances = 0;
  rdcfixedarray<uint32_t, 3> dispatchDim = {0, 0, 0};
  rdcfixedarray<uint32_t, 3> dispatchThreads = {0, 0, 0};
  bool indirect = false;
};

struct AnalyzerResourceRow
{
  ResourceId id;
  rdcstr name;
  rdcstr kind;
  uint64_t bytes = 0;
  uint32_t width = 0;
  uint32_t height = 0;
  uint32_t depth = 0;
  uint32_t mips = 0;
  uint32_t arraySize = 0;
  uint32_t samples = 0;
  rdcstr format;
};

struct AnalyzerShaderRow
{
  ResourceId id;
  rdcstr name;
  rdcstr stage;
  uint32_t byteSize = 0;
  uint32_t useCount = 0;
  uint32_t firstEID = 0;
  uint32_t lastEID = 0;
  rdcstr maliHash;
  rdcstr maliGpu;
  bool maliValid = false;
  float maliTotalCycles = 0.0f;
  float maliShortestPath = 0.0f;
  float maliLongestPath = 0.0f;
  float maliFmaCycles = 0.0f;
  float maliCvtCycles = 0.0f;
  float maliSfuCycles = 0.0f;
  float maliLoadStoreCycles = 0.0f;
  float maliTextureCycles = 0.0f;
  float maliVaryingCycles = 0.0f;
  uint32_t maliWorkRegs = 0;
  uint32_t maliUniformRegs = 0;
  uint32_t maliSpillCount = 0;
  float maliCost = 0.0f;
  rdcstr maliBound;
  rdcstr maliError;
};

struct AnalyzerSummary
{
  rdcstr api;
  uint32_t frameNumber = 0;
  uint32_t drawCount = 0;
  uint32_t dispatchCount = 0;
  uint32_t textureCount = 0;
  uint32_t bufferCount = 0;
  uint32_t passCount = 0;
  uint64_t textureBytes = 0;
  uint64_t bufferBytes = 0;
};

struct AnalyzerSnapshot
{
  rdcstr schemaVersion = "analysis.native.qt.v1";
  AnalyzerSummary summary;
  rdcarray<AnalyzerEventRow> events;
  rdcarray<AnalyzerDrawDispatchRow> drawDispatch;
  rdcarray<AnalyzerResourceRow> resources;
  rdcarray<AnalyzerShaderRow> shaders;
  rdcarray<AnalyzerIssue> issues;
};
