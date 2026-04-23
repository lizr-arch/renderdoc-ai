/******************************************************************************
 * The MIT License (MIT)
 *
 * Copyright (c) 2016-2026 Baldur Karlsson
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

#include "LiveCapture.h"
#include <QDesktopServices>
#include <QDir>
#include <QFileInfo>
#include <QHostInfo>
#include <QMenu>
#include <QMetaProperty>
#include <QMouseEvent>
#include <QPainter>
#include <QProcess>
#include <QScrollBar>
#include <QStyledItemDelegate>
#include <QToolBar>
#include <QToolButton>
#include "Code/QRDUtils.h"
#include "Code/Resources.h"
#include "Code/qprocessinfo.h"
#include "Widgets/Extended/RDLabel.h"
#include "Windows/MainWindow.h"
#include "toolwindowmanager/ToolWindowManager.h"
#include "ui_LiveCapture.h"

static const int PIDRole = Qt::UserRole + 1;
static const int IdentRole = Qt::UserRole + 2;
static const int CapPtrRole = Qt::UserRole + 3;

class NameEditOnlyDelegate : public QStyledItemDelegate
{
public:
  LiveCapture *live;
  NameEditOnlyDelegate(LiveCapture *l) : live(l) {}
  void setEditorData(QWidget *editor, const QModelIndex &index) const override
  {
    QByteArray n = editor->metaObject()->userProperty().name();
    QListWidgetItem *item = live->ui->captures->item(index.row());

    if(!n.isEmpty() && item)
    {
      LiveCapture::Capture *cap = live->GetCapture(item);
      if(cap)
        editor->setProperty(n, cap->name);
    }
  }

  void setModelData(QWidget *editor, QAbstractItemModel *model, const QModelIndex &index) const override
  {
    QByteArray n = editor->metaObject()->userProperty().name();
    QListWidgetItem *item = live->ui->captures->item(index.row());

    if(!n.isEmpty() && item)
    {
      LiveCapture::Capture *cap = live->GetCapture(item);
      if(cap)
      {
        cap->name = editor->property(n).toString();
        item->setText(live->MakeText(cap));
      }
    }
  }
};

LiveCapture::LiveCapture(ICaptureContext &ctx, const QString &hostname, const QString &friendlyname,
                         uint32_t ident, MainWindow *main, QWidget *parent)
    : QFrame(parent),
      ui(new Ui::LiveCapture),
      m_Ctx(ctx),
      m_Hostname(hostname),
      m_HostFriendlyname(friendlyname),
      m_RemoteIdent(ident),
      m_Main(main)
{
  ui->setupUi(this);

  m_Disconnect.release();

  QObject::connect(&childUpdateTimer, &QTimer::timeout, this, &LiveCapture::childUpdate);
  childUpdateTimer.setSingleShot(false);
  childUpdateTimer.setInterval(1000);
  childUpdateTimer.start();

  QObject::connect(&countdownTimer, &QTimer::timeout, this, &LiveCapture::captureCountdownTick);
  countdownTimer.setSingleShot(true);
  countdownTimer.setInterval(1000);

  childUpdate();

  ui->previewSplit->setCollapsible(1, true);
  ui->previewSplit->setSizes({1, 0});

  QObject::connect(ui->preview, &RDLabel::clicked, this, &LiveCapture::preview_mouseClick);
  QObject::connect(ui->preview, &RDLabel::mouseMoved, this, &LiveCapture::preview_mouseMove);

  ui->preview->setMouseTracking(true);

  setTitle(tr("Connecting"));
  ui->connectionStatus->setText(tr("Connecting"));
  ui->connectionIcon->setPixmap(Pixmaps::hourglass(ui->connectionIcon));

  ui->apiIcon->setVisible(false);

  ui->triggerDelayedCapture->setEnabled(false);
  ui->triggerImmediateCapture->setEnabled(false);
  ui->queueCap->setEnabled(false);
  ui->cycleActiveWindow->setEnabled(false);
  ui->getLatestCapture->setEnabled(false);

  ui->target->setText(QString());

  ui->progressLabel->setVisible(false);
  ui->progressBar->setVisible(false);
  updateCaptureControls();
  updateLatestCaptureUI();

  ui->captures->setItemDelegate(new NameEditOnlyDelegate(this));

  ui->captures->verticalScrollBar()->setSingleStep(20);

  {
    QToolBar *bottomTools = new QToolBar(this);

    QWidget *rightAlign = new QWidget(this);
    rightAlign->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
    bottomTools->addWidget(rightAlign);

    previewToggle = new QAction(tr("Preview"), this);
    previewToggle->setCheckable(true);

    bottomTools->addAction(previewToggle);

    QMenu *openMenu = new QMenu(tr("&Open in..."), this);
    QAction *thisAction = new QAction(tr("This instance"), this);
    newWindowAction = new QAction(tr("New instance"), this);

    openMenu->addAction(thisAction);
    openMenu->addAction(newWindowAction);

    openButton = new QToolButton(this);
    openButton->setText(tr("Open"));
    openButton->setPopupMode(QToolButton::MenuButtonPopup);
    openButton->setMenu(openMenu);

    bottomTools->addWidget(openButton);

    saveAction = new QAction(tr("Save"), this);
    deleteAction = new QAction(tr("Delete"), this);

    bottomTools->addAction(saveAction);
    bottomTools->addAction(deleteAction);

    QObject::connect(previewToggle, &QAction::toggled, this, &LiveCapture::previewToggle_toggled);
    QObject::connect(openButton, &QToolButton::clicked, this, &LiveCapture::openCapture_triggered);
    QObject::connect(thisAction, &QAction::triggered, this, &LiveCapture::openCapture_triggered);
    QObject::connect(newWindowAction, &QAction::triggered, this,
                     &LiveCapture::openNewWindow_triggered);
    QObject::connect(saveAction, &QAction::triggered, this, &LiveCapture::saveCapture_triggered);
    QObject::connect(deleteAction, &QAction::triggered, this, &LiveCapture::deleteCapture_triggered);

    QObject::connect(ui->captures, &RDListWidget::keyPress, this, &LiveCapture::captures_keyPress);

    ui->mainLayout->addWidget(bottomTools);
  }
}

LiveCapture::~LiveCapture()
{
  m_Main->LiveCaptureClosed(this);

  cleanItems();
  killThread();

  delete ui;
}

void LiveCapture::QueueCapture(int frameNumber, int numFrames)
{
  m_QueueCaptureFrameNum = frameNumber;
  m_CaptureNumFrames = numFrames;
  m_QueueCapture.release();
}

void LiveCapture::showEvent(QShowEvent *event)
{
  if(!m_ConnectThread)
  {
    m_ConnectThread = new LambdaThread([this]() { this->connectionThreadEntry(); });
    m_ConnectThread->start();
  }

  on_captures_itemSelectionChanged();
}

void LiveCapture::on_captures_mouseClicked(QMouseEvent *e)
{
  if(e->buttons() & Qt::RightButton && !ui->captures->selectedItems().empty())
  {
    QMenu contextMenu(this);

    QMenu contextOpenMenu(tr("&Open in..."), this);
    QAction thisAction(tr("This instance"), this);
    QAction newAction(tr("New instance"), this);

    contextOpenMenu.addAction(&thisAction);
    contextOpenMenu.addAction(&newAction);

    QAction contextRenameAction(tr("&Rename capture"), this);
    QAction contextSaveAction(tr("&Save"), this);
    QAction contextDeleteAction(tr("&Delete"), this);

    contextMenu.addAction(contextOpenMenu.menuAction());
    contextMenu.addAction(&contextRenameAction);
    contextMenu.addAction(&contextSaveAction);
    contextMenu.addAction(&contextDeleteAction);

    if(ui->captures->selectedItems().size() == 1)
    {
      newAction.setEnabled(GetCapture(ui->captures->selectedItems()[0])->local);
    }
    else
    {
      contextOpenMenu.setEnabled(false);
      contextRenameAction.setEnabled(false);
      contextSaveAction.setText(tr("&Save All"));
      contextDeleteAction.setText(tr("&Delete All"));
    }

    QObject::connect(&thisAction, &QAction::triggered, this, &LiveCapture::openCapture_triggered);
    QObject::connect(&newAction, &QAction::triggered, this, &LiveCapture::openNewWindow_triggered);
    QObject::connect(&contextRenameAction, &QAction::triggered,
                     [this]() { ui->captures->editItem(ui->captures->selectedItems()[0]); });
    QObject::connect(&contextSaveAction, &QAction::triggered, this,
                     &LiveCapture::saveCapture_triggered);
    QObject::connect(&contextDeleteAction, &QAction::triggered, this,
                     &LiveCapture::deleteCapture_triggered);

    m_ContextMenu = &contextMenu;
    RDDialog::show(&contextMenu, QCursor::pos());
    m_ContextMenu = NULL;
  }
}

void LiveCapture::on_captures_itemActivated(QListWidgetItem *item)
{
  openCapture_triggered();
}

void LiveCapture::on_childProcesses_itemActivated(QListWidgetItem *item)
{
  QList<QListWidgetItem *> sel = ui->childProcesses->selectedItems();
  if(sel.count() == 1)
  {
    uint32_t ident = sel[0]->data(IdentRole).toUInt();
    if(ident > 0)
    {
      LiveCapture *live =
          new LiveCapture(m_Ctx, m_Hostname, m_HostFriendlyname, ident, m_Main, m_Main);
      m_Main->ShowLiveCapture(live);
    }
  }
}

void LiveCapture::on_queueCap_clicked()
{
  m_CaptureRequested = true;
  m_LatestCaptureCopyFailed = false;
  m_LatestCaptureFailure = QString();
  m_CaptureNumFrames = (int)ui->numFrames->value();
  m_QueueCaptureFrameNum = (int)ui->captureFrame->value();
  m_QueueCapture.release();
  updateLatestCaptureUI();
}

void LiveCapture::on_triggerImmediateCapture_clicked()
{
  m_CaptureRequested = true;
  m_LatestCaptureCopyFailed = false;
  m_LatestCaptureFailure = QString();
  m_CaptureNumFrames = (int)ui->numFrames->value();
  m_TriggerCapture.release();
  updateLatestCaptureUI();
}

void LiveCapture::on_cycleActiveWindow_clicked()
{
  m_CycleWindow.release();
}

void LiveCapture::on_triggerDelayedCapture_clicked()
{
  if(ui->captureDelay->value() == 0.0)
  {
    on_triggerImmediateCapture_clicked();
  }
  else
  {
    m_CaptureRequested = true;
    m_LatestCaptureCopyFailed = false;
    m_LatestCaptureFailure = QString();
    m_CaptureCounter = (int)ui->captureDelay->value();
    countdownTimer.start();
    ui->triggerDelayedCapture->setEnabled(false);
    ui->triggerDelayedCapture->setText(tr("Triggering in %1s").arg(m_CaptureCounter));
    updateLatestCaptureUI();
  }
}

void LiveCapture::on_getLatestCapture_clicked()
{
  QListWidgetItem *item = NULL;
  Capture *cap = FindCapture(m_LatestCaptureID, &item);

  if(!cap)
  {
    m_LatestCaptureFailure = tr("No capture has been reported by this target yet.");
    RDDialog::information(this, tr("No capture available"),
                          tr("No capture has been reported by this target yet."));
    updateLatestCaptureUI();
    return;
  }

  if(item)
    ui->captures->setCurrentItem(item);

  if(cap->local)
  {
    if(QFileInfo::exists(cap->path))
    {
      m_LatestCaptureFailure = QString();
      RevealFilenameInExternalFileBrowser(cap->path);
    }
    else
    {
      m_LatestCaptureFailure =
          tr("The latest capture file can't be found at:\n%1").arg(QDir::toNativeSeparators(cap->path));
      RDDialog::critical(this, tr("Cannot reveal latest capture"),
                         tr("The latest capture file can't be found at:\n%1")
                             .arg(QDir::toNativeSeparators(cap->path)));
    }

    updateLatestCaptureUI();
    return;
  }

  if(m_LatestCaptureCopying)
  {
    m_LatestCaptureFailure = QString();
    RDDialog::information(this, tr("Copy in progress"),
                          tr("The latest capture is already being copied locally."));
    return;
  }

  const bool replayContextActive = m_Ctx.Replay().CurrentRemote().Hostname() == rdcstr(m_Hostname);
  const QString hostName = !m_HostFriendlyname.isEmpty()
                               ? m_HostFriendlyname
                               : (!m_Hostname.isEmpty() ? m_Hostname : tr("this host"));

  if(!m_LiveConnection && !replayContextActive)
  {
    m_LatestCaptureFailure =
        tr("Reconnect to %1 or switch to a replay context on that host to copy the latest capture.")
            .arg(hostName);
    RDDialog::critical(
        this, tr("Cannot copy latest capture"),
        tr("The latest capture is only available on remote host %1.\nReconnect or switch to a "
           "replay context on that host first.")
            .arg(hostName));
    updateLatestCaptureUI();
    return;
  }

  if(saveCapture(cap, QString()))
  {
    m_LatestCaptureFailure = QString();
    m_LatestCaptureCopying = !cap->local;
    m_LatestCaptureCopyFailed = false;
    updateLatestCaptureUI();
  }
  else
  {
    if(m_LatestCaptureFailure.isEmpty())
      m_LatestCaptureFailure = tr("The latest capture copy couldn't be started.");

    updateLatestCaptureUI();
  }
}

void LiveCapture::openCapture_triggered()
{
  if(ui->captures->selectedItems().size() == 1)
    openCapture(GetCapture(ui->captures->selectedItems()[0]));
}

void LiveCapture::openNewWindow_triggered()
{
  if(ui->captures->selectedItems().size() == 1)
  {
    Capture *cap = GetCapture(ui->captures->selectedItems()[0]);

    QString temppath = m_Ctx.TempCaptureFilename(lit("newwindow"));

    if(!cap->local)
    {
      RDDialog::critical(this, tr("Cannot open new instance"),
                         tr("Can't open capture in new instance with remote server in use"));
      return;
    }

    QFile f(cap->path);

    if(!f.copy(temppath))
    {
      RDDialog::critical(this, tr("Cannot save temporary capture"),
                         tr("Couldn't save capture to temporary location\n%1").arg(f.errorString()));
      return;
    }

    QStringList args;
    args << lit("--tempfile") << temppath;
    QProcess::startDetached(qApp->applicationFilePath(), args);
  }
}

void LiveCapture::saveCapture_triggered()
{
  if(ui->captures->selectedItems().size() == 1)
  {
    saveCapture(GetCapture(ui->captures->selectedItems()[0]), QString());
  }
  else
  {
    QString path = m_Main->GetSavePath(tr("Save All Captures As"));

    if(!path.isEmpty())
    {
      if(path.endsWith(lit(".rdc")))
        path.chop(4);

      // don't save duplicates if we have multiple captures from the same frame (possible if the
      // application is not presenting at all and using the API to capture)
      QMap<uint32_t, uint32_t> existingFiles;

      for(QListWidgetItem *item : ui->captures->selectedItems())
      {
        Capture *cap = GetCapture(item);

        QString filename = QFormatStr("%1-frame%2").arg(path).arg(cap->frameNumber);
        if(cap->frameNumber == ~0U)
          filename = QFormatStr("%1-capture").arg(path);

        if(existingFiles.contains(cap->frameNumber))
        {
          filename += QFormatStr("_%1").arg(existingFiles[cap->frameNumber]);
          existingFiles[cap->frameNumber]++;
        }
        else
        {
          // start on 2 next time
          existingFiles[cap->frameNumber] = 2;
        }

        saveCapture(cap, QFormatStr("%1.rdc").arg(filename));
      }
    }
  }
}

void LiveCapture::deleteCapture_triggered()
{
  bool allow = checkAllowDelete();

  if(!allow)
    return;

  QList<QListWidgetItem *> sel = ui->captures->selectedItems();

  for(QListWidgetItem *item : sel)
  {
    Capture *cap = GetCapture(item);

    if(!cap->saved)
    {
      if(cap->path == m_Ctx.GetCaptureFilename())
      {
        m_Main->takeCaptureOwnership();
        m_Main->CloseCapture();
      }
      else
      {
        // if connected, prefer using the live connection
        if(m_Connected.available() && !cap->local)
        {
          QMutexLocker l(&m_DeleteCapturesLock);
          m_DeleteCaptures.push_back(cap->remoteID);
        }
        else
        {
          m_Ctx.Replay().DeleteCapture(cap->path, cap->local);
        }

        if(cap->local)
        {
          m_Main->RemoveRecentCapture(cap->path);
        }
      }
    }

    delete cap;

    delete ui->captures->takeItem(ui->captures->row(item));
  }

  if(m_LatestCaptureID != ~0U && FindCapture(m_LatestCaptureID, NULL) == NULL)
    refreshLatestCaptureFromList();

  updateLatestCaptureUI();
}

void LiveCapture::childUpdate()
{
  // first do a small lock and check if the list is currently empty
  {
    QMutexLocker l(&m_ChildrenLock);

    if(m_Children.empty())
    {
      ui->childProcessLabel->setVisible(false);
      ui->childProcesses->setVisible(false);
    }
  }

  // We only compare the child processes for a local context
  const bool local = isLocal();

  // enumerate processes outside of the lock
  QProcessList processes;
  if(local)
  {
    processes = QProcessInfo::enumerate(false);
  }

  // now since we're adding and removing, we lock around the whole rest of the function. It won't be
  // too slow.
  {
    QMutexLocker l(&m_ChildrenLock);

    if(!m_Children.empty())
    {
      // remove any stale processes
      for(int i = 0; i < m_Children.size(); i++)
      {
        bool found = false;

        for(QProcessInfo &p : processes)
        {
          if(p.pid() == m_Children[i].PID)
          {
            found = true;
            break;
          }
        }

        if(!found && local)
        {
          if(m_Children[i].added)
          {
            for(int c = 0; c < ui->childProcesses->count(); c++)
            {
              QListWidgetItem *item = ui->childProcesses->item(c);
              if(item->data(PIDRole).toUInt() == m_Children[i].PID)
                delete ui->childProcesses->takeItem(c);
            }
          }

          // process expired/doesn't exist anymore
          m_Children.removeAt(i);

          // don't increment i, check the next element at i (if we weren't at the end
          i--;
        }
      }

      for(int i = 0; i < m_Children.size(); i++)
      {
        if(!m_Children[i].added)
        {
          QString name = tr("Unknown Process");

          // find the name
          for(QProcessInfo &p : processes)
          {
            if(p.pid() == m_Children[i].PID)
            {
              name = p.name();
              break;
            }
          }

          QString text = QFormatStr("%1 [PID %2]").arg(name).arg(m_Children[i].PID);

          m_Children[i].added = true;
          QListWidgetItem *item = new QListWidgetItem(text, ui->childProcesses);
          item->setData(PIDRole, QVariant(m_Children[i].PID));
          item->setData(IdentRole, QVariant(m_Children[i].ident));
          ui->childProcesses->addItem(item);
        }
      }
    }

    if(!m_Children.empty())
    {
      ui->childProcessLabel->setVisible(true);
      ui->childProcesses->setVisible(true);
    }
    else
    {
      ui->childProcessLabel->setVisible(false);
      ui->childProcesses->setVisible(false);
    }
  }
}

void LiveCapture::captureCountdownTick()
{
  m_CaptureCounter--;

  if(m_CaptureCounter == 0)
  {
    m_CaptureNumFrames = (int)ui->numFrames->value();
    updateCaptureControls();
    ui->triggerDelayedCapture->setText(tr("Trigger After Delay"));
    m_TriggerCapture.release();
  }
  else
  {
    countdownTimer.start();
    ui->triggerDelayedCapture->setText(tr("Triggering in %1s").arg(m_CaptureCounter));
  }
}

void LiveCapture::killThread()
{
  if(m_ConnectThread)
  {
    m_Disconnect.acquire();
    m_ConnectThread->wait();
    m_ConnectThread->deleteLater();
  }
}

void LiveCapture::setTitle(const QString &title)
{
  setWindowTitle((!m_HostFriendlyname.isEmpty() ? (m_HostFriendlyname + lit(" - ")) : QString()) +
                 title);
}

LiveCapture::Capture *LiveCapture::GetCapture(QListWidgetItem *item)
{
  return (Capture *)item->data(CapPtrRole).value<void *>();
}

LiveCapture::Capture *LiveCapture::FindCapture(uint32_t remoteID, QListWidgetItem **item)
{
  for(int i = 0; i < ui->captures->count(); i++)
  {
    QListWidgetItem *captureItem = ui->captures->item(i);
    Capture *cap = GetCapture(captureItem);

    if(cap && cap->remoteID == remoteID)
    {
      if(item)
        *item = captureItem;

      return cap;
    }
  }

  return NULL;
}

void LiveCapture::AddCapture(QListWidgetItem *item, Capture *cap)
{
  item->setData(CapPtrRole, QVariant::fromValue<void *>(cap));
}

void LiveCapture::updateCaptureItem(Capture *cap)
{
  for(int i = 0; i < ui->captures->count(); i++)
  {
    QListWidgetItem *item = ui->captures->item(i);

    if(GetCapture(item) == cap)
    {
      QFont f = item->font();
      f.setItalic(!cap->local);
      item->setFont(f);
      item->setText(MakeText(cap));
      item->setIcon(QIcon(QPixmap::fromImage(MakeThumb(cap->thumb))));
      break;
    }
  }
}

void LiveCapture::refreshLatestCaptureFromList()
{
  m_LatestCaptureID = ~0U;
  m_CaptureRequested = false;
  m_LatestCaptureCopying = false;
  m_LatestCaptureCopyFailed = false;
  m_LatestCaptureFailure = QString();

  if(ui->captures->count() > 0)
  {
    Capture *cap = GetCapture(ui->captures->item(ui->captures->count() - 1));

    if(cap)
      m_LatestCaptureID = cap->remoteID;
  }
}

QString LiveCapture::latestCaptureDescription(Capture *cap) const
{
  QString captureName = cap->title;

  if(captureName.isEmpty())
  {
    if(cap->frameNumber == ~0U)
      captureName = tr("User-defined capture");
    else
      captureName = tr("Frame #%1").arg(cap->frameNumber);
  }

  if(!cap->name.isEmpty())
    captureName = tr("%1 from %2").arg(captureName).arg(cap->name);

  return captureName;
}

void LiveCapture::updateCaptureControls()
{
  bool canCapture = false;
  bool unsupportedAPI = false;
  bool nonPresentingAPI = false;
  QString tooltip;

  if(!m_LiveConnection)
  {
    tooltip =
        tr("Capture controls become available after a live target connection is established.");
  }
  else if(m_APIs.empty())
  {
    tooltip = tr("Waiting for the target to report a graphics API.");
  }
  else
  {
    for(const QString &api : m_APIs.keys())
    {
      const APIStatus &status = m_APIs[api];

      if(status.supported && status.presenting)
      {
        canCapture = true;
      }
      else if(status.supported)
      {
        nonPresentingAPI = true;
      }
      else
      {
        unsupportedAPI = true;
      }
    }

    if(canCapture)
    {
      tooltip = tr("Trigger a capture on the connected target.");
    }
    else if(nonPresentingAPI)
    {
      tooltip =
          tr("The target is running, but no reported API is currently presenting to a "
             "capturable window. Use Cycle Active Window or in-application API markers if "
             "needed.");
    }
    else if(unsupportedAPI)
    {
      tooltip = tr("The connected target only reported unsupported APIs for live capture.");
    }
    else
    {
      tooltip = tr("The connected target hasn't reported a capturable API yet.");
    }
  }

  ui->triggerImmediateCapture->setEnabled(canCapture);
  ui->triggerImmediateCapture->setToolTip(tooltip);
  ui->triggerDelayedCapture->setEnabled(canCapture && m_CaptureCounter == 0);
  ui->triggerDelayedCapture->setToolTip(tooltip);
  ui->queueCap->setEnabled(canCapture);
  ui->queueCap->setToolTip(tooltip);
}

void LiveCapture::updateLatestCaptureUI()
{
  const QString hostName = !m_HostFriendlyname.isEmpty()
                               ? m_HostFriendlyname
                               : (!m_Hostname.isEmpty() ? m_Hostname : tr("this host"));
  RemoteHost remoteHost = m_Ctx.Config().GetRemoteHost(m_Hostname);

  ui->getLatestCapture->setText(tr("Get Latest Capture"));
  ui->getLatestCapture->setEnabled(false);
  ui->getLatestCapture->setToolTip(tr("No capture has been reported by this target yet."));
  ui->latestCaptureStatus->setText(tr("No captures reported yet."));

  Capture *cap = FindCapture(m_LatestCaptureID, NULL);

  if(!cap)
  {
    if(m_CaptureRequested)
      ui->latestCaptureStatus->setText(tr("Waiting for the target to report a new capture..."));
    else if(!m_LatestCaptureFailure.isEmpty())
      ui->latestCaptureStatus->setText(m_LatestCaptureFailure);

    return;
  }

  const QString latestCapture = latestCaptureDescription(cap);
  const bool replayContextActive = m_Ctx.Replay().CurrentRemote().Hostname() == rdcstr(m_Hostname);

  if(cap->local)
  {
    ui->getLatestCapture->setText(tr("Reveal Latest Capture"));

    if(QFileInfo::exists(cap->path))
    {
      ui->getLatestCapture->setEnabled(true);
      ui->getLatestCapture->setToolTip(tr("Reveal the latest local capture in the file browser."));
      ui->latestCaptureStatus->setText(
          tr("%1 is local. Use Open to inspect it, or Reveal Latest Capture to show it in the "
             "file browser.")
              .arg(latestCapture));
    }
    else
    {
      ui->getLatestCapture->setToolTip(tr("The copied local file can't be found anymore."));
      ui->latestCaptureStatus->setText(
          tr("%1 was copied locally, but the file can't be found at:\n%2")
              .arg(latestCapture)
              .arg(QDir::toNativeSeparators(cap->path)));
    }

    return;
  }

  if(m_LatestCaptureCopying)
  {
    ui->getLatestCapture->setToolTip(tr("The latest capture is currently being copied locally."));
    ui->latestCaptureStatus->setText(
        tr("Copying %1 to:\n%2").arg(latestCapture).arg(QDir::toNativeSeparators(cap->path)));
    return;
  }

  ui->getLatestCapture->setEnabled(m_LiveConnection || replayContextActive);
  ui->getLatestCapture->setToolTip(tr("Copy the latest capture from %1 to this PC.").arg(hostName));

  if(!m_LatestCaptureFailure.isEmpty())
  {
    ui->latestCaptureStatus->setText(m_LatestCaptureFailure);
  }
  else if(m_CaptureRequested)
  {
    ui->latestCaptureStatus->setText(
        tr("Waiting for a newer capture from %1 before the latest-capture status is updated.")
            .arg(hostName));
  }
  else if(m_LatestCaptureCopyFailed)
  {
    ui->latestCaptureStatus->setText(
        tr("Copy of %1 didn't complete before the live connection closed. Try Get Latest Capture "
           "again.")
            .arg(latestCapture));
  }
  else if(m_LiveConnection)
  {
    ui->latestCaptureStatus->setText(
        tr("%1 is available on %2. Click Get Latest Capture to copy it locally.")
            .arg(latestCapture)
            .arg(hostName));
  }
  else if(replayContextActive)
  {
    ui->latestCaptureStatus->setText(
        tr("%1 is available on %2. Click Get Latest Capture to copy it through the active replay "
           "context.")
            .arg(latestCapture)
            .arg(hostName));
  }
  else if(remoteHost.IsVersionMismatch())
  {
    ui->getLatestCapture->setToolTip(
        tr("Update the device-side RenderDoc components, then reconnect before copying."));
    ui->latestCaptureStatus->setText(
        tr("%1 is on %2, but the remote server version doesn't match this RenderDoc build. "
           "Update the device-side RenderDoc components, then reconnect.")
            .arg(latestCapture)
            .arg(hostName));
  }
  else if(remoteHost.IsBusy())
  {
    ui->getLatestCapture->setToolTip(
        tr("The remote server on %1 is currently busy with another RenderDoc client.").arg(hostName));
    ui->latestCaptureStatus->setText(
        tr("%1 is on %2, but that remote server is busy with another RenderDoc client. Free that "
           "connection, then retry the copy.")
            .arg(latestCapture)
            .arg(hostName));
  }
  else
  {
    ui->getLatestCapture->setToolTip(
        tr("Reconnect to %1 or switch to a replay context on that host to copy the latest capture.")
            .arg(hostName));
    ui->latestCaptureStatus->setText(
        tr("%1 is only available on %2. Reconnect or switch to a replay context on that host to "
           "copy it.")
            .arg(latestCapture)
            .arg(hostName));
  }
}

QImage LiveCapture::MakeThumb(const QImage &screenshot)
{
  const QSizeF thumbSize(ui->captures->iconSize());
  const QSizeF imSize(screenshot.size());

  float x = 0, y = 0;
  float width = 0, height = 0;

  const float srcaspect = imSize.width() / imSize.height();
  const float dstaspect = thumbSize.width() / thumbSize.height();

  if(srcaspect > dstaspect)
  {
    width = thumbSize.width();
    height = width / srcaspect;

    y = (thumbSize.height() - height) / 2;
  }
  else
  {
    height = thumbSize.height();
    width = height * srcaspect;

    x = (thumbSize.width() - width) / 2;
  }

  QImage ret(thumbSize.width(), thumbSize.height(), QImage::Format_RGBA8888);
  ret.fill(Qt::transparent);
  QPainter paint(&ret);
  paint.drawImage(QRectF(x, y, width, height),
                  screenshot.scaled(width, height, Qt::IgnoreAspectRatio, Qt::SmoothTransformation));
  return ret;
}

bool LiveCapture::checkAllowDelete()
{
  bool needcheck = false;

  for(int i = 0; i < ui->captures->count(); i++)
  {
    Capture *cap = GetCapture(ui->captures->item(i));
    needcheck |= !cap->saved;
  }

  if(!needcheck || ui->captures->selectedItems().empty())
    return true;

  ToolWindowManager::raiseToolWindow(this);

  QMessageBox::StandardButton res =
      RDDialog::question(this, tr("Unsaved capture(s)", "", ui->captures->selectedItems().size()),
                         tr("Are you sure you wish to delete the capture(s)?\nAny capture "
                            "currently opened will be closed",
                            "", ui->captures->selectedItems().size()),
                         RDDialog::YesNoCancel);

  return (res == QMessageBox::Yes);
}

void LiveCapture::updateAPIStatus()
{
  QString apiStatus;

  bool nonpresenting = false;

  // add any fully working APIs first in the list.
  for(QString api : m_APIs.keys())
  {
    if(m_APIs[api].supported && m_APIs[api].presenting)
      apiStatus += lit(", <b>%1 (Active)</b>").arg(api);
  }

  // then add any problem APIs
  for(QString api : m_APIs.keys())
  {
    if(!m_APIs[api].supported)
    {
      apiStatus += tr(", %1 (Unsupported)").arg(api);
      if(!m_APIs[api].supportMessage.isEmpty())
        apiStatus += lit("\n") + m_APIs[api].supportMessage;
    }
    else if(!m_APIs[api].presenting)
    {
      apiStatus += tr(", %1 (Not Presenting)").arg(api);
      nonpresenting = true;
    }
  }

  // remove the redundant starting ", "
  apiStatus.remove(0, 2);

  apiStatus.replace(QLatin1Char('\n'), lit("<br>"));

  ui->apiStatus->setText(apiStatus);

  ui->apiIcon->setVisible(nonpresenting);
  updateCaptureControls();
}

QString LiveCapture::MakeText(Capture *cap)
{
  QString text = cap->name;
  if(!cap->local)
    text += tr(" (Remote)");

  text += lit("\n") + cap->api;
  if(!cap->title.isEmpty())
    text += QFormatStr("\n%1").arg(cap->title);
  else if(cap->frameNumber == ~0U)
    text += tr("\nUser-defined Capture");
  else
    text += tr("\nFrame #%1").arg(cap->frameNumber);

  if(cap->byteSize > 0)
    text += QFormatStr(" (%1 MB)").arg(double(cap->byteSize) / 1000000.0, 0, 'f', 2);

  text += cap->timestamp.toString(lit("\nyyyy-MM-dd HH:mm:ss"));

  return text;
}

bool LiveCapture::checkAllowClose(int totalUnsavedCaptures, bool &noToAll)
{
  m_IgnoreThreadClosed = true;

  bool suppressRemoteWarning = false;

  QMessageBox::StandardButtons msgFlags = RDDialog::YesNoCancel;

  const int unsavedCaptures = unsavedCaptureCount();
  const bool multipleClosures = totalUnsavedCaptures > unsavedCaptures;

  if(unsavedCaptures > 1 || multipleClosures)
    msgFlags |= QMessageBox::NoToAll;

  for(int i = 0; i < ui->captures->count(); i++)
  {
    QListWidgetItem *item = ui->captures->item(i);
    Capture *cap = GetCapture(ui->captures->item(i));

    if(cap->saved)
      continue;

    ui->captures->clearSelection();
    ToolWindowManager::raiseToolWindow(this);
    ui->captures->setFocus();
    item->setSelected(true);

    QMessageBox::StandardButton res = QMessageBox::No;

    if(!suppressRemoteWarning && !noToAll)
    {
      QString frameName = tr("Frame #%1").arg(cap->frameNumber);
      if(cap->frameNumber == ~0U)
        frameName = tr("User-defined Capture");

      res = RDDialog::question(this, tr("Unsaved capture"),
                               tr("Save this capture '%1 %2' at %3?")
                                   .arg(cap->name)
                                   .arg(frameName)
                                   .arg(cap->timestamp.toString(lit("HH:mm:ss"))),
                               msgFlags);

      if(res == QMessageBox::NoToAll)
      {
        // if we're closing multiple connections make sure the user is sure of what they're doing
        if(multipleClosures)
        {
          QMessageBox::StandardButton res2 = RDDialog::question(
              this, tr("Discarding all captures"),
              tr("Multiple connections open have potentially unsaved captures, "
                 "this will discard all captures in all connections, are you sure?"));

          // if the user is sure, apply the no to all
          if(res2 == QMessageBox::Yes)
          {
            noToAll = true;
          }
          else
          {
            // otherwise if the user changed their mind at this stage, cancel everything rather than
            // trying to continue, to keep the flow simple and ensure the user is clear what is
            // happening at all points. We do not support discarding all captures in one connection
            // then individually filtering another.
            m_IgnoreThreadClosed = false;
            return false;
          }
        }
        else
        {
          // if we're not closing multiple, we can just immediately accept the 'no to all'
          noToAll = true;
        }

        res = QMessageBox::No;
      }
    }

    if(res == QMessageBox::Cancel)
    {
      m_IgnoreThreadClosed = false;
      return false;
    }

    // we either have to save or delete the capture. Make sure that if it's remote that we are able
    // to by having an active connection or replay context on that host.
    if(suppressRemoteWarning == false && !m_Connected.available() && !cap->local &&
       m_Ctx.Replay().CurrentRemote().Hostname() != rdcstr(m_Hostname))
    {
      QMessageBox::StandardButton res2 = RDDialog::question(
          this, tr("No active replay context"),
          tr("This capture is on remote host %1 and there is no active replay context on that "
             "host.\n")
                  .arg(m_HostFriendlyname) +
              tr("Without an active replay context the capture cannot be %1.\n\n")
                  .arg(tr(res == QMessageBox::Yes ? "saved" : "deleted")) +
              tr("Would you like to continue and discard this capture and any others, to be left "
                 "in the temporary folder on the remote machine?"),
          RDDialog::YesNoCancel);

      if(res2 == QMessageBox::Yes)
      {
        suppressRemoteWarning = true;
        res = QMessageBox::No;
      }
      else
      {
        m_IgnoreThreadClosed = false;
        return false;
      }
    }

    if(res == QMessageBox::Yes)
    {
      bool success = saveCapture(cap, QString());

      if(!success)
      {
        m_IgnoreThreadClosed = false;
        return false;
      }
    }
  }

  m_IgnoreThreadClosed = false;
  return true;
}

bool LiveCapture::checkAllowClose()
{
  bool dummy = false;
  return checkAllowClose(unsavedCaptureCount(), dummy);
}

void LiveCapture::openCapture(Capture *cap)
{
  cap->opened = true;

  if(!cap->local && m_Ctx.Replay().CurrentRemote().Hostname() != rdcstr(m_Hostname))
  {
    RDDialog::critical(
        this, tr("No active replay context"),
        tr("This capture is on remote host %1 and there is no active replay context on that "
           "host.\nYou can either save the capture locally, or switch to a replay context on %1.")
            .arg(m_HostFriendlyname));
    return;
  }

  m_Main->LoadCapture(cap->path, m_Ctx.Config().DefaultReplayOptions, !cap->saved, cap->local);
}

bool LiveCapture::saveCapture(Capture *cap, QString path)
{
  bool copiedLocal = cap->local;

  // if this is the current capture, do the save through the main window
  if(QString(m_Ctx.GetCaptureFilename()) == cap->path)
  {
    // if there's no target path, let the main window prompt for save.
    if(path.isEmpty())
      return m_Main->PromptSaveCaptureAs();
    else
      return m_Main->SaveCurrentCapture(path);
  }

  if(path.isEmpty())
  {
    path = m_Main->GetSavePath();

    if(path.isEmpty())
      return false;
  }

  if(QString(m_Ctx.GetCaptureFilename()) == path)
  {
    RDDialog::critical(this, tr("Cannot save"),
                       tr("Can't overwrite currently open capture at %1\n"
                          "Close the capture or save to another location.")
                           .arg(path));
    return false;
  }

  // we copy the temp capture to the desired path, but the capture item remains referring to the
  // temp path.
  // This ensures that if the user deletes the saved path we can still open or re-save it.
  if(cap->local)
  {
    QFile src(cap->path);
    QFile dst(path);

    // remove any existing file, the user was already prompted to overwrite
    if(dst.exists())
    {
      if(!dst.remove())
      {
        RDDialog::critical(this, tr("Cannot save"),
                           tr("Couldn't remove file at %1\n%2").arg(path).arg(dst.errorString()));
        return false;
      }
    }

    if(!src.copy(path))
    {
      RDDialog::critical(this, tr("Cannot save"),
                         tr("Couldn't copy file to %1\n%2").arg(path).arg(src.errorString()));
      return false;
    }
  }
  else if(m_Connected.available())
  {
    // if we have a current live connection, prefer using it
    m_CopyCaptureLocalPath = path;
    m_CopyCaptureID = cap->remoteID;

    m_CopyCapture.release();
  }
  else
  {
    if(m_Ctx.Replay().CurrentRemote().Hostname() != rdcstr(m_Hostname))
    {
      RDDialog::critical(this, tr("No active replay context"),
                         tr("This capture is on remote host %1 and there is no active replay "
                            "context on that host.\n")
                                 .arg(m_Hostname) +
                             tr("Without an active replay context the capture cannot be saved, "
                                "try switching to a replay context on %1.")
                                 .arg(m_Hostname));
      return false;
    }

    m_Ctx.Replay().CopyCaptureFromRemote(cap->path, path, this);
    copiedLocal = true;

    if(!QFile::exists(path))
    {
      RDDialog::critical(this, tr("Cannot save"),
                         tr("File couldn't be transferred from remote host"));
      return false;
    }

    m_Ctx.Replay().DeleteCapture(cap->path, false);
  }

  // delete the temporary copy
  if(!cap->saved)
    m_Ctx.Replay().DeleteCapture(cap->path, cap->local);

  m_Main->RemoveRecentCapture(cap->path);
  cap->saved = true;
  cap->path = path;
  cap->local = copiedLocal;
  AddRecentFile(m_Ctx.Config().RecentCaptureFiles, path);
  m_Main->PopulateRecentCaptureFiles();
  updateCaptureItem(cap);
  return true;
}

void LiveCapture::cleanItems()
{
  for(int i = 0; i < ui->captures->count(); i++)
  {
    Capture *cap = GetCapture(ui->captures->item(i));

    if(!cap->saved)
    {
      if(cap->path == m_Ctx.GetCaptureFilename())
      {
        m_Main->takeCaptureOwnership();
      }
      else
      {
        // if connected, prefer using the live connection
        if(m_Connected.available() && !cap->local)
        {
          QMutexLocker l(&m_DeleteCapturesLock);
          m_DeleteCaptures.push_back(cap->remoteID);
        }
        else
        {
          m_Ctx.Replay().DeleteCapture(cap->path, cap->local);
        }

        if(cap->local)
        {
          m_Main->RemoveRecentCapture(cap->path);
        }
      }
    }

    delete cap;
  }
  ui->captures->clear();
}

void LiveCapture::fileSaved(QString from, QString to)
{
  for(int i = 0; i < ui->captures->count(); i++)
  {
    Capture *cap = GetCapture(ui->captures->item(i));

    if(cap->path == from)
    {
      cap->path = to;
      cap->saved = true;
      cap->local = true;
      updateCaptureItem(cap);

      if(cap->remoteID == m_LatestCaptureID)
        updateLatestCaptureUI();
    }
  }
}

int LiveCapture::unsavedCaptureCount()
{
  int ret = 0;

  for(int i = 0; i < ui->captures->count(); i++)
  {
    Capture *cap = GetCapture(ui->captures->item(i));

    if(!cap->saved)
      ret++;
  }

  return ret;
}

void LiveCapture::previewToggle_toggled(bool checked)
{
  if(m_IgnorePreviewToggle)
    return;

  if(checked)
    ui->previewSplit->setSizes({1, 1});
  else
    ui->previewSplit->setSizes({1, 0});
}

void LiveCapture::on_previewSplit_splitterMoved(int pos, int index)
{
  m_IgnorePreviewToggle = true;

  QList<int> sizes = ui->previewSplit->sizes();

  previewToggle->setChecked(sizes[1] != 0);

  m_IgnorePreviewToggle = false;
}

void LiveCapture::on_apiIcon_clicked(QMouseEvent *event)
{
  QDesktopServices::openUrl(QUrl(lit("https://renderdoc.org/docs/in_application_api.html")));
}

void LiveCapture::captures_keyPress(QKeyEvent *e)
{
  if(e->key() == Qt::Key_Delete)
  {
    deleteCapture_triggered();
  }
}

void LiveCapture::preview_mouseClick(QMouseEvent *e)
{
  QPoint mouse = QCursor::pos();
  if(e->buttons() & Qt::LeftButton)
  {
    previewDragStart = mouse;
    ui->preview->setCursor(QCursor(Qt::SizeAllCursor));
  }
}

void LiveCapture::preview_mouseMove(QMouseEvent *e)
{
  QPoint mouse = QCursor::pos();
  if(e->buttons() & Qt::LeftButton)
  {
    QScrollBar *h = ui->previewScroll->horizontalScrollBar();
    QScrollBar *v = ui->previewScroll->verticalScrollBar();

    h->setValue(h->value() + previewDragStart.x() - mouse.x());
    v->setValue(v->value() + previewDragStart.y() - mouse.y());

    previewDragStart = mouse;
  }
  else
  {
    ui->preview->unsetCursor();
  }
}

void LiveCapture::on_captures_itemSelectionChanged()
{
  int numSelected = ui->captures->selectedItems().size();

  openButton->setEnabled(numSelected == 1);
  saveAction->setEnabled(numSelected != 0);
  deleteAction->setEnabled(numSelected != 0);

  if(ui->captures->selectedItems().size() == 1)
  {
    QListWidgetItem *item = ui->captures->selectedItems()[0];
    Capture *cap = GetCapture(item);

    newWindowAction->setEnabled(cap->local);

    if(cap->thumb.width() > 0)
    {
      ui->preview->setPixmap(QPixmap::fromImage(cap->thumb));
      ui->preview->setMinimumSize(cap->thumb.size());
      ui->preview->setMaximumSize(cap->thumb.size());
    }
    else
    {
      ui->preview->setPixmap(QPixmap());
      ui->preview->setMinimumSize(QSize(16, 16));
      ui->preview->setMaximumSize(QSize(16, 16));
    }
  }
}

void LiveCapture::captureCopied(uint32_t ID, const QString &localPath)
{
  QListWidgetItem *latestItem = NULL;

  for(int i = 0; i < ui->captures->count(); i++)
  {
    QListWidgetItem *item = ui->captures->item(i);
    Capture *cap = GetCapture(ui->captures->item(i));

    if(cap && cap->remoteID == ID)
    {
      cap->local = true;
      cap->path = localPath;
      updateCaptureItem(cap);

      if(ID == m_LatestCaptureID)
        latestItem = item;
    }
  }

  if(ID == m_LatestCaptureID)
  {
    m_CaptureRequested = false;
    m_LatestCaptureCopying = false;
    m_LatestCaptureCopyFailed = false;
    m_LatestCaptureFailure = QString();

    if(latestItem)
      ui->captures->setCurrentItem(latestItem);

    updateLatestCaptureUI();
  }
}

void LiveCapture::captureAdded(const QString &name, const NewCaptureData &newCapture)
{
  Capture *cap = new Capture();

  cap->name = name;

  cap->api = newCapture.api;

  cap->timestamp =
      QDateTime(QDate(1970, 1, 1), QTime(0, 0, 0), Qt::UTC).addSecs(newCapture.timestamp).toLocalTime();
  cap->byteSize = newCapture.byteSize;

  cap->thumb = QImage(newCapture.thumbnail.data(), newCapture.thumbWidth, newCapture.thumbHeight,
                      newCapture.thumbWidth * 3, QImage::Format_RGB888)
                   .copy(0, 0, newCapture.thumbWidth, newCapture.thumbHeight);

  cap->remoteID = newCapture.captureId;
  cap->saved = false;
  cap->path = newCapture.path;
  cap->local = newCapture.local;
  cap->frameNumber = newCapture.frameNumber;
  cap->title = newCapture.title;

  QListWidgetItem *item = new QListWidgetItem();
  item->setFlags(item->flags() | Qt::ItemIsEditable);
  item->setText(MakeText(cap));
  item->setIcon(QIcon(QPixmap::fromImage(MakeThumb(cap->thumb))));
  if(!newCapture.local)
  {
    QFont f = item->font();
    f.setItalic(true);
    item->setFont(f);
  }

  AddCapture(item, cap);

  ui->captures->addItem(item);

  m_LatestCaptureID = cap->remoteID;
  m_CaptureRequested = false;
  m_LatestCaptureCopying = false;
  m_LatestCaptureCopyFailed = false;
  m_LatestCaptureFailure = QString();
  updateLatestCaptureUI();
}

void LiveCapture::connectionClosed()
{
  const QString hostName = !m_HostFriendlyname.isEmpty()
                               ? m_HostFriendlyname
                               : (!m_Hostname.isEmpty() ? m_Hostname : tr("this host"));

  m_LiveConnection = false;
  updateCaptureControls();
  ui->progressLabel->setVisible(false);
  ui->progressBar->setVisible(false);

  if(m_CaptureRequested)
  {
    m_LatestCaptureFailure =
        tr("The most recent capture request didn't report a new capture before the live "
           "connection to %1 closed.")
            .arg(hostName);
    m_CaptureRequested = false;
  }

  if(m_LatestCaptureCopying)
  {
    m_LatestCaptureCopying = false;
    m_LatestCaptureCopyFailed = true;
    m_LatestCaptureFailure =
        tr("Copy of the latest capture didn't complete because the live connection to %1 closed.")
            .arg(hostName);
  }

  updateLatestCaptureUI();

  if(m_IgnoreThreadClosed)
    return;

  if(ui->captures->count() <= 1)
  {
    if(ui->captures->count() == 1)
    {
      Capture *cap = GetCapture(ui->captures->item(0));

      // only auto-open a non-local capture if we are successfully connected
      // to this machine as a remote context
      if(!cap->local)
      {
        if(m_Ctx.Replay().CurrentRemote().Hostname() != rdcstr(m_Hostname))
          return;
      }

      // don't close if a dialog is open
      if(QApplication::activeModalWidget() || QApplication::activePopupWidget())
        return;

      if(cap->opened)
        return;

      openCapture(cap);
      if(!cap->saved)
      {
        cap->saved = true;
        m_Main->takeCaptureOwnership();
      }
    }

    // auto-close and load capture if we got a capture. If we
    // don't have any captures but DO have child processes,
    // then don't close just yet.
    if(ui->captures->count() == 1 || m_Children.count() == 0)
    {
      // raise the texture viewer if it exists, instead of falling back to most likely the capture
      // executable dialog which is not useful.
      if(ui->captures->count() == 1 && m_Ctx.HasTextureViewer())
        m_Ctx.ShowTextureViewer();
      selfClose();
      return;
    }

    // if we have no captures and only one child, close and
    // open up a connection to it (similar to behaviour with
    // only one capture
    if(ui->captures->count() == 0 && m_Children.count() == 1)
    {
      LiveCapture *live =
          new LiveCapture(m_Ctx, m_Hostname, m_HostFriendlyname, m_Children[0].ident, m_Main);
      m_Main->ShowLiveCapture(live);
      selfClose();
      return;
    }
  }
}

void LiveCapture::selfClose()
{
  if(m_ContextMenu)
  {
    qInfo() << "preventing race";
    // hide the menu and close our window shortly after
    m_ContextMenu->close();
    QTimer *timer = new QTimer(this);
    QObject::connect(timer, &QTimer::timeout, [this]() { ToolWindowManager::closeToolWindow(this); });
    timer->setSingleShot(true);
    timer->start(250);
  }
  else
  {
    ToolWindowManager::closeToolWindow(this);
  }
}

void LiveCapture::connectionThreadEntry()
{
  ITargetControl *conn =
      RENDERDOC_CreateTargetControl(m_Hostname, m_RemoteIdent, GetSystemUsername(), true);
  m_Connected.release();

  if(!conn || !conn->Connected())
  {
    if(conn)
      conn->Shutdown();

    GUIInvoke::call(this, [this]() {
      setTitle(tr("Connection failed"));
      ui->connectionStatus->setText(tr("Failed"));
      ui->connectionIcon->setPixmap(Pixmaps::del(ui->connectionIcon));
      updateCaptureControls();

      connectionClosed();
    });

    m_Connected.acquire();
    return;
  }

  uint32_t pid = conn->GetPID();
  QString target = conn->GetTarget();

  GUIInvoke::call(this, [this, pid, target]() {
    if(!m_Connected.available())
      return;

    m_LiveConnection = true;

    if(pid)
      setTitle(QFormatStr("%1 [PID %2]").arg(target).arg(pid));
    else
      setTitle(target);

    ui->target->setText(windowTitle());
    ui->connectionIcon->setPixmap(Pixmaps::connect(ui->connectionIcon));
    ui->connectionStatus->setText(tr("Established"));
    updateCaptureControls();
    updateLatestCaptureUI();
  });

  while(conn && conn->Connected())
  {
    if(m_TriggerCapture.tryAcquire())
    {
      conn->TriggerCapture((uint)m_CaptureNumFrames);
      m_CaptureNumFrames = 1;
    }

    if(m_QueueCapture.tryAcquire())
    {
      conn->QueueCapture((uint32_t)m_QueueCaptureFrameNum, (uint32_t)m_CaptureNumFrames);
      m_QueueCaptureFrameNum = 0;
      m_CaptureNumFrames = 1;
    }

    if(m_CopyCapture.tryAcquire())
    {
      conn->CopyCapture(m_CopyCaptureID, m_CopyCaptureLocalPath);
      m_CopyCaptureLocalPath = QString();
      m_CopyCaptureID = ~0U;
    }

    if(m_CycleWindow.tryAcquire())
    {
      conn->CycleActiveWindow();
    }

    QVector<uint32_t> dels;
    {
      QMutexLocker l(&m_DeleteCapturesLock);
      dels.swap(m_DeleteCaptures);
    }

    for(uint32_t del : dels)
      conn->DeleteCapture(del);

    if(!m_Disconnect.available())
    {
      conn->Shutdown();
      conn = NULL;
      m_Connected.acquire();
      return;
    }

    TargetControlMessage msg = conn->ReceiveMessage([this](float progress) {
      GUIInvoke::call(this, [this, progress]() {
        if(progress >= 0.0f && progress < 1.0f)
        {
          ui->progressLabel->setText(tr("Copy in Progress:"));
          ui->progressLabel->setVisible(true);
          ui->progressBar->setVisible(true);
          ui->progressBar->setMaximum(1000);
          ui->progressBar->setValue(1000 * progress);
        }
        else
        {
          ui->progressLabel->setVisible(false);
          ui->progressBar->setVisible(false);
        }
      });
    });

    if(msg.type == TargetControlMessageType::RegisterAPI)
    {
      GUIInvoke::call(this, [this, msg]() {
        m_APIs[msg.apiUse.name] =
            APIStatus(msg.apiUse.presenting, msg.apiUse.supported, msg.apiUse.supportMessage);

        updateAPIStatus();
      });
    }

    if(msg.type == TargetControlMessageType::CaptureProgress)
    {
      float progress = msg.capProgress;
      GUIInvoke::call(this, [this, progress]() {
        if(progress >= 0.0f && progress < 1.0f)
        {
          ui->progressLabel->setText(tr("Capture in Progress:"));
          ui->progressLabel->setVisible(true);
          ui->progressBar->setVisible(true);
          ui->progressBar->setMaximum(1000);
          ui->progressBar->setValue(1000 * progress);
        }
        else
        {
          ui->progressLabel->setVisible(false);
          ui->progressBar->setVisible(false);
        }
      });
    }

    if(msg.type == TargetControlMessageType::NewCapture)
    {
      NewCaptureData cap = msg.newCapture;
      if(cap.api.isEmpty())
        cap.api = conn->GetAPI();
      QString name = conn->GetTarget();
      GUIInvoke::call(this, [this, name, cap]() { captureAdded(name, cap); });
    }

    if(msg.type == TargetControlMessageType::CaptureCopied)
    {
      uint32_t capID = msg.newCapture.captureId;
      QString path = msg.newCapture.path;

      GUIInvoke::call(this, [this, capID, path]() { captureCopied(capID, path); });
    }

    if(msg.type == TargetControlMessageType::NewChild)
    {
      if(msg.newChild.processId != 0)
      {
        ChildProcess c;
        c.PID = (int)msg.newChild.processId;
        c.ident = msg.newChild.ident;

        {
          QMutexLocker l(&m_ChildrenLock);
          m_Children.push_back(c);
        }

        // force a child update immediately, don't wait for the tick which is intended for decaying
        // processes that exit
        GUIInvoke::call(this, [this]() { childUpdate(); });
      }
    }

    if(msg.type == TargetControlMessageType::CapturableWindowCount)
    {
      uint32_t windows = msg.capturableWindowCount;
      GUIInvoke::call(this, [this, windows]() { ui->cycleActiveWindow->setEnabled(windows > 1); });
    }

    if(msg.type == TargetControlMessageType::RequestShow)
    {
      GUIInvoke::call(this, [this]() { m_Main->BringToFront(); });
    }
  }

  if(conn)
  {
    conn->Shutdown();
    conn = NULL;
    m_Connected.acquire();
  }

  GUIInvoke::call(this, [this]() {
    ui->connectionStatus->setText(tr("Closed"));
    ui->connectionIcon->setPixmap(Pixmaps::disconnect(ui->connectionIcon));

    ui->numFrames->setEnabled(false);
    ui->captureDelay->setEnabled(false);
    ui->captureFrame->setEnabled(false);
    ui->triggerDelayedCapture->setEnabled(false);
    ui->triggerImmediateCapture->setEnabled(false);
    ui->queueCap->setEnabled(false);
    ui->cycleActiveWindow->setEnabled(false);

    ui->apiStatus->setText(tr("None"));
    ui->apiIcon->setVisible(false);
    m_APIs.clear();
    updateCaptureControls();

    connectionClosed();
  });
}

bool LiveCapture::isLocal() const
{
  return m_Hostname.isEmpty() || QHostInfo::localHostName() == m_Hostname ||
         QLatin1String("0.0.0.0") == m_Hostname || QHostAddress(m_Hostname).isLoopback();
}
