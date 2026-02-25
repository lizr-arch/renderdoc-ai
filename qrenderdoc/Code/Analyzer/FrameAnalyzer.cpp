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
#include <map>

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

  auto populateFromReplay = [&snapshot](IReplayController *r) {
    for(AnalyzerEventRow &event : snapshot.events)
    {
      if(event.eid == 0)
        continue;
      if(event.type != "draw" && event.type != "dispatch")
        continue;

      r->SetFrameEvent(event.eid, false);
      const PipeState &pipe = r->GetPipelineState();

      event.vs = pipe.GetShader(ShaderStage::Vertex);
      event.ps = pipe.GetShader(ShaderStage::Pixel);
      event.cs = pipe.GetShader(ShaderStage::Compute);
    }
  };

  if(replay != NULL)
    populateFromReplay(replay);
  else
    ctx.Replay().BlockInvoke([&populateFromReplay](IReplayController *r) { populateFromReplay(r); });

  std::map<rdcpair<ResourceId, rdcstr>, size_t> shaderIndices;

  for(const AnalyzerEventRow &event : snapshot.events)
  {
    RegisterShaderUse(ctx, snapshot, shaderIndices, event.vs, "VS", event.eid);
    RegisterShaderUse(ctx, snapshot, shaderIndices, event.ps, "PS", event.eid);
    RegisterShaderUse(ctx, snapshot, shaderIndices, event.cs, "CS", event.eid);
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
                                      ResourceId shaderId, const char *stageLabel, uint32_t eid) const
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
    return;
  }

  AnalyzerShaderRow shader;
  shader.id = shaderId;
  shader.name = ctx.GetResourceName(shaderId);
  shader.stage = stageLabel;
  shader.useCount = 1;
  shader.firstEID = eid;
  shader.lastEID = eid;
  snapshot.shaders.push_back(shader);
  shaderIndices[key] = (size_t)snapshot.shaders.count() - 1;
}
