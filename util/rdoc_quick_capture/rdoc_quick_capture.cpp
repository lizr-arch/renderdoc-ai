#include "rdoc_quick_capture.h"

static const RENDERDOC_Version kRDocVersions[] = {
  eRENDERDOC_API_Version_1_6_0,
  eRENDERDOC_API_Version_1_5_0,
  eRENDERDOC_API_Version_1_4_2,
};

RDocQuickCapture::RDocQuickCapture()
{
#if defined(_WIN32)
  m_module = NULL;
#endif
  m_api = NULL;
}

bool RDocQuickCapture::Init(const char *explicitDllPath)
{
#if !defined(_WIN32)
  (void)explicitDllPath;
  return false;
#else
  if(explicitDllPath && explicitDllPath[0])
    m_module = LoadLibraryA(explicitDllPath);

  if(!m_module)
    m_module = GetModuleHandleA("renderdoc.dll");

  if(!m_module)
    m_module = LoadLibraryA("renderdoc.dll");

  if(!m_module)
    return false;

  pRENDERDOC_GetAPI getapi =
      (pRENDERDOC_GetAPI)GetProcAddress(m_module, "RENDERDOC_GetAPI");
  if(!getapi)
    return false;

  const int versionCount = (int)(sizeof(kRDocVersions) / sizeof(kRDocVersions[0]));
  for(int i = 0; i < versionCount; i++)
  {
    int ret = getapi(kRDocVersions[i], (void **)&m_api);
    if(ret && m_api)
      return true;
  }

  m_api = NULL;
  return false;
#endif
}

bool RDocQuickCapture::IsAvailable() const
{
  return (m_api != NULL);
}

void RDocQuickCapture::SetHotkeyF12()
{
  if(!m_api)
    return;

  RENDERDOC_InputButton keys[1] = { eRENDERDOC_Key_F12 };
  m_api->SetCaptureKeys(keys, 1);
}

void RDocQuickCapture::SetCapturePathTemplate(const char *pathTemplate)
{
  if(!m_api || !pathTemplate)
    return;

  m_api->SetCaptureFilePathTemplate(pathTemplate);
}

void RDocQuickCapture::Trigger()
{
  if(!m_api)
    return;

  m_api->TriggerCapture();
}

void RDocQuickCapture::StartFrame(void *device, void *window)
{
  if(!m_api)
    return;

  m_api->StartFrameCapture(device, window);
}

uint32_t RDocQuickCapture::EndFrame(void *device, void *window)
{
  if(!m_api)
    return 0;

  return m_api->EndFrameCapture(device, window);
}
