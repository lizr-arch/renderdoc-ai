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

AnalyzerSnapshot FrameAnalyzer::Build(ICaptureContext &ctx) const
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
