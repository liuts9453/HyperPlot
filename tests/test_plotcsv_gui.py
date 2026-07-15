from types import SimpleNamespace
import unittest

from PlotCSV_GUI import PlotApp


class FakeSelectionList:
    def __init__(self, selected=(), nearest_index=0, size=3, row_bounds=None):
        self.selected = tuple(selected)
        self.nearest_index = nearest_index
        self.item_count = size
        self.row_bounds = row_bounds or (0, nearest_index * 10, 100, 10)
        self.selection_was_changed = False

    def size(self):
        return self.item_count

    def nearest(self, _y):
        return self.nearest_index

    def bbox(self, _index):
        return self.row_bounds

    def curselection(self):
        return self.selected

    def selection_clear(self, _first, _last):
        self.selection_was_changed = True
        self.selected = ()

    def selection_set(self, index):
        self.selection_was_changed = True
        self.selected = (index,)


class PlotAppGuiLogicTest(unittest.TestCase):
    def test_workbench_context_menu_remembers_the_clicked_row(self):
        app = PlotApp.__new__(PlotApp)
        app.selection_list = FakeSelectionList(
            selected=(0, 2),
            nearest_index=2,
        )
        app.common_menu = object()
        app.show_menu = lambda menu, event: (menu, event)
        event = SimpleNamespace(y=25)

        PlotApp.show_workbench_menu(app, event)

        self.assertEqual(app._workbench_context_index, 2)
        self.assertFalse(app.selection_list.selection_was_changed)

    def test_workbench_context_menu_ignores_blank_space(self):
        app = PlotApp.__new__(PlotApp)
        app.selection_list = FakeSelectionList(
            selected=(0,),
            nearest_index=2,
            row_bounds=(0, 20, 100, 10),
        )
        app.common_menu = object()
        menu_calls = []
        app.show_menu = lambda menu, event: menu_calls.append((menu, event))

        result = PlotApp.show_workbench_menu(app, SimpleNamespace(y=45))

        self.assertEqual(result, "break")
        self.assertIsNone(app._workbench_context_index)
        self.assertEqual(menu_calls, [])

    def test_set_x_axis_command_uses_the_context_clicked_row(self):
        class FakePlotter:
            def __init__(self):
                self._elements = [object(), object(), object()]
                self.called_with = None

            def set_x_axis(self, index):
                self.called_with = index
                return {
                    "x_label": "temperature",
                    "file_name": "data.csv",
                    "curve_count": 2,
                }

        app = PlotApp.__new__(PlotApp)
        app._workbench_context_index = 2
        app.plotter = FakePlotter()
        app.selection_list = FakeSelectionList(selected=(), size=3)
        updates = []
        messages = []
        app.update_selection_list = lambda: updates.append(True)
        app.log_message = messages.append

        PlotApp.set_context_curve_as_x_axis(app)

        self.assertEqual(app.plotter.called_with, 2)
        self.assertEqual(updates, [True])
        self.assertIn("Set 'temperature' as the X axis", messages[-1])


if __name__ == "__main__":
    unittest.main()
