from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QObject, QRunnable, QSettings, QThreadPool, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QDialog,
    QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QVBoxLayout, QWidget)

from .batch import process_batch


class WorkerSignals(QObject):
    message = Signal(str)
    progress = Signal(int, int)
    finished = Signal(object)
    fatal = Signal(str)


class BatchWorker(QRunnable):
    def __init__(self, files: list[str], output: str, density: float,
                 phases: dict[str, tuple[str, ...] | None]):
        super().__init__(); self.files=files; self.output=output; self.density=density; self.phases=phases
        self.signals=WorkerSignals()

    def run(self) -> None:
        try:
            value=process_batch(self.files,self.output,self.density,self.signals.message.emit,self.signals.progress.emit,self.phases)
            self.signals.finished.emit(value)
        except Exception as exc:
            self.signals.fatal.emit(str(exc))


class DropList(QListWidget):
    def __init__(self):
        super().__init__(); self.setAcceptDrops(True); self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setToolTip("Przeciągnij tutaj pliki IFC")

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls(): event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        self.add_paths([u.toLocalFile() for u in event.mimeData().urls()]); event.acceptProposedAction()

    def add_paths(self, paths: list[str]) -> None:
        current={self.item(i).text() for i in range(self.count())}
        for raw in paths:
            path=Path(raw)
            candidates=path.glob("*.ifc") if path.is_dir() else [path]
            for candidate in candidates:
                value=str(candidate.resolve())
                if candidate.suffix.lower()==".ifc" and value not in current:
                    self.addItem(value); current.add(value)


class PhaseSelectionDialog(QDialog):
    def __init__(self, filename: str, phases: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Wybór faz")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f"{filename}\nZaznacz jedną lub kilka faz do zestawienia:", self,
        ))
        self.phase_list = QListWidget(self)
        for phase in phases:
            item = QListWidgetItem(f"Faza {phase}", self.phase_list)
            item.setData(Qt.ItemDataRole.UserRole, phase)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
        layout.addWidget(self.phase_list)
        selection_buttons = QHBoxLayout()
        select_all = QPushButton("Zaznacz wszystkie", self)
        clear_all = QPushButton("Odznacz wszystkie", self)
        select_all.clicked.connect(lambda: self._set_all(Qt.CheckState.Checked))
        clear_all.clicked.connect(lambda: self._set_all(Qt.CheckState.Unchecked))
        selection_buttons.addWidget(select_all)
        selection_buttons.addWidget(clear_all)
        layout.addLayout(selection_buttons)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self._accept_selection)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _set_all(self, state: Qt.CheckState) -> None:
        for index in range(self.phase_list.count()):
            self.phase_list.item(index).setCheckState(state)

    def selected_phases(self) -> tuple[str, ...]:
        return tuple(
            str(self.phase_list.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(self.phase_list.count())
            if self.phase_list.item(index).checkState() == Qt.CheckState.Checked
        )

    def _accept_selection(self) -> None:
        if not self.selected_phases():
            QMessageBox.warning(self, "Brak faz", "Zaznacz co najmniej jedną fazę.")
            return
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.settings=QSettings("Jumo", "IFC Steel List Generator")
        self.pool=QThreadPool.globalInstance(); self.setWindowTitle("IFC Steel List Generator")
        self.resize(self.settings.value("size", self.size()))
        root=QWidget(); layout=QVBoxLayout(root); self.setCentralWidget(root)
        title=QLabel("IFC Steel List Generator"); title.setStyleSheet("font-size:24px;font-weight:bold;color:#17365d")
        hint=QLabel("Przeciągnij tutaj pliki IFC"); hint.setStyleSheet("font-size:16px;font-weight:bold")
        layout.addWidget(title); layout.addWidget(hint); self.files=DropList(); self.files.setMinimumHeight(180); layout.addWidget(self.files)
        buttons=QHBoxLayout()
        for text,slot in (("Dodaj pliki IFC",self.add_files),("Dodaj folder",self.add_folder),("Usuń zaznaczone",self.remove_selected),("Wyczyść listę",self.files.clear)):
            button=QPushButton(text); button.clicked.connect(slot); buttons.addWidget(button)
        layout.addLayout(buttons)
        form=QFormLayout(); out_row=QHBoxLayout(); self.output=QLabel(self.settings.value("output", str(Path.home()/"Documents")))
        choose=QPushButton("Wybierz"); choose.clicked.connect(self.choose_output); out_row.addWidget(self.output,1); out_row.addWidget(choose)
        form.addRow("Folder wynikowy:",out_row); self.density=QDoubleSpinBox(); self.density.setRange(1,30000); self.density.setDecimals(2); self.density.setValue(float(self.settings.value("density",7850)))
        form.addRow("Gęstość stali [kg/m³]:",self.density); layout.addLayout(form)
        self.open_folder=QCheckBox("Otwórz folder po zakończeniu"); self.open_folder.setChecked(True); layout.addWidget(self.open_folder)
        self.generate=QPushButton("GENERUJ ZESTAWIENIA"); self.generate.setMinimumHeight(48); self.generate.setStyleSheet("font-size:16px;font-weight:bold;background:#4472c4;color:white")
        self.generate.clicked.connect(self.start); layout.addWidget(self.generate)
        self.progress=QProgressBar(); self.progress.setRange(0,1); layout.addWidget(self.progress)
        self.stage=QLabel("Gotowy"); layout.addWidget(self.stage); self.log=QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumHeight(160); layout.addWidget(self.log)

    def add_files(self):
        paths,_=QFileDialog.getOpenFileNames(self,"Dodaj pliki IFC",self.settings.value("input",""),"IFC (*.ifc)")
        if paths: self.settings.setValue("input",str(Path(paths[0]).parent)); self.files.add_paths(paths)

    def add_folder(self):
        path=QFileDialog.getExistingDirectory(self,"Dodaj folder",self.settings.value("input",""))
        if path: self.settings.setValue("input",path); self.files.add_paths([path])

    def remove_selected(self):
        for item in self.files.selectedItems(): self.files.takeItem(self.files.row(item))

    def choose_output(self):
        path=QFileDialog.getExistingDirectory(self,"Folder wynikowy",self.output.text())
        if path: self.output.setText(path); self.settings.setValue("output",path)

    def append_log(self,message: str):
        self.stage.setText(message); self.log.appendPlainText(f"[{datetime.now():%H:%M:%S}] {message}")

    def start(self):
        files=[self.files.item(i).text() for i in range(self.files.count())]
        if not files: QMessageBox.warning(self,"Brak plików","Dodaj co najmniej jeden plik IFC."); return
        if not Path(self.output.text()).is_dir(): QMessageBox.warning(self,"Błędny folder","Wybierz istniejący folder wynikowy."); return
        phases = self.choose_phases(files)
        if phases is None:
            return
        self.generate.setEnabled(False); self.progress.setRange(0,0); self.settings.setValue("density",self.density.value())
        self.progress.setRange(0,len(files)); self.progress.setValue(0)
        worker=BatchWorker(files,self.output.text(),self.density.value(),phases); worker.signals.message.connect(self.append_log); worker.signals.progress.connect(self.update_progress); worker.signals.finished.connect(self.done); worker.signals.fatal.connect(self.failed); self.pool.start(worker)

    def choose_phases(self, files: list[str]) -> dict[str, tuple[str, ...] | None] | None:
        from .parser import IfcParser
        parser = IfcParser(); selections: dict[str, tuple[str, ...] | None] = {}
        for file in files:
            try:
                detected = parser.detect_phases(file)
            except Exception as exc:
                QMessageBox.critical(self, "Błąd odczytu faz", f"{Path(file).name}\n{exc}")
                return None
            if not detected:
                selections[file] = None
                continue
            dialog = PhaseSelectionDialog(Path(file).name, detected, self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return None
            selected = dialog.selected_phases()
            selections[file] = None if len(selected) == len(detected) else selected
        return selections

    def update_progress(self, value: int, total: int):
        self.progress.setRange(0,total); self.progress.setValue(value)

    def done(self,results):
        self.generate.setEnabled(True); self.progress.setRange(0,1); self.progress.setValue(1)
        good=sum(r.error is None for r in results); profiles=sum(r.profiles for r in results); plates=sum(r.plates for r in results); mass=sum(r.mass_kg for r in results); errors=len(results)-good; warnings=sum(len(r.warnings) for r in results)
        text=f"Przetworzono: {len(results)}\nPoprawnie: {good}\nBłędy: {errors}\nProfile: {profiles}\nBlachy: {plates}\nMasa: {mass/1000:.3f} t\nOstrzeżenia: {warnings}\nFolder: {self.output.text()}"
        QMessageBox.information(self,"Zakończono",text); self.stage.setText("Zakończono")
        if self.open_folder.isChecked(): QDesktopServices.openUrl(QUrl.fromLocalFile(self.output.text()))

    def failed(self,message: str):
        self.generate.setEnabled(True); self.progress.setRange(0,1); self.append_log(message); QMessageBox.critical(self,"Błąd",message)

    def closeEvent(self,event):
        self.settings.setValue("size",self.size()); super().closeEvent(event)
