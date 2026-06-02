import math
import os
import tempfile
import unittest

import HyperPlot


def write_csv(path, columns=("x", "a", "b"), rows=None):
    if rows is None:
        rows = [
            (0.0, 1.0, 2.0),
            (1.0, 2.0, 4.0),
            (2.0, 3.0, 6.0),
        ]
    with open(path, "w", encoding="utf-8") as file:
        file.write(",".join(columns) + "\n")
        for row in rows:
            file.write(",".join(str(value) for value in row) + "\n")


def visible_y_ticks(axis):
    lower, upper = sorted(axis.get_ylim())
    span = upper - lower
    tolerance = span * 1e-9
    return [
        tick
        for tick in axis.get_yticks()
        if lower - tolerance <= tick <= upper + tolerance
    ]


def normalized_y_positions(axis, ticks):
    lower, upper = axis.get_ylim()
    span = upper - lower
    return [(tick - lower) / span for tick in ticks]


def is_nice_step(step):
    step = abs(step)
    if step <= 0:
        return False
    exponent = math.floor(math.log10(step))
    mantissa = step / (10**exponent)
    return any(abs(mantissa - nice) < 1e-8 for nice in (1, 2, 2.5, 5, 10))


class HyperPlotBackendTest(unittest.TestCase):
    def test_csv_import_creates_plot_elements(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "data.csv")
            write_csv(csv_path)

            plotter = HyperPlot.HyperPlot()
            plotter.catch(csv_path)

            self.assertEqual(len(plotter._elements), 2)
            self.assertEqual([element.label for element in plotter._elements], ["a", "b"])
            self.assertEqual(plotter._elements[0].file_name, "data.csv")

    def test_list_catch_preserves_all_new_elements_in_last_catch(self):
        with tempfile.TemporaryDirectory() as tempdir:
            first = os.path.join(tempdir, "first.csv")
            second = os.path.join(tempdir, "second.csv")
            write_csv(first)
            write_csv(second)

            plotter = HyperPlot.HyperPlot()
            plotter.catch([first, second])

            self.assertEqual(len(plotter._elements), 4)
            self.assertEqual(len(plotter._last_catch), 4)
            self.assertEqual(
                [element.file_name for element in plotter._last_catch],
                ["first.csv", "first.csv", "second.csv", "second.csv"],
            )

    def test_batch_style_updates_labels_and_line_styles(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "data.csv")
            write_csv(csv_path)

            plotter = HyperPlot.HyperPlot()
            plotter.catch(csv_path)
            plotter._apply_styles(plotter._elements, "Experiment==-ro|Simulation==--b")

            self.assertEqual(plotter._elements[0].label, "Experiment")
            self.assertEqual(plotter._elements[0].ls, "-ro")
            self.assertEqual(plotter._elements[1].label, "Simulation")
            self.assertEqual(plotter._elements[1].ls, "--b")

    def test_background_group_consumes_one_batch_style_target(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "data.csv")
            write_csv(
                csv_path,
                columns=("x", "low", "high", "curve"),
                rows=[
                    (0.0, 1.0, 2.0, 1.5),
                    (1.0, 2.0, 3.0, 2.5),
                    (2.0, 3.0, 4.0, 3.5),
                ],
            )

            plotter = HyperPlot.HyperPlot()
            plotter.catch(csv_path)
            plotter.set_background([0, 1])
            plotter._apply_styles(
                plotter._elements,
                "Envelope==-r|Centerline==--b",
            )

            self.assertEqual(plotter._elements[0].background_label, "Envelope")
            self.assertEqual(plotter._elements[1].background_label, "Envelope")
            self.assertEqual(plotter._elements[0].ls, "-r")
            self.assertEqual(plotter._elements[1].ls, "-r")
            self.assertEqual(plotter._elements[2].label, "Centerline")
            self.assertEqual(plotter._elements[2].ls, "--b")

    def test_template_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tempdir:
            template_path = os.path.join(tempdir, "custom.hpt.json")
            plotter = HyperPlot.HyperPlot(
                fig_width_cm="12",
                background_alpha="0.4",
                color_palette={"r": "#111111"},
            )
            plotter.save_template(template_path)

            restored = HyperPlot.HyperPlot()
            restored.load_template(template_path)

            self.assertEqual(restored.fig_width_cm, 12.0)
            self.assertEqual(restored.background_alpha, 0.4)
            self.assertEqual(restored.color_palette["r"], "#111111")

    def test_default_axis_labels_use_names_and_units_only(self):
        plotter = HyperPlot.HyperPlot()

        self.assertEqual(plotter.axis_labels["strain"], "Engineering Strain [-]")
        self.assertEqual(plotter.axis_labels["Truestrain"], "True Strain [-]")
        self.assertEqual(plotter.axis_labels["Stretch"], "Stretch [-]")
        self.assertEqual(plotter.axis_labels["stress"], "True stress [MPa]")
        self.assertEqual(plotter.axis_labels["heat"], "Heat Generation [mW]")
        self.assertEqual(plotter.axis_labels["tempK"], "Temperature [K]")
        self.assertEqual(plotter.axis_labels["tempD"], "Temperature [$^\\circ$C]")

    def test_axes_box_has_requested_physical_size(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "data.csv")
            write_csv(csv_path)

            plotter = HyperPlot.HyperPlot(fig_width_cm=13, fig_height_cm=8)
            plotter.catch(csv_path)
            fig = plotter.get_plot([0], "")
            fig.canvas.draw()

            bbox = fig.axes[0].get_window_extent()
            self.assertAlmostEqual(bbox.width / bbox.height, 13 / 8, places=2)
            self.assertAlmostEqual(bbox.width / fig.dpi, 13 / 2.54, delta=0.01)
            self.assertAlmostEqual(bbox.height / fig.dpi, 8 / 2.54, delta=0.01)

    def test_twin_axes_box_has_requested_physical_size(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "data.csv")
            write_csv(csv_path)

            plotter = HyperPlot.HyperPlot(fig_width_cm=13, fig_height_cm=8)
            plotter.catch(csv_path)
            plotter.toggle_axis([1])
            fig = plotter.get_plot([0, 1], "Left==-b|Right==-r")
            fig.canvas.draw()

            bbox = fig.axes[0].get_window_extent()
            self.assertAlmostEqual(bbox.width / fig.dpi, 13 / 2.54, delta=0.01)
            self.assertAlmostEqual(bbox.height / fig.dpi, 8 / 2.54, delta=0.01)

    def test_right_axis_uses_nice_ticks_aligned_to_left_grid(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "data.csv")
            write_csv(
                csv_path,
                columns=("x", "left", "right"),
                rows=[
                    (0.0, 0.0, 23.44),
                    (1.0, 2.5, 24.11),
                    (2.0, 5.0, 24.72),
                    (3.0, 7.5, 25.68),
                ],
            )

            plotter = HyperPlot.HyperPlot(fig_width_cm=13, fig_height_cm=8)
            plotter.catch(csv_path)
            plotter.toggle_axis([1])
            fig = plotter.get_plot([0, 1], "Left==-b|Right==-r")
            fig.canvas.draw()

            left_axis, right_axis = fig.axes
            left_ticks = visible_y_ticks(left_axis)
            right_ticks = visible_y_ticks(right_axis)
            self.assertEqual(len(left_ticks), len(right_ticks))

            left_positions = normalized_y_positions(left_axis, left_ticks)
            right_positions = normalized_y_positions(right_axis, right_ticks)
            for left_position, right_position in zip(left_positions, right_positions):
                self.assertAlmostEqual(left_position, right_position, places=8)

            right_steps = [
                right_ticks[index + 1] - right_ticks[index]
                for index in range(len(right_ticks) - 1)
            ]
            self.assertTrue(all(abs(step - right_steps[0]) < 1e-8 for step in right_steps))
            self.assertTrue(is_nice_step(right_steps[0]))

    def test_svg_state_roundtrip(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "data.csv")
            write_csv(csv_path)

            plotter = HyperPlot.HyperPlot(outpath=tempdir + os.sep)
            plotter.catch(csv_path)
            plotter.out([0], "Experiment==-r", "state.svg")

            restored = HyperPlot.HyperPlot()
            restored_count = restored.catch_svg(os.path.join(tempdir, "state.svg"))

            self.assertEqual(restored_count, 1)
            self.assertEqual(restored._elements[0].label, "Experiment")
            self.assertEqual(restored._elements[0].ls, "-r")

    def test_png_state_roundtrip_if_pillow_is_available(self):
        try:
            import PIL  # noqa: F401
        except ImportError:
            self.skipTest("Pillow is not available.")

        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "data.csv")
            write_csv(csv_path)

            plotter = HyperPlot.HyperPlot(outpath=tempdir + os.sep)
            plotter.catch(csv_path)
            plotter.out([0], "Experiment==-r", "state.png")

            restored = HyperPlot.HyperPlot()
            restored_count = restored.catch_png(os.path.join(tempdir, "state.png"))

            self.assertEqual(restored_count, 1)
            self.assertEqual(restored._elements[0].label, "Experiment")
            self.assertEqual(restored._elements[0].ls, "-r")


if __name__ == "__main__":
    unittest.main()
