#include "rdoc_quick_capture.h"

// Minimal usage sketch for a D3D12 game loop.
// - device: ID3D12Device*
// - window: HWND (or NULL if you don't have a window handle)
void ExampleRDocQuickCapture(bool inTargetUI, bool pressedF12, void *device, void *window)
{
  static RDocQuickCapture rdoc;
  static bool initialized = false;

  if(!initialized)
  {
    initialized = true;
    if(rdoc.Init(NULL))
    {
      rdoc.SetHotkeyF12();
      rdoc.SetCapturePathTemplate("captures/my_game");
    }
  }

  if(!rdoc.IsAvailable())
    return;

  if(inTargetUI && pressedF12)
    rdoc.Trigger();

  // Alternative: explicit frame boundaries.
  // rdoc.StartFrame(device, window);
  // ... render frame ...
  // rdoc.EndFrame(device, window);
}
