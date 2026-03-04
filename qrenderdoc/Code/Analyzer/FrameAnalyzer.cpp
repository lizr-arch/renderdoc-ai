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

#include "FrameAnalyzer.h"
#include <algorithm>
#include <cctype>
#include <map>

namespace
{
ShaderStage StageFromLabel(const rdcstr &stage)
{
  if(stage == "VS")
    return ShaderStage::Vertex;
  if(stage == "PS")
    return ShaderStage::Pixel;
  if(stage == "CS")
    return ShaderStage::Compute;
  return ShaderStage::Count;
}

rdcstr StageLabel(ShaderStage stage)
{
  switch(stage)
  {
    case ShaderStage::Vertex: return "VS";
    case ShaderStage::Hull: return "HS";
    case ShaderStage::Domain: return "DS";
    case ShaderStage::Geometry: return "GS";
    case ShaderStage::Pixel: return "PS";
    case ShaderStage::Compute: return "CS";
    case ShaderStage::Task: return "AS";
    case ShaderStage::Mesh: return "MS";
    default: break;
  }

  return "Unknown";
}

rdcstr ToLower(rdcstr text)
{
  for(char &c : text)
    c = (char)tolower(c);
  return text;
}

int TextureCounterScore(const CounterDescription &desc)
{
  rdcstr text = desc.name + " " + desc.category + " " + desc.description;
  text = ToLower(text);

  int score = 0;
  if(text.contains("sample"))
    score += 4;
  if(text.contains("texel"))
    score += 4;
  if(text.contains("texture"))
    score += 2;
  if(text.contains("sampler"))
    score += 2;
  if(text.contains("fetch"))
    score += 1;
  if(text.contains("read"))
    score += 1;

  return score;
}

double CounterToDouble(const CounterResult &result, const CounterDescription &desc)
{
  switch(desc.resultType)
  {
    case CompType::Float:
    case CompType::UNorm:
    case CompType::SNorm:
    case CompType::UScaled:
    case CompType::SScaled:
    case CompType::Depth:
    case CompType::UNormSRGB:
      return desc.resultByteWidth == 8 ? result.value.d : (double)result.value.f;
    case CompType::UInt:
    case CompType::SInt:
      return desc.resultByteWidth == 8 ? (double)result.value.u64 : (double)result.value.u32;
    default: break;
  }

  return 0.0;
}

uint64_t CounterToUInt64(const CounterResult &result, const CounterDescription &desc)
{
  if(desc.resultByteWidth == 8)
    return result.value.u64;
  return (uint64_t)result.value.u32;
}

ShaderEntryPoint PickEntryPointForStage(const rdcarray<ShaderEntryPoint> &entries,
                                        ShaderStage preferredStage)
{
  if(entries.empty())
    return ShaderEntryPoint();

  if(preferredStage != ShaderStage::Count)
  {
    for(const ShaderEntryPoint &entry : entries)
    {
      if(entry.stage == preferredStage)
        return entry;
    }
  }

  return entries[0];
}

uint32_t ComputeShaderByteSize(IReplayController *replay, ResourceId shaderId, ShaderStage stage,
                               ResourceId pipelineId)
{
  if(replay == NULL || shaderId == ResourceId())
    return 0;

  rdcarray<ShaderEntryPoint> entries = replay->GetShaderEntryPoints(shaderId);
  if(entries.empty())
    return 0;

  ShaderEntryPoint selected = PickEntryPointForStage(entries, stage);
  const ShaderReflection *refl = replay->GetShader(ResourceId(), shaderId, selected);
  if(!refl && pipelineId != ResourceId())
    refl = replay->GetShader(pipelineId, shaderId, selected);

  if(!refl || refl->rawBytes.count() == 0)
    return 0;

  return (uint32_t)refl->rawBytes.count();
}
}

AnalyzerSnapshot FrameAnalyzer::Build(ICaptureContext &ctx, IReplayController *replay) const
{
  AnalyzerSnapshot snapshot;

  const FrameDescription &frame = ctx.FrameInfo();

  snapshot.summary.api = APIName(ctx.APIProps().pipelineType);
  snapshot.summary.frameNumber = frame.frameNumber;
  snapshot.summary.drawCount = frame.stats.draws.calls;
  snapshot.summary.dispatchCount = frame.stats.dispatches.calls;

  const rdcarray<TextureDescription> &textures = ctx.GetTextures();
  const rdcarray<BufferDescription> &buffers = ctx.GetBuffers();

  snapshot.summary.textureCount = textures.count();
  snapshot.summary.bufferCount = buffers.count();

  for(const TextureDescription &texture : textures)
    snapshot.summary.textureBytes += texture.byteSize;

  for(const BufferDescription &buffer : buffers)
    snapshot.summary.bufferBytes += buffer.length;

  uint32_t passIndex = 0;
  FlattenActions(ctx.CurRootActions(), snapshot.events, passIndex);
  snapshot.summary.passCount = passIndex;

  PopulateDrawDispatch(ctx, snapshot);
  PopulateStateThrash(ctx, snapshot);
  PopulatePipelineBandwidth(ctx, snapshot, replay);
  PopulateGpuCounters(ctx, snapshot, replay);
  PopulateResources(ctx, snapshot);
  PopulateShaderUsage(ctx, snapshot, replay);

  return snapshot;
}

void FrameAnalyzer::FlattenActions(const rdcarray<ActionDescription> &actions,
                                   rdcarray<AnalyzerEventRow> &rows, uint32_t &passIndex) const
{
  for(const ActionDescription &action : actions)
  {
    if(action.flags & ActionFlags::BeginPass)
      passIndex++;

    AnalyzerEventRow row;
    row.eid = action.eventId;
    row.name = ActionName(action);
    row.type = ActionType(action);
    row.drawIndex = action.actionId;
    row.passIndex = passIndex;

    if(action.flags & ActionFlags::Drawcall)
    {
      for(int i = 0; i < action.outputs.count(); i++)
      {
        if(action.outputs[i] != ResourceId())
          row.rts.push_back(action.outputs[i]);
      }

      row.ds = action.depthOut;
    }

    rows.push_back(row);

    if(!action.children.empty())
      FlattenActions(action.children, rows, passIndex);
  }
}

void FrameAnalyzer::FlattenDrawDispatch(const rdcarray<ActionDescription> &actions,
                                        rdcarray<AnalyzerDrawDispatchRow> &rows) const
{
  for(const ActionDescription &action : actions)
  {
    if(action.flags & (ActionFlags::Drawcall | ActionFlags::Dispatch))
    {
      AnalyzerDrawDispatchRow row;
      row.eid = action.eventId;
      row.name = ActionName(action);
      row.type = ActionType(action);
      row.numIndices = action.numIndices;
      row.numInstances = action.numInstances;
      row.dispatchDim = action.dispatchDimension;
      row.dispatchThreads = action.dispatchThreadsDimension;
      row.indirect = !!(action.flags & ActionFlags::Indirect);
      rows.push_back(row);
    }

    if(!action.children.empty())
      FlattenDrawDispatch(action.children, rows);
  }
}

void FrameAnalyzer::PopulateDrawDispatch(ICaptureContext &ctx, AnalyzerSnapshot &snapshot) const
{
  FlattenDrawDispatch(ctx.CurRootActions(), snapshot.drawDispatch);

  std::sort(snapshot.drawDispatch.begin(), snapshot.drawDispatch.end(),
            [](const AnalyzerDrawDispatchRow &a, const AnalyzerDrawDispatchRow &b) {
              if(a.eid != b.eid)
                return a.eid < b.eid;
              return a.name < b.name;
            });
}

void FrameAnalyzer::PopulateStateThrash(ICaptureContext &ctx, AnalyzerSnapshot &snapshot) const
{
  const FrameStatistics &stats = ctx.FrameInfo().stats;

  uint32_t fallbackEID = 0;
  for(const AnalyzerEventRow &event : snapshot.events)
  {
    if(event.type == "draw" || event.type == "dispatch")
    {
      fallbackEID = event.eid;
      break;
    }
  }

  const ShaderStage stages[] = {ShaderStage::Vertex, ShaderStage::Hull,    ShaderStage::Domain,
                                ShaderStage::Geometry, ShaderStage::Pixel, ShaderStage::Compute};

  for(ShaderStage stage : stages)
  {
    int idx = (int)stage;
    AnalyzerStateThrashRow row;
    row.stage = StageLabel(stage);
    row.available = stats.recorded;
    row.fallbackEID = fallbackEID;

    if(stats.recorded && idx >= 0 && idx < stats.shaders.count() &&
       idx < stats.resources.count() && idx < stats.samplers.count() &&
       idx < stats.constants.count())
    {
      row.shaderChanges = stats.shaders[idx].sets;
      row.redundantShaderBinds = stats.shaders[idx].redundants;
      row.resourceBinds = stats.resources[idx].sets;
      row.samplerBinds = stats.samplers[idx].sets;
      row.constantBinds = stats.constants[idx].sets;
    }

    snapshot.stateThrash.push_back(row);
  }
}

void FrameAnalyzer::PopulatePipelineBandwidth(ICaptureContext &ctx, AnalyzerSnapshot &snapshot,
                                              IReplayController *replay) const
{
  if(snapshot.events.empty())
    return;

  std::map<ResourceId, uint32_t> textureSamples;
  const rdcarray<TextureDescription> &textures = ctx.GetTextures();
  for(const TextureDescription &texture : textures)
    textureSamples[texture.resourceId] = std::max(1U, texture.msSamp);

  auto populateFromReplay = [&snapshot, &textureSamples](IReplayController *r) {
    for(const AnalyzerEventRow &event : snapshot.events)
    {
      if(event.eid == 0 || event.type != "draw")
        continue;

      r->SetFrameEvent(event.eid, false);
      const PipeState &pipe = r->GetPipelineState();

      AnalyzerPipelineBandwidthRow row;
      row.eid = event.eid;
      row.name = event.name;

      rdcarray<Descriptor> outputs = pipe.GetOutputTargets();
      for(const Descriptor &rt : outputs)
      {
        if(rt.resource != ResourceId())
          row.rtCount++;
      }

      rdcarray<ColorBlend> blends = pipe.GetColorBlends();
      for(const ColorBlend &blend : blends)
      {
        if(blend.enabled || blend.logicOperationEnabled)
        {
          row.blendEnabled = true;
          break;
        }
      }

      const D3D11Pipe::State *d3d11 = r->GetD3D11PipelineState();
      const D3D12Pipe::State *d3d12 = r->GetD3D12PipelineState();
      const GLPipe::State *gl = r->GetGLPipelineState();
      const VKPipe::State *vk = r->GetVulkanPipelineState();

      if(d3d11)
        row.depthWrite = d3d11->outputMerger.depthStencilState.depthWrites;
      else if(d3d12)
        row.depthWrite = d3d12->outputMerger.depthStencilState.depthWrites;
      else if(gl)
        row.depthWrite = gl->depthState.depthWrites;
      else if(vk)
        row.depthWrite = vk->depthStencil.depthWriteEnable;

      auto updateSamples = [&row, &textureSamples](ResourceId id) {
        if(id == ResourceId())
          return;
        auto it = textureSamples.find(id);
        if(it != textureSamples.end())
          row.samples = std::max(row.samples, it->second);
      };

      for(const Descriptor &rt : outputs)
        updateSamples(rt.resource);

      updateSamples(pipe.GetDepthTarget().resource);

      if(d3d12 && d3d12->outputMerger.multiSampleCount > 0)
        row.samples = std::max(row.samples, d3d12->outputMerger.multiSampleCount);
      if(vk && vk->multisample.rasterSamples > 0)
        row.samples = std::max(row.samples, vk->multisample.rasterSamples);

      snapshot.pipelineBandwidth.push_back(row);
    }
  };

  if(replay != NULL)
    populateFromReplay(replay);
  else
    ctx.Replay().BlockInvoke([&populateFromReplay](IReplayController *r) { populateFromReplay(r); });

  std::sort(snapshot.pipelineBandwidth.begin(), snapshot.pipelineBandwidth.end(),
            [](const AnalyzerPipelineBandwidthRow &a, const AnalyzerPipelineBandwidthRow &b) {
              if(a.eid != b.eid)
                return a.eid < b.eid;
              return a.name < b.name;
            });
}

void FrameAnalyzer::PopulateGpuCounters(ICaptureContext &ctx, AnalyzerSnapshot &snapshot,
                                        IReplayController *replay) const
{
  if(snapshot.events.empty())
    return;

  std::map<uint32_t, rdcstr> eventNames;
  for(const AnalyzerEventRow &event : snapshot.events)
  {
    if(event.eid != 0)
      eventNames[event.eid] = event.name;
  }

  auto populateFromReplay = [&snapshot, &eventNames](IReplayController *r) {
    rdcarray<GPUCounter> available = r->EnumerateCounters();
    if(available.empty())
      return;

    auto hasCounter = [&available](GPUCounter counter) {
      return std::find(available.begin(), available.end(), counter) != available.end();
    };

    rdcarray<GPUCounter> counters;
    std::map<GPUCounter, CounterDescription> descriptions;

    auto addCounter = [&counters, &descriptions, r, &hasCounter](GPUCounter counter) {
      if(!hasCounter(counter))
        return false;
      counters.push_back(counter);
      descriptions[counter] = r->DescribeCounter(counter);
      return true;
    };

    addCounter(GPUCounter::EventGPUDuration);
    addCounter(GPUCounter::VSInvocations);
    addCounter(GPUCounter::PSInvocations);
    addCounter(GPUCounter::CSInvocations);

    GPUCounter textureCounter = GPUCounter::Count;
    CounterDescription textureDesc;
    int textureScore = 0;
    for(GPUCounter counter : available)
    {
      CounterDescription desc = r->DescribeCounter(counter);
      int score = TextureCounterScore(desc);
      if(score > textureScore)
      {
        textureScore = score;
        textureCounter = counter;
        textureDesc = desc;
      }
    }

    if(textureScore > 0)
    {
      counters.push_back(textureCounter);
      descriptions[textureCounter] = textureDesc;
    }

    if(counters.empty())
      return;

    rdcarray<CounterResult> results = r->FetchCounters(counters);
    if(results.empty())
      return;

    std::map<uint32_t, size_t> rowIndex;
    auto ensureRow = [&snapshot, &rowIndex, &eventNames](uint32_t eid) -> AnalyzerGpuCounterRow & {
      auto it = rowIndex.find(eid);
      if(it != rowIndex.end())
        return snapshot.gpuCounters[it->second];

      AnalyzerGpuCounterRow row;
      row.eid = eid;
      auto nameIt = eventNames.find(eid);
      if(nameIt != eventNames.end())
        row.name = nameIt->second;
      else
        row.name = "Event";
      snapshot.gpuCounters.push_back(row);
      rowIndex[eid] = (size_t)snapshot.gpuCounters.count() - 1;
      return snapshot.gpuCounters.back();
    };

    for(const CounterResult &result : results)
    {
      if(result.eventId == 0)
        continue;

      AnalyzerGpuCounterRow &row = ensureRow(result.eventId);
      const CounterDescription &desc = descriptions[result.counter];

      if(result.counter == GPUCounter::EventGPUDuration)
      {
        double value = CounterToDouble(result, desc);
        if(desc.unit == CounterUnit::Seconds)
          value *= 1000.0;
        row.gpuTimeMs = value;
        row.gpuTimeValid = true;
      }
      else if(result.counter == GPUCounter::VSInvocations)
      {
        row.vsInvocations = CounterToUInt64(result, desc);
        row.vsValid = true;
      }
      else if(result.counter == GPUCounter::PSInvocations)
      {
        row.psInvocations = CounterToUInt64(result, desc);
        row.psValid = true;
      }
      else if(result.counter == GPUCounter::CSInvocations)
      {
        row.csInvocations = CounterToUInt64(result, desc);
        row.csValid = true;
      }
      else if(textureScore > 0 && result.counter == textureCounter)
      {
        row.textureSamples = CounterToDouble(result, desc);
        row.textureValid = true;
        row.textureCounterName = desc.name;
      }
    }
  };

  if(replay != NULL)
    populateFromReplay(replay);
  else
    ctx.Replay().BlockInvoke([&populateFromReplay](IReplayController *r) { populateFromReplay(r); });

  std::sort(snapshot.gpuCounters.begin(), snapshot.gpuCounters.end(),
            [](const AnalyzerGpuCounterRow &a, const AnalyzerGpuCounterRow &b) {
              if(a.eid != b.eid)
                return a.eid < b.eid;
              return a.name < b.name;
            });
}

rdcstr FrameAnalyzer::ActionName(const ActionDescription &action) const
{
  if(!action.customName.empty())
    return action.customName;

  if(action.flags & ActionFlags::Drawcall)
    return "Draw";

  if(action.flags & ActionFlags::Dispatch)
    return "Dispatch";

  if(action.flags & ActionFlags::Clear)
    return "Clear";

  if(action.flags & ActionFlags::Copy)
    return "Copy";

  if(action.flags & ActionFlags::PushMarker)
    return "PushMarker";

  if(action.flags & ActionFlags::PopMarker)
    return "PopMarker";

  return "Action";
}

rdcstr FrameAnalyzer::ActionType(const ActionDescription &action) const
{
  if(action.flags & ActionFlags::Drawcall)
    return "draw";

  if(action.flags & ActionFlags::Dispatch)
    return "dispatch";

  if(action.flags & ActionFlags::Clear)
    return "clear";

  if(action.flags & ActionFlags::Copy)
    return "copy";

  if(action.flags & ActionFlags::Present)
    return "present";

  if(action.flags & ActionFlags::PushMarker)
    return "marker";

  return "other";
}

rdcstr FrameAnalyzer::APIName(GraphicsAPI api) const
{
  if(api == GraphicsAPI::D3D11)
    return "D3D11";

  if(api == GraphicsAPI::D3D12)
    return "D3D12";

  if(api == GraphicsAPI::OpenGL)
    return "OpenGL";

  if(api == GraphicsAPI::Vulkan)
    return "Vulkan";

  return "Unknown";
}

void FrameAnalyzer::PopulateResources(ICaptureContext &ctx, AnalyzerSnapshot &snapshot) const
{
  const rdcarray<TextureDescription> &textures = ctx.GetTextures();
  for(const TextureDescription &texture : textures)
  {
    AnalyzerResourceRow row;
    row.id = texture.resourceId;
    row.name = ctx.GetResourceName(texture.resourceId);
    row.kind = "texture";
    row.bytes = texture.byteSize;
    row.width = texture.width;
    row.height = texture.height;
    row.depth = texture.depth;
    row.mips = texture.mips;
    row.arraySize = texture.arraysize;
    row.samples = texture.msSamp;
    row.format = texture.format.Name();
    snapshot.resources.push_back(row);
  }

  const rdcarray<BufferDescription> &buffers = ctx.GetBuffers();
  for(const BufferDescription &buffer : buffers)
  {
    AnalyzerResourceRow row;
    row.id = buffer.resourceId;
    row.name = ctx.GetResourceName(buffer.resourceId);
    row.kind = "buffer";
    row.bytes = buffer.length;
    row.width = (uint32_t)std::min(buffer.length, (uint64_t)0xffffffffULL);
    snapshot.resources.push_back(row);
  }

  std::sort(snapshot.resources.begin(), snapshot.resources.end(),
            [](const AnalyzerResourceRow &a, const AnalyzerResourceRow &b) {
              if(a.bytes != b.bytes)
                return a.bytes > b.bytes;
              return a.id < b.id;
            });
}

void FrameAnalyzer::PopulateShaderUsage(ICaptureContext &ctx, AnalyzerSnapshot &snapshot,
                                        IReplayController *replay) const
{
  if(snapshot.events.empty())
    return;

  rdcarray<ResourceId> graphicsPipelines;
  rdcarray<ResourceId> computePipelines;
  graphicsPipelines.resize(snapshot.events.count());
  computePipelines.resize(snapshot.events.count());

  auto populateFromReplay = [&snapshot, &graphicsPipelines,
                             &computePipelines](IReplayController *r) {
    for(int i = 0; i < snapshot.events.count(); i++)
    {
      AnalyzerEventRow &event = snapshot.events[i];
      graphicsPipelines[i] = ResourceId();
      computePipelines[i] = ResourceId();

      if(event.eid == 0)
        continue;
      if(event.type != "draw" && event.type != "dispatch")
        continue;

      r->SetFrameEvent(event.eid, false);
      const PipeState &pipe = r->GetPipelineState();

      event.vs = pipe.GetShader(ShaderStage::Vertex);
      event.ps = pipe.GetShader(ShaderStage::Pixel);
      event.cs = pipe.GetShader(ShaderStage::Compute);
      graphicsPipelines[i] = pipe.GetGraphicsPipelineObject();
      computePipelines[i] = pipe.GetComputePipelineObject();
    }
  };

  if(replay != NULL)
    populateFromReplay(replay);
  else
    ctx.Replay().BlockInvoke(
        [&populateFromReplay](IReplayController *r) { populateFromReplay(r); });

  std::map<rdcpair<ResourceId, rdcstr>, size_t> shaderIndices;

  for(int i = 0; i < snapshot.events.count(); i++)
  {
    const AnalyzerEventRow &event = snapshot.events[i];
    ResourceId graphicsPipeline =
        i < graphicsPipelines.count() ? graphicsPipelines[i] : ResourceId();
    ResourceId computePipeline =
        i < computePipelines.count() ? computePipelines[i] : ResourceId();

    RegisterShaderUse(ctx, snapshot, shaderIndices, replay, event.vs, ShaderStage::Vertex,
                      graphicsPipeline, "VS", event.eid);
    RegisterShaderUse(ctx, snapshot, shaderIndices, replay, event.ps, ShaderStage::Pixel,
                      graphicsPipeline, "PS", event.eid);
    RegisterShaderUse(ctx, snapshot, shaderIndices, replay, event.cs, ShaderStage::Compute,
                      computePipeline, "CS", event.eid);
  }

  std::sort(snapshot.shaders.begin(), snapshot.shaders.end(),
            [](const AnalyzerShaderRow &a, const AnalyzerShaderRow &b) {
              if(a.useCount != b.useCount)
                return a.useCount > b.useCount;
              if(a.firstEID != b.firstEID)
                return a.firstEID < b.firstEID;
              return a.id < b.id;
            });
}

void FrameAnalyzer::RegisterShaderUse(ICaptureContext &ctx, AnalyzerSnapshot &snapshot,
                                      std::map<rdcpair<ResourceId, rdcstr>, size_t> &shaderIndices,
                                      IReplayController *replay, ResourceId shaderId,
                                      ShaderStage stage, ResourceId pipelineId,
                                      const char *stageLabel, uint32_t eid) const
{
  if(shaderId == ResourceId())
    return;

  rdcpair<ResourceId, rdcstr> key(shaderId, stageLabel);
  auto it = shaderIndices.find(key);
  if(it != shaderIndices.end())
  {
    AnalyzerShaderRow &shader = snapshot.shaders[it->second];
    shader.useCount++;
    if(shader.firstEID == 0 || eid < shader.firstEID)
      shader.firstEID = eid;
    if(eid > shader.lastEID)
      shader.lastEID = eid;
    if(shader.byteSize == 0 && replay != NULL)
    {
      ShaderStage resolvedStage = stage != ShaderStage::Count
                                      ? stage
                                      : StageFromLabel(rdcstr(stageLabel));
      shader.byteSize = ComputeShaderByteSize(replay, shaderId, resolvedStage, pipelineId);
    }
    return;
  }

  AnalyzerShaderRow shader;
  shader.id = shaderId;
  shader.name = ctx.GetResourceName(shaderId);
  shader.stage = stageLabel;
  shader.useCount = 1;
  shader.firstEID = eid;
  shader.lastEID = eid;
  {
    ShaderStage resolvedStage = stage != ShaderStage::Count
                                    ? stage
                                    : StageFromLabel(rdcstr(stageLabel));
    shader.byteSize = ComputeShaderByteSize(replay, shaderId, resolvedStage, pipelineId);
  }
  snapshot.shaders.push_back(shader);
  shaderIndices[key] = (size_t)snapshot.shaders.count() - 1;
}
