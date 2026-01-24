#pragma once

#if defined(_WIN32)
#include <windows.h>
#endif

#include <stdint.h>

#include "renderdoc/api/app/renderdoc_app.h"

struct RDocQuickCapture
{
  RDocQuickCapture();

  // Returns true if renderdoc.dll is loaded and the API is available.
  bool Init(const char *explicitDllPath);
  bool IsAvailable() const;

  void SetHotkeyF12();
  void SetCapturePathTemplate(const char *pathTemplate);
  void Trigger();
  void StartFrame(void *device, void *window);
  uint32_t EndFrame(void *device, void *window);

private:
#if defined(_WIN32)
  HMODULE m_module;
#endif
  RENDERDOC_API_1_6_0 *m_api;
};
