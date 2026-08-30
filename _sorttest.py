# -*- coding: utf-8 -*-
"""What happens to setIndexWidget widgets when QStandardItemModel.sort runs?

Checks: (a) do widgets follow their row or stay at the fixed row number?
(b) does modelReset fire? (c) after removeRows, are widgets deleted?
"""
import os
import sys

os.environ.pop("QT_QPA_PLATFORM", None)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from app.utils import Qt, setup_scaling  # noqa: E402

setup_scaling()
app = Qt.QtWidgets.QApplication(sys.argv)
W = Qt.QtWidgets
C = Qt.QtCore
Gui = Qt.QtGui

view = W.QTableView()
model = Qt.QtGui.QStandardItemModel(0, 2)
model.setHorizontalHeaderLabels(["n", "act"])
view.setModel(model)
view.show()

resets = []
removed = []
inserted = []
model.modelReset.connect(lambda: resets.append(1))
model.rowsRemoved.connect(lambda p, f, l: removed.append((f, l)))
model.rowsInserted.connect(lambda p, f, l: inserted.append((f, l)))

for i in range(10):
    model.appendRow([Qt.QtGui.QStandardItem(str(10 - i)),
                     Qt.QtGui.QStandardItem("")])
    lab = W.QLabel("W%d" % i)
    view.setIndexWidget(model.index(i, 1), lab)

app.processEvents()
print("before sort: row0 col1 widget text:",
      view.indexWidget(model.index(0, 1)).text())
print("before sort: row9 col1 widget text:",
      view.indexWidget(model.index(9, 1)).text())

model.sort(0, C.Qt.AscendingOrder)
app.processEvents()
print("modelReset fired on sort:", bool(resets))
print("after sort: row0 col1 widget:",
      view.indexWidget(model.index(0, 1)) and
      view.indexWidget(model.index(0, 1)).text())
print("after sort: row9 col1 widget:",
      view.indexWidget(model.index(9, 1)) and
      view.indexWidget(model.index(9, 1)).text())
print("row0 display now:", model.item(0, 0).text(),
      "(W0 was attached to the row with n=10)")

# removeRows with widgets present
n_before = len(removed)
model.removeRows(0, 5)
app.processEvents()
print("rowsRemoved fired:", len(removed) > n_before)
w = view.indexWidget(model.index(0, 1))
print("after removeRows: row0 widget:", w and w.text())

# setIndexWidget(idx, None) cleanup path
view.setIndexWidget(model.index(0, 1), None)
app.processEvents()
print("after setIndexWidget(None): row0 widget:",
      view.indexWidget(model.index(0, 1)))
print("DONE")
