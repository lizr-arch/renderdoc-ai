/******************************************************************************
 * The MIT License (MIT)
 *
 * Copyright (c) 2017-2026 Baldur Karlsson
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

#include "RemoteManager.h"
#include <QCoreApplication>
#include <QDialogButtonBox>
#include <QDir>
#include <QFileInfo>
#include <QFormLayout>
#include <QIntValidator>
#include <QKeyEvent>
#include <QLabel>
#include <QLineEdit>
#include <QPushButton>
#include <QSet>
#include <QThread>
#include <QVBoxLayout>
#include "Code/Interface/QRDInterface.h"
#include "Code/QRDUtils.h"
#include "Code/Resources.h"
#include "Windows/Dialogs/LiveCapture.h"
#include "Windows/MainWindow.h"
#include "flowlayout/FlowLayout.h"
#include "ui_RemoteManager.h"

namespace
{
struct AdbCommandResult
{
  int exitCode = -1;
  bool started = false;
  bool finished = false;
  QString stdOut;
  QString stdErr;
};

struct WirelessAndroidConfig
{
  QString host;
  uint16_t pairPort = 0;
  QString pairCode;
  uint16_t connectPort = 0;

  bool HasPairing() const { return pairPort > 0 || !pairCode.trimmed().isEmpty(); }
  QString PairEndpoint() const { return QFormatStr("%1:%2").arg(host).arg(pairPort); }
  QString ConnectEndpoint() const { return QFormatStr("%1:%2").arg(host).arg(connectPort); }
};

struct WirelessAndroidResult
{
  bool success = false;
  bool enumerated = false;
  QString targetHost;
  QString error;
};

static QString RemoteManagerTranslate(const char *context, const char *sourceText)
{
  return QCoreApplication::translate(context, sourceText);
}

static bool IsDigitString(const rdcstr &value)
{
  if(value.empty())
    return false;

  for(char c : value)
  {
    if(c < '0' || c > '9')
      return false;
  }

  return true;
}

static bool IsWirelessAndroidHost(const RemoteHost &host)
{
  if(!host.Protocol() || host.Protocol()->GetProtocolName() != "adb")
    return false;

  rdcstr deviceID = host.Hostname();
  int32_t scheme = deviceID.find("://");

  if(scheme > 0)
    deviceID.erase(0, scheme + 3);

  if(deviceID.contains("._adb-tls-connect._tcp") || deviceID.contains("._adb-tls-pairing._tcp"))
    return true;

  int32_t colon = deviceID.find(':');
  if(colon <= 0 || colon >= deviceID.count() - 1)
    return false;

  rdcstr adbHost = deviceID.substr(0, colon);
  rdcstr adbPort = deviceID.substr(colon + 1);

  return IsDigitString(adbPort) &&
         (adbHost == "localhost" || adbHost.contains('.') || adbHost.contains('['));
}

static QString ConfigStringOrEmpty(const char *settingName)
{
  if(const SDObject *setting = RENDERDOC_GetConfigSetting(settingName))
    return QString::fromUtf8(setting->AsString().c_str()).trimmed();

  return QString();
}

static QString GetAdbExecutable()
{
  const QString sdkPath = ConfigStringOrEmpty("Android.SDKDirPath");

  if(!sdkPath.isEmpty())
  {
#if defined(Q_OS_WIN)
    const QString adbPath = QDir(sdkPath).filePath(lit("platform-tools/adb.exe"));
#else
    const QString adbPath = QDir(sdkPath).filePath(lit("platform-tools/adb"));
#endif

    if(QFileInfo(adbPath).exists())
      return adbPath;
  }

#if defined(Q_OS_WIN)
  return lit("adb.exe");
#else
  return lit("adb");
#endif
}

static AdbCommandResult RunAdbCommand(const QStringList &arguments)
{
  AdbCommandResult result;

  QProcess process;
  process.setProgram(GetAdbExecutable());
  process.setArguments(arguments);
  process.start();

  result.started = process.waitForStarted(5000);

  if(result.started)
  {
    process.closeWriteChannel();
    result.finished = process.waitForFinished(30000);

    if(!result.finished)
    {
      result.stdErr = process.errorString();
      process.kill();
      process.waitForFinished();
    }
  }
  else
  {
    result.stdErr = process.errorString();
  }

  result.stdOut = QString::fromUtf8(process.readAllStandardOutput());

  if(result.stdErr.isEmpty())
    result.stdErr = QString::fromUtf8(process.readAllStandardError());

  result.exitCode = process.exitStatus() == QProcess::NormalExit ? process.exitCode() : -1;

  return result;
}

static QString AdbCommandOutput(const AdbCommandResult &result)
{
  QStringList output;

  QString stdOut = result.stdOut.trimmed();
  QString stdErr = result.stdErr.trimmed();

  if(!stdOut.isEmpty())
    output << stdOut;
  if(!stdErr.isEmpty())
    output << stdErr;

  return output.join(lit("\n")).trimmed();
}

static bool HasAdbFailureText(const AdbCommandResult &result)
{
  QString output = AdbCommandOutput(result).toLower();
  return output.contains(lit("failed")) || output.contains(lit("unable")) ||
         output.contains(lit("error:"));
}

static bool PairSucceeded(const AdbCommandResult &result)
{
  if(!result.started || !result.finished || result.exitCode != 0)
    return false;

  QString output = AdbCommandOutput(result).toLower();
  if(output.contains(lit("successfully paired")) || output.contains(lit("already paired")))
    return true;

  return !HasAdbFailureText(result);
}

static bool ConnectSucceeded(const AdbCommandResult &result)
{
  if(!result.started || !result.finished || result.exitCode != 0)
    return false;

  QString output = AdbCommandOutput(result).toLower();
  if(output.contains(lit("connected to")) || output.contains(lit("already connected to")))
    return true;

  return !HasAdbFailureText(result);
}

static QString FormatAdbFailure(const QString &step, const QString &command,
                                const AdbCommandResult &result)
{
  QString message =
      RemoteManagerTranslate("RemoteManager", "%1 failed while running `%2`.").arg(step).arg(command);

  QString output = AdbCommandOutput(result);

  if(!result.started)
  {
    message += RemoteManagerTranslate(
        "RemoteManager",
        "\n\nadb couldn't be started. Configure Settings > Android > SDK path or ensure adb is "
        "available in PATH.");
  }
  else if(!result.finished)
  {
    message += RemoteManagerTranslate("RemoteManager",
                                      "\n\nadb didn't finish before the timeout expired.");
  }

  if(!output.isEmpty())
  {
    message += RemoteManagerTranslate("RemoteManager", "\n\nadb output:\n%1").arg(output);
  }
  else if(result.started && result.finished)
  {
    message +=
        RemoteManagerTranslate("RemoteManager",
                               "\n\nadb didn't return any output. Configure Settings > Android > "
                               "SDK path or ensure adb is available in PATH.");
  }

  return message;
}

class AndroidWirelessSetupDialog : public QDialog
{
public:
  explicit AndroidWirelessSetupDialog(QWidget *parent) : QDialog(parent)
  {
    setWindowTitle(RemoteManagerTranslate("AndroidWirelessSetupDialog", "Android Wireless Setup"));
    setWindowFlags(windowFlags() & ~Qt::WindowContextHelpButtonHint);

    QLabel *intro = new QLabel(
        RemoteManagerTranslate("AndroidWirelessSetupDialog",
                               "Enter the values shown in Android Wireless debugging. "
                               "Pairing is optional if this computer is already paired."),
        this);
    intro->setWordWrap(true);

    m_Host = new QLineEdit(this);
    m_Host->setPlaceholderText(
        RemoteManagerTranslate("AndroidWirelessSetupDialog", "192.168.0.25"));

    m_PairPort = new QLineEdit(this);
    m_PairPort->setPlaceholderText(
        RemoteManagerTranslate("AndroidWirelessSetupDialog", "e.g. 37163"));
    m_PairPort->setValidator(new QIntValidator(1, 65535, m_PairPort));

    m_PairCode = new QLineEdit(this);
    m_PairCode->setPlaceholderText(
        RemoteManagerTranslate("AndroidWirelessSetupDialog", "6-digit pairing code"));
    m_PairCode->setEchoMode(QLineEdit::PasswordEchoOnEdit);

    m_ConnectPort = new QLineEdit(this);
    m_ConnectPort->setPlaceholderText(
        RemoteManagerTranslate("AndroidWirelessSetupDialog", "e.g. 45591"));
    m_ConnectPort->setValidator(new QIntValidator(1, 65535, m_ConnectPort));

    QFormLayout *form = new QFormLayout;
    form->addRow(RemoteManagerTranslate("AndroidWirelessSetupDialog", "Device Address:"), m_Host);
    form->addRow(RemoteManagerTranslate("AndroidWirelessSetupDialog", "Pairing Port:"), m_PairPort);
    form->addRow(RemoteManagerTranslate("AndroidWirelessSetupDialog", "Pairing Code:"), m_PairCode);
    form->addRow(RemoteManagerTranslate("AndroidWirelessSetupDialog", "Connect Port:"),
                 m_ConnectPort);

    QLabel *hint = new QLabel(
        RemoteManagerTranslate("AndroidWirelessSetupDialog",
                               "Leave Pairing Port and Pairing Code empty to skip `adb pair` and "
                               "only run `adb connect`."),
        this);
    hint->setWordWrap(true);

    QDialogButtonBox *buttons =
        new QDialogButtonBox(QDialogButtonBox::Ok | QDialogButtonBox::Cancel, this);
    buttons->button(QDialogButtonBox::Ok)
        ->setText(RemoteManagerTranslate("AndroidWirelessSetupDialog", "Connect"));

    QObject::connect(buttons, &QDialogButtonBox::accepted, [this]() { validateAndAccept(); });
    QObject::connect(buttons, &QDialogButtonBox::rejected, this, &QDialog::reject);

    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->addWidget(intro);
    layout->addLayout(form);
    layout->addWidget(hint);
    layout->addWidget(buttons);
    resize(420, sizeHint().height());
  }

  WirelessAndroidConfig Config() const
  {
    WirelessAndroidConfig config;
    config.host = m_Host->text().trimmed();
    config.pairPort = uint16_t(m_PairPort->text().toUShort());
    config.pairCode = m_PairCode->text().trimmed();
    config.connectPort = uint16_t(m_ConnectPort->text().toUShort());
    return config;
  }

private:
  void validateAndAccept()
  {
    WirelessAndroidConfig config = Config();

    if(config.host.isEmpty())
    {
      RDDialog::critical(
          this, RemoteManagerTranslate("AndroidWirelessSetupDialog", "Missing Device Address"),
          RemoteManagerTranslate("AndroidWirelessSetupDialog",
                                 "Enter the Android device IP address or hostname."));
      return;
    }

    if(config.connectPort == 0)
    {
      RDDialog::critical(
          this, RemoteManagerTranslate("AndroidWirelessSetupDialog", "Missing Connect Port"),
          RemoteManagerTranslate("AndroidWirelessSetupDialog",
                                 "Enter the wireless debugging port to use with `adb connect`."));
      return;
    }

    if(config.HasPairing() && (config.pairPort == 0 || config.pairCode.isEmpty()))
    {
      RDDialog::critical(
          this, RemoteManagerTranslate("AndroidWirelessSetupDialog", "Incomplete Pairing Details"),
          RemoteManagerTranslate("AndroidWirelessSetupDialog",
                                 "Fill in both Pairing Port and Pairing Code, or leave both blank "
                                 "to skip pairing."));
      return;
    }

    accept();
  }

  QLineEdit *m_Host = NULL;
  QLineEdit *m_PairPort = NULL;
  QLineEdit *m_PairCode = NULL;
  QLineEdit *m_ConnectPort = NULL;
};
}    // namespace

struct RemoteConnect
{
  RemoteConnect() {}
  RemoteConnect(const QString &h, const QString &f, uint32_t i) : host(h), friendly(f), ident(i) {}
  QString host;
  QString friendly;
  uint32_t ident = 0;
};

Q_DECLARE_METATYPE(RemoteConnect);

static void setRemoteConnect(RDTreeWidgetItem *item, const RemoteConnect &connect)
{
  if(!item)
    return;

  item->setTag(QVariant::fromValue(connect));
}

static RemoteConnect getRemoteConnect(RDTreeWidgetItem *item)
{
  if(!item)
    return RemoteConnect();

  return item->tag().value<RemoteConnect>();
}

static void setRemoteHost(RDTreeWidgetItem *item, RemoteHost host)
{
  if(!item)
    return;

  item->setTag(host.Hostname());
}

void deleteItemAndHost(RDTreeWidgetItem *item)
{
  delete item;
}

RemoteManager::RemoteManager(ICaptureContext &ctx, MainWindow *main)
    : QDialog(NULL), ui(new Ui::RemoteManager), m_Ctx(ctx), m_Main(main)
{
  ui->setupUi(this);

  m_ExternalRef.release(1);

  ui->hosts->setFont(Formatter::PreferredFont());
  ui->hostname->setFont(Formatter::PreferredFont());
  ui->runCommand->setFont(Formatter::PreferredFont());

  ui->hosts->setColumns({tr("Hostname"), tr("Running")});

  ui->hosts->header()->setSectionResizeMode(0, QHeaderView::Stretch);
  ui->hosts->header()->setSectionResizeMode(1, QHeaderView::ResizeToContents);

  setWindowFlags(windowFlags() & ~Qt::WindowContextHelpButtonHint);

  lookupsProgressFlow = new QWidget(this);

  FlowLayout *flow = new FlowLayout(lookupsProgressFlow, 0, 3, 3);

  lookupsProgressFlow->setSizePolicy(QSizePolicy::Preferred, QSizePolicy::Minimum);

  flow->addWidget(ui->progressIcon);
  flow->addWidget(ui->progressText);
  flow->addWidget(ui->progressCount);

  QVBoxLayout *vertical = new QVBoxLayout(this);

  vertical->addWidget(ui->hosts);
  vertical->addWidget(lookupsProgressFlow);
  vertical->addWidget(ui->bottomLayout->parentWidget());

  for(RemoteHost h : m_Ctx.Config().GetRemoteHosts())
    addHost(h);

  on_hosts_itemSelectionChanged();
}

RemoteManager::~RemoteManager()
{
  for(RDTreeWidgetItem *item : m_QueuedDeletes)
    delete item;
  delete ui;
}

RemoteHost RemoteManager::getRemoteHost(RDTreeWidgetItem *item)
{
  if(!item)
    return RemoteHost();

  return m_Ctx.Config().GetRemoteHost(item->tag().toString());
}

RDTreeWidgetItem *RemoteManager::findHostItem(const QString &hostname) const
{
  for(int i = 0; i < ui->hosts->topLevelItemCount(); i++)
  {
    RDTreeWidgetItem *item = ui->hosts->topLevelItem(i);
    if(item && item->tag().toString() == hostname)
      return item;
  }

  return NULL;
}

void RemoteManager::closeWhenFinished()
{
  m_ExternalRef.acquire(1);
  updateStatus();
}

void RemoteManager::setRemoteServerLive(RDTreeWidgetItem *node, bool live, bool busy)
{
  RemoteHost host = getRemoteHost(node);

  if(!host.IsValid())
    return;

  if(host.IsLocalhost())
  {
    node->setIcon(0, QIcon());
    node->setText(1, QString());
  }
  else
  {
    QString text = live ? tr("Remote server running") : tr("No remote server");

    if(IsWirelessAndroidHost(host))
      text += tr(" (Wireless)");

    if(host.IsConnected())
    {
      text += tr(" (Active Context)");
    }
    else if(host.IsVersionMismatch())
    {
      QString message = host.VersionMismatchError();
      text += QFormatStr(" (%1)").arg(message);
    }
    else if(host.IsBusy())
    {
      text += tr(" (Busy)");
    }

    node->setText(1, text);

    node->setIcon(0, live ? Icons::connect() : Icons::disconnect());
  }
}

void RemoteManager::addHost(RemoteHost host)
{
  RDTreeWidgetItem *node = new RDTreeWidgetItem({host.Name(), lit("...")});

  node->setItalic(true);
  node->setIcon(0, Icons::hourglass());
  setRemoteHost(node, host);

  ui->hosts->addTopLevelItem(node);
  ui->hosts->setSelectedItem(node);

  ui->refreshOne->setEnabled(false);
  ui->refreshAll->setEnabled(false);

  refreshHost(node);

  updateLookupsStatus();
}

void RemoteManager::syncHostList(const QString &preferredHost)
{
  QSet<QString> configuredHosts;
  for(const RemoteHost &host : m_Ctx.Config().GetRemoteHosts())
    configuredHosts.insert(QString::fromUtf8(host.Hostname().c_str()));

  for(int i = ui->hosts->topLevelItemCount() - 1; i >= 0; i--)
  {
    RDTreeWidgetItem *item = ui->hosts->topLevelItem(i);
    if(item == NULL)
      continue;

    QString hostname = item->tag().toString();
    if(hostname.isEmpty() || configuredHosts.contains(hostname))
      continue;

    item->clear();
    queueDelete(ui->hosts->takeTopLevelItem(i));
  }

  for(const RemoteHost &host : m_Ctx.Config().GetRemoteHosts())
  {
    QString hostname = QString::fromUtf8(host.Hostname().c_str());
    if(findHostItem(hostname) == NULL)
      addHost(host);
  }

  if(!preferredHost.isEmpty())
  {
    RDTreeWidgetItem *preferredItem = findHostItem(preferredHost);
    if(preferredItem)
    {
      ui->hosts->setSelectedItem(preferredItem);

      if(ui->refreshAll->isEnabled())
        refreshHostItem(preferredItem);
    }
  }

  on_hosts_itemSelectionChanged();
}

void RemoteManager::refreshHostItem(RDTreeWidgetItem *node)
{
  if(node == NULL || m_Lookups.available())
    return;

  ui->refreshOne->setEnabled(false);
  ui->refreshAll->setEnabled(false);

  node->clear();
  node->setItalic(true);
  node->setIcon(0, Icons::hourglass());

  refreshHost(node);
  updateLookupsStatus();
}

void RemoteManager::updateLookupsStatus()
{
  lookupsProgressFlow->setVisible(!ui->refreshAll->isEnabled());
  ui->progressCount->setText(tr("%1 lookups remaining").arg(m_Lookups.available()));
}

void RemoteManager::runRemoteServer(RDTreeWidgetItem *node)
{
  RemoteHost host = getRemoteHost(node);

  if(!host.IsValid())
  {
    m_Lookups.acquire();
    return;
  }

  host.Launch();

  // now refresh this host
  refreshHost(node);

  m_Lookups.acquire();
}

void RemoteManager::refreshHost(RDTreeWidgetItem *node)
{
  RemoteHost host = getRemoteHost(node);

  if(!host.IsValid())
    return;

  m_Lookups.release();

  // this function looks up the remote connections and for each one open
  // queries it for the API, target (usually executable name) and if any user is already connected
  LambdaThread *th = new LambdaThread([this, node, h = host]() {
    QByteArray username = GetSystemUsername().toUtf8();

    // make a mutable copy and check the status
    RemoteHost host = h;
    host.CheckStatus();

    GUIInvoke::call(this, [this, node, host]() {
      setRemoteServerLive(node, host.IsServerRunning(), host.IsBusy());
    });

    uint32_t nextIdent = 0;

    for(;;)
    {
      // just a sanity check to make sure we don't hit some unexpected case and infinite loop
      uint32_t prevIdent = nextIdent;

      nextIdent = RENDERDOC_EnumerateRemoteTargets(host.Hostname(), nextIdent);

      if(nextIdent == 0 || prevIdent >= nextIdent)
        break;

      ITargetControl *conn =
          RENDERDOC_CreateTargetControl(host.Hostname(), nextIdent, username.data(), false);

      if(conn)
      {
        QString target = conn->GetTarget();
        QString api = conn->GetAPI();
        QString busy = conn->GetBusyClient();

        QString running;

        if(!busy.isEmpty())
          running = tr("Running %1, %2 is connected").arg(api).arg(busy);
        else
          running = tr("Running %1").arg(api);

        RemoteConnect tag(host.Hostname(), host.Name(), nextIdent);

        GUIInvoke::call(this, [this, node, target, running, tag]() {
          RDTreeWidgetItem *child = new RDTreeWidgetItem({target, running});
          setRemoteConnect(child, tag);
          node->addChild(child);
          ui->hosts->expandItem(node);
        });

        conn->Shutdown();
      }
    }

    GUIInvoke::call(this, [node]() { node->setItalic(false); });

    GUIInvoke::call(this, [this]() {
      m_Lookups.acquire();
      updateStatus();
    });
  });
  th->selfDelete(true);
  th->start();
}

// don't allow the user to refresh until all pending connections have been checked
// (to stop flooding)
void RemoteManager::updateStatus()
{
  if(m_Lookups.available() == 0)
  {
    ui->refreshOne->setEnabled(true);
    ui->refreshAll->setEnabled(true);

    for(RDTreeWidgetItem *item : m_QueuedDeletes)
      delete item;
    m_QueuedDeletes.clear();

    // if the external ref is gone now, we can delete ourselves
    if(m_ExternalRef.available() == 0)
    {
      deleteLater();
      return;
    }
  }

  updateConnectButton();
  updateLookupsStatus();
}

void RemoteManager::connectToApp(RDTreeWidgetItem *node)
{
  if(node)
  {
    RemoteConnect connect = getRemoteConnect(node);

    if(connect.ident > 0)
    {
      LiveCapture *live =
          new LiveCapture(m_Ctx, connect.host, connect.friendly, connect.ident, m_Main, m_Main);
      m_Main->ShowLiveCapture(live);
      accept();
    }
  }
}

void RemoteManager::updateConnectButton()
{
  RDTreeWidgetItem *item = ui->hosts->selectedItem();

  if(item)
  {
    ui->connect->setEnabled(true);
    ui->connect->setText(tr("Connect to App"));

    RemoteHost host = getRemoteHost(item);

    if(host.IsValid())
    {
      if(host.IsLocalhost())
      {
        ui->connect->setText(tr("Run Server"));
        ui->connect->setEnabled(false);
      }
      else if(host.IsServerRunning())
      {
        ui->connect->setText(tr("Shutdown"));

        if(host.IsBusy() && !host.IsConnected())
          ui->connect->setEnabled(false);
      }
      else
      {
        ui->connect->setText(IsWirelessAndroidHost(host) ? tr("Start via ADB") : tr("Run Server"));

        if(host.RunCommand().isEmpty())
          ui->connect->setEnabled(false);
      }
    }
  }
  else
  {
    ui->connect->setEnabled(false);
  }
}

void RemoteManager::addNewHost()
{
  QString host = ui->hostname->text().trimmed();
  if(!host.isEmpty())
  {
    bool found = false;

    RemoteHost h = m_Ctx.Config().GetRemoteHost(host);

    if(!h.IsValid())
    {
      h = RemoteHost((rdcstr)host);
      h.SetRunCommand(ui->runCommand->text().trimmed());

      m_Ctx.Config().AddRemoteHost(h);
      m_Ctx.Config().Save();

      addHost(h);
    }
  }
  ui->hostname->setText(host);
  on_hostname_textEdited(host);
}

void RemoteManager::setRunCommand()
{
  RDTreeWidgetItem *item = ui->hosts->selectedItem();

  if(!item)
    return;

  RemoteHost h = getRemoteHost(item);

  if(h.IsValid())
  {
    h.SetRunCommand(ui->runCommand->text().trimmed());
    m_Ctx.Config().Save();
  }
}

void RemoteManager::queueDelete(RDTreeWidgetItem *item)
{
  // if there are refreshes pending, queue it for deletion when they complete.
  if(m_Lookups.available() > 0)
  {
    m_QueuedDeletes.push_back(item);
  }
  else
  {
    delete item;
  }
}

void RemoteManager::on_hosts_itemActivated(RDTreeWidgetItem *item, int column)
{
  RemoteConnect connect = getRemoteConnect(item);
  if(connect.ident > 0)
    connectToApp(item);
}

void RemoteManager::on_hosts_itemSelectionChanged()
{
  ui->hostnameLabel->setText(tr("Hostname:"));
  ui->hostnameLabel->setToolTip(QString());
  ui->runCommandLabel->setText(
      tr("Run Command: Configure a command to run that launches the remote server on this host."));
  ui->runCommandLabel->setToolTip(QString());

  ui->addUpdateHost->setText(tr("Add"));
  ui->addUpdateHost->setEnabled(true);
  ui->deleteHost->setEnabled(false);
  ui->refreshOne->setEnabled(false);
  ui->hostname->setEnabled(true);
  ui->runCommand->setEnabled(true);

  RDTreeWidgetItem *item = ui->hosts->selectedItem();

  RemoteHost host = getRemoteHost(item);

  ui->runCommand->setText(QString());

  if(host.IsValid())
  {
    if(ui->refreshAll->isEnabled())
      ui->refreshOne->setEnabled(true);

    ui->runCommand->setText(host.RunCommand());
    ui->hostname->setText(host.Name());

    ui->addUpdateHost->setText(tr("Update"));

    if(host.IsLocalhost() || host.Protocol())
    {
      // localhost and protocol-configured hosts cannot be updated or have their run command changed
      ui->addUpdateHost->setEnabled(false);
      ui->runCommand->setEnabled(false);

      if(IsWirelessAndroidHost(host))
      {
        ui->hostnameLabel->setText(tr("Android Endpoint:"));
        ui->hostnameLabel->setToolTip(tr("adb serial used for this wireless Android connection."));
        ui->hostname->setText(QString::fromUtf8(host.Hostname().c_str()));
        ui->runCommandLabel->setText(
            tr("Run Command: Launched automatically over adb for wireless Android hosts."));
        ui->runCommandLabel->setToolTip(
            tr("Wireless Android hosts are started through adb. No manual command is required."));
      }
    }
    else
    {
      // any other host can be deleted
      ui->deleteHost->setEnabled(true);
    }
  }

  updateConnectButton();
}

void RemoteManager::on_hostname_textEdited(const QString &text)
{
  RDTreeWidgetItem *node = NULL;

  for(int i = 0; i < ui->hosts->topLevelItemCount(); i++)
  {
    RDTreeWidgetItem *n = ui->hosts->topLevelItem(i);

    if(n->text(0) == text)
    {
      node = n;
      break;
    }
  }

  if(node)
    ui->hosts->setSelectedItem(node);
  else
    ui->hosts->clearSelection();
}

void RemoteManager::on_hosts_keyPress(QKeyEvent *event)
{
  if(event->key() == Qt::Key_Return || event->key() == Qt::Key_Enter)
  {
    if(ui->connect->isEnabled())
      on_connect_clicked();
  }

  if(event->key() == Qt::Key_Delete && ui->deleteHost->isEnabled())
    on_deleteHost_clicked();
}

void RemoteManager::on_hostname_keyPress(QKeyEvent *event)
{
  if(event->key() == Qt::Key_Return || event->key() == Qt::Key_Enter)
  {
    if(ui->addUpdateHost->isEnabled())
      on_addUpdateHost_clicked();
  }
}

void RemoteManager::on_runCommand_keyPress(QKeyEvent *event)
{
  if(event->key() == Qt::Key_Return || event->key() == Qt::Key_Enter)
  {
    if(ui->addUpdateHost->isEnabled())
      on_addUpdateHost_clicked();
  }
}

void RemoteManager::on_addUpdateHost_clicked()
{
  RDTreeWidgetItem *item = ui->hosts->selectedItem();
  if(getRemoteHost(item).IsValid())
    setRunCommand();
  else
    addNewHost();
}

void RemoteManager::on_refreshAll_clicked()
{
  if(m_Lookups.available())
    return;

  ui->refreshOne->setEnabled(false);
  ui->refreshAll->setEnabled(false);

  for(int i = 0; i < ui->hosts->topLevelItemCount(); i++)
  {
    RDTreeWidgetItem *n = ui->hosts->topLevelItem(i);

    n->clear();
    n->setItalic(true);
    n->setIcon(0, Icons::hourglass());

    refreshHost(n);
  }

  updateLookupsStatus();
}

void RemoteManager::on_refreshOne_clicked()
{
  RDTreeWidgetItem *n = ui->hosts->selectedItem();

  if(m_Lookups.available() || !n)
    return;

  ui->refreshOne->setEnabled(false);
  ui->refreshAll->setEnabled(false);

  {
    n->clear();
    n->setItalic(true);
    n->setIcon(0, Icons::hourglass());

    refreshHost(n);
  }

  updateLookupsStatus();
}

void RemoteManager::on_pairAndroid_clicked()
{
  AndroidWirelessSetupDialog setup(this);
  if(RDDialog::show(&setup) != QDialog::Accepted)
    return;

  WirelessAndroidConfig config = setup.Config();
  WirelessAndroidResult result;

  ui->pairAndroid->setEnabled(false);

  LambdaThread *th = new LambdaThread([this, config, &result]() {
    result.targetHost = lit("adb://") + config.ConnectEndpoint();

    if(config.HasPairing())
    {
      AdbCommandResult pairResult =
          RunAdbCommand({lit("pair"), config.PairEndpoint(), config.pairCode});

      if(!PairSucceeded(pairResult))
      {
        result.error = FormatAdbFailure(
            tr("Wireless pairing"),
            QFormatStr("adb pair %1 %2").arg(config.PairEndpoint()).arg(config.pairCode), pairResult);
        return;
      }
    }

    AdbCommandResult connectResult = RunAdbCommand({lit("connect"), config.ConnectEndpoint()});

    if(!ConnectSucceeded(connectResult))
    {
      result.error = FormatAdbFailure(tr("Wireless connection"),
                                      QFormatStr("adb connect %1").arg(config.ConnectEndpoint()),
                                      connectResult);
      return;
    }

    for(int attempt = 0; attempt < 8; attempt++)
    {
      m_Ctx.Config().UpdateEnumeratedProtocolDevices();

      if(m_Ctx.Config().GetRemoteHost(result.targetHost).IsValid())
      {
        result.enumerated = true;
        break;
      }

      QThread::msleep(250);
    }

    result.success = true;
  });

  th->setName(lit("Android wireless pairing"));
  th->start();

  ShowProgressDialog(this, tr("Running Android wireless pairing/connection, please wait..."),
                     [th]() { return !th->isRunning(); });

  th->wait();
  th->deleteLater();

  ui->pairAndroid->setEnabled(true);

  if(!result.success)
  {
    RDDialog::critical(this, tr("Android wireless setup failed"), result.error);
    return;
  }

  syncHostList(result.targetHost);

  if(!result.enumerated)
  {
    RDDialog::information(
        this, tr("Android connected"),
        tr("adb connected to %1, but the device hasn't appeared in the remote host list yet.\n\n"
           "Try Refresh All in a moment if it doesn't show up automatically.")
            .arg(config.ConnectEndpoint()));
  }
}

void RemoteManager::on_connect_clicked()
{
  RDTreeWidgetItem *node = ui->hosts->selectedItem();

  if(!node)
    return;

  RemoteConnect connect = getRemoteConnect(node);
  RemoteHost host = getRemoteHost(node);

  if(connect.ident > 0)
  {
    connectToApp(node);
  }
  else if(host.IsValid())
  {
    if(host.IsServerRunning())
    {
      QMessageBox::StandardButton res = RDDialog::question(
          this, tr("Remote server shutdown"),
          tr("Are you sure you wish to shut down running remote server on %1?").arg(host.Name()),
          RDDialog::YesNoCancel);

      if(res == QMessageBox::Cancel || res == QMessageBox::No)
        return;

      // shut down
      if(host.IsConnected())
      {
        m_Ctx.Replay().ShutdownServer();
        setRemoteServerLive(node, false, false);
      }
      else
      {
        ResultDetails result = {ResultCode::Succeeded};
        LambdaThread *th = new LambdaThread([&host, &result]() {
          IRemoteServer *server = NULL;
          result = host.Connect(&server);
          if(server)
            server->ShutdownServerAndConnection();
        });
        th->start();
        th->wait(500);
        if(th->isRunning())
        {
          ShowProgressDialog(this, tr("Shutting down server, please wait..."),
                             [th]() { return !th->isRunning(); });
        }
        th->deleteLater();

        setRemoteServerLive(node, false, false);

        if(!result.OK())
          RDDialog::critical(this, tr("Shutdown error"),
                             tr("Error shutting down remote server: %1").arg(result.Message()));
      }

      // kick off a thread to check the status
      LambdaThread *th = new LambdaThread([h = host]() {
        RemoteHost host = h;
        host.CheckStatus();
      });
      th->selfDelete(true);
      th->start();

      updateConnectButton();
    }
    else
    {
      // try to run
      ui->refreshOne->setEnabled(false);
      ui->refreshAll->setEnabled(false);

      // hold a ref for running the remote server
      m_Lookups.release();

      LambdaThread *th = new LambdaThread([this, node]() { runRemoteServer(node); });
      th->selfDelete(true);
      th->start();

      updateLookupsStatus();
    }
  }
}

void RemoteManager::on_deleteHost_clicked()
{
  RDTreeWidgetItem *item = ui->hosts->selectedItem();

  if(!item)
    return;

  RemoteHost host = getRemoteHost(item);

  int itemIdx = ui->hosts->indexOfTopLevelItem(item);

  // don't delete running instances on a host
  if(item->parent() != ui->hosts->invisibleRootItem() || itemIdx < 0 || !host.IsValid())
    return;

  QString hostname = item->text(0);

  if(hostname == lit("localhost"))
    return;

  QMessageBox::StandardButton res = RDDialog::question(
      this, tr("Deleting host"), tr("Are you sure you wish to delete %1?").arg(hostname),
      RDDialog::YesNoCancel);

  if(res == QMessageBox::Cancel || res == QMessageBox::No)
    return;

  if(res == QMessageBox::Yes)
  {
    RemoteHost h = m_Ctx.Config().GetRemoteHost(host.Hostname());
    if(!h.IsValid())
      return;

    // the host will be removed in queueDelete.
    m_Ctx.Config().RemoveRemoteHost(h);
    m_Ctx.Config().Save();

    item->clear();

    queueDelete(ui->hosts->takeTopLevelItem(itemIdx));

    ui->hosts->clearSelection();

    ui->hostname->setText(hostname);
    on_hostname_textEdited(hostname);
  }
}
