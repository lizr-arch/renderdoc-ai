#pragma once

#include <QStyledItemDelegate>
#include <QWidget>

class AnalyzerScoreRingWidget : public QWidget
{
  Q_OBJECT

public:
  explicit AnalyzerScoreRingWidget(QWidget *parent = 0);

  void SetScore(double value);
  void SetLabel(const QString &label);

  QSize sizeHint() const override;

protected:
  void paintEvent(QPaintEvent *event) override;

private:
  double m_Score = 0.0;
  QString m_Label;
};

class AnalyzerSeverityBadgeDelegate : public QStyledItemDelegate
{
  Q_OBJECT

public:
  explicit AnalyzerSeverityBadgeDelegate(QObject *parent = 0);

  void paint(QPainter *painter, const QStyleOptionViewItem &option,
             const QModelIndex &index) const override;
  QSize sizeHint(const QStyleOptionViewItem &option,
                 const QModelIndex &index) const override;
};

class AnalyzerImpactBarDelegate : public QStyledItemDelegate
{
  Q_OBJECT

public:
  explicit AnalyzerImpactBarDelegate(QObject *parent = 0);

  void paint(QPainter *painter, const QStyleOptionViewItem &option,
             const QModelIndex &index) const override;
};

class AnalyzerTimingBadgeWidget : public QWidget
{
  Q_OBJECT

public:
  explicit AnalyzerTimingBadgeWidget(QWidget *parent = nullptr);

  void SetConfidence(const QString &confidence);
  QSize sizeHint() const override;

protected:
  void paintEvent(QPaintEvent *event) override;

private:
  QString m_Confidence;
};
