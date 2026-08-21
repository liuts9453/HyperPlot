import os
import tempfile
import unittest

from electron.backend import HyperPlotBridge


def write_csv(path):
    with open(path, "w", encoding="utf-8") as file:
        file.write("time,experiment,simulation\n")
        file.write("0,0,0\n")
        file.write("1,2,1.8\n")
        file.write("2,4,4.1\n")


class ElectronBackendBridgeTest(unittest.TestCase):
    def setUp(self):
        self.bridge = HyperPlotBridge()

    def test_import_preview_and_mutation_round_trip(self):
        with tempfile.TemporaryDirectory() as tempdir:
            source = os.path.join(tempdir, "curves.csv")
            write_csv(source)

            imported = self.bridge.dispatch(
                "import_files",
                {"paths": [source], "fastCsv": False, "legends": ""},
            )
            self.assertEqual(len(imported["state"]["elements"]), 2)

            toggled = self.bridge.dispatch("toggle_axis", {"indices": [1]})
            self.assertEqual(
                toggled["state"]["elements"][1]["axis"],
                "right",
            )

            preview = self.bridge.dispatch(
                "preview",
                {
                    "indices": [0, 1],
                    "legends": "Experiment==-ro|Simulation==--b",
                },
            )
            self.assertTrue(
                preview["preview"].startswith("data:image/svg+xml;base64,")
            )
            self.assertEqual(
                preview["state"]["elements"][0]["label"],
                "Experiment",
            )

    def test_exact_export_paths_are_honored(self):
        with tempfile.TemporaryDirectory() as tempdir:
            source = os.path.join(tempdir, "curves.csv")
            output_svg = os.path.join(tempdir, "result.svg")
            output_csv = os.path.join(tempdir, "result.csv")
            write_csv(source)
            self.bridge.dispatch(
                "import_files",
                {"paths": [source], "fastCsv": False},
            )

            saved = self.bridge.dispatch(
                "save_plot",
                {"path": output_svg, "indices": [0, 1], "legends": ""},
            )
            exported = self.bridge.dispatch(
                "export_csv",
                {"path": output_csv, "indices": [0, 1]},
            )

            self.assertEqual(saved["path"], output_svg)
            self.assertEqual(exported["path"], output_csv)
            self.assertTrue(os.path.isfile(output_svg))
            self.assertTrue(os.path.isfile(output_csv))


if __name__ == "__main__":
    unittest.main()
