import os
import threading
from time import monotonic

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from ifc_steel_generator.gui import MainWindow
from ifc_steel_generator.gui import PhaseScanWorker


def test_phase_scan_keeps_event_loop_alive_and_prevents_duplicate_jobs(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.output.setText(str(tmp_path))
    (tmp_path / "a.ifc").touch()
    (tmp_path / "b.ifc").touch()
    window.files.add_paths([str(tmp_path / "a.ifc"), str(tmp_path / "b.ifc")])
    release = threading.Event()
    calls = []
    selected = []
    main_thread = threading.get_ident()

    def detect(self, path):
        assert threading.get_ident() != main_thread
        calls.append(path)
        assert release.wait(5)
        return ["10", "20"]

    def choose(files, detected):
        assert threading.get_ident() == main_thread
        selected.append(detected)
        return None  # Cancel must re-enable both buttons.

    monkeypatch.setattr("ifc_steel_generator.parser.IfcParser.detect_phases", detect)
    monkeypatch.setattr(window, "choose_phases", choose)
    beats = []
    timer = QTimer()
    timer.timeout.connect(lambda: beats.append(1))
    timer.start(5)
    try:
        window.start()
        window.start_assemblies()
        assert not window.generate.isEnabled()
        deadline = monotonic() + 3
        while len(beats) < 3 and monotonic() < deadline:
            app.processEvents()
        assert len(beats) >= 3
        release.set()
        deadline = monotonic() + 5
        while not selected and monotonic() < deadline:
            app.processEvents()
        assert len(calls) == 2
        assert len(selected) == 1
        assert window.generate.isEnabled()
        assert window.generate_assemblies.isEnabled()
    finally:
        release.set()
        window.pool.waitForDone(5000)
        timer.stop()
        window.close()


def test_phase_cache_invalidates_changed_model(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "model.ifc"
    source.write_text("first")
    calls = []
    def detect(self, path):
        calls.append(path)
        return [str(len(calls))]
    monkeypatch.setattr("ifc_steel_generator.parser.IfcParser.detect_phases", detect)
    cache = {}
    output = []
    for change in (False, False, True):
        if change:
            source.write_text("changed model")
        worker = PhaseScanWorker([str(source)], cache)
        worker.signals.finished.connect(output.append)
        worker.run()
    assert len(calls) == 2
    assert [value[str(source)] for value in output] == [["1"], ["1"], ["2"]]
