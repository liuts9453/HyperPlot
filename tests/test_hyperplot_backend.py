import csv
import math
import os
import tempfile
import unittest

import HyperPlot
from hyperplot.settings import PLOT_RC_PARAMS


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


def assert_right_axis_ticks_are_aligned_and_nice(test_case, left_axis, right_axis):
    left_ticks = visible_y_ticks(left_axis)
    right_ticks = visible_y_ticks(right_axis)
    test_case.assertEqual(len(left_ticks), len(right_ticks))

    left_positions = normalized_y_positions(left_axis, left_ticks)
    right_positions = normalized_y_positions(right_axis, right_ticks)
    for left_position, right_position in zip(left_positions, right_positions):
        test_case.assertAlmostEqual(left_position, right_position, places=8)

    right_steps = [
        right_ticks[index + 1] - right_ticks[index]
        for index in range(len(right_ticks) - 1)
    ]
    test_case.assertTrue(
        all(abs(step - right_steps[0]) < 1e-8 for step in right_steps)
    )
    test_case.assertTrue(is_nice_step(right_steps[0]))


class HyperPlotBackendTest(unittest.TestCase):
    def test_default_plot_typography_matches_cmame_body_text(self):
        self.assertEqual(PLOT_RC_PARAMS["font.size"], 10)
        self.assertEqual(PLOT_RC_PARAMS["xtick.labelsize"], 10)
        self.assertEqual(PLOT_RC_PARAMS["ytick.labelsize"], 10)
        self.assertEqual(PLOT_RC_PARAMS["legend.fontsize"], 10)
        self.assertEqual(PLOT_RC_PARAMS["axes.labelsize"], 10)
        self.assertEqual(PLOT_RC_PARAMS["font.serif"][0], "Times New Roman")
        self.assertIn("TeX Gyre Termes", PLOT_RC_PARAMS["font.serif"])

    def test_csv_import_creates_plot_elements(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "data.csv")
            write_csv(csv_path)

            plotter = HyperPlot.HyperPlot()
            plotter.catch(csv_path)

            self.assertEqual(len(plotter._elements), 2)
            self.assertEqual([element.label for element in plotter._elements], ["a", "b"])
            self.assertEqual(plotter._elements[0].file_name, "data.csv")
            self.assertEqual(plotter._elements[0].source_path, os.path.abspath(csv_path))

    def test_same_named_csvs_from_different_paths_keep_distinct_elements(self):
        with tempfile.TemporaryDirectory() as tempdir:
            first_dir = os.path.join(tempdir, "first")
            second_dir = os.path.join(tempdir, "second")
            os.makedirs(first_dir)
            os.makedirs(second_dir)
            first_path = os.path.join(first_dir, "data.csv")
            second_path = os.path.join(second_dir, "data.csv")
            write_csv(
                first_path,
                rows=[
                    (0.0, 1.0, 2.0),
                    (1.0, 2.0, 4.0),
                ],
            )
            write_csv(
                second_path,
                rows=[
                    (0.0, 10.0, 20.0),
                    (1.0, 20.0, 40.0),
                ],
            )

            plotter = HyperPlot.HyperPlot()
            plotter.catch([first_path, second_path])

            self.assertEqual(len(plotter._elements), 4)
            self.assertEqual(
                {element.source_path for element in plotter._elements},
                {os.path.abspath(first_path), os.path.abspath(second_path)},
            )
            self.assertEqual(
                len({element.signature for element in plotter._elements}),
                4,
            )

    def test_reimport_and_reload_identify_same_named_csvs_by_full_path(self):
        with tempfile.TemporaryDirectory() as tempdir:
            first_dir = os.path.join(tempdir, "first")
            second_dir = os.path.join(tempdir, "second")
            os.makedirs(first_dir)
            os.makedirs(second_dir)
            first_path = os.path.join(first_dir, "data.csv")
            second_path = os.path.join(second_dir, "data.csv")
            write_csv(first_path)
            write_csv(
                second_path,
                rows=[
                    (0.0, 10.0, 20.0),
                    (1.0, 20.0, 40.0),
                    (2.0, 30.0, 60.0),
                ],
            )

            plotter = HyperPlot.HyperPlot()
            plotter.catch([first_path, second_path])
            first_a = next(
                element
                for element in plotter._elements
                if element.source_path == os.path.abspath(first_path)
                and element.y_label == "a"
            )
            second_a = next(
                element
                for element in plotter._elements
                if element.source_path == os.path.abspath(second_path)
                and element.y_label == "a"
            )
            first_signature = first_a.signature
            second_signature = second_a.signature
            first_a.label = "First A"
            first_a.ls = "--r"
            second_a.label = "Second A"
            second_a.ls = "-.b"
            second_a.axis = "right"

            write_csv(
                first_path,
                rows=[
                    (0.0, 101.0, 102.0),
                    (1.0, 201.0, 204.0),
                ],
            )
            plotter.catch(first_path)

            self.assertEqual(len(plotter._elements), 4)
            reimported_first_a = next(
                element
                for element in plotter._elements
                if element.source_path == os.path.abspath(first_path)
                and element.y_label == "a"
            )
            untouched_second_a = next(
                element
                for element in plotter._elements
                if element.source_path == os.path.abspath(second_path)
                and element.y_label == "a"
            )
            self.assertEqual(reimported_first_a.signature, first_signature)
            self.assertEqual(untouched_second_a.signature, second_signature)
            self.assertNotEqual(first_signature, second_signature)
            self.assertEqual(list(reimported_first_a.y), [101.0, 201.0])
            self.assertEqual(list(untouched_second_a.y), [10.0, 20.0, 30.0])

            plotter.reload_all()
            elements_by_source_and_column = {
                (element.source_path, element.y_label): element
                for element in plotter._elements
            }
            reloaded_first_a = elements_by_source_and_column[
                (os.path.abspath(first_path), "a")
            ]
            reloaded_second_a = elements_by_source_and_column[
                (os.path.abspath(second_path), "a")
            ]
            self.assertEqual(reloaded_first_a.label, "First A")
            self.assertEqual(reloaded_first_a.ls, "--r")
            self.assertEqual(reloaded_second_a.label, "Second A")
            self.assertEqual(reloaded_second_a.ls, "-.b")
            self.assertEqual(reloaded_second_a.axis, "right")

    def test_set_x_axis_swaps_selected_y_with_previous_x(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "data.csv")
            write_csv(
                csv_path,
                columns=("time", "stress", "temperature"),
                rows=[
                    (0.0, 10.0, 100.0),
                    (1.0, 11.0, 101.0),
                    (2.0, 12.0, 102.0),
                ],
            )

            plotter = HyperPlot.HyperPlot()
            plotter.catch(csv_path)
            result = plotter.set_x_axis(1)

            self.assertEqual(result["x_label"], "temperature")
            self.assertEqual(result["file_name"], "data.csv")
            self.assertEqual(result["curve_count"], 2)
            self.assertEqual(
                [element.y_label for element in plotter._elements],
                ["stress", "time"],
            )
            self.assertEqual(plotter._elements[1].label, "time")
            self.assertEqual(list(plotter._elements[1].y), [0.0, 1.0, 2.0])
            for element in plotter._elements:
                self.assertEqual(element.x_label, "temperature")
                self.assertEqual(list(element.x), [100.0, 101.0, 102.0])

    def test_set_x_axis_updates_only_the_selected_source_file(self):
        with tempfile.TemporaryDirectory() as tempdir:
            first_dir = os.path.join(tempdir, "first")
            second_dir = os.path.join(tempdir, "second")
            os.makedirs(first_dir)
            os.makedirs(second_dir)
            first_path = os.path.join(first_dir, "data.csv")
            second_path = os.path.join(second_dir, "data.csv")
            write_csv(
                first_path,
                columns=("time", "a", "b"),
                rows=[
                    (0.0, 1.0, 10.0),
                    (1.0, 2.0, 20.0),
                ],
            )
            write_csv(
                second_path,
                columns=("step", "c", "d"),
                rows=[
                    (5.0, 50.0, 500.0),
                    (6.0, 60.0, 600.0),
                ],
            )

            plotter = HyperPlot.HyperPlot()
            plotter.catch([first_path, second_path])
            second_elements_before = [
                (
                    element.x_label,
                    element.y_label,
                    list(element.x),
                    list(element.y),
                )
                for element in plotter._elements
                if element.source_path == os.path.abspath(second_path)
            ]

            result = plotter.set_x_axis(1)

            self.assertEqual(result["file_name"], "data.csv")
            self.assertEqual(result["x_label"], "b")
            self.assertEqual(result["curve_count"], 2)
            first_elements = [
                element
                for element in plotter._elements
                if element.source_path == os.path.abspath(first_path)
            ]
            self.assertEqual(
                [element.x_label for element in first_elements],
                ["b", "b"],
            )
            self.assertTrue(
                all(list(element.x) == [10.0, 20.0] for element in first_elements)
            )
            second_elements_after = [
                (
                    element.x_label,
                    element.y_label,
                    list(element.x),
                    list(element.y),
                )
                for element in plotter._elements
                if element.source_path == os.path.abspath(second_path)
            ]
            self.assertEqual(second_elements_after, second_elements_before)

    def test_set_x_axis_can_switch_back_to_the_default_x_column(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "data.csv")
            write_csv(
                csv_path,
                columns=("x", "a", "b"),
                rows=[
                    (0.0, 1.0, 10.0),
                    (1.0, 2.0, 20.0),
                ],
            )

            plotter = HyperPlot.HyperPlot()
            plotter.catch(csv_path)
            plotter.set_x_axis(1)
            old_x_index = next(
                index
                for index, element in enumerate(plotter._elements)
                if element.y_label == "x"
            )

            result = plotter.set_x_axis(old_x_index)

            self.assertEqual(result["x_label"], "x")
            self.assertEqual(result["curve_count"], 2)
            self.assertEqual(
                [element.y_label for element in plotter._elements],
                ["a", "b"],
            )
            self.assertEqual(
                [list(element.y) for element in plotter._elements],
                [[1.0, 2.0], [10.0, 20.0]],
            )
            for element in plotter._elements:
                self.assertEqual(element.x_label, "x")
                self.assertEqual(list(element.x), [0.0, 1.0])

    def test_catching_the_same_source_again_keeps_its_custom_x_axis(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "data.csv")
            write_csv(csv_path)

            plotter = HyperPlot.HyperPlot()
            plotter.catch(csv_path)
            plotter.set_x_axis(1)

            plotter.catch(csv_path)

            self.assertEqual(len(plotter._elements), 2)
            self.assertEqual(
                [element.y_label for element in plotter._elements],
                ["a", "x"],
            )
            self.assertEqual(
                {element.x_label for element in plotter._elements},
                {"b"},
            )

    def test_set_x_axis_rejects_non_numeric_columns_without_mutating_data(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "data.csv")
            write_csv(
                csv_path,
                columns=("x", "value", "category"),
                rows=[
                    (0.0, 1.0, "first"),
                    (1.0, 2.0, "second"),
                ],
            )

            plotter = HyperPlot.HyperPlot()
            plotter.catch(csv_path)
            before = [
                (element.x_label, element.y_label, list(element.x), list(element.y))
                for element in plotter._elements
            ]

            with self.assertRaisesRegex(ValueError, "must contain numeric values"):
                plotter.set_x_axis(1)

            after = [
                (element.x_label, element.y_label, list(element.x), list(element.y))
                for element in plotter._elements
            ]
            self.assertEqual(after, before)

    def test_reload_all_preserves_custom_x_axis_and_other_curve_styles(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "data.csv")
            write_csv(
                csv_path,
                columns=("time", "a", "b", "c"),
                rows=[
                    (0.0, 1.0, 10.0, 100.0),
                    (1.0, 2.0, 20.0, 200.0),
                ],
            )

            plotter = HyperPlot.HyperPlot()
            plotter.catch(csv_path)
            plotter.update_element_style(
                0,
                label="Styled A",
                ls="--r",
                axis="right",
            )
            plotter.update_element_style(
                2,
                label="Styled C",
                ls="-.b",
                axis="left",
            )
            plotter.set_x_axis(1)

            write_csv(
                csv_path,
                columns=("time", "a", "b", "c"),
                rows=[
                    (5.0, 11.0, 110.0, 101.0),
                    (6.0, 12.0, 120.0, 201.0),
                ],
            )
            result = plotter.reload_all()

            self.assertEqual(result["element_count"], 3)
            self.assertEqual(result["paths"], [os.path.abspath(csv_path)])
            self.assertEqual(
                {element.x_label for element in plotter._elements},
                {"b"},
            )
            self.assertTrue(
                all(
                    list(element.x) == [110.0, 120.0]
                    for element in plotter._elements
                )
            )
            elements_by_y_label = {
                element.y_label: element for element in plotter._elements
            }
            self.assertEqual(set(elements_by_y_label), {"time", "a", "c"})
            self.assertEqual(
                [element.y_label for element in plotter._elements],
                ["a", "time", "c"],
            )
            self.assertEqual(list(elements_by_y_label["time"].y), [5.0, 6.0])
            self.assertEqual(list(elements_by_y_label["a"].y), [11.0, 12.0])
            self.assertEqual(elements_by_y_label["a"].label, "Styled A")
            self.assertEqual(elements_by_y_label["a"].ls, "--r")
            self.assertEqual(elements_by_y_label["a"].axis, "right")
            self.assertEqual(list(elements_by_y_label["c"].y), [101.0, 201.0])
            self.assertEqual(elements_by_y_label["c"].label, "Styled C")
            self.assertEqual(elements_by_y_label["c"].ls, "-.b")
            self.assertEqual(elements_by_y_label["c"].axis, "left")

    def test_export_selected_elements_csv_uses_shared_x_when_possible(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "data.csv")
            export_path = os.path.join(tempdir, "selected.csv")
            write_csv(csv_path)

            plotter = HyperPlot.HyperPlot()
            plotter.catch(csv_path)
            result_path = plotter.export_elements_csv([0, 1], export_path)

            with open(result_path, newline="", encoding="utf-8") as file:
                rows = list(csv.reader(file))

            self.assertEqual(result_path, export_path)
            self.assertEqual(rows[0], ["x", "a", "b"])
            self.assertEqual(
                rows[1:],
                [
                    ["0.0", "1.0", "2.0"],
                    ["1.0", "2.0", "4.0"],
                    ["2.0", "3.0", "6.0"],
                ],
            )

    def test_export_selected_elements_csv_keeps_separate_x_columns(self):
        with tempfile.TemporaryDirectory() as tempdir:
            export_path = os.path.join(tempdir, "selected.csv")
            plotter = HyperPlot.HyperPlot()
            plotter._elements = [
                HyperPlot.PlotElement(
                    x=[0.0, 1.0],
                    y=[10.0, 11.0],
                    label="low",
                    x_label="time",
                ),
                HyperPlot.PlotElement(
                    x=[0.0, 2.0],
                    y=[20.0, 22.0],
                    label="high",
                    x_label="time",
                ),
            ]

            plotter.export_elements_csv([0, 1], export_path)

            with open(export_path, newline="", encoding="utf-8") as file:
                rows = list(csv.reader(file))

            self.assertEqual(rows[0], ["low time", "low", "high time", "high"])
            self.assertEqual(
                rows[1:],
                [
                    ["0.0", "10.0", "0.0", "20.0"],
                    ["1.0", "11.0", "2.0", "22.0"],
                ],
            )

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

    def test_background_group_connects_curve_heads_into_polygon(self):
        plotter = HyperPlot.HyperPlot(background_points=7)
        plotter._elements = [
            HyperPlot.PlotElement(
                [0.0, 1.0, 2.0],
                [0.0, 0.0, 0.0],
                label="lower",
                ls="-r",
                is_background=True,
                background_group="group",
                background_label="Envelope",
            ),
            HyperPlot.PlotElement(
                [1.0, 2.0, 3.0],
                [2.0, 2.0, 2.0],
                label="upper",
                ls="-r",
                is_background=True,
                background_group="group",
                background_label="Envelope",
            ),
        ]

        fig = plotter.get_plot([0, 1], "")
        ax = fig.axes[0]
        envelope = ax.collections[0]
        vertices = envelope.get_paths()[0].vertices
        xs = [vertex[0] for vertex in vertices]
        ys_at_half = sorted(
            {
                round(vertex[1], 6)
                for vertex in vertices
                if abs(vertex[0] - 0.5) < 1e-9
            }
        )

        self.assertEqual(round(min(xs), 6), 0.0)
        self.assertEqual(round(max(xs), 6), 3.0)
        self.assertEqual(ys_at_half, [0.0, 1.0])

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

    def test_default_plot_box_size_is_cmame_column_ratio(self):
        plotter = HyperPlot.HyperPlot()

        self.assertEqual(plotter.fig_width_cm, 8.25)
        self.assertEqual(plotter.fig_height_cm, 5.5)

    def test_legend_frame_can_be_disabled(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "data.csv")
            write_csv(csv_path)

            plotter = HyperPlot.HyperPlot(legend_frame=False)
            plotter.catch(csv_path)
            fig = plotter.get_plot([0, 1], "Experiment==-r|Simulation==--b")
            legend = fig.axes[0].get_legend()

            self.assertIsNotNone(legend)
            self.assertFalse(legend.get_frame().get_visible())

    def test_legend_can_be_hidden(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "data.csv")
            write_csv(csv_path)

            plotter = HyperPlot.HyperPlot(show_legend=False)
            plotter.catch(csv_path)
            fig = plotter.get_plot([0, 1], "Experiment==-r|Simulation==--b")

            self.assertIsNone(fig.axes[0].get_legend())

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
            assert_right_axis_ticks_are_aligned_and_nice(self, left_axis, right_axis)

    def test_right_axis_alignment_does_not_depend_on_grid_visibility(self):
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

            plotter = HyperPlot.HyperPlot(
                fig_width_cm=13,
                fig_height_cm=8,
                grid=False,
            )
            plotter.catch(csv_path)
            plotter.toggle_axis([1])
            fig = plotter.get_plot([0, 1], "Left==-b|Right==-r")
            fig.canvas.draw()

            left_axis, right_axis = fig.axes
            assert_right_axis_ticks_are_aligned_and_nice(self, left_axis, right_axis)

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
            self.assertEqual(restored._elements[0].source_path, os.path.abspath(csv_path))

    def test_reload_all_refreshes_csv_data_and_preserves_style(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "data.csv")
            write_csv(csv_path)

            plotter = HyperPlot.HyperPlot()
            plotter.catch(csv_path)
            plotter.toggle_axis([1])
            plotter.set_background([0])
            plotter._apply_styles(plotter._elements, "Envelope==-r|Simulation==--b")

            write_csv(
                csv_path,
                rows=[
                    (0.0, 10.0, 20.0),
                    (1.0, 11.0, 21.0),
                ],
            )

            result = plotter.reload_all()

            self.assertEqual(result["element_count"], 2)
            self.assertEqual(result["paths"], [os.path.abspath(csv_path)])
            self.assertEqual(plotter._elements[0].background_label, "Envelope")
            self.assertEqual(plotter._elements[0].ls, "-r")
            self.assertTrue(plotter._elements[0].is_background)
            self.assertEqual(plotter._elements[1].label, "Simulation")
            self.assertEqual(plotter._elements[1].ls, "--b")
            self.assertEqual(plotter._elements[1].axis, "right")
            self.assertEqual(list(plotter._elements[0].y), [10.0, 11.0])

    def test_legacy_svg_state_resolves_source_path_from_svg_directory(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "data.csv")
            svg_path = os.path.join(tempdir, "legacy.svg")
            write_csv(csv_path)

            plotter = HyperPlot.HyperPlot()
            plotter.catch(csv_path)
            state = plotter.to_state()
            for element_state in state["elements"]:
                element_state.pop("source_path", None)

            with open(svg_path, "w", encoding="utf-8") as file:
                file.write('<svg xmlns="http://www.w3.org/2000/svg"><metadata /></svg>')
            plotter._write_svg_state(svg_path, state)

            restored = HyperPlot.HyperPlot()
            restored.catch_svg(svg_path)

            self.assertEqual(restored._elements[0].source_path, os.path.abspath(csv_path))

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
