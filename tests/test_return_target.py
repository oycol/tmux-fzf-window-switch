import unittest
from unittest.mock import Mock
from scripts.switcher.model import Window, SessionGroup, Pane
from scripts.switcher.state import AppState, BROWSE, SEARCH, LOCATE
from scripts.switcher.app import SwitcherApp


def window(session, sid, wid, index, *, source=False, active=False, last=False):
    return Window(session, sid, '1', wid, index, wid, active, last, source,
                  '%1', 'bash', '/tmp', [Pane('%1', 0, '', 'bash', '/tmp', 1, True, 80, 20, 0, 0)])


def groups(source='@A'):
    a = window('s1', '$1', '@A', 1, source=source == '@A', active=True)
    old_a = window('s1', '$1', '@oldA', 2, last=True)
    b = window('s2', '$2', '@B', 2, source=source == '@B', active=True)
    old_b = window('s2', '$2', '@oldB', 3, last=True)
    return [SessionGroup('s1', '$1', '1', [a, old_a]),
            SessionGroup('s2', '$2', '2', [b, old_b])]


class ReturnJourney(unittest.TestCase):
    def test_global_return_target_overrides_each_sessions_last(self):
        state = AppState.create(groups('@B'), '@B', return_window_id='@A')
        self.assertEqual(state.selected_window_id, '@A')
        state = AppState.create(groups('@A'), '@A', return_window_id='@B')
        self.assertEqual(state.selected_window_id, '@B')

    def test_jumps_follow_sessions_active_not_last(self):
        state = AppState.create(groups('@B'), '@B', return_window_id='@A')
        state.handle_key('J')
        self.assertEqual(state.selected_window_id, '@oldB')  # source B excluded
        state.handle_key('K')
        self.assertEqual(state.selected_window_id, '@A')

    def test_tab_is_not_navigation(self):
        state = AppState.create(groups('@B'), '@B', return_window_id='@A')
        state.handle_key('\t')
        self.assertEqual(state.selected_window_id, '@A')

    def test_switch_failure_stays_open_and_does_not_store_history(self):
        adapter = Mock()
        adapter.switch_client.return_value = (False, 'target gone')
        app = SwitcherApp(adapter)
        app.state = AppState.create(groups('@B'), '@B', return_window_id='@A')
        self.assertFalse(app._handle_input(10))
        adapter.set_return_window_id.assert_not_called()
        self.assertIn('target gone', app.state.status_msg)

    def test_first_delete_is_enabled_but_repeat_is_not(self):
        state = AppState.create(groups('@B'), '@B', return_window_id='@A')
        self.assertTrue(state.can_delete_selected())
        state.on_window_deleted('@A')
        self.assertFalse(state.can_delete_selected())
        before = state.selected_window_id
        state.handle_key('j')
        self.assertNotEqual(state.selected_window_id, before)
        self.assertTrue(state.can_delete_selected())

    def test_filter_never_keeps_invisible_selection(self):
        state = AppState.create(groups('@B'), '@B', return_window_id='@A')
        state.handle_key('/')
        state.handle_key('old')
        self.assertIn(state.selected_window_id, {w.window_id for w in state.get_eligible_windows()})
        state.handle_key('Z')
        self.assertIsNone(state.selected_window_id)

    def test_locate_escape_restores_focus(self):
        state = AppState.create(groups('@B'), '@B', return_window_id='@A')
        state.handle_key('1')
        state.handle_key('.')
        state.handle_key('2')
        self.assertEqual(state.selected_window_id, '@oldA')
        state.handle_key('ESC')
        self.assertEqual(state.selected_window_id, '@A')


if __name__ == '__main__':
    unittest.main()
