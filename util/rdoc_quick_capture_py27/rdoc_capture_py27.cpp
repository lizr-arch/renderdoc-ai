// Minimal Python 2.7 extension to trigger RenderDoc captures in-process.
// Built for embedded Python (2.7.x) without ctypes.

#include <Windows.h>

#include "renderdoc_app.h"

#include <Python.h>

static const char *g_lastError = "";
static RENDERDOC_API_1_6_0 *g_rdoc = NULL;
static HMODULE g_rdocModule = NULL;

static void SetLastErrorString(const char *msg)
{
  g_lastError = msg ? msg : "";
}

static PyObject *RDocLoad(PyObject *, PyObject *args)
{
  const char *dllPath = NULL;
  if(!PyArg_ParseTuple(args, "|s", &dllPath))
    return NULL;

  if(!g_rdocModule)
  {
    if(dllPath && dllPath[0] != '\0')
      g_rdocModule = LoadLibraryA(dllPath);
    if(!g_rdocModule)
      g_rdocModule = GetModuleHandleA("renderdoc.dll");
    if(!g_rdocModule)
      g_rdocModule = LoadLibraryA("renderdoc.dll");
  }

  if(!g_rdocModule)
  {
    SetLastErrorString("renderdoc.dll not loaded");
    Py_RETURN_FALSE;
  }

  pRENDERDOC_GetAPI getapi =
      (pRENDERDOC_GetAPI)GetProcAddress(g_rdocModule, "RENDERDOC_GetAPI");
  if(!getapi)
  {
    SetLastErrorString("RENDERDOC_GetAPI not found");
    Py_RETURN_FALSE;
  }

  int ret = getapi(eRENDERDOC_API_Version_1_6_0, (void **)&g_rdoc);
  if(!ret || !g_rdoc)
  {
    SetLastErrorString("RENDERDOC_GetAPI failed");
    Py_RETURN_FALSE;
  }

  SetLastErrorString("");
  Py_RETURN_TRUE;
}

static PyObject *RDocIsAvailable(PyObject *, PyObject *)
{
  if(g_rdoc)
    Py_RETURN_TRUE;
  Py_RETURN_FALSE;
}

static PyObject *RDocSetCapturePath(PyObject *, PyObject *args)
{
  const char *path = NULL;
  if(!PyArg_ParseTuple(args, "s", &path))
    return NULL;
  if(g_rdoc && path && path[0] != '\0')
    g_rdoc->SetCaptureFilePathTemplate(path);
  Py_RETURN_NONE;
}

static PyObject *RDocSetCaptureTitle(PyObject *, PyObject *args)
{
  const char *title = NULL;
  if(!PyArg_ParseTuple(args, "s", &title))
    return NULL;
  if(g_rdoc && title && title[0] != '\0')
    g_rdoc->SetCaptureTitle(title);
  Py_RETURN_NONE;
}

static PyObject *RDocTriggerCapture(PyObject *, PyObject *)
{
  if(g_rdoc)
    g_rdoc->TriggerCapture();
  Py_RETURN_NONE;
}

static PyObject *RDocLastError(PyObject *, PyObject *)
{
  return PyString_FromString(g_lastError ? g_lastError : "");
}

static PyMethodDef RDocMethods[] = {
    {"load", RDocLoad, METH_VARARGS, "Load renderdoc.dll and get API"},
    {"is_available", RDocIsAvailable, METH_NOARGS, "Check API availability"},
    {"set_capture_path", RDocSetCapturePath, METH_VARARGS, "Set capture path template"},
    {"set_capture_title", RDocSetCaptureTitle, METH_VARARGS, "Set capture title"},
    {"trigger_capture", RDocTriggerCapture, METH_NOARGS, "Trigger a capture"},
    {"last_error", RDocLastError, METH_NOARGS, "Return last error string"},
    {NULL, NULL, 0, NULL}};

PyMODINIT_FUNC initrdoc_capture(void)
{
  Py_InitModule("rdoc_capture", RDocMethods);
}
